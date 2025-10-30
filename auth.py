
import os, time, jwt, hashlib
from fastapi import HTTPException, status

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-"+hashlib.sha256(b"default").hexdigest())
ALGO = "HS256"
TOKEN_TTL = 60 * 60 * 8  # 8h

def hash_pw(pw: str) -> str:
    # Simple salted hash for demo (not for production)
    salt = "cir$2025!"
    return hashlib.sha256((salt + pw).encode()).hexdigest()

def create_token(sub: str, name: str, role: str) -> str:
    now = int(time.time())
    payload = {"sub": sub, "name": name, "role": role, "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
