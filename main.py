from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
import itertools
import os

# ---------------------------------
# Estado em memória (utilizadores e consultas)
# ---------------------------------

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
    role: str  # "admin", etc.


# "base de dados" em memória
USERS: Dict[str, User] = {}
CONSULTAS: Dict[str, Dict] = {}

def bootstrap_admin():
    """
    Garante que existe um utilizador administrador para login:
    email: admin@checkrisk.com
    password: admin123
    """
    if "admin@checkrisk.com" not in USERS:
        USERS["admin@checkrisk.com"] = User(
            id=next_user_id(),
            name="Administrador",
            email="admin@checkrisk.com",
            password="admin123",
            role="admin"
        )

bootstrap_admin()

# garantir pasta onde os PDFs vão ser guardados
os.makedirs("reports", exist_ok=True)


# ---------------------------------
# Modelos (request/response)
# ---------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    user_name: str
    role: str

class RiskCheckRequest(BaseModel):
    identifier: str
    identifier_type: str  # ex: "NIF", "BI"

class RiskCheckResponse(BaseModel):
    consulta_id: str
    timestamp: str
    score_final: int
    decisao: str
    justificacao: str
    pep_alert: bool
    sanctions_alert: bool
    benchmark_internacional: str


# ---------------------------------
# Helpers de autenticação
# ---------------------------------

def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Lê Authorization: Bearer <token>
    O token é simplesmente o email devolvido no login.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")

    token = authorization.replace("Bearer ", "").strip()
    user = USERS.get(token)

    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")

    return user


# ---------------------------------
# Instância FastAPI + CORS
# ---------------------------------

app = FastAPI(
    title="Check Insurance Risk Backend (root version)",
    version="1.0",
    description="Versão mínima para Render, sem subpastas."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção podes restringir ao teu domínio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------
# GET /api/health
# usado pelo browser para ver se o backend está vivo
# ---------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------
# POST /api/login
# devolve token e perfil
# ---------------------------------

@app.post("/api/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """
    O frontend envia email e password.
    Se válido devolvemos:
      - access_token (igual ao email)
      - user_name
      - role
    O frontend guarda access_token em localStorage como cir_token.
    """
    user = USERS.get(body.email)

    if not user or user.password != body.password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    return LoginResponse(
        access_token=user.email,
        user_name=user.name,
        role=user.role
    )


# ---------------------------------
# POST /api/risk-check
# simula a análise de risco e devolve um ID de consulta
# ---------------------------------

@app.post("/api/risk-check", response_model=RiskCheckResponse)
def risk_check(body: RiskCheckRequest, current=Depends(get_current_user)):
    """
    Esta rota faz o "check de risco".
    Gera um score e regista a consulta para depois gerar PDF.
    """

    # Simulação (placeholder técnico)
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

    # Guardar esta consulta em memória para podermos gerar/servir PDF depois
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


# ---------------------------------
# Função interna: gerar PDF
# ---------------------------------

def generate_pdf(consulta_id: str, data: Dict):
    """
    Gera um PDF mínimo com dados técnicos da consulta.
    Escreve em ./reports/<consulta_id>.pdf
    """
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


# ---------------------------------
# GET /api/report/{consulta_id}
# devolve o PDF dessa consulta
# ---------------------------------

@app.get("/api/report/{consulta_id}")
def get_report(consulta_id: str, token: str):
    """
    O front chama isto assim:
    GET /api/report/<consulta_id>?token=<cir_token>

    Onde cir_token é exatamente o access_token devolvido em /api/login,
    que no nosso caso é o email do user.
    """

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
