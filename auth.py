# auth.py
import os
import time
import hashlib
import hmac
from typing import Optional, Dict, Any

import jwt  # PyJWT

SECRET = os.getenv("JWT_SECRET") or os.urandom(32).hex()
JWT_ALG = "HS256"
JWT_EXP_SECONDS = 60 * 60 * 8  # 8h

def create_token(*, sub: str, name: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "name": name,
        "role": role,
        "iat": now,
        "exp": now + JWT_EXP_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])

# Passwords
def hash_pw(pw: str) -> str:
    # bcrypt já vem via passlib[bcrypt], mas podemos usar SHA256 HMAC simples
    # se quiseres trocar para passlib, adapta aqui.
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()

def verify_pw(pw: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_pw(pw), hashed)
