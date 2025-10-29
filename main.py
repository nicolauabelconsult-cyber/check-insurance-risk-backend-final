from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
import itertools
import os
import shutil
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit

_user_id_counter = itertools.count(1)
_consulta_id_counter = itertools.count(100000)
_risk_id_counter = itertools.count(1)

def next_user_id():
    return next(_user_id_counter)

def next_consulta_id_raw() -> int:
    return next(_consulta_id_counter)

def format_consulta_id_display(raw_id: int) -> str:
    return f"CIR-{raw_id}"

def next_risk_id():
    return next(_risk_id_counter)

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
    if "analyst@checkrisk.com" not in USERS:
        USERS["analyst@checkrisk.com"] = User(
            id=next_user_id(),
            name="Analista Técnico",
            email="analyst@checkrisk.com",
            password="analyst123",
            role="analyst"
        )

bootstrap_admin()

CONSULTAS: Dict[int, Dict] = {}
RISK_DATA_STORE: List[Dict] = []
SOURCES_STORE: List[Dict] = []

os.makedirs("reports", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

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
    consulta_id_raw: int
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

def require_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")

app = FastAPI(
    title="Check Insurance Risk Backend (Consolidado)",
    version="1.2",
    description="Backend consolidado com área admin, geração de PDF profissional e suporte a passaporte/cartão de residente."
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
    tipo = body.identifier_type.strip().upper()
    ident = body.identifier.strip()

    score_final = 72
    decisao = "Aceitar Risco Técnico"
    justificacao = "Baseline técnico aplicado."
    pep_alert = False
    sanctions_alert = False
    benchmark = "Benchmarks internos e alertas PEP/Sanções UE/FMI."

    if tipo in ["PASSAPORTE", "CARTAO_RESIDENTE"]:
        score_final = 65
        decisao = "Escalar para Compliance"
        justificacao = "Documento de identificação internacional. Rever KYC manualmente."
        benchmark = "Sujeito a validação documental adicional."

    consulta_id_raw = next_consulta_id_raw()
    consulta_id_display = format_consulta_id_display(consulta_id_raw)
    ts = now_ts()

    CONSULTAS[consulta_id_raw] = {
        "consulta_id_raw": consulta_id_raw,
        "consulta_id_display": consulta_id_display,
        "timestamp": ts,
        "identifier": ident,
        "identifier_type": tipo,
        "score_final": score_final,
        "decisao": decisao,
        "justificacao": justificacao,
        "pep_alert": pep_alert,
        "sanctions_alert": sanctions_alert,
        "benchmark_internacional": benchmark,
    }

    return {
        "consulta_id": consulta_id_display,
        "consulta_id_raw": consulta_id_raw,
        "timestamp": ts,
        "score_final": score_final,
        "decisao": decisao,
        "justificacao": justificacao,
        "pep_alert": pep_alert,
        "sanctions_alert": sanctions_alert,
        "benchmark_internacional": benchmark,
    }

def draw_wrapped_line(c, text, x, y, max_width, leading=14, fontName="Helvetica", fontSize=10):
    c.setFont(fontName, fontSize)
    lines = simpleSplit(str(text), fontName, fontSize, max_width)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y

def generate_pdf(consulta_id_raw: int, data: Dict):
    pdf_path = os.path.join("reports", f"{consulta_id_raw}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4
    y = h - 50

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "CHECK INSURANCE RISK")
    y -= 16
    c.setFont("Helvetica", 10)
    y = draw_wrapped_line(c,
        "Motor de Compliance e Suporte Técnico de Subscrição",
        40, y, max_width=500, leading=14, fontName="Helvetica", fontSize=10)
    y -= 10

    c.line(40, y, w-40, y)
    y -= 20

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Dados da Consulta")
    y -= 18

    y = draw_wrapped_line(c, f"Consulta ID: {data.get('consulta_id_display','')}", 40, y, 500)
    y = draw_wrapped_line(c, f"ID Interno: {data.get('consulta_id_raw','')}", 40, y, 500)
    y = draw_wrapped_line(c, f"Data/Hora (UTC): {data.get('timestamp','')}", 40, y, 500)
    y = draw_wrapped_line(c, f"Identificador Analisado: {data.get('identifier','')}", 40, y, 500)
    y = draw_wrapped_line(c, f"Tipo de Identificador: {data.get('identifier_type','')}", 40, y, 500)
    y -= 10

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Resumo de Risco")
    y -= 18

    score_final = data.get("score_final", "")
    decisao = data.get("decisao", "")
    pep_alert = "SIM" if data.get("pep_alert") else "NÃO"
    sanc_alert = "SIM" if data.get("sanctions_alert") else "NÃO"

    y = draw_wrapped_line(c, f"Score Final: {score_final}/100", 40, y, 500)
    y = draw_wrapped_line(c, f"Decisão Recomendada: {decisao}", 40, y, 500)
    y = draw_wrapped_line(c, f"Alerta PEP / Exposição Política: {pep_alert}", 40, y, 500)
    y = draw_wrapped_line(c, f"Alerta Sanções Internacionais: {sanc_alert}", 40, y, 500)
    y -= 10

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Detalhes Técnicos")
    y -= 18

    justificacao = data.get("justificacao", "")
    benchmark = data.get("benchmark_internacional", "")

    y = draw_wrapped_line(c, f"Justificação Técnica: {justificacao}", 40, y, 500)
    y = draw_wrapped_line(c, f"Benchmark / Referência: {benchmark}", 40, y, 500)
    y -= 10

    match_hist = None
    for rec in RISK_DATA_STORE:
        if data.get("identifier") in [
            rec.get("nif",""),
            rec.get("bi",""),
            rec.get("passaporte",""),
            rec.get("cartao_residente",""),
            rec.get("nome",""),
        ]:
            match_hist = rec
            break

    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Histórico e Compliance Interno")
    y -= 14
    if match_hist:
        hist_pag = match_hist.get("historico_pagamentos", "Sem registo interno")
        sin_tot = match_hist.get("sinistros_total", "0")
        sin_12m = match_hist.get("sinistros_ult_12m", "0")
        fraude_flag = "SIM" if match_hist.get("fraude_suspeita") else "NÃO"
        fraude_com  = match_hist.get("comentario_fraude","")

        y = draw_wrapped_line(c, f"Pagamentos: {hist_pag}", 40, y, 500)
        y = draw_wrapped_line(c, f"Sinistros Totais: {sin_tot}", 40, y, 500)
        y = draw_wrapped_line(c, f"Sinistros Últimos 12 Meses: {sin_12m}", 40, y, 500)
        y = draw_wrapped_line(c, f"Fraude Suspeita: {fraude_flag}", 40, y, 500)
        if fraude_com:
            y = draw_wrapped_line(c, f"Nota Fraude: {fraude_com}", 40, y, 500)
    else:
        y = draw_wrapped_line(c, "Sem histórico interno associado a este identificador.", 40, y, 500)

    y -= 10

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Notas e Conformidade")
    y -= 18

    bloco_conf = (
        "Esta análise resulta da consolidação de fontes internas e externas "
        "autorizadas pela seguradora. O score técnico e a decisão recomendada "
        "servem como apoio à subscrição e compliance e não substituem a avaliação "
        "humana em casos de risco elevado, suspeita de fraude ou quando existam "
        "alertas PEP / sanções.

"
        "Assinatura técnica:
"
        "Check Insurance Risk — Motor de Compliance

"
        "CONFIDENCIAL • USO INTERNO"
    )
    y = draw_wrapped_line(c, bloco_conf, 40, y, 500)

    c.showPage()
    c.save()
    return pdf_path

@app.get("/api/report/{consulta_id_raw}")
def get_report(consulta_id_raw: int, token: str):
    user = USERS.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido")

    data = CONSULTAS.get(consulta_id_raw)
    if not data:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    pdf_path = os.path.join("reports", f"{consulta_id_raw}.pdf")
    if not os.path.exists(pdf_path):
        generate_pdf(consulta_id_raw, data)

    display_id = data.get("consulta_id_display", f"CIR-{consulta_id_raw}")
    filename = f"relatorio_{display_id}.pdf"

    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)

@app.post("/api/admin/user-add")
def admin_user_add(
    new_name: str = Form(""),
    new_email: str = Form(""),
    new_password: str = Form(""),
    new_role: str = Form("analyst"),
    current=Depends(get_current_user)
):
    require_admin(current)

    if not new_email.strip() or not new_password.strip() or not new_name.strip():
        raise HTTPException(status_code=422, detail="Campos obrigatórios em falta")

    if new_email in USERS:
        raise HTTPException(status_code=409, detail="Utilizador já existe")

    USERS[new_email] = User(
        id=next_user_id(),
        name=new_name.strip(),
        email=new_email.strip(),
        password=new_password.strip(),
        role=new_role.strip() or "analyst"
    )
    return {
        "status": "created",
        "user": {
            "id": USERS[new_email].id,
            "name": USERS[new_email].name,
            "email": USERS[new_email].email,
            "role": USERS[new_email].role,
        }
    }

def _as_int_or_default(v, default=0):
    v = (v or "").strip()
    return int(v) if v.isdigit() else default

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
    require_admin(current)

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
                    "pep_alert": (pep_alert == "1"),
                    "sanctions_alert": (sanctions_alert == "1"),
                    "historico_pagamentos": historico_pagamentos,
                    "sinistros_total": _as_int_or_default(sinistros_total, 0),
                    "sinistros_ult_12m": _as_int_or_default(sinistros_ult_12m, 0),
                    "fraude_suspeita": (fraude_suspeita == "1"),
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
        "pep_alert": (pep_alert == "1"),
        "sanctions_alert": (sanctions_alert == "1"),
        "historico_pagamentos": historico_pagamentos,
        "sinistros_total": _as_int_or_default(sinistros_total, 0),
        "sinistros_ult_12m": _as_int_or_default(sinistros_ult_12m, 0),
        "fraude_suspeita": (fraude_suspeita == "1"),
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
