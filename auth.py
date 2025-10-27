
from fastapi import APIRouter, HTTPException, Depends, Form
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import uuid

from storage import get_users_db, set_user, disable_user_account

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

    users_db = get_users_db()
    user = users_db.get(email)
    if (not user) or (not user["active"]) or (user["password"] != pwd):
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

def has_sensitive_access(user):
    return getattr(user, "role", None) in ["admin","fraude","compliance"]

class CreateUserBody(BaseModel):
    name: str
    email: str
    password: str
    role: str  # "admin" / "analyst" / "fraude" / "compliance"

@router.get("/admin/users")
def list_users(user=Depends(get_current_user)):
    assert_admin(user)
    out = []
    for email, data in get_users_db().items():
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
    users_db = get_users_db()
    if email in users_db:
        raise HTTPException(status_code=400, detail="Utilizador já existe")
    new_user = {
        "password": body.password,
        "name": body.name,
        "role": body.role,
        "active": True,
    }
    set_user(email, new_user)
    return {"status":"ok","created":email}

@router.patch("/admin/users/disable")
def disable_user(email: str = Form(...), user=Depends(get_current_user)):
    assert_admin(user)
    email = email.strip().lower()
    users_db = get_users_db()
    if email not in users_db:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    disable_user_account(email)
    return {"status":"ok","disabled":email}
