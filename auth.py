# auth.py
import os, time
from typing import Optional, Dict, Any
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from passlib.context import CryptContext

# >>> DEFINA ESTE NOME DE VARIÁVEL NO RENDER <<<
SECRET_KEY = os.getenv("JWT_SECRET", "cir-dev-secret")  # NÃO deixar default em produção
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "360"))  # 6 horas por default

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_pw(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_pw(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_token(*, sub: str, name: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "name": name,
        "role": role,
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRE_MIN * 60,
        "iss": "cir-backend",
        "aud": "cir-frontend",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], audience="cir-frontend")
    except ExpiredSignatureError:
        # mensagem diferenciada para o frontend poder tratar
        raise JWTError("expired")

    except JWTError:
        raise

