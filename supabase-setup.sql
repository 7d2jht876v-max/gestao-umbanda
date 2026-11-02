-- Executar uma vez no SQL Editor do projeto Gestão Umbanda.
-- Dados compartilhados somente entre usuários autenticados deste projeto.
-- Administradores podem alterar; médiuns podem consultar.
create table if not exists public.gestao_dados (
  id text primary key check (id = 'templo'),
  conteudo jsonb not null default '{}'::jsonb,
  atualizado_em timestamptz not null default now()
);
alter table public.gestao_dados enable row level security;
revoke all on public.gestao_dados from anon;
grant select, insert, update on public.gestao_dados to authenticated;
drop policy if exists "gestao_leitura_autenticados" on public.gestao_dados;
create policy "gestao_leitura_autenticados" on public.gestao_dados
for select to authenticated using (true);
drop policy if exists "gestao_escrita_admin" on public.gestao_dados;
create policy "gestao_escrita_admin" on public.gestao_dados
for insert to authenticated
with check (exists (select 1 from public.perfis p where p.id = (select auth.uid()) and p.perfil = 'admin'));
drop policy if exists "gestao_atualizacao_admin" on public.gestao_dados;
create policy "gestao_atualizacao_admin" on public.gestao_dados
for update to authenticated
using (exists (select 1 from public.perfis p where p.id = (select auth.uid()) and p.perfil = 'admin'))
with check (exists (select 1 from public.perfis p where p.id = (select auth.uid()) and p.perfil = 'admin'));
