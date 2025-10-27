import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.hash import bcrypt
from models import LoginRequest, LoginResponse
from db import get_conn

router = APIRouter(prefix="/api", tags=["auth"])

SECRET_KEY = "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 8 * 60 * 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def create_access_token(data: dict, expires_delta_seconds: int = ACCESS_TOKEN_EXPIRE_SECONDS):
    to_encode = data.copy()
    expire = int(time.time()) + expires_delta_seconds
    to_encode.update({ "exp": expire })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/login", response_model=LoginResponse)
def login(login_req: LoginRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT email, name, password_hash, role, active FROM users WHERE email = ?",
        (login_req.email,)
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if row["active"] != 1:
        raise HTTPException(status_code=401, detail="Utilizador inactivo")

    if not bcrypt.verify(login_req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = create_access_token({
        "sub": row["email"],
        "role": row["role"]
    })

    return LoginResponse(
        access_token=token,
        user_name=row["name"],
        role=row["role"]
    )

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        role: Optional[str] = payload.get("role")
        exp: Optional[int] = payload.get("exp")

        now = int(time.time())
        if not email or not role or not exp or now > exp:
            raise HTTPException(status_code=401, detail="Token inválido ou expirado")

        return { "email": email, "role": role }

    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    return verify_token(token)

def require_admin(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user
