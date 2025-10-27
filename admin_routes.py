from fastapi import APIRouter, Depends, HTTPException, Form
from passlib.hash import bcrypt
from datetime import datetime, timezone

from auth import require_admin
from db import get_conn
from models import CreateUserRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/users")
def list_users(admin=Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT email, name, role, active FROM users ORDER BY role DESC, email ASC"
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "email": r["email"],
            "name": r["name"],
            "role": r["role"],
            "active": bool(r["active"])
        }
        for r in rows
    ]

@router.post("/users")
def create_user(user_req: CreateUserRequest, admin=Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (email, name, password_hash, role, active) VALUES (?, ?, ?, ?, 1)",
            (
                user_req.email,
                user_req.name,
                bcrypt.hash(user_req.password),
                user_req.role
            )
        )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=400, detail="Não foi possível criar utilizador (email duplicado?)")
    conn.close()
    return {"status": "ok", "message": "Utilizador criado"}

@router.patch("/users/disable")
def disable_user(email: str = Form(...), admin=Depends(require_admin)):
    if email == "admin@checkrisk.com":
        raise HTTPException(status_code=403, detail="Não pode desactivar o admin inicial")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET active = 0 WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"Acesso desactivado para {email}"}

@router.post("/risk-data/add-record")
def add_risk_record(
    identifier: str = Form(...),
    identifier_type: str = Form(...),
    score_final: int = Form(...),
    justificacao: str = Form(...),
    pep_alert: int = Form(...),
    sanctions_alert: int = Form(...),
    admin=Depends(require_admin)
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO risk_data
        (identifier, identifier_type, score_final, justificacao, pep_alert, sanctions_alert, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identifier,
            identifier_type,
            score_final,
            justificacao,
            pep_alert,
            sanctions_alert,
            datetime.now(timezone.utc).isoformat()
        )
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Registo de risco inserido/actualizado"}

@router.get("/audit/logs")
def get_audit_logs(limit: int = 20, admin=Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT consulta_id, identifier, decisao, score_final, requested_by, timestamp FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "consulta_id": r["consulta_id"],
            "identifier": r["identifier"],
            "decisao": r["decisao"],
            "score_final": r["score_final"],
            "requested_by": r["requested_by"],
            "timestamp": r["timestamp"]
        }
        for r in rows
    ]
