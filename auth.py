"""Módulo de autenticação do Check Insurance Risk (com Argon2)."""

from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
import os

# -------------------------------------------------------------------
# Configuração JWT
# -------------------------------------------------------------------
SECRET_KEY = os.getenv("AUTH_SECRET", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

# -------------------------------------------------------------------
# Configuração de hashing de passwords (ARGON2)
# -------------------------------------------------------------------
# Usa Argon2 em vez de bcrypt – não tem limite de 72 caracteres.
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a password em texto simples corresponde ao hash guardado.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Gera um hash seguro da password usando Argon2.
    """
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    """
    Cria um token JWT com expiração em ACCESS_TOKEN_EXPIRE_HOURS.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
