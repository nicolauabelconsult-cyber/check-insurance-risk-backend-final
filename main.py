
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
import itertools
import os
import shutil

# ---------------------------------
# CONTADORES E HELPERS BÁSICOS
# ---------------------------------

_user_id_counter = itertools.count(1)
_consulta_id_counter = itertools.count(100000)
_risk_id_counter = itertools.count(1)

def next_user_id():
    return next(_user_id_counter)

def next_consulta_id():
    return str(next(_consulta_id_counter))

def next_risk_id():
    return next(_risk_id_counter)

def now_ts():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

# ---------------------------------
# ESTRUTURAS EM MEMÓRIA
# (substitui base de dados por enquanto)
# ---------------------------------

class User(BaseModel):
    id: int
    name: str
    email: str
    password: str
    role: str

USERS: Dict[str, User] = {}

def bootstrap_admin():
    # utilizador inicial admin
    if "admin@checkrisk.com" not in USERS:
        USERS["admin@checkrisk.com"] = User(
            id=next_user_id(),
            name="Administrador",
            email="admin@checkrisk.com",
            password="admin123",
            role="admin"
        )
    # utilizador analista base (para testar sem admin)
    if "analyst@checkrisk.com" not in USERS:
        USERS["analyst@checkrisk.com"] = User(
            id=next_user_id(),
            name="Analista Técnico",
            email="analyst@checkrisk.com",
            password="analyst123",
            role="analyst"
        )

bootstrap_admin()

# consultas feitas no dashboard /api/risk-check
CONSULTAS: Dict[str, Dict] = {}

# base manual de risco que o admin.html grava
# cada item: dict com todos os campos capturados no formulário
RISK_DATA_STORE: List[Dict] = []

# fontes de informação (admin.html > Fontes de Informação)
SOURCES_STORE: List[Dict] = []

