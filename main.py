# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
import io
import os
import random

# -------------------------------------------------------------------
# FASTAPI + CORS
# -------------------------------------------------------------------
app = FastAPI(
    title="Check Insurance Risk Backend (Consolidado)",
    version="1.3",
    description="Backend consolidado com área admin, geração de PDF profissional e suporte a passaporte/cartão de residente."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://checkinsurancerisk.com",
        "https://www.checkinsurancerisk.com",
        # (opcional para testes locais)
        "http://localhost", "http://localhost:3000", "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# SAÚDE
# -------------------------------------------------------------------
@app.get("/api/health")
def health_check():
    return {"status": "ok"}

# -------------------------------------------------------------------
# MODELOS
# -------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    user_name: str
    role: str

class RiskCheckRequest(BaseModel):
    identifier: str
    identifier_type: str  # NIF | BI | NOME | PASSAPORTE | CARTAO_RESIDENTE

class RiskCheckResponse(BaseModel):
    consulta_id: str
    consulta_id_raw: int
    score_final: int
    decisao: str
    timestamp: str

# -------------------------------------------------------------------
# DADOS EM MEMÓRIA (ephemeral no Render, suficiente para PoC)
# -------------------------------------------------------------------
class User:
    def __init__(self, name: str, email: str, password: str, role: str):
        self.name = name
        self.email = email
        self.password = password
        self.role = role

USERS: Dict[str, User] = {
    "admin@checkrisk.com":   User("Administrador", "admin@checkrisk.com",   "admin123",   "admin"),
    "analyst@checkrisk.com": User("Analista",      "analyst@checkrisk.com", "analyst123", "analyst"),
}

# Base de risco (ID autoincremental)
RISK_DATA: List[Dict[str, Any]] = []
RISK_SEQ = 1

# Fontes de informação
INFO_SOURCES: List[Dict[str, Any]] = []

# Resultados das consultas para gerar PDF
LAST_RESULTS: Dict[int, Dict[str, Any]] = {}

UPLOAD_DIR = os.environ.get("CIR_UPLOAD_DIR", "/tmp/cir_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------------------------------------------------------
# AUTH SIMPLES (token = email do utilizador)
# -------------------------------------------------------------------
def get_current_user(authorization: Optional[str] = None) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token em falta")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Formato de Authorization inválido")
    token = parts[1].strip().lower()
    user = USERS.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")
    return user

# -------------------------------------------------------------------
# LOGIN
# -------------------------------------------------------------------
@app.post("/api/login", response_model=LoginResponse)
def login(body: LoginRequest):
    email = body.email.strip().lower()
    password = body.password.strip()
    user = USERS.get(email)
    if not user or user.password != password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return LoginResponse(access_token=user.email, user_name=user.name, role=user.role)

# -------------------------------------------------------------------
# LÓGICA DE RISCO (mock com regras alinhadas ao combinado)
# -------------------------------------------------------------------
def calcular_score_e_decisao(identifier: str, identifier_type: str) -> (int, str):
    idt = (identifier_type or "").upper()
    # Regra: documentos internacionais escalam para compliance e ~score 65
    if idt in ("PASSAPORTE", "CARTAO_RESIDENTE"):
        return 65, "Escalar para Compliance"
    # Para NIF/BI/NOME criamos regra simples determinística:
    seed = sum(ord(c) for c in (identifier.strip() + idt))
    random.seed(seed)
    base = random.randint(20, 95)
    # Se houver “alertas” na base de risco, penaliza/eleva
    alerta = False
    for r in RISK_DATA:
        ids = [r.get("nif",""), r.get("bi",""), r.get("nome",""), r.get("passaporte",""), r.get("cartao_residente","")]
        if identifier.strip() in ids:
            alerta = (r.get("pep_alert") == "1" or r.get("sanctions_alert") == "1" or r.get("fraude_suspeita") == "1")
            break
    if alerta:
        base = max(base, 70)
    decisao = "Aprovar" if base >= 60 else "Rever Manualmente"
    return base, decisao

def gerar_consulta_id(n: int) -> str:
    return f"CIR-{n:05d}"

# -------------------------------------------------------------------
# /api/risk-check
# -------------------------------------------------------------------
@app.post("/api/risk-check", response_model=RiskCheckResponse)
def risk_check(req: RiskCheckRequest, user: User = Depends(get_current_user)):
    global RISK_SEQ
    score, decisao = calcular_score_e_decisao(req.identifier, req.identifier_type)
    consulta_id_raw = RISK_SEQ
    RISK_SEQ += 1
    consulta_id = gerar_consulta_id(consulta_id_raw)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    payload = {
        "consulta_id": consulta_id,
        "consulta_id_raw": consulta_id_raw,
        "score_final": score,
        "decisao": decisao,
        "timestamp": ts,
        "identifier": req.identifier,
        "identifier_type": req.identifier_type,
        "user": user.email,
    }
    LAST_RESULTS[consulta_id_raw] = payload
    return RiskCheckResponse(**payload)

# -------------------------------------------------------------------
# /api/report/{id} – PDF profissional
# -------------------------------------------------------------------
def _build_pdf(data: Dict[str, Any]) -> bytes:
    # ReportLab
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    W, H = A4

    # Header
    c.setFillColor(colors.HexColor("#0f172a"))
    c.rect(0, H-60, W, 60, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(20*mm, H-25, "Check Insurance Risk")
    c.setFont("Helvetica", 10)
    c.drawRightString(W-20*mm, H-25, f"Relatório de Risco — {data['consulta_id']}")

    # Bloco principal
    c.setFillColor(colors.black)
    y = H-90
    def line(lbl, val):
        nonlocal y
        c.setFont("Helvetica-Bold", 11)
        c.drawString(20*mm, y, str(lbl))
        c.setFont("Helvetica", 11)
        c.drawString(70*mm, y, str(val))
        y -= 12

    c.setFont("Helvetica-Bold", 13)
    c.drawString(20*mm, y, "Resumo da Consulta")
    y -= 14
    line("Consulta ID:", data["consulta_id"])
    line("Timestamp:",  data["timestamp"])
    line("Analista:",   data["user"])
    line("Identificador:", data["identifier"])
    line("Tipo:", data["identifier_type"])
    line("Score Final:", data["score_final"])
    line("Decisão:", data["decisao"])

    y -= 10
    c.setFont("Helvetica-Bold", 13)
    c.drawString(20*mm, y, "Notas de Conformidade")
    y -= 14
    notes = "Documentos internacionais (Passaporte/CR) são escalados automaticamente para Compliance."
    c.setFont("Helvetica", 10)
    for chunk in [notes[i:i+90] for i in range(0, len(notes), 90)]:
        c.drawString(20*mm, y, chunk); y -= 12

    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.gray)
    c.drawRightString(W-10*mm, 10*mm, "Gerado automaticamente — CheckInsuranceRisk")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

@app.get("/api/report/{consulta_id_raw}")
def get_report(consulta_id_raw: int, token: str):
    # token simples: e-mail do utilizador (igual ao access_token que enviamos)
    user = USERS.get((token or "").strip().lower())
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")

    data = LAST_RESULTS.get(consulta_id_raw)
    if not data:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    pdf_bytes = _build_pdf(data)
    headers = {"Content-Disposition": f'inline; filename="{data["consulta_id"]}.pdf"'}
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)

