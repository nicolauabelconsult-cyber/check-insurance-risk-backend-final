from fastapi import APIRouter, HTTPException, status, Depends, Form
from . import models, schemas, utils

router = APIRouter()

@router.post("/login", response_model=schemas.LoginResponse)
def login(body: schemas.LoginRequest):
    user = models.USERS.get(body.email)
    if not user or user.password != body.password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    return schemas.LoginResponse(
        access_token=user.email,
        user_name=user.name,
        role=user.role
    )

@router.get("/admin/users/list")
def list_users(current=Depends(utils.get_current_user)):
    utils.require_admin(current)
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role
        }
        for u in models.USERS.values()
    ]

@router.post("/admin/users/create")
def create_user(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    current=Depends(utils.get_current_user)
):
    utils.require_admin(current)

    if email in models.USERS:
        raise HTTPException(status_code=409, detail="Email já existente")

    new_user = models.User(
        id=models.next_user_id(),
        name=name,
        email=email,
        password=password,
        role=role
    )
    models.USERS[email] = new_user
    return {"status":"ok","id": new_user.id}
