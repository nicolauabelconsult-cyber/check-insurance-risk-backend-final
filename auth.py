# auth.py
"""
Camada de compatibilidade para código antigo que faz 'import auth'.
Reencaminha funções para o módulo security.
"""

from datetime import timedelta
from typing import Optional

from jose import jwt

from security import (
    SECRET_KEY,
    ALGORITHM,
    hash_password,
    verify_password,
    create_access_token,
)


def hash_pw(password: str) -> str:
    """Compatível com código antigo: hash_pw -> hash_password."""
    return hash_password(password)


def verify_pw(password: str, password_hash: str) -> bool:
    """Compatível com código antigo: verify_pw -> verify_password."""
    return verify_password(password, password_hash)


def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Compatível com código antigo: create_token -> create_access_token."""
    return create_access_token(data, expires_delta)


def decode_token(token: str) -> dict:
    """Decodifica um JWT usando a mesma chave/algoritmo do security."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
