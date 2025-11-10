import os, time
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
JWT_TTL = int(os.getenv("JWT_TTL", "86400"))

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_pw(p: str) -> str:
    return pwd.hash(p)

def verify_pw(p: str, hashed: str) -> bool:
    return pwd.verify(p, hashed)

def create_token(sub: str, name: str, role: str) -> str:
    now = int(time.time())
    payload = {"sub": sub, "name": name, "role": role, "iat": now, "exp": now + JWT_TTL}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError as e:
        raise Exception("Invalid token") from e
