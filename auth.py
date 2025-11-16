# auth.py - DEV: leitura manual do Bearer + fallback para admin
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Body, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User

# --------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-super-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8h

router = APIRouter(prefix="/auth", tags=["auth"])


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
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "is_admin": user.is_admin,
        "exp": expire,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_token(token: str) -> Optional[dict]:
    """
    Tenta decodificar o token.
    Em DEV **não** lança HTTPException – devolve None se falhar.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# --------------------------------------------------------------------
# OBTENÇÃO DO TOKEN A PARTIR DO HEADER
# --------------------------------------------------------------------
def get_bearer_token(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Lê `Authorization: Bearer <token>` do header.
    Devolve apenas o token ou None se não existir / estiver mal formado.
    """
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


# --------------------------------------------------------------------
# DEPENDENCIES (DEV: fallback para admin)
# --------------------------------------------------------------------
def get_current_user(
    token: Optional[str] = Depends(get_bearer_token),
    db: Session = Depends(get_db),
) -> User:
    """
    Lógica DEV:
    1) Se houver token e for válido -> devolve o utilizador do token.
    2) Se não houver token OU o token for inválido -> usa o utilizador 'admin'.
    """
    user: Optional[User] = None

    # 1) tentar usar o token, se existir
    if token:
        payload = decode_token(token)
        if payload:
            user_id = payload.get("sub")
            if user_id is not None:
                user = db.query(User).get(int(user_id))

    # 2) fallback DEV: usar sempre o admin se algo falhar
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


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso reservado ao administrador",
        )
    return current_user


# --------------------------------------------------------------------
# ROTAS DE AUTENTICAÇÃO
# --------------------------------------------------------------------
@router.post("/login")
def login(
    username: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db),
):
    """
    Login simples para ambiente de testes.
    Ajusta a validação de password conforme o teu modelo real.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    # validação mínima de password em DEV (ajusta à tua lógica real)
    if user.username == "admin" and password != "admin123":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password inválida",
        )

    token = create_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "is_admin": user.is_admin,
        },
    }


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
    }
