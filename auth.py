# auth.py
import os
import time
from typing import Optional, Dict, Any

from jose import jwt, JWTError
from passlib.context import CryptContext

# --- Config ---
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-prod")  # define na Render
ALGO = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", "3600"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Password helpers ---
def hash_pw(raw_password: str) -> str:
    # Nota: bcrypt tem limite ~72 bytes; aqui validamos para evitar erro de runtime.
    if isinstance(raw_password, str) and len(raw_password.encode("utf-8")) > 72:
        raise ValueError("Password não pode ultrapassar 72 bytes (limite do bcrypt).")
    return pwd_context.hash(raw_password)

def verify_pw(raw_password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(raw_password, hashed)
    except Exception:
        return False

# --- JWT helpers ---
def create_token(*, sub: str, name: str, role: str, extra: Optional[Dict[str, Any]] = None) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "name": name,
        "role": role,
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRE_SECONDS,
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGO)
    return token

def decode_token(token: str) -> Dict[str, Any]:
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
        return data
    except JWTError as e:
        # Mantemos a mensagem genérica; o main traduz para 401 "Token inválido".
        raise ValueError("Invalid token") from e
