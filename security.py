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

def _pbkdf2_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200_000,
        dklen=32,
    )


def hash_password(password: str) -> str:
    """Gera um hash seguro para a password, com salt aleatório."""
    salt = os.urandom(16)
    pwd_hash = _pbkdf2_hash(password, salt)

    salt_b64 = base64.b64encode(salt).decode("utf-8")
    hash_b64 = base64.b64encode(pwd_hash).decode("utf-8")
    return f"{salt_b64}${hash_b64}"


def verify_password(password: str, stored_value: str) -> bool:
    """Verifica se a password fornecida gera o mesmo hash que o armazenado."""
    try:
        salt_b64, hash_b64 = stored_value.split("$", 1)
    except ValueError:
        return False

    salt = base64.b64decode(salt_b64.encode("utf-8"))
    expected_hash = base64.b64decode(hash_b64.encode("utf-8"))

    pwd_hash = _pbkdf2_hash(password, salt)
    return hmac.compare_digest(pwd_hash, expected_hash)


# ---------- JWT ----------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ---------- Dependências de autenticação ----------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou não fornecido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise credentials_exception
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso reservado a administradores")
    return user
