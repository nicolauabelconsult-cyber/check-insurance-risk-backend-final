from fastapi import HTTPException, status, Header
from typing import Optional
from . import models

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente")
    token = authorization.replace("Bearer ", "").strip()
    user = models.USERS.get(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    return user

def require_admin(user):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
