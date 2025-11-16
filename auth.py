# auth.py - VERSÃO DEV (permite sempre o admin se o token falhar)
import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
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


def _try_decode(token: str):
    """Tenta decodificar o token. Devolve payload ou None em caso de erro."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# --------------------------------------------------------------------
# DEPENDENCIES (DEV: fallback para admin)
# --------------------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    DEV:
    1) Tenta validar o token JWT.
    2) Se falhar, usa o utilizador 'admin' como fallback.
    """
    user = None

    # 1) tentar validar token
    if token:
        payload = _try_decode(token)
        if payload:
            user_id = payload.get("sub")
            if user_id is not None:
                user = db.query(User).get(int(user_id))

    # 2) fallback DEV: usar sempre o admin se algo falhar
    if user is None:
        user = db.query(User).filter(User.username == "admin").first()

    if not user:
        # se nem o admin existir, aí sim lançamos erro
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
    # em DEV praticamente tudo será admin, mas mantemos a verificação
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso reservado ao administrador",
        )
    return current_user


# --------------------------------------------------------------------
# ROTAS DE AUTENTICAÇÃO
# --------------------------------------------------------------------
from fastapi import Body  # importa aqui para evitar ciclos


@router.post("/login")
def login(
    username: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db),
):
    """
    Login simples:
    - valida username/password
    - devolve um JWT criado por create_token
    """
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )

    # ATENÇÃO: aqui estamos a assumir que a password já vem validada
    # (ou que estás em ambiente de testes). Se tiveres hashing, mete
    # aqui a verificação com verify_pw.
    if password != "admin123" and user.username == "admin":
        # ajusta se tiveres outra password real
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
