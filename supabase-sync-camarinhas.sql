create or replace function public.ler_exercicios_camarinhas(numero integer, versao_esperada timestamptz) returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare v timestamptz; raw bytea;
begin
 if auth.uid() is null then raise insufficient_privilege;end if;
 if numero is null or numero<0 or numero>399 then raise exception 'Parte inválida';end if;
 select atualizado_em,convert_to(jsonb_build_object('📂 Exercícios das camarinhas',coalesce(conteudo->'📂 Exercícios das camarinhas','[]'::jsonb),'_deleted',jsonb_build_object('📂 Exercícios das camarinhas',coalesce(conteudo->'_deleted'->'📂 Exercícios das camarinhas','{}'::jsonb)))::text,'UTF8') into v,raw from public.gestao_dados where id='templo';
 if v is null or v is distinct from versao_esperada then raise exception 'Dados alterados. Tente novamente.' using errcode='40001';end if;
 return jsonb_build_object('versao',v,'bytes',octet_length(raw),'partes',greatest(1,ceil(octet_length(raw)/196608.0)::integer),'numero',numero,'payload',encode(substring(raw from numero*196608+1 for 196608),'base64'));
end $$;
revoke all on function public.ler_exercicios_camarinhas(integer,timestamptz) from public,anon;
grant execute on function public.ler_exercicios_camarinhas(integer,timestamptz) to authenticated;
notify pgrst,'reload schema';