import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlsplit

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, ForeignKey,
    UniqueConstraint, inspect, text, Boolean, func,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

import secrets

import dna_data
from missions_data import MISSIONS, POINTS  # missões iniciais (semente)

load_dotenv()

# ---------------------------------------------------------------------------
# Configuração (o servidor se recusa a subir sem os segredos)
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError("Defina SECRET_KEY no .env com 32+ caracteres.")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Defina DATABASE_URL no .env.")

# SQLAlchemy 2.1+ usa o driver "psycopg" (v3) por padrão em "postgresql://".
# Fixamos o psycopg2 (o que está no requirements.txt) para funcionar em qualquer versão.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgresql://"):]

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500"
    ).split(",")
    if o.strip()
]

# --- Sessão em cookie (HttpOnly) -------------------------------------------
# O token NÃO vai mais para o navegador: ele fica num cookie HttpOnly,
# que JavaScript não consegue ler (protege contra XSS).
SESSION_COOKIE = os.getenv("SESSION_COOKIE", "estresse_em_foco_session")
# "lax" funciona com front e API no mesmo site (inclusive portas diferentes).
# Use "none" + HTTPS se o front e a API ficarem em domínios diferentes.
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()
# "auto" = segue o esquema da requisição (https vira Secure).
# "true"/"false" = força o comportamento (útil atrás de proxy).
COOKIE_SECURE_MODE = os.getenv("COOKIE_SECURE", "auto").lower()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

try:
    make_url(DATABASE_URL)
except Exception:
    # "from None" evita que o erro original (que mostra pedaços da senha) apareça no terminal
    raise RuntimeError(
        "DATABASE_URL inválida. O formato é: "
        "postgresql://postgres.REF:SENHA@aws-1-sa-east-1.pooler.supabase.com:5432/postgres "
        "(confira se há um '@' entre a senha e o host, e se a senha não tem símbolos)."
    ) from None

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # reconecta se o pooler derrubou a sessão
    pool_size=5,              # conexões por worker
    max_overflow=5,           # fila curta para picos
    pool_timeout=30,          # não trava mais que 30s esperando conexão
    pool_recycle=1800,        # recicla antes do limite do pooler (30 min)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Código de acesso: quem não o conhece não consegue criar conta de aluno.
# É UM código único da escola (vale para todas as turmas e cursos).
# Se estiver vazio, o cadastro por conta própria fica desativado.
CLASS_CODE = os.getenv("CLASS_CODE", "").strip()

ROLES_STAFF = ("teacher", "admin")


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    # e-mail (equipe) ou e-mail/matrícula (aluno), sempre em minúsculas
    email = Column(String(160), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="student")

    # rubricas de observação (0 a 4), usadas só para alunos
    comm = Column(Integer, default=0, nullable=False)
    conflict = Column(Integer, default=0, nullable=False)
    coop = Column(Integer, default=0, nullable=False)

    # Versão do token: subir o número invalida todas as sessões antigas.
    token_version = Column(Integer, default=0, nullable=False)
    # Marca conta que ainda precisa trocar a senha (primeiro acesso com PIN).
    must_change_password = Column(Integer, default=0, nullable=False)

    diaries = relationship(
        "Diary", back_populates="user", cascade="all, delete-orphan"
    )
    mission_progress = relationship("MissionProgress", cascade="all, delete-orphan")
    dna_results = relationship("DnaResult", cascade="all, delete-orphan")


class LoginAttempt(Base):
    """Tentativas de login guardadas no banco (sobrevivem a reinício do servidor)."""

    __tablename__ = "login_attempts"
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_login_attempts_scope_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String(10), nullable=False)  # "email" | "ip" | "signup"
    key = Column(String(160), nullable=False, index=True)
    failures = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RevokedToken(Base):
    """Tokens encerrados no logout: o logout acontece no servidor, não só no navegador."""

    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class LoginLog(Base):
    """Auditoria de acessos: quem tentou entrar, de onde e com que resultado.

    Guardada no banco para a equipe conseguir investigating ataques e saber
    quem ainda nao trocou a senha provisoria.
    """

    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    email = Column(String(160), nullable=False, default="", index=True)
    ip = Column(String(64), nullable=False, default="")
    success = Column(Integer, default=1, nullable=False)
    reason = Column(String(120), nullable=False, default="")
    user_agent = Column(String(200), nullable=False, default="")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )


class Diary(Base):
    __tablename__ = "diary_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mood = Column(String(40), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", back_populates="diaries")


class Mission(Base):
    """Missão criada pela psicologia/coordenação e vista pelos alunos."""
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(120), nullable=False)
    dimension = Column(String(20), nullable=False)  # comunicacao | conflitos | cooperacao
    scenario = Column(Text, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    options = relationship(
        "MissionOption", cascade="all, delete-orphan",
        order_by="MissionOption.key", back_populates="mission",
    )
    progress = relationship("MissionProgress", cascade="all, delete-orphan")


class MissionOption(Base):
    __tablename__ = "mission_options"

    id = Column(Integer, primary_key=True)
    mission_id = Column(Integer, ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(1), nullable=False)        # A, B, C, D
    text = Column(Text, nullable=False)
    level = Column(String(8), nullable=False)      # good | ok | poor
    fb_title = Column(String(160), nullable=False)
    feedback = Column(Text, nullable=False)

    mission = relationship("Mission", back_populates="options")


class MissionProgress(Base):
    """Uma linha por aluno e missão: melhor pontuação e número de tentativas."""
    __tablename__ = "mission_progress"
    __table_args__ = (UniqueConstraint("user_id", "mission_id", name="uq_progress_user_mission"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mission_id = Column(Integer, ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True)
    last_option = Column(String(1), nullable=False)
    best_points = Column(Integer, nullable=False, default=0)
    attempts = Column(Integer, nullable=False, default=1)
    answered_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class DnaResult(Base):
    """Respostas do teste "Meu DNA da Personalidade". As pontuações são calculadas ao ler."""
    __tablename__ = "dna_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    answers = Column(String(120), nullable=False)  # "3,4,5,..." (30 números de 1 a 5)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


Base.metadata.create_all(bind=engine)


def ensure_schema():
    """create_all cria tabelas novas, mas NÃO adiciona colunas em tabelas que já
    existem. Aqui acrescentamos as colunas que faltarem, sem tocar nos dados."""
    wanted = {
        "users": [
            ("token_version", "INTEGER NOT NULL DEFAULT 0"),
            ("must_change_password", "INTEGER NOT NULL DEFAULT 0"),
        ],
    }
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table, columns in wanted.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns:
            if name in existing:
                continue
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


ensure_schema()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class StudentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=160)  # e-mail ou matrícula


class StudentRegister(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=160)  # e-mail ou matrícula
    password: str = Field(min_length=10, max_length=72)
    class_code: str = Field(min_length=1, max_length=64)


class StaffCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=10, max_length=72)
    role: str = Field(pattern="^(teacher|psychologist|admin)$")


class RubricUpdate(BaseModel):
    comm: int = Field(ge=0, le=4)
    conflict: int = Field(ge=0, le=4)
    coop: int = Field(ge=0, le=4)


class MissionAnswerIn(BaseModel):
    option: str = Field(pattern="^[A-D]$")


class MissionOptionIn(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    level: str = Field(pattern="^(good|ok|poor)$")
    title: str = Field(min_length=1, max_length=160)
    feedback: str = Field(min_length=1, max_length=1200)


class MissionIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    dimension: str = Field(pattern="^(comunicacao|conflitos|cooperacao)$")
    scenario: str = Field(min_length=10, max_length=1500)
    active: bool = True
    options: list[MissionOptionIn] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def tem_opcao_melhor(self):
        if not any(o.level == "good" for o in self.options):
            raise ValueError("Marque pelo menos uma opção como a melhor escolha.")
        return self


class DnaSubmit(BaseModel):
    answers: list[int] = Field(min_length=dna_data.N_QUESTIONS, max_length=dna_data.N_QUESTIONS)

    @field_validator("answers")
    @classmethod
    def valores_de_1_a_5(cls, v):
        if any(x < 1 or x > 5 for x in v):
            raise ValueError("Cada resposta deve ser de 1 a 5.")
        return v


class DiaryCreate(BaseModel):
    mood: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=5000)


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def norm(identifier: str) -> str:
    return identifier.strip().lower()


def hash_secret(value: str) -> str:
    # bcrypt só aceita até 72 BYTES (acentos contam mais de 1)
    if len(value.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Senha muito longa (máximo 72 bytes).")
    return pwd_context.hash(value)


def check_secret(plain: str, hashed: str) -> bool:
    if len(plain.encode("utf-8")) > 72:
        return False
    try:
        return pwd_context.verify(plain, hashed)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Política de senha (Fase 2)
# A regra e curta de propósito: 10+ caracteres e nada de senha "de dicionário".
# Senha de aluno precisa ser fácil de lembrar, mas difícil de adivinhar.
# ---------------------------------------------------------------------------
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 72

# Senhas comuns ja normalizadas (sem acentos, só letras e números).
COMMON_PASSWORDS = {
    "123456", "1234567", "12345678", "123456789", "1234567890",
    "password", "password1", "senha", "senha1", "senha123", "senha1234",
    "qwerty", "qwerty123", "qwertyuiop", "abc123", "abc12345",
    "111111", "000000", "11111111", "00000000", "654321", "987654321",
    "maria123", "joao123", "aluno123", "aluno1234", "escola123",
    "admin", "admin123", "admin1234", "root", "root123", "default",
    "teste123", "teste1234", "test1234", "estresse", "estressemfoco",
    "foco12345", "foco2024", "foco2025", "foco2026", "projeto123",
    "estresse123", "estresse1234", "emfoco1234", "bemestar123",
    "senha12345", "senha123456", "aluno123456", "escola1234",
    "iloveyou", "letmein", "welcome", "welcome1", "mudar123",
}


def normalize_password(value: str) -> str:
    """Reduz a senha a letras e números minúsculos, para comparar com segurança."""
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _is_sequential(text: str) -> bool:
    """True para 123456789, abcdefghij, 987654321 e afins."""
    if len(text) < 3:
        return False
    diffs = {ord(text[i + 1]) - ord(text[i]) for i in range(len(text) - 1)}
    return diffs in ({1}, {-1})


def _has_sequential_run(text: str, run: int = 6) -> bool:
    """True se qualquer pedaço da senha é uma sequência ("...123456...").

    Sem isso, "1234567890a" passaria como senha boa só porque tem uma letra no fim.
    """
    if len(text) < run:
        return False
    for i in range(len(text) - run + 1):
        window = text[i:i + run]
        diffs = {ord(window[k + 1]) - ord(window[k]) for k in range(run - 1)}
        if diffs in ({1}, {-1}):
            return True
    return False


def password_problem(password: str, user: Optional["User"] = None) -> Optional[str]:
    """Devolve o que está errado na senha (ou None se ela estiver aceitável)."""
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
    if len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        return "A senha é longa demais (máximo 72 bytes)."
    if not password.strip():
        return "A senha não pode ser só espaços."

    flat = normalize_password(password)
    if flat in COMMON_PASSWORDS:
        return "Essa senha é muito comum. Escolha uma outra."
    if len(set(flat)) == 1:
        return "A senha não pode repetir o mesmo caractere."
    if flat.isdigit():
        return "A senha precisa combinar letras e números."
    if len(flat) >= 6 and _has_sequential_run(flat):
        return "A senha não pode ter uma sequência (ex: 123456)."

    if user is not None:
        own = {
            normalize_password(user.name or ""),
            normalize_password(user.email or ""),
        }
        own = {p for p in own if len(p) >= 4}
        if flat in own:
            return "A senha não pode ser igual ao seu nome ou e-mail."
    return None


def new_pin() -> str:
    # PIN de 8 dígitos, gerado com fonte criptograficamente segura
    return "".join(secrets.choice("0123456789") for _ in range(8))


def create_token(user: User) -> tuple[str, str, datetime]:
    """Devolve (token, jti, expiracao). O jti permite revogar o token no logout."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = uuid.uuid4().hex
    token = jwt.encode(
        {
            "sub": str(user.id),
            "jti": jti,
            "exp": expire,
            # Versão do token: se a senha for trocada, o número sobe e as
            # sessões antigas deixam de valer no mesmo instante.
            "tv": int(user.token_version or 0),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return token, jti, expire


# ---------------------------------------------------------------------------
# Cookie de sessao
# ---------------------------------------------------------------------------
def _cookie_secure(request: Request) -> bool:
    if COOKIE_SECURE_MODE in ("true", "1", "yes"):
        return True
    if COOKIE_SECURE_MODE in ("false", "0", "no"):
        return False
    return request.url.scheme == "https"


def _set_session_cookie(response: Response, request: Request, token: str, max_age: int):
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=_cookie_secure(request),
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def _clear_session_cookie(response: Response, request: Request):
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=_cookie_secure(request),
        samesite=COOKIE_SAMESITE,
    )


# ---------------------------------------------------------------------------
# Bloqueio de tentativas -- persistido no banco (nao zera quando o servidor reinicia)
# ---------------------------------------------------------------------------
MAX_FAILS_EMAIL = 5
MAX_FAILS_IP = 100  # a escola inteira sai pelo MESMO IP (NAT): o limite por e-mail é o que protege cada conta
LOCK_SECONDS = 15 * 60
# A escola toda se cadastra pelo mesmo IP (NAT da unidade). 100/hora apertava
# em campanha de matrícula; 400/hora cobre a escola inteira com folga.
SIGNUP_MAX = 400
SIGNUP_WINDOW = 60 * 60


def _aware(dt):
    """Postgres devolve com fuso; SQLite devolve sem. Comparamos sempre com fuso."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


_DUMMY_HASH = None


def _burn_time(password: str):
    """Gasta o tempo de um bcrypt quando o e-mail não existe."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = pwd_context.hash("nao-existe")
    check_secret(password, _DUMMY_HASH)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


def _user_from_payload(db: Session, payload: dict) -> Optional[User]:
    """Recupera o usuário a partir do "sub" de um token já decodificado."""
    try:
        return db.get(User, int(payload.get("sub")))
    except (TypeError, ValueError):
        return None


def log_event(
    db: Session,
    *,
    user: Optional[User] = None,
    email: str = "",
    ip: str = "",
    success: bool = True,
    reason: str = "",
    request: Optional[Request] = None,
):
    """Registra uma tentativa de acesso no log de auditoria."""
    agent = request.headers.get("user-agent", "") if request is not None else ""
    db.add(
        LoginLog(
            user_id=user.id if user is not None else None,
            email=norm(email or (user.email if user is not None else "")),
            ip=ip or "",
            success=1 if success else 0,
            reason=(reason or "")[:120],
            user_agent=(agent or "")[:200],
        )
    )
    db.commit()


def _attempt_row(db: Session, scope: str, key: str) -> LoginAttempt:
    row = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.scope == scope, LoginAttempt.key == key)
        .first()
    )
    if row is None:
        row = LoginAttempt(scope=scope, key=key, failures=0)
        db.add(row)
        db.flush()
    return row


def check_login_lock(db: Session, email: str, ip: str):
    """Bloqueia por e-mail e por IP. Levanta 429 se algum dos dois estiver travado."""
    now = datetime.now(timezone.utc)
    for scope, key in (("email", email), ("ip", ip)):
        row = (
            db.query(LoginAttempt)
            .filter(LoginAttempt.scope == scope, LoginAttempt.key == key)
            .first()
        )
        if not row:
            continue
        locked = _aware(row.locked_until)
        if locked and locked > now:
            minutes = max(1, round((locked - now).total_seconds() / 60))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Muitas tentativas. Tente novamente em {minutes} minuto(s).",
            )


def register_login_fail(db: Session, email: str, ip: str):
    """Conta a falha no e-mail e no IP e trava quando o limite for atingido."""
    now = datetime.now(timezone.utc)
    for scope, key, limit in (
        ("email", email, MAX_FAILS_EMAIL),
        ("ip", ip, MAX_FAILS_IP),
    ):
        row = _attempt_row(db, scope, key)
        row.failures = (row.failures or 0) + 1
        row.updated_at = now
        if row.failures >= limit:
            row.locked_until = now + timedelta(seconds=LOCK_SECONDS)
            row.failures = 0
    db.commit()


def clear_login_fail(db: Session, email: str):
    """Login certo zera o contador do e-mail (o do IP continua: se zerasse, um
    invasor que acerta a propria conta liberaria o IP inteiro)."""
    row = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.scope == "email", LoginAttempt.key == email)
        .first()
    )
    if row:
        row.failures = 0
        row.locked_until = None
        row.updated_at = datetime.now(timezone.utc)
        db.commit()


def check_signup_rate(db: Session, ip: str):
    """Limite de cadastros por IP, tambem no banco (SIGNUP_MAX por hora)."""
    now = datetime.now(timezone.utc)
    row = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.scope == "signup", LoginAttempt.key == ip)
        .first()
    )
    if row:
        updated = _aware(row.updated_at) or now
        if (now - updated).total_seconds() >= SIGNUP_WINDOW:
            row.failures = 0
            row.updated_at = now
        elif (row.failures or 0) >= SIGNUP_MAX:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas de cadastro. Tente mais tarde.",
            )
    row = _attempt_row(db, "signup", ip)
    row.failures = (row.failures or 0) + 1
    row.updated_at = now
    db.commit()


# O perfil vem SEMPRE do banco, nunca do que o navegador diz.
ALLOWED_WHILE_MUST_CHANGE = {"/api/me", "/api/logout", "/api/password/change"}


def _extract_token(request: Request, authorization) -> Optional[str]:
    # O header Authorization ainda e aceito (util para testes e ferramentas),
    # mas o navegador usa apenas o cookie.
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return request.cookies.get(SESSION_COOKIE)


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessao invalida ou expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _extract_token(request, authorization)
    if not token:
        raise credentials_error
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        jti = payload.get("jti")
    except (JWTError, TypeError, ValueError):
        raise credentials_error

    if jti and db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise credentials_error  # token encerrado no logout

    user = db.get(User, user_id)
    if not user:
        raise credentials_error

    # A senha trocada sobe o token_version: qualquer cookie antigo (de outro
    # navegador, de outra máquina) deixa de valer na hora.
    if int(payload.get("tv") or 0) != int(user.token_version or 0):
        raise credentials_error

    # Conta com PIN provisório precisa trocar a senha antes de usar o sistema.
    if user.must_change_password and request.url.path not in ALLOWED_WHILE_MUST_CHANGE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Troca de senha obrigatória antes de continuar.",
        )
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Acesso não permitido.")
        return user

    return checker


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app):
    bootstrap_admin()  # cria o primeiro admin na inicialização
    seed_missions()    # cria as missões iniciais, se ainda não existir nenhuma
    yield


app = FastAPI(title="Estresse em Foco API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,  # o cookie de sessao precisa viajar junto
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/api/health")
def health():
    """Health check do Render: se isso responde, a API subiu."""
    return {"ok": True, "service": "estresse-em-foco-api"}


def _same_origin(origin: str, request: Request) -> bool:
    """True quando o Origin casa com o Host da requisicao.

    Com o rewrite da Vercel (site.vercel.app/api -> API na Oracle), o navegador
    fala so com a Vercel, mas o Host que chega na API continua sendo o do site.
    Como o navegador nao consegue forjar o header Host, comparar os dois e
    seguro contra CSRF e evita depender de lista de origens.
    """
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if not parsed.netloc:
        return False
    return parsed.netloc.lower() == request.headers.get("host", "").lower()


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    """Protecao contra CSRF: requisicoes que mudam estado so vem de origem conhecida."""
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in CORS_ORIGINS:
            if not _same_origin(origin, request):
                return JSONResponse(
                    {"detail": "Origem nao permitida."}, status_code=status.HTTP_403_FORBIDDEN
                )
    return await call_next(request)


def seed_missions():
    """Na primeira vez, carrega as missões de missions_data.py para o banco.
    Depois disso a psicologia gerencia tudo pelo site."""
    db = SessionLocal()
    try:
        if db.query(Mission).count() == 0:
            for i, m in enumerate(MISSIONS):
                mission = Mission(
                    title=m["title"], dimension=m["dimension"], scenario=m["scenario"],
                    active=True, position=i,
                )
                for o in m["options"]:
                    mission.options.append(MissionOption(
                        key=o["key"], text=o["text"], level=o["level"],
                        fb_title=o["title"], feedback=o["feedback"],
                    ))
                db.add(mission)
            db.commit()
    finally:
        db.close()


def bootstrap_admin():
    """Cria o primeiro administrador a partir do .env, se ainda não existir."""
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    if not email or not password:
        return
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.role == "admin").first():
            db.add(
                User(
                    name=os.getenv("ADMIN_NAME", "Administrador"),
                    email=norm(email),
                    password_hash=hash_secret(password),
                    role="admin",
                )
            )
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Autenticação
# (aluno: e-mail/matrícula + PIN | equipe: e-mail + senha — mesmo endpoint)
# ---------------------------------------------------------------------------
@app.post("/api/login")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = norm(form.username)
    ip = _client_ip(request)
    check_login_lock(db, email, ip)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        _burn_time(form.password)  # mesmo tempo de resposta: não revela quais e-mails existem
    if not user or not check_secret(form.password, user.password_hash):
        register_login_fail(db, email, ip)
        log_event(
            db, email=email, ip=ip, success=False,
            reason="credenciais invalidas", request=request,
        )
        raise HTTPException(status_code=401, detail="Credenciais invalidas.")

    clear_login_fail(db, email)
    log_event(
        db, user=user, email=email, ip=ip, success=True,
        reason="login", request=request,
    )
    token, jti, expire = create_token(user)
    response = JSONResponse(
        {
            "role": user.role,
            "name": user.name,
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "must_change_password": bool(user.must_change_password),
        }
    )
    _set_session_cookie(response, request, token, ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return response


@app.get("/api/me")
def me(user: User = Depends(get_current_user)):
    """Quem sou eu? O front usa isso para saber se ainda tem sessao."""
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "must_change_password": bool(user.must_change_password),
    }


@app.post("/api/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    """Logout de verdade: o token e invalidado no servidor e o cookie e apagado."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={"verify_exp": False},
            )
        except JWTError:
            payload = {}
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti:
            expires_at = (
                datetime.fromtimestamp(exp, tz=timezone.utc)
                if exp
                else datetime.now(timezone.utc)
                + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            db.add(RevokedToken(jti=jti, expires_at=expires_at))
        # limpeza dos tokens vencidos
        db.query(RevokedToken).filter(RevokedToken.expires_at < datetime.now(timezone.utc)).delete()
        db.commit()
        log_event(
            db,
            user=_user_from_payload(db, payload),
            ip=_client_ip(request),
            success=True,
            reason="logout",
            request=request,
        )

    response = JSONResponse({"ok": True})
    _clear_session_cookie(response, request)
    return response


# ---------------------------------------------------------------------------
# Troca de senha (Fase 2)
# Vale para aluno e para equipe. Ao trocar, o token_version sobe: as outras
# sessões do mesmo usuário caem e a conta fica com a senha nova.
# ---------------------------------------------------------------------------
class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=1, max_length=72)


@app.post("/api/password/change")
def change_password(
    data: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Troca a senha do usuário logado. Também serve para trocar o PIN provisório."""
    if not check_secret(data.current_password, user.password_hash):
        log_event(
            db, user=user, email=user.email, ip=_client_ip(request),
            success=False, reason="senha atual incorreta", request=request,
        )
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")

    problem = password_problem(data.new_password, user)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    if check_secret(data.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="A nova senha precisa ser diferente da atual.")

    user.password_hash = hash_secret(data.new_password)
    user.must_change_password = 0
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    db.refresh(user)

    log_event(
        db, user=user, email=user.email, ip=_client_ip(request),
        success=True, reason="senha alterada", request=request,
    )

    # Cookie novo: a sessão continua valendo com a senha nova.
    token, jti, expire = create_token(user)
    response = JSONResponse(
        {
            "ok": True,
            "name": user.name,
            "role": user.role,
            "must_change_password": False,
        }
    )
    _set_session_cookie(response, request, token, ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return response


# ---------------------------------------------------------------------------
# Auditoria de acessos (só a equipe/admin vê)
# ---------------------------------------------------------------------------
@app.get("/api/logs")
def list_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    limit = max(1, min(limit, 500))
    rows = (
        db.query(LoginLog)
        .order_by(LoginLog.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "email": r.email,
            "ip": r.ip,
            "success": bool(r.success),
            "reason": r.reason,
            "created_at": r.created_at,
        }
        for r in rows
    ]


# O aluno cria a própria conta. O perfil é SEMPRE "student" (o cliente não
# escolhe) e o código de acesso impede que estranhos se cadastrem.
@app.post("/api/register", status_code=201)
def register_student(
    data: StudentRegister, request: Request, db: Session = Depends(get_db)
):
    if not CLASS_CODE:
        raise HTTPException(
            status_code=503, detail="Cadastro de alunos está desativado no momento."
        )

    ip = _client_ip(request)
    check_signup_rate(db, ip)

    if not secrets.compare_digest(
        data.class_code.strip().encode(), CLASS_CODE.encode()
    ):
        raise HTTPException(status_code=403, detail="Código de acesso inválido.")

    email = norm(data.email)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=409,
            detail="Já existe uma conta com esse e-mail/matrícula. Se for sua, peça ao professor para redefinir o acesso.",
        )

    problem = password_problem(data.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_secret(data.password),
        role="student",
        must_change_password=0,  # o aluno escolheu a própria senha
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token, jti, expire = create_token(user)
    response = JSONResponse(
        {
            "role": user.role,
            "name": user.name,
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "must_change_password": False,
        },
        status_code=201,
    )
    _set_session_cookie(response, request, token, ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return response


# Professores e admin ainda podem cadastrar contas manualmente.
@app.post("/api/staff", status_code=201)
def create_staff(
    data: StaffCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    email = norm(data.email)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="E-mail já cadastrado.")
    problem = password_problem(data.password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_secret(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    return {"id": user.id, "name": user.name, "role": user.role}


# ---------------------------------------------------------------------------
# Estudantes (equipe)
# ---------------------------------------------------------------------------
@app.post("/api/students", status_code=201)
def create_student(
    data: StudentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ROLES_STAFF)),
):
    email = norm(data.email)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Já existe um cadastro com esse e-mail/matrícula.")
    pin = new_pin()
    student = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_secret(pin),
        role="student",
        # PIN provisório: no primeiro acesso o aluno precisa criar a senha dele.
        must_change_password=1,
    )
    db.add(student)
    db.commit()
    # O PIN só aparece AGORA; no banco fica apenas o hash.
    return {"id": student.id, "name": student.name, "email": student.email, "pin": pin}


@app.post("/api/students/{student_id}/reset-pin")
def reset_pin(
    student_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ROLES_STAFF)),
):
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(status_code=404, detail="Estudante não encontrado.")
    pin = new_pin()
    student.password_hash = hash_secret(pin)
    student.must_change_password = 1
    # O acesso anterior do aluno deixa de funcionar.
    student.token_version = int(student.token_version or 0) + 1
    db.commit()
    return {"id": student.id, "pin": pin}


@app.get("/api/students")
def list_students(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ROLES_STAFF)),
):
    students = (
        db.query(User).filter(User.role == "student").order_by(User.name).all()
    )
    return [
        {
            "id": s.id,
            "name": s.name,
            "email": s.email,
            "comm": s.comm,
            "conflict": s.conflict,
            "coop": s.coop,
            "must_change_password": bool(s.must_change_password),
        }
        for s in students
    ]


@app.put("/api/students/{student_id}/rubric")
def update_rubric(
    student_id: int,
    data: RubricUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ROLES_STAFF)),
):
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(status_code=404, detail="Estudante não encontrado.")
    student.comm, student.conflict, student.coop = data.comm, data.conflict, data.coop
    db.commit()
    return {"ok": True}


@app.delete("/api/students/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(status_code=404, detail="Estudante não encontrado.")
    # O log de acessos é histórico: desliga o vínculo em vez de apagar o
    # registro (e libera a FK do Postgres para excluir a conta).
    db.query(LoginLog).filter(LoginLog.user_id == student.id).update(
        {LoginLog.user_id: None}, synchronize_session=False
    )
    db.delete(student)  # apaga também o diário (cascade)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Diário — cada aluno só acessa o PRÓPRIO diário. Equipe não lê diários.
# ---------------------------------------------------------------------------
@app.post("/api/diary", status_code=201)
def save_diary(
    data: DiaryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("student")),
):
    entry = Diary(user_id=user.id, mood=data.mood.strip(), text=data.text.strip())
    db.add(entry)
    db.commit()
    return {"id": entry.id}


@app.get("/api/diary")
def my_diary(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("student")),
):
    entries = (
        db.query(Diary)
        .filter(Diary.user_id == user.id)
        .order_by(Diary.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {"id": e.id, "mood": e.mood, "text": e.text, "created_at": e.created_at}
        for e in entries
    ]


# ---------------------------------------------------------------------------
# Missões — alunos respondem; psicologia/admin criam e editam
# ---------------------------------------------------------------------------
ROLES_MISSIONS = ("psychologist", "admin")


def _mission_dict(m: Mission, full: bool) -> dict:
    options = []
    for o in m.options:
        item = {"key": o.key, "text": o.text}
        if full:  # nível e feedback só vão para quem gerencia; o aluno recebe depois de responder
            item.update({"level": o.level, "title": o.fb_title, "feedback": o.feedback})
        options.append(item)
    return {
        "id": m.id, "title": m.title, "dimension": m.dimension,
        "scenario": m.scenario, "active": m.active, "options": options,
    }


def _active_missions(db: Session):
    return (
        db.query(Mission).filter(Mission.active.is_(True))
        .order_by(Mission.position, Mission.id).all()
    )


def _student_progress(db: Session, user_id: int, mission_ids: list):
    if not mission_ids:
        return []
    return (
        db.query(MissionProgress)
        .filter(MissionProgress.user_id == user_id, MissionProgress.mission_id.in_(mission_ids))
        .all()
    )


@app.get("/api/missions")
def list_missions(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("student")),
):
    missions = _active_missions(db)
    rows = _student_progress(db, user.id, [m.id for m in missions])
    done = {r.mission_id: r for r in rows}
    out = []
    for m in missions:
        d = _mission_dict(m, full=False)
        d["done"] = m.id in done
        d["best_points"] = done[m.id].best_points if m.id in done else 0
        out.append(d)
    return {
        "total_points": sum(r.best_points for r in rows),
        "max_points": len(missions) * POINTS["good"],
        "completed": len(rows),
        "total_missions": len(missions),
        "missions": out,
    }


@app.post("/api/missions/{mission_id}/answer")
def answer_mission(
    mission_id: int,
    data: MissionAnswerIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("student")),
):
    mission = db.get(Mission, mission_id)
    if not mission or not mission.active:
        raise HTTPException(status_code=404, detail="Missão não encontrada.")
    option = next((o for o in mission.options if o.key == data.option), None)
    if not option:
        raise HTTPException(status_code=400, detail="Opção inválida.")

    points = POINTS[option.level]

    def save():
        row = (
            db.query(MissionProgress)
            .filter(MissionProgress.user_id == user.id, MissionProgress.mission_id == mission.id)
            .first()
        )
        if row:
            row.attempts += 1
            row.last_option = option.key
            row.best_points = max(row.best_points, points)
            row.answered_at = datetime.now(timezone.utc)
        else:
            row = MissionProgress(
                user_id=user.id, mission_id=mission.id,
                last_option=option.key, best_points=points,
            )
            db.add(row)
        db.commit()
        return row

    try:
        row = save()
    except IntegrityError:  # dois cliques ao mesmo tempo na primeira resposta
        db.rollback()
        row = save()

    rows = _student_progress(db, user.id, [m.id for m in _active_missions(db)])
    return {
        "level": option.level,
        "title": option.fb_title,
        "feedback": option.feedback,
        "points": points,
        "best_points": row.best_points,
        "total_points": sum(r.best_points for r in rows),
        "completed": len(rows),
    }


# --- gerenciamento (psicologia / admin) ---
def _apply_mission(m: Mission, data: MissionIn):
    m.title = data.title.strip()
    m.dimension = data.dimension
    m.scenario = data.scenario.strip()
    m.active = data.active
    m.options.clear()
    for i, o in enumerate(data.options):
        m.options.append(MissionOption(
            key=chr(65 + i), text=o.text.strip(), level=o.level,
            fb_title=o.title.strip(), feedback=o.feedback.strip(),
        ))


@app.get("/api/missions/manage")
def manage_list_missions(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ROLES_MISSIONS)),
):
    missions = db.query(Mission).order_by(Mission.position, Mission.id).all()
    counts = dict(
        db.query(MissionProgress.mission_id, func.count(MissionProgress.id))
        .group_by(MissionProgress.mission_id).all()
    )
    out = []
    for m in missions:
        d = _mission_dict(m, full=True)
        d["responses"] = counts.get(m.id, 0)
        out.append(d)
    return out


@app.post("/api/missions/manage", status_code=201)
def manage_create_mission(
    data: MissionIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ROLES_MISSIONS)),
):
    last = db.query(func.max(Mission.position)).scalar()
    m = Mission(position=(last + 1) if last is not None else 0)
    _apply_mission(m, data)
    db.add(m)
    db.commit()
    return {"id": m.id}


@app.put("/api/missions/manage/{mission_id}")
def manage_update_mission(
    mission_id: int,
    data: MissionIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ROLES_MISSIONS)),
):
    m = db.get(Mission, mission_id)
    if not m:
        raise HTTPException(status_code=404, detail="Missão não encontrada.")
    _apply_mission(m, data)
    db.commit()
    return {"ok": True}


@app.delete("/api/missions/manage/{mission_id}")
def manage_delete_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ROLES_MISSIONS)),
):
    m = db.get(Mission, mission_id)
    if not m:
        raise HTTPException(status_code=404, detail="Missão não encontrada.")
    db.delete(m)  # apaga também o progresso dos alunos nessa missão
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Meu DNA da Personalidade — cada aluno só vê o PRÓPRIO resultado
# ---------------------------------------------------------------------------
def _dna_out(r: DnaResult) -> dict:
    answers = [int(x) for x in r.answers.split(",")]
    return {"created_at": r.created_at, "dimensions": dna_data.compute(answers)}


@app.get("/api/dna")
def dna_get(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("student")),
):
    latest = (
        db.query(DnaResult).filter(DnaResult.user_id == user.id)
        .order_by(DnaResult.created_at.desc(), DnaResult.id.desc()).first()
    )
    return {
        "scale": dna_data.SCALE,
        "questions": [{"n": i + 1, "text": t} for i, t in enumerate(dna_data.QUESTIONS)],
        "latest": _dna_out(latest) if latest else None,
    }


@app.post("/api/dna", status_code=201)
def dna_submit(
    data: DnaSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("student")),
):
    row = DnaResult(user_id=user.id, answers=",".join(str(x) for x in data.answers))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _dna_out(row)


# ---------------------------------------------------------------------------
# Indicadores coletivos (psicologia / coordenação)
# Cada dimensão vale até 200 pts; a nota geral é normalizada para 1000.
# Só entram alunos que já tenham alguma observação registrada.
# ---------------------------------------------------------------------------
@app.get("/api/metrics")
def metrics(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "psychologist")),
):
    students = db.query(User).filter(User.role == "student").all()
    evaluated = [s for s in students if (s.comm or s.conflict or s.coop)]
    n = len(evaluated)

    def dim(attr: str) -> int:
        if n == 0:
            return 0
        avg = sum(getattr(s, attr) for s in evaluated) / n  # 0..4
        return round(avg / 4 * 200)

    dim_comm, dim_conflict, dim_coop = dim("comm"), dim("conflict"), dim("coop")
    score = round((dim_comm + dim_conflict + dim_coop) / 600 * 1000)

    return {
        "total_students": n,
        "score": score,
        "percentage": round(score / 10),
        "dim_comm": dim_comm,
        "dim_conflict": dim_conflict,
        "dim_coop": dim_coop,
    }

# Serve os ficheiros de estilos e scripts diretamente da raiz
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("index.html")