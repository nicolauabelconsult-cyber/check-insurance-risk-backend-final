from fastapi import APIRouter, HTTPException, Form
from app.admin.storage_users import validate_login
from app.auth.security import create_token

router = APIRouter(prefix="/api", tags=["auth"])

@router.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...)
):
    u = validate_login(email, password)
    if not u:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = create_token(
        email=u["email"],
        name=u["name"],
        role=u["role"]
    )
    return {
        "access_token": token,
        "user_name": u["name"],
        "role": u["role"]
    }
