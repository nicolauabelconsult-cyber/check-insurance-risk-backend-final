# auth.py
import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User  # ajusta se o nome for diferente

# --------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-super-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8h

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()


# --------------------------------------------------------------------
# TOKEN HELPERS
# --------------------------------------------------------------------
def create_token(user: User) -> str:
  """Cria um JWT com os dados mínimos do utilizador."""
  expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  payload = {
    "sub": str(user.id),
    "username": user.username,
    "is_admin": user.is_admin,
    "exp": expire,
  }
  token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
  return token


def decode_token(token: str) -> dict:
  """Valida e devolve o payload do token."""
  try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload
  except JWTError:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Token inválido ou não fornecido",
      headers={"WWW-Authenticate": "Bearer"},
    )


# --------------------------------------------------------------------
# DEPENDENCIES
# --------------------------------------------------------------------
def get_current_user(
  token: str = Depends(oauth2_scheme),
  db: Session = Depends(get_db),
) -> User:
  payload = decode_token(token)
  user_id = payload.get("sub")
  if user_id is None:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Token inválido ou não fornecido",
    )
  user = db.query(User).get(int(user_id))
  if not user or not user.is_active:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Utilizador inválido ou inactivo",
    )
  return user


def get_current_admin(
  current_user: User = Depends(get_current_user),
) -> User:
  if not current_user.is_admin:
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Acesso reservado ao administrador",
    )
  return current_user
