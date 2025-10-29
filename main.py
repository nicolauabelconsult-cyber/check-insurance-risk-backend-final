from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
import itertools
import os

_user_id_counter = itertools.count(1)
_consulta_id_counter = itertools.count(100000)

def next_user_id():
    return next(_user_id_counter)

def next_consulta_id():
    return str(next(_consulta_id_counter))

def now_ts():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

class User(BaseModel):
    id: int
    name: str
    email: str
    password: str
    role: str

USERS: Dict[str, User] = {}

def bootstrap_admin():
    if "admin@checkrisk.com" not in USERS:
        USERS["admin@checkrisk.com"] = User(
            id=next_user_id(),
            name="Administrador",
            email="admin@checkrisk.com",
            password="admin123",
            role="admin"
        )

bootstrap_admin()

CONSULTAS: Dict[str, Dict] = {}

os.makedirs("reports", exist_ok=True)

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    user_name: str
    role: str

class RiskCheckRequest(BaseModel):
    identifier: str
    identifier_type: str

class RiskCheckResponse(BaseModel):
    consulta_id: str
    timestamp: str
    score_final: int
    decisao: str
    justificacao: str
    pep_alert: bool
    sanctions_alert: bool
    benchmark_internacional: str

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")
    token = authorization.replace("Bearer ", "").strip()
    user = USERS.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")
    return user

app = FastAPI(
    title="Check Insurance Risk Backend (root version)",
    version="1.0",
    description="Versão mínima para Render, sem subpastas."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/login", response_model=LoginResponse)
def login(body: LoginRequest):
    user = USERS.get(body.email)
    if not user or user.password != body.password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return LoginResponse(
        access_token=user.email,
        user_name=user.name,
        role=user.role
    )

@app.post("/api/risk-check", response_model=RiskCheckResponse)
def risk_check(body: RiskCheckRequest, current=Depends(get_current_user)):
    score_final = 72
    decisao = "Aceitar Risco Técnico"
    justificacao = "Baseline técnico aplicado."
    pep_alert = False
    sanctions_alert = False
    benchmark = "Benchmarks internos e alertas PEP/Sanções UE/FMI."

    consulta_id = next_consulta_id()
    ts = now_ts()

    payload = {
        "consulta_id": consulta_id,
        "timestamp": ts,
        "identifier": body.identifier,
        "identifier_type": body.identifier_type,
        "score_final": score_final,
        "decisao": decisao,
        "justificacao": justificacao,
        "pep_alert": pep_alert,
        "sanctions_alert": sanctions_alert,
        "benchmark_internacional": benchmark,
    }
    CONSULTAS[consulta_id] = payload

    return {
        "consulta_id": consulta_id,
        "timestamp": ts,
        "score_final": score_final,
        "decisao": decisao,
        "justificacao": justificacao,
        "pep_alert": pep_alert,
        "sanctions_alert": sanctions_alert,
        "benchmark_internacional": benchmark,
    }

def generate_pdf(consulta_id: str, data: Dict):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    pdf_path = os.path.join("reports", f"{consulta_id}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4
    y = h - 50

    lines = [
        "Check Insurance Risk - Relatório Técnico",
        f"Consulta ID: {consulta_id}",
        f"Timestamp: {data.get('timestamp','')}",
        "",
        f"Identificador: {data.get('identifier','')} ({data.get('identifier_type','')})",
        "",
        f"Score Final: {data.get('score_final','')} /100",
        f"Decisão: {data.get('decisao','')}",
        f"PEP Alert: {data.get('pep_alert','')}",
        f"Sanções Alert: {data.get('sanctions_alert','')}",
        "",
        "Justificação Técnica:",
        data.get("justificacao",""),
        "",
        f"Benchmark Internacional: {data.get('benchmark_internacional','')}",
    ]

    for line in lines:
        c.drawString(40, y, str(line))
        y -= 15
        if y < 80:
            c.showPage()
            y = h - 50

    c.save()
    return pdf_path

@app.get("/api/report/{consulta_id}")
def get_report(consulta_id: str, token: str):
    user = USERS.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")
    data = CONSULTAS.get(consulta_id)
    if not data:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    pdf_path = os.path.join("reports", f"{consulta_id}.pdf")
    if not os.path.exists(pdf_path):
        generate_pdf(consulta_id, data)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"relatorio_{consulta_id}.pdf"
    )
