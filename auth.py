from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import uuid

USERS_DB = {
    "admin@checkrisk.com": {
        "password": "admin123",
        "name": "Admin Master",
        "role": "admin",
        "active": True,
    },
    "analyst@checkrisk.com": {
        "password": "analyst123",
        "name": "Analyst Demo",
        "role": "analyst",
        "active": True,
    },
}

TOKEN_STORE = {}
TOKEN_TTL_MINUTES = 480  # 8h

router = APIRouter(prefix="/api", tags=["auth"])

class LoginBody(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    role: str

def _issue_token(email: str, name: str, role: str):
    token = str(uuid.uuid4())
    TOKEN_STORE[token] = {
        "email": email,
        "name": name,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES),
    }
    return token

@router.post("/login", response_model=LoginResponse)
def login(body: LoginBody):
    email = body.email.strip().lower()
    pwd = body.password.strip()

    user = USERS_DB.get(email)
    if not user or not user["active"] or user["password"] != pwd:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = _issue_token(email, user["name"], user["role"])
    return LoginResponse(
        access_token=token,
        user_name=user["name"],
        role=user["role"],
    )

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Token ausente")

    token = credentials.credentials
    info = TOKEN_STORE.get(token)
    if not info:
        raise HTTPException(status_code=401, detail="Token inválido")

    if info["exp"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Sessão expirada")

    class SessionUser:
        email: str = info["email"]
        name: str = info["name"]
        role: str = info["role"]
    return SessionUser()

def assert_admin(user):
    if getattr(user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")

class CreateUserBody(BaseModel):
    name: str
    email: str
    password: str
    role: str  # "admin" ou "analyst"

@router.get("/admin/users")
def list_users(user=Depends(get_current_user)):
    assert_admin(user)
    out = []
    for email, data in USERS_DB.items():
        out.append({
            "email": email,
            "name": data["name"],
            "role": data["role"],
            "active": data["active"],
        })
    return out

@router.post("/admin/users")
def create_user(body: CreateUserBody, user=Depends(get_current_user)):
    assert_admin(user)
    email = body.email.strip().lower()
    if email in USERS_DB:
        raise HTTPException(status_code=400, detail="Utilizador já existe")

    USERS_DB[email] = {
        "password": body.password,
        "name": body.name,
        "role": body.role,
        "active": True,
    }
    return {"status": "ok", "created": email}

@router.patch("/admin/users/disable")
def disable_user(email: str, user=Depends(get_current_user)):
    assert_admin(user)
    email = email.strip().lower()
    if email not in USERS_DB:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    USERS_DB[email]["active"] = False
    return {"status": "ok", "disabled": email}