# garantir pastas
os.makedirs("reports", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

# ---------------------------------
# MODELOS Pydantic (entradas/saídas)
# ---------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    user_name: str
    role: str

class RiskCheckRequest(BaseModel):
    identifier: str            # NIF / BI / NOME / PASSAPORTE / CARTAO_RESIDENTE
    identifier_type: str       # "NIF" | "BI" | "NOME" | "PASSAPORTE" | "CARTAO_RESIDENTE"

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
# AUTENTICAÇÃO / AUTORIZAÇÃO
# ---------------------------------

def get_current_user(authorization: Optional[str] = Header(None)):
    """
    O frontend guarda o token = email (cir_token = data.access_token).
    Aqui validamos esse token e devolvemos o utilizador.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")
    token = authorization.replace("Bearer ", "").strip()
    user = USERS.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")
    return user

def require_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")

# ---------------------------------
# INICIALIZA FASTAPI + CORS
# ---------------------------------

app = FastAPI(
    title="Check Insurance Risk Backend (consolidado)",
    version="1.1",
    description="Versão consolidada para Render, com rotas admin + relatório PDF."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # em produção convém fechar isto
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------
# HEALTHCHECK
# ---------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}

# ---------------------------------
# LOGIN
# ---------------------------------

@app.post("/api/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """
    Frontend (index.html) faz POST /api/login com {email, password}.
    Resposta devolve access_token = email, user_name, role.
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
# CHECK DE RISCO (dashboard acesso.html)
# ---------------------------------

@app.post("/api/risk-check", response_model=RiskCheckResponse)
def risk_check(body: RiskCheckRequest, current=Depends(get_current_user)):
    """
    Recebe identificador + tipo (NIF / BI / NOME / PASSAPORTE / CARTAO_RESIDENTE)
    Gera score, decisão e flags simuladas.
    Guarda em CONSULTAS para depois gerar PDF.
    """

    # lógica mock - pode ser refinada depois
    base_score = 72
    pep_alert = False
    sanctions_alert = False
    decisao = "Aceitar Risco Técnico"
    justificacao = "Baseline técnico aplicado."
    benchmark = "Benchmarks internos e alertas PEP/Sanções UE/FMI."

    # normalizar tipo
    tipo_upper = body.identifier_type.strip().upper()
    ident = body.identifier.strip()

    # Se vier passaporte / cartão de residente forçamos revisão manual mais apertada
    if tipo_upper in ["PASSAPORTE", "CARTAO_RESIDENTE"]:
        decisao = "Escalar para Compliance"
        justificacao = "Documento de identificação internacional. Rever KYC manualmente."
        sanctions_alert = False
        pep_alert = False
        base_score = 65
        benchmark = "Sujeito a validação documental adicional."

    consulta_id = next_consulta_id()
    ts = now_ts()

    payload = {
        "consulta_id": consulta_id,
        "timestamp": ts,
        "identifier": ident,
        "identifier_type": tipo_upper,
        "score_final": base_score,
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
        "score_final": base_score,
        "decisao": decisao,
        "justificacao": justificacao,
        "pep_alert": pep_alert,
        "sanctions_alert": sanctions_alert,
        "benchmark_internacional": benchmark,
    }

# ---------------------------------
# GERAR / SERVIR RELATÓRIO PDF
# ---------------------------------

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
    """
    acesso.html faz:
      /api/report/{consulta_id}?token={cir_token}

    'token' aqui é o email do utilizador guardado no localStorage.
    Verificamos se existe e se a consulta existe.
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

# ---------------------------------
# ROTAS ADMIN - BASE DE RISCO MANUAL
# (admin.html -> enviarRegistoRisco / carregarRiscoLista / apagarRisco)
# ---------------------------------

@app.post("/api/admin/risk-data/add-record")
def admin_add_risk_record(
    id: str = Form(""),
    nome: str = Form(""),
    nif: str = Form(""),
    bi: str = Form(""),
    passaporte: str = Form(""),
    cartao_residente: str = Form(""),
    score_final: str = Form(""),
    justificacao: str = Form(""),
    pep_alert: str = Form("0"),
    sanctions_alert: str = Form("0"),
    historico_pagamentos: str = Form(""),
    sinistros_total: str = Form(""),
    sinistros_ult_12m: str = Form(""),
    fraude_suspeita: str = Form("0"),
    comentario_fraude: str = Form(""),
    esg_score: str = Form(""),
    country_risk: str = Form(""),
    credit_rating: str = Form(""),
    kyc_confidence: str = Form(""),
    current=Depends(get_current_user)
):
    # só admin
    require_admin(current)

    # update se id existir
    if id and id.strip():
        for rec in RISK_DATA_STORE:
            if str(rec["id"]) == str(id.strip()):
                rec.update({
                    "nome": nome,
                    "nif": nif,
                    "bi": bi,
                    "passaporte": passaporte,
                    "cartao_residente": cartao_residente,
                    "score_final": score_final,
                    "justificacao": justificacao,
                    "pep_alert": pep_alert == "1",
                    "sanctions_alert": sanctions_alert == "1",
                    "historico_pagamentos": historico_pagamentos,
                    "sinistros_total": sinistros_total,
                    "sinistros_ult_12m": sinistros_ult_12m,
                    "fraude_suspeita": fraude_suspeita == "1",
                    "comentario_fraude": comentario_fraude,
                    "esg_score": esg_score,
                    "country_risk": country_risk,
                    "credit_rating": credit_rating,
                    "kyc_confidence": kyc_confidence,
                    "last_update": now_ts(),
                })
                return {"id": rec["id"], "status": "updated"}

    new_id = next_risk_id()
    rec = {
        "id": new_id,
        "nome": nome,
        "nif": nif,
        "bi": bi,
        "passaporte": passaporte,
        "cartao_residente": cartao_residente,
        "score_final": score_final,
        "justificacao": justificacao,
        "pep_alert": pep_alert == "1",
        "sanctions_alert": sanctions_alert == "1",
        "historico_pagamentos": historico_pagamentos,
        "sinistros_total": sinistros_total,
        "sinistros_ult_12m": sinistros_ult_12m,
        "fraude_suspeita": fraude_suspeita == "1",
        "comentario_fraude": comentario_fraude,
        "esg_score": esg_score,
        "country_risk": country_risk,
        "credit_rating": credit_rating,
        "kyc_confidence": kyc_confidence,
        "created_at": now_ts(),
        "last_update": now_ts(),
    }
    RISK_DATA_STORE.append(rec)
    return {"id": new_id, "status": "created"}

@app.get("/api/admin/risk-data/list")
def admin_list_risk_data(current=Depends(get_current_user)):
    require_admin(current)
    return RISK_DATA_STORE

@app.post("/api/admin/risk-data/delete-record")
def admin_delete_risk_record(
    id: str = Form(...),
    current=Depends(get_current_user)
):
    require_admin(current)
    global RISK_DATA_STORE
    before = len(RISK_DATA_STORE)
    RISK_DATA_STORE = [r for r in RISK_DATA_STORE if str(r["id"]) != str(id)]
    after = len(RISK_DATA_STORE)
    if before == after:
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    return {"status": "deleted", "id": id}

# ---------------------------------
# ROTAS ADMIN - FONTES DE INFORMAÇÃO
# (admin.html -> uploadFonte / registarFonte / carregarFontes / apagarFonte)
# ---------------------------------

@app.post("/api/admin/info-sources/upload")
def admin_upload_source_file(
    file: UploadFile = File(...),
    current=Depends(get_current_user)
):
    require_admin(current)

    stored_filename = f"{int(datetime.utcnow().timestamp())}_{file.filename}"
    dest_path = os.path.join("uploads", stored_filename)

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"stored_filename": stored_filename}

@app.post("/api/admin/info-sources/create")
def admin_create_source(
    title: str = Form(""),
    description: str = Form(""),
    url: str = Form(""),
    directory: str = Form(""),
    filename: str = Form(""),
    categoria: str = Form(""),
    source_owner: str = Form(""),
    validade: str = Form(""),
    current=Depends(get_current_user)
):
    require_admin(current)

    if not title.strip() or not description.strip():
        raise HTTPException(status_code=422, detail="Título e descrição são obrigatórios")

    record = {
        "title": title.strip(),
        "description": description.strip(),
        "url": url.strip(),
        "directory": directory.strip(),
        "filename": filename.strip(),
        "categoria": categoria.strip(),
        "source_owner": source_owner.strip(),
        "validade": validade.strip(),
        "uploaded_at": now_ts(),
    }
    SOURCES_STORE.append(record)
    return {"status": "ok"}

@app.get("/api/admin/info-sources/list")
def admin_list_sources(current=Depends(get_current_user)):
    require_admin(current)
    return SOURCES_STORE

@app.post("/api/admin/info-sources/delete")
def admin_delete_source(
    index: int = Form(...),
    current=Depends(get_current_user)
):
    require_admin(current)
    if index < 0 or index >= len(SOURCES_STORE):
        raise HTTPException(status_code=404, detail="Fonte não encontrada")
    SOURCES_STORE.pop(index)
    return {"status": "deleted", "index": index}
