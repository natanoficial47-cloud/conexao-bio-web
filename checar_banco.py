"""Checagem da conexao com o Supabase — sem expor a senha.

Roda com o .env da pasta do projeto e diz:
  - se a DATABASE_URL conecta
  - se o host e pooler (recomendado) ou conexao direta
  - se o projeto e IPv6-only (a conexao direta nao funciona em rede IPv4)
  - em qual regiao esta o projeto (descobrindo pelo pooler)
  - quais tabelas ja existem e o que falta

Uso:
    .\\venv\\Scripts\\python.exe checar_banco.py
"""

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.getenv("ENV_PATH") or os.path.join(HERE, ".env")


def parse_dsn(url):
    """Separa usuario/senha/host/porta sem depender do urlsplit.

    O urlsplit trata colchetes como marcador de IPv6, o que quebra quando a
    senha tem '[' ou quando ainda e o placeholder [YOUR-PASSWORD].
    """
    m = re.match(
        r"^(?P<scheme>[a-zA-Z0-9+]+)://"
        r"(?P<userinfo>[^@]*)@"
        r"(?P<host>[^:/?#]+)"
        r"(?::(?P<port>\d+))?"
        r"(?:/(?P<db>[^?#]*))?",
        url.strip(),
    )
    if not m:
        return {"scheme": "", "user": "", "password": "", "host": "", "port": 5432, "db": ""}
    d = m.groupdict()
    userinfo = d.get("userinfo") or ""
    user, _, senha = userinfo.partition(":")
    return {
        "scheme": d.get("scheme") or "",
        "user": user,
        "password": senha,
        "host": d.get("host") or "",
        "port": int(d.get("port") or 5432),
        "db": d.get("db") or "",
    }

# Regioes em que o Supabase costuma hospedar projetos.
REGIOES = [
    "sa-east-1",   # Sao Paulo
    "us-east-1",   # Virginia
    "us-west-1",   # Oregon
    "eu-west-1",   # Ireland
    "eu-west-2",   # London
    "eu-central-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "ca-central-1",
]


def read_env(path=ENV_PATH):
    data = {}
    if not os.path.exists(path):
        print(f"ERRO: .env nao encontrado em {path}")
        sys.exit(1)
    with io.open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def montar(host, user, senha, porta=5432):
    return f"postgresql://{user}:{senha}@{host}:{porta}/postgres"


def testar(dsn):
    """Devolve (ok, mensagem)."""
    try:
        import psycopg2
    except ImportError:
        return False, "psycopg2 nao instalado no venv"
    try:
        pg = psycopg2.connect(dsn, connect_timeout=12)
    except Exception as exc:
        return False, " ".join(str(exc).strip().splitlines()[:2])
    pg.close()
    return True, "conectou"


