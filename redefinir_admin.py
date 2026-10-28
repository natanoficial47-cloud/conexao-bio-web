"""Redefine a senha de um administrador (ou cria o primeiro) direto no banco.

Use quando esquecer a senha do admin. A senha é digitada no terminal, não aparece na
tela e não passa por nenhum chat. Roda com o .env da pasta (o mesmo da API).

    python redefinir_admin.py

O que ele faz:
  - lista os administradores existentes (e-mail e nome, nunca senha)
  - troca a senha pela que você digitar (precisa passar na política de senha do sistema)
  - encerra as sessões antigas dessa conta e limpa o bloqueio de tentativas
  - se não existir nenhum administrador, cria um
"""

import getpass
import sys

from main import (  # carrega o .env e conecta no mesmo banco da API
    SessionLocal, User, LoginAttempt, hash_secret, password_problem, norm,
)


def listar_admins(db):
    return db.query(User).filter(User.role == "admin").order_by(User.id).all()


def redefinir(db, email, senha, nome=None):
    """Troca a senha de um admin existente ou cria o admin. Devolve 'trocada' ou 'criado'."""
    email = norm(email)
    user = db.query(User).filter(User.email == email).first()
    if user is not None and user.role != "admin":
        raise ValueError("Esse e-mail pertence a uma conta que não é de administrador.")
    problema = password_problem(senha, user)
    if problema:
        raise ValueError(problema)

    if user is None:
        user = User(name=(nome or "Administrador").strip(), email=email,
                    password_hash=hash_secret(senha), role="admin",
                    must_change_password=0)
        db.add(user)
        resultado = "criado"
    else:
        user.password_hash = hash_secret(senha)
        user.must_change_password = 0
        user.token_version = int(user.token_version or 0) + 1  # derruba sessões antigas
        resultado = "trocada"
    # libera a conta se ela estava bloqueada por tentativas erradas
    db.query(LoginAttempt).filter(LoginAttempt.scope == "email",
                                  LoginAttempt.key == email).delete()
    db.commit()
    return resultado


def main():
    db = SessionLocal()
    try:
        admins = listar_admins(db)
        if admins:
            print("Administradores existentes:")
            for a in admins:
                print(f"  - {a.email}  ({a.name})")
            if len(admins) == 1:
                email = admins[0].email
                print(f"\nVou redefinir a senha de: {email}")
            else:
                email = input("\nDigite o e-mail do admin a redefinir: ").strip()
            nome = None
        else:
            print("Não existe nenhum administrador neste banco. Vou criar um.")
            nome = input("Nome: ").strip() or "Administrador"
            email = input("E-mail: ").strip()

        print("\nA senha precisa ter 10+ caracteres, sem ser comum nem sequência (ex: 123456).")
        print("Ela não aparece na tela enquanto você digita. Ctrl+C cancela.\n")
        try:
            senha = getpass.getpass("Nova senha: ")
            if getpass.getpass("Repita a senha: ") != senha:
                print("\nAs senhas não são iguais. Nada foi alterado.")
                sys.exit(1)
        except KeyboardInterrupt:
            print("\nCancelado. Nada foi alterado.")
            sys.exit(1)

        try:
            resultado = redefinir(db, email, senha, nome)
        except ValueError as exc:
            print(f"\nNão deu certo: {exc}\nNada foi alterado.")
            sys.exit(1)
        print(f"\nPronto: senha {resultado} para {norm(email)}.")
        print("Entre no site com esse e-mail e a nova senha.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
