# security.py
import os
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User


# -------------------------------------------------
# CONFIGURAÇÃO JWT E HASH
# -------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "check-insurance-risk-dev-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

PASSWORD_SALT = os.getenv("PASSWORD_SALT", "cir-dev-salt")


# -------------------------------------------------
# DB
# -------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------
# HASH DE PASSWORD (simples, suficiente para POC)
# -------------------------------------------------
def _hash_internal(password: str) -> str:
    data = (password + PASSWORD_SALT).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_password(password: str) -> str:
    return _hash_internal(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return hmac.compare_digest(_hash_internal(plain_password), password_hash)


# -------------------------------------------------
# TOKEN JWT
# -------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# -------------------------------------------------
# UTILIZADOR AUTENTICADO
# -------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Versão mais tolerante (DEV):

    1) Tenta validar o token JWT.
    2) Tenta encontrar o utilizador pelo ID (sub) ou pelo username.
    3) Se falhar, faz fallback para o utilizador 'admin'.
    """
    # 1) tentar decodificar o token normalmente
    payload = None
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            # ignora erro, vamos tentar fallback
            payload = None

    user: Optional[User] = None

    # 2) tentar obter o utilizador a partir do payload
    if payload:
        sub = payload.get("sub")
        username_claim = payload.get("username")

        # tentar primeiro como ID
        if sub is not None:
            try:
                user_id = int(sub)
                user = db.query(User).filter(User.id == user_id).first()
            except (TypeError, ValueError):
                user = None

        # se ainda não encontrou, tenta por username
        if user is None and username_claim:
            user = db.query(User).filter(User.username == username_claim).first()

    # 3) Fallback DEV: se nada disso funcionar, usa o admin
    if user is None:
        user = db.query(User).filter(User.username == "admin").first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilizador não encontrado (nem admin).",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilizador inactivo.",
        )

    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return current_user
