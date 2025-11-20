
i"""
Módulo de autenticação - versão Argon2
"""

from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import os

# Chave JWT e configuração
SECRET_KEY = os.getenv("AUTH_SECRET", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

# ✅ Agora usamos Argon2 em vez de bcrypt
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar senha (Argon2)"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Se o hash estiver num formato antigo/incorrecto, devolve False
        return False


def get_password_hash(password: str) -> str:
    """Gerar hash Argon2 para a senha"""
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    """Criar token JWT"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verificar token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )
