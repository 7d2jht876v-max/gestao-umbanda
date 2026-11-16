
create table public.gestao_sync_partes (
 owner uuid not null default auth.uid() references auth.users(id) on delete cascade,
 envio uuid not null,
 parte integer not null check(parte>=0 and parte<256),
 total integer not null check(total>0 and total<=256),
 trecho text not null check(octet_length(trecho)<=2097152),
 criado_em timestamptz not null default now(),
 primary key(owner,envio,parte)
);
alter table public.gestao_sync_partes enable row level security;
revoke all on public.gestao_sync_partes from anon;
grant select,insert,update,delete on public.gestao_sync_partes to authenticated;
create policy sync_partes_admin on public.gestao_sync_partes for all to authenticated
using(owner=(select auth.uid()) and exists(select 1 from public.perfis where id=(select auth.uid()) and perfil='admin'))
with check(owner=(select auth.uid()) and exists(select 1 from public.perfis where id=(select auth.uid()) and perfil='admin'));
create function public.finalizar_sincronizacao_partes(envio_id uuid,versao_esperada timestamptz)
returns timestamptz language plpgsql security invoker set search_path='' as $$
declare
 v timestamptz; n integer; total_min integer; total_max integer; first_part integer; last_part integer; payload jsonb;
begin
 if auth.uid() is null or not exists(select 1 from public.perfis where id=auth.uid() and perfil='admin') then raise insufficient_privilege; end if;
 select atualizado_em into v from public.gestao_dados where id='templo' and conteudo->>'_sync_write_id'=envio_id::text;
 if found then return v; end if;
 select count(*),min(total),max(total),min(parte),max(parte) into n,total_min,total_max,first_part,last_part
 from public.gestao_sync_partes where owner=auth.uid() and envio=envio_id;
 if n=0 or n<>total_min or total_min<>total_max or first_part<>0 or last_part<>n-1 then
 raise exception 'Envio incompleto. Retome a sincronização.' using errcode='22023'; end if;
 select string_agg(trecho,'' order by parte)::jsonb into payload from public.gestao_sync_partes where owner=auth.uid() and envio=envio_id;
 if payload->>'_sync_write_id' is distinct from envio_id::text then raise exception 'Identificação do envio inválida.' using errcode='22023'; end if;
 v:=public.sincronizar_gestao(payload,versao_esperada);
 delete from public.gestao_sync_partes where owner=auth.uid() and (envio=envio_id or criado_em<now()-interval '7 days');
 return v;
end $$;
revoke all on function public.finalizar_sincronizacao_partes(uuid,timestamptz) from public,anon;
grant execute on function public.finalizar_sincronizacao_partes(uuid,timestamptz) to authenticated;
