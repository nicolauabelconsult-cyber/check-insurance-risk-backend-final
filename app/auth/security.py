from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Header
from typing import Optional
from app.config import JWT_SECRET, JWT_ALGO, JWT_EXPIRE_MINUTES
from app.admin.storage_users import get_user_by_email_no_pwd

def create_token(email: str, name: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "name": name,
        "role": role,
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token(token: str):
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return data
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Credenciais ausentes")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Formato inválido")
    token = authorization.split(" ", 1)[1]
    data = decode_token(token)
    user = get_user_by_email_no_pwd(data["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Utilizador não encontrado")
    return user

def require_admin(user):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
