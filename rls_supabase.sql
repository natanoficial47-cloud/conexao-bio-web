-- Estresse em Foco — liga o RLS em TODAS as tabelas do schema public (idempotente).
-- Rode no Supabase: SQL Editor -> New query -> colar -> Run.
-- Rode DEPOIS da primeira subida da API (é ela quem cria as tabelas) e de novo
-- sempre que uma tabela nova aparecer.
--
-- Por quê: a "anon key" do projeto é pública. Sem RLS, ela consegue ler as tabelas
-- (inclusive os hashes de senha em "users") pela API REST do Supabase.
-- A API da escola entra como "postgres" (BYPASSRLS), então continua funcionando.

do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t.tablename);
    execute format('revoke all on public.%I from anon, authenticated', t.tablename);
  end loop;
end $$;

revoke all on all sequences in schema public from anon, authenticated;

-- Conferir: todas devem mostrar relrowsecurity = true
select relname, relrowsecurity
from pg_class
where relnamespace = 'public'::regnamespace and relkind = 'r'
order by relname;
