import os, time, jwt, hashlib
from fastapi import HTTPException, status

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGO = "HS256"
TOKEN_TTL = int(os.getenv("TOKEN_TTL_SECONDS", str(60*60*24)))  # 24h por defeito

def hash_pw(pw: str) -> str:
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
