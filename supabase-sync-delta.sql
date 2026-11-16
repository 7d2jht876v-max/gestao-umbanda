-- Transfer only new or changed records. Existing clients remain compatible.
create or replace function public.gestao_delta_indice(doc jsonb) returns jsonb
language plpgsql immutable security invoker set search_path='' as $$
declare k text; v jsonb; result jsonb='{}'; hashes jsonb;
begin
 for k,v in select * from jsonb_each(doc) loop
  if jsonb_typeof(v)='array' and not exists(select 1 from jsonb_array_elements(v) r where jsonb_typeof(r)<>'object' or coalesce(r->>'id','')='')
   and (select count(*)=count(distinct r->>'id') from jsonb_array_elements(v) r) then
   select coalesce(jsonb_object_agg(r->>'id',encode(sha256(convert_to(r::text,'UTF8')),'hex')),'{}') into hashes from jsonb_array_elements(v) r;
   result=result||jsonb_build_object(k,jsonb_build_object('rows',hashes));
  else result=result||jsonb_build_object(k,jsonb_build_object('hash',encode(sha256(convert_to(v::text,'UTF8')),'hex'))); end if;
 end loop;
 return result;
end $$;
create or replace function public.ler_gestao_delta(conhecido jsonb,numero integer,versao_esperada timestamptz) returns jsonb
language plpgsql stable security invoker set search_path='' as $$
declare doc jsonb; idx jsonb; v timestamptz; k text; val jsonb; sets jsonb='{}'; rows jsonb='{}'; selected jsonb; raw bytea;
begin
 if auth.uid() is null or not exists(select 1 from public.perfis where id=auth.uid() and perfil='admin') then raise insufficient_privilege;end if;
 if numero is null or numero<0 or numero>399 or jsonb_typeof(conhecido)<>'object' then raise exception 'Parte inválida';end if;
 select conteudo,atualizado_em into doc,v from public.gestao_dados where id='templo';
 if not found or v is distinct from versao_esperada then raise exception 'A versão mudou' using errcode='40001';end if;
 idx=public.gestao_delta_indice(doc);
 for k,val in select * from jsonb_each(doc) loop
  if idx->k is not distinct from conhecido->k then continue;end if;
  if (idx->k)?'rows' and (conhecido->k)?'rows' then
   select coalesce(jsonb_agg(r),'[]') into selected from jsonb_array_elements(val) r where (idx->k->'rows'->(r->>'id')) is distinct from (conhecido->k->'rows'->(r->>'id'));
   rows=rows||jsonb_build_object(k,selected);
  else sets=sets||jsonb_build_object(k,val);end if;
 end loop;
 raw=convert_to(jsonb_build_object('sets',sets,'rows',rows)::text,'UTF8');
 return jsonb_build_object('versao',v,'numero',numero,'partes',greatest(1,ceil(octet_length(raw)/196608.0)::integer),'bytes',octet_length(raw),'payload',encode(substring(raw from numero*196608+1 for 196608),'base64'),'indice',case when numero=0 then idx else null end);
end $$;

create or replace function public.gestao_aplicar_delta(doc jsonb,patch jsonb) returns jsonb
language plpgsql immutable security invoker set search_path='' as $$
declare result jsonb; k text; items jsonb; existing jsonb; combined jsonb; dead jsonb; item jsonb; pos integer;
begin
 if jsonb_typeof(patch->'sets') is distinct from 'object' or jsonb_typeof(patch->'rows') is distinct from 'object' then raise exception 'Alterações inválidas';end if;
 result=doc||(patch->'sets');
 for k,items in select * from jsonb_each(patch->'rows') loop
  if jsonb_typeof(items)<>'array' or exists(select 1 from jsonb_array_elements(items) r where coalesce(r->>'id','')='') then raise exception 'Registros inválidos';end if;
  existing=case when jsonb_typeof(result->k)='array' then result->k else '[]'::jsonb end;
  for item in select * from jsonb_array_elements(items) loop
   select ord::integer-1 into pos from jsonb_array_elements(existing) with ordinality e(r,ord) where r->>'id'=item->>'id' limit 1;
   if pos is null then existing=existing||jsonb_build_array(item);
   else existing=jsonb_set(existing,array[pos::text],item);end if;
  end loop;
  result=result||jsonb_build_object(k,existing);
 end loop;
 for k,dead in select * from jsonb_each(coalesce(result->'_deleted','{}')) loop
  if jsonb_typeof(result->k)='array' and jsonb_typeof(dead)='object' and exists(select 1 from jsonb_array_elements(result->k) r where dead ? (r->>'id')) then
   select coalesce(jsonb_agg(r),'[]') into combined from jsonb_array_elements(result->k) r where not dead ? (r->>'id');
   result=result||jsonb_build_object(k,combined);
  end if;
 end loop;
 return result;