# -------------------------------------------------------------------
# ADMIN — Utilizadores
# -------------------------------------------------------------------
@app.post("/api/admin/user-add")
def admin_user_add(
    new_name: str = Form(...),
    new_email: str = Form(...),
    new_password: str = Form(...),
    new_role: str = Form("analyst"),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin")
    email = new_email.strip().lower()
    if email in USERS:
        raise HTTPException(status_code=409, detail="E-mail já existe")
    USERS[email] = User(new_name.strip(), email, new_password.strip(), new_role.strip())
    return {"status": "ok", "user": {"email": email, "name": new_name, "role": new_role}}

# -------------------------------------------------------------------
# ADMIN — Base de Risco (CRUD)
# -------------------------------------------------------------------
@app.post("/api/admin/risk-data/add-record")
def admin_risk_add_record(
    id: Optional[str] = Form(None),
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
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin")
    # update
    if id and str(id).strip().isdigit():
        rec_id = int(str(id).strip())
        for r in RISK_DATA:
            if r["id"] == rec_id:
                r.update({
                    "nome": nome, "nif": nif, "bi": bi, "passaporte": passaporte,
                    "cartao_residente": cartao_residente, "score_final": score_final,
                    "justificacao": justificacao, "pep_alert": pep_alert,
                    "sanctions_alert": sanctions_alert, "historico_pagamentos": historico_pagamentos,
                    "sinistros_total": sinistros_total, "sinistros_ult_12m": sinistros_ult_12m,
                    "fraude_suspeita": fraude_suspeita, "comentario_fraude": comentario_fraude,
                    "esg_score": esg_score, "country_risk": country_risk,
                    "credit_rating": credit_rating, "kyc_confidence": kyc_confidence,
                })
                return {"status": "updated", "id": rec_id}
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    # insert
    global RISK_SEQ
    rec_id = RISK_SEQ
    RISK_SEQ += 1
    rec = {
        "id": rec_id, "nome": nome, "nif": nif, "bi": bi, "passaporte": passaporte,
        "cartao_residente": cartao_residente, "score_final": score_final,
        "justificacao": justificacao, "pep_alert": pep_alert, "sanctions_alert": sanctions_alert,
        "historico_pagamentos": historico_pagamentos, "sinistros_total": sinistros_total,
        "sinistros_ult_12m": sinistros_ult_12m, "fraude_suspeita": fraude_suspeita,
        "comentario_fraude": comentario_fraude, "esg_score": esg_score, "country_risk": country_risk,
        "credit_rating": credit_rating, "kyc_confidence": kyc_confidence
    }
    RISK_DATA.append(rec)
    return {"status": "created", "id": rec_id}

@app.get("/api/admin/risk-data/list")
def admin_risk_list(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    return RISK_DATA

@app.post("/api/admin/risk-data/delete-record")
def admin_risk_delete_record(
    id: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin")
    if not id.strip().isdigit():
        raise HTTPException(status_code=400, detail="ID inválido")
    rec_id = int(id.strip())
    for i, r in enumerate(RISK_DATA):
        if r["id"] == rec_id:
            RISK_DATA.pop(i)
            return {"status": "deleted", "id": rec_id}
    raise HTTPException(status_code=404, detail="Registo não encontrado")

# -------------------------------------------------------------------
# ADMIN — Fontes de Informação
# -------------------------------------------------------------------
@app.post("/api/admin/info-sources/upload")
def admin_upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin")
    safe_name = file.filename.replace("..", ".").replace("/", "_")
    stored_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(stored_path, "wb") as f:
        f.write(file.file.read())
    return {"status": "ok", "stored_filename": safe_name}

@app.post("/api/admin/info-sources/create")
def admin_info_create(
    title: str = Form(...),
    description: str = Form(""),
    url: str = Form(""),
    directory: str = Form(""),
    filename: str = Form(""),
    categoria: str = Form(""),
    source_owner: str = Form(""),
    validade: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin")
    INFO_SOURCES.append({
        "title": title, "description": description, "url": url, "directory": directory,
        "filename": filename, "categoria": categoria, "source_owner": source_owner,
        "validade": validade
    })
    return {"status": "ok", "count": len(INFO_SOURCES)}

@app.get("/api/admin/info-sources/list")
def admin_info_list(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    return INFO_SOURCES

@app.post("/api/admin/info-sources/delete")
def admin_info_delete(
    index: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin")
    if not index.strip().isdigit():
        raise HTTPException(status_code=400, detail="Índice inválido")
    i = int(index.strip())
    if i < 0 or i >= len(INFO_SOURCES):
        raise HTTPException(status_code=404, detail="Não encontrado")
    INFO_SOURCES.pop(i)
    return {"status": "deleted", "index": i}
