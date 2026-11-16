-- Chunked transfer, with existing admin authorization and atomic version check.
alter table public.gestao_dados add column if not exists sync_bytes bytea;
alter table public.gestao_dados alter column sync_bytes set storage external;
create or replace function public.gestao_cache_bytes() returns trigger language plpgsql security invoker set search_path='' as $$
begin new.sync_bytes=convert_to(new.conteudo::text,'UTF8');return new;end $$;
revoke all on function public.gestao_cache_bytes() from public,anon,authenticated;
create trigger gestao_cache_bytes before insert or update of conteudo on public.gestao_dados for each row execute function public.gestao_cache_bytes();
update public.gestao_dados set sync_bytes=convert_to(conteudo::text,'UTF8') where sync_bytes is null;
create or replace function public.ler_gestao_parte(numero integer, versao_esperada timestamptz) returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare result jsonb;
begin
 if auth.uid() is null then raise insufficient_privilege;end if;
 if numero is null or numero<0 or numero>199 then raise exception 'Parte inválida';end if;
 select jsonb_build_object('versao',atualizado_em,'bytes',octet_length(sync_bytes),'partes',greatest(1,ceil(octet_length(sync_bytes)/393216.0)::integer),'numero',numero,'payload',encode(substring(sync_bytes from numero*393216+1 for 393216),'base64')) into result from public.gestao_dados where id='templo' and (versao_esperada is null or atualizado_em=versao_esperada);
 if result is null then raise exception 'A versão da nuvem mudou. Tente novamente.' using errcode='40001';end if;
 return result;
end $$;
create table public.gestao_sync_envios (
 id uuid primary key, owner uuid not null default auth.uid(), esperado timestamptz,
 total integer not null check(total between 1 and 267), bytes integer not null check(bytes between 1 and 52428800),
 concluido timestamptz, criado timestamptz not null default now()
);
create table public.gestao_sync_blocos (
 envio uuid not null references public.gestao_sync_envios(id) on delete cascade,
 numero integer not null check(numero between 0 and 266), payload bytea not null check(octet_length(payload)<=196608), primary key(envio,numero)
);
alter table public.gestao_sync_envios enable row level security;
alter table public.gestao_sync_blocos enable row level security;
create policy admin_envios on public.gestao_sync_envios for all to authenticated using(owner=(select auth.uid()) and exists(select 1 from public.perfis where id=(select auth.uid()) and perfil='admin')) with check(owner=(select auth.uid()) and exists(select 1 from public.perfis where id=(select auth.uid()) and perfil='admin'));
create policy admin_blocos on public.gestao_sync_blocos for all to authenticated using(exists(select 1 from public.gestao_sync_envios where id=envio)) with check(exists(select 1 from public.gestao_sync_envios where id=envio));
revoke all on public.gestao_sync_envios,public.gestao_sync_blocos from anon;
grant select,insert,update,delete on public.gestao_sync_envios,public.gestao_sync_blocos to authenticated;
create or replace function public.enviar_gestao_bloco(upload_id uuid, numero integer, total integer, bytes integer, payload text, versao_esperada timestamptz) returns boolean language plpgsql security invoker set search_path='' as $$
declare session public.gestao_sync_envios; raw bytea;
begin
 if auth.uid() is null then raise insufficient_privilege;end if;
 if numero is null or total is null or bytes is null or payload is null or numero<0 or numero>=total or length(payload)>262144 or total<>ceil(bytes/196608.0)::integer then raise exception 'Bloco inválido';end if;
 raw=decode(payload,'base64');
 if octet_length(raw)<>least(196608,bytes-numero*196608) then raise exception 'Tamanho inválido';end if;
 delete from public.gestao_sync_envios where criado<now()-interval '2 days';
 insert into public.gestao_sync_envios(id,total,bytes,esperado) values(upload_id,total,bytes,versao_esperada) on conflict(id) do nothing;
 select * into strict session from public.gestao_sync_envios where id=upload_id for update;
 if session.total<>total or session.bytes<>bytes or session.esperado is distinct from versao_esperada then raise exception 'Envio diferente';end if;
 if session.concluido is not null then return true;end if;
 insert into public.gestao_sync_blocos(envio,numero,payload) values(upload_id,numero,raw) on conflict on constraint gestao_sync_blocos_pkey do update set payload=excluded.payload;
 return true;
end $$;
create or replace function public.concluir_gestao_envio(upload_id uuid) returns timestamptz language plpgsql security invoker set search_path='' set statement_timeout='55s' as $$
declare session public.gestao_sync_envios; raw bytea; n integer; version timestamptz;
begin
 if auth.uid() is null then raise insufficient_privilege;end if;
 select * into strict session from public.gestao_sync_envios where id=upload_id for update;
 if session.concluido is not null then return session.concluido;end if;
 select count(*),string_agg(payload,''::bytea order by numero) into n,raw from public.gestao_sync_blocos where envio=upload_id;
 if n<>session.total or octet_length(raw)<>session.bytes then raise exception 'Envio incompleto';end if;
 version=public.sincronizar_gestao(convert_from(raw,'UTF8')::jsonb,session.esperado);
 update public.gestao_sync_envios set concluido=version where id=upload_id;
 delete from public.gestao_sync_blocos where envio=upload_id;
 return version;
end $$;
revoke all on function public.enviar_gestao_bloco(uuid,integer,integer,integer,text,timestamptz),public.concluir_gestao_envio(uuid),public.ler_gestao_parte(integer,timestamptz) from public,anon;
grant execute on function public.enviar_gestao_bloco(uuid,integer,integer,integer,text,timestamptz),public.concluir_gestao_envio(uuid),public.ler_gestao_parte(integer,timestamptz) to authenticated;
notify pgrst,'reload schema';
