import os, time, jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGO = "HS256"
TOKEN_TTL = int(os.getenv("TOKEN_TTL_SECONDS", str(60*60*24)))  # 24h por defeito
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_pw(pw: str) -> str:
    # Sem typos: usa 'pw' (não 'p')
    return pwd_context.hash(pw, rounds=BCRYPT_ROUNDS)

def verify_pw(pw: str, hashed: str) -> bool:
    return pwd_context.verify(pw, hashed)

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