def main():
    env = read_env()
    url = env.get("DATABASE_URL", "")
    if not url:
        print("ERRO: DATABASE_URL ausente no .env")
        sys.exit(1)

    parsed = parse_dsn(url)
    host = parsed["host"] or "?"
    user = parsed["user"] or "postgres"
    senha = parsed["password"] or ""
    print("=== Configuracao ===")
    print(f"  host    : {host}")
    print(f"  usuario : {user}")
    print(f"  senha   : {'preenchida' if senha and senha != '[YOUR-PASSWORD]' else 'VAZIA ou PLACEHOLDER'}")
    print(f"  modo    : {'pooler' if 'pooler.supabase.com' in host else 'conexao direta'}")

    if not senha or senha == "[YOUR-PASSWORD]":
        print("\nERRO: a senha do banco ainda esta como placeholder.")
        print("No painel do Supabase: Database -> Reset database password (ou 'Connect' -> Connection string).")
        print("Depois cole a senha aqui no .env, na linha DATABASE_URL, e rode de novo.")
        sys.exit(1)

    print("\n=== Testando a conexao ===")
    ok, msg = testar(url)
    print(f"  {'CONECTOU' if ok else 'FALHOU'}: {msg}")

    # Se falhou, procura a regiao certa pelo pooler.
    ref = ""
    if "." in user:
        ref = user.split(".")[-1]
    if not ok and ref:
        print("\n=== Procurando a regiao do projeto pelo pooler ===")
        achou = None
        for regiao in REGIOES:
            for prefixo in ("aws-0", "aws-1"):
                for porta in (5432, 6543):
                    dsn = montar(f"{prefixo}-{regiao}.pooler.supabase.com",
                                 f"postgres.{ref}", senha, porta)
                    ok_r, msg_r = testar(dsn)
                    if ok_r:
                        achou = (regiao, dsn)
                        print(f"  {prefixo}-{regiao}:{porta}: CONECTOU")
                        break
                    if "tenant" in msg_r.lower() or "not found" in msg_r.lower():
                        # o prefixo/regiao nao serve para este projeto
                        break
                if achou:
                    break
            if achou:
                break
        if achou:
            regiao, dsn = achou
            print(f"\n  O projeto esta em: {regiao}")
            print(f"  Use esta DATABASE_URL no .env e na VM:")
            print(f"    DATABASE_URL={dsn}")
            url = dsn
        else:
            print("\n  Nenhuma regiao respondeu. Confirme a senha e a regiao no painel.")

    if not ok:
        print("\nDicas:")
        print("  - senha errada? use 'Reset database password' no painel do Supabase")
        print("  - use o POOLER (aws-0-<regiao>.pooler.supabase.com), nao o host direto:")
        print("    projetos novos sao IPv6-only e nao funcionam em rede IPv4 (a VM da Oracle)")
        sys.exit(1)

    print("\n=== Schema ===")
    import psycopg2
    dsn = url.replace("postgres://", "postgresql://", 1)
    pg = psycopg2.connect(dsn, connect_timeout=15)
    cur = pg.cursor()
    cur.execute("select version()")
    print("  " + cur.fetchone()[0].split(",")[0])

    cur.execute(
        "select table_name from information_schema.tables "
        "where table_schema='public' order by table_name"
    )
    tables = {r[0] for r in cur.fetchall()}
    print("  tabelas: " + (", ".join(sorted(tables)) if tables else "(nenhuma)"))

    esperadas = {"users", "diary_entries", "login_attempts", "revoked_tokens", "login_logs",
                "missions", "mission_options", "mission_progress", "dna_results"}
    faltando = esperadas - tables
    if faltando:
        print(f"  faltam (a API cria no boot): {', '.join(sorted(faltando))}")
    else:
        print("  schema completo.")

    if "users" in tables:
        cur.execute(
            "select column_name from information_schema.columns "
            "where table_schema='public' and table_name='users'"
        )
        existentes = {r[0] for r in cur.fetchall()}
        for c in ("token_version", "must_change_password"):
            print(f"  users.{c}: {'ok' if c in existentes else 'FALTA (criado no boot)'}")

    # ------------------------------------------------------- seguranca (RLS)
    # Sem RLS a anon key do projeto (publica) leria users via PostgREST,
    # inclusive os hashes de senha. A API entra como postgres (BYPASSRLS),
    # entao ligar o RLS nao quebra nada.
    print("\n=== Seguranca (RLS) ===")
    try:
        cur.execute(
            "select c.relname, c.relrowsecurity from pg_class c "
            "join pg_namespace n on n.oid = c.relnamespace "
            "where n.nspname='public' and c.relkind='r' order by c.relname"
        )
        sem_rls = [r[0] for r in cur.fetchall() if not r[1]]
        if sem_rls:
            print(f"  RLS DESLIGADO em: {', '.join(sem_rls)}")
            print("  >>> a anon key do projeto consegue ler essas tabelas.")
            print("  >>> Corrija com:")
            print("      rode o arquivo rls_supabase.sql no SQL Editor do Supabase")
            print("      (ou: alter table public.<tabela> enable row level security;)")
        else:
            print("  RLS ligado em todas as tabelas publicas. ok")
    except Exception as exc:
        print(f"  (nao consegui verificar o RLS: {exc})")

    cur.close()
    pg.close()
    print("\nTudo certo. Agora rode os validadores contra o banco real:")
    print("  .\\venv\\Scripts\\python.exe validar_fase1.py")
    print("  .\\venv\\Scripts\\python.exe validar_fase2.py")


if __name__ == "__main__":
    main()
