# security.py
from datetime import datetime, timedelta
from typing import Optional

import base64
import os
import hashlib
import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User

# Chave secreta para JWT – em produção usa variável de ambiente
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ALTERAR_PARA_UMA_CHAVE_LONGA_E_SECRETA")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------- Ligação à BD ----------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Hash de password (sem passlib) ----------

# Vamos usar PBKDF2-HMAC-SHA256 da biblioteca padrão
# Formato guardado na BD:  salt_base64$hash_base64

def _pbkdf2_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,   # número de iterações
        dklen=32,
    )


def hash_password(password: str) -> str:
    """
    Gera um hash seguro para a password, com salt aleatório.
    Retorna uma string "salt$hash" (ambos em base64).
    """
    salt = os.urandom(16)
    pwd_hash = _pbkdf2_hash(password, salt)

    salt_b64 = base64.b64encode(salt).decode("utf-8")
    hash_b64 = base64.b64encode(pwd_hash).decode("utf-8")
    return f"{salt_b64}${hash_b64}"


def verify_password(password: str, stored_value: str) -> bool:
    """
    Verifica se a password fornecida gera o mesmo hash que o armazenado.
    """
    try:
        salt_b64, hash_b64 = stored_value.split("$", 1)
    except ValueError:
        # Formato inesperado – tratamos como inválido
        return False

    salt = base64.b64decode(salt_b64.encode("utf-8"))
    expected_hash = base64.b64decode(hash_b64.encode("utf-8"))

    pwd_hash = _pbkdf2_hash(password, salt)
    # hmac.compare_digest evita ataques de timing
    return hmac.compare_digest(pwd_hash, expected_hash)


# ---------- JWT ----------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.ut
