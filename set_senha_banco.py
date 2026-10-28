"""Grava a senha do banco no .env sem deixar rastro no terminal.

A senha e digitada no prompt (nao aparece na tela, nao fica no historico do
PowerShell e nao passa por nenhum chat). Ela e gravada com URL-encoding, que e
o que o Postgres espera quando a senha tem caractere especial.

Uso:
    .\\venv\\Scripts\\python.exe set_senha_banco.py
"""

import io
import os
import sys
import urllib.parse as up

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.getenv("ENV_PATH") or os.path.join(HERE, ".env")


def main():
    if not os.path.exists(ENV_PATH):
        print(f"ERRO: .env nao encontrado em {ENV_PATH}")
        sys.exit(1)

    with io.open(ENV_PATH, "r", encoding="utf-8") as f:
        linhas = f.read().splitlines()

    alvo = None
    for i, linha in enumerate(linhas):
        if linha.strip().startswith("DATABASE_URL="):
            alvo = i
            break
    if alvo is None:
        print("ERRO: DATABASE_URL nao encontrada no .env")
        sys.exit(1)

    atual = linhas[alvo].split("=", 1)[1].strip()
    pre, _, resto = atual.partition("@")
    # pre = "postgresql://usuario" ou "postgresql://usuario:senha"
    if ":" in pre.split("://", 1)[-1]:
        usuario = pre.split("://", 1)[1].split(":", 1)[0]
    else:
        usuario = pre.split("://", 1)[1]
    host = resto

    print(f"\nBanco : {host}")
    print(f"Usuario: {usuario}")
    print("\nCole a SENHA DO BANCO do Supabase (Database -> Reset database password).")
    print("Nao aparece na tela. Ctrl+C para cancelar.\n")

    try:
        import getpass
        senha = getpass.getpass("Senha do banco: ")
    except KeyboardInterrupt:
        print("\nCancelado. Nada foi alterado.")
        sys.exit(1)

    if not senha:
        print("\nSenha vazia. Nada foi alterado.")
        sys.exit(1)

    senha_url = up.quote(senha, safe="")
    novo = f"DATABASE_URL=postgresql://{usuario}:{senha_url}@{host}"
    linhas[alvo] = novo

    with io.open(ENV_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(linhas) + "\n")

    print("\nSenha gravada no .env (a senha em si nao e mostrada).")
    print("Agora rode:")
    print("  .\\venv\\Scripts\\python.exe checar_banco.py")


if __name__ == "__main__":
    main()