end $$;
create or replace function public.concluir_gestao_delta(upload_id uuid) returns timestamptz
language plpgsql security invoker set search_path='' set statement_timeout='55s' as $$
declare session public.gestao_sync_envios; raw bytea; n integer; version timestamptz; doc jsonb; current_version timestamptz;
begin
 if auth.uid() is null or not exists(select 1 from public.perfis where id=auth.uid() and perfil='admin') then raise insufficient_privilege;end if;
 select * into strict session from public.gestao_sync_envios where id=upload_id for update;
 if session.concluido is not null then return session.concluido;end if;
 select count(*),string_agg(payload,''::bytea order by numero) into n,raw from public.gestao_sync_blocos where envio=upload_id;
 if n<>session.total or octet_length(raw)<>session.bytes then raise exception 'Envio incompleto';end if;
 select conteudo,atualizado_em into doc,current_version from public.gestao_dados where id='templo' for update;
 if current_version is distinct from session.esperado then raise exception 'Dados alterados em outro aparelho' using errcode='40001';end if;
 doc=public.gestao_aplicar_delta(coalesce(doc,'{}'),convert_from(raw,'UTF8')::jsonb);
 version=public.sincronizar_gestao(doc,session.esperado);
 update public.gestao_sync_envios set concluido=version where id=upload_id;
 delete from public.gestao_sync_blocos where envio=upload_id;
 return version;
end $$;
revoke all on function public.gestao_delta_indice(jsonb),public.gestao_aplicar_delta(jsonb,jsonb),public.ler_gestao_delta(jsonb,integer,timestamptz),public.concluir_gestao_delta(uuid) from public,anon;
grant execute on function public.gestao_delta_indice(jsonb),public.gestao_aplicar_delta(jsonb,jsonb),public.ler_gestao_delta(jsonb,integer,timestamptz),public.concluir_gestao_delta(uuid) to authenticated;
notify pgrst,'reload schema';


alter table public.gestao_dados add column if not exists sync_indice jsonb;

create or replace function public.gestao_cache_indice() returns trigger language plpgsql security invoker set search_path='' as $$
declare k text; val jsonb; idx jsonb='{}'; part jsonb; old_doc jsonb='{}';
begin
 -- Materialize once: repeated extraction from a toasted 39 MB value is costly.
 if tg_op='UPDATE' then old_doc=old.conteudo||'{}'::jsonb;end if;
 for k,val in select * from jsonb_each(new.conteudo) loop
  if tg_op='UPDATE' and old.sync_indice is not null and val is not distinct from old_doc->k then
   part=old.sync_indice->k;
  else part=public.gestao_delta_indice(jsonb_build_object(k,val))->k;end if;
  idx=idx||jsonb_build_object(k,part);
 end loop;
 new.sync_indice=idx;return new;
end $$;
revoke all on function public.gestao_cache_indice() from public,anon,authenticated;
create trigger gestao_cache_indice before insert or update of conteudo on public.gestao_dados for each row execute function public.gestao_cache_indice();
update public.gestao_dados set sync_indice=public.gestao_delta_indice(conteudo) where sync_indice is null;
create or replace function public.ler_gestao_delta(conhecido jsonb,numero integer,versao_esperada timestamptz) returns jsonb
language plpgsql stable security invoker set search_path='' as $$
declare doc jsonb; idx jsonb; v timestamptz; k text; val jsonb; sets jsonb='{}'; rows jsonb='{}'; selected jsonb; raw bytea;
begin
 if auth.uid() is null or not exists(select 1 from public.perfis where id=auth.uid() and perfil='admin') then raise insufficient_privilege;end if;
 if numero is null or numero<0 or numero>399 or jsonb_typeof(conhecido)<>'object' then raise exception 'Parte inválida';end if;
 select sync_indice,atualizado_em into idx,v from public.gestao_dados where id='templo';
 if not found or v is distinct from versao_esperada then raise exception 'A versão mudou' using errcode='40001';end if;
 if idx is null then raise exception 'Índice indisponível';end if;
 if idx is distinct from conhecido then
  select conteudo into doc from public.gestao_dados where id='templo' and atualizado_em=v;
  if not found then raise exception 'A versão mudou' using errcode='40001';end if;
  for k in select jsonb_object_keys(idx) loop
   if idx->k is not distinct from conhecido->k then continue;end if;
   val=doc->k;
   if (idx->k)?'rows' and (conhecido->k)?'rows' then
    select coalesce(jsonb_agg(r),'[]') into selected from jsonb_array_elements(val) r where (idx->k->'rows'->(r->>'id')) is distinct from (conhecido->k->'rows'->(r->>'id'));
    rows=rows||jsonb_build_object(k,selected);
   else sets=sets||jsonb_build_object(k,val);end if;
  end loop;
 end if;
 raw=convert_to(jsonb_build_object('sets',sets,'rows',rows)::text,'UTF8');
 return jsonb_build_object('versao',v,'numero',numero,'partes',greatest(1,ceil(octet_length(raw)/196608.0)::integer),'bytes',octet_length(raw),'payload',encode(substring(raw from numero*196608+1 for 196608),'base64'),'indice',case when numero=0 then idx else null end);
end $$;
notify pgrst,'reload schema';
