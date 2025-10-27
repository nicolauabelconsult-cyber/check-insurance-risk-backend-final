import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from models import LoginRequest, LoginResponse

router = APIRouter(prefix="/api", tags=["auth"])

SECRET_KEY = "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 8 * 60 * 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

FAKE_USER = {
    "email": "admin@checkrisk.com",
    "password": "123456",
    "user_name": "Administrador"
}

def create_access_token(data: dict, expires_delta_seconds: int = ACCESS_TOKEN_EXPIRE_SECONDS):
    to_encode = data.copy()
    expire = int(time.time()) + expires_delta_seconds
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token

@router.post("/login", response_model=LoginResponse)
def login(login_req: LoginRequest):
    if login_req.email != FAKE_USER["email"] or login_req.password != FAKE_USER["password"]:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    token = create_access_token(data={"sub": login_req.email})
    return LoginResponse(access_token=token, user_name=FAKE_USER["user_name"])

def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        exp: Optional[int] = payload.get("exp")
        if email is None or exp is None:
            raise HTTPException(status_code=401, detail="Token inválido ou expirado")
        now = int(time.time())
        if now > exp:
            raise HTTPException(status_code=401, detail="Token inválido ou expirado")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    return verify_token(token)
