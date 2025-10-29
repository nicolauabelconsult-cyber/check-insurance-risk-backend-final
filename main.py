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

# ============================================================================
# CONTADORES / HELPERS
# ============================================================================

_user_id_counter = itertools.count(1)
_consulta_id_counter = itertools.count(100000)  # base incremental
_risk_id_counter = itertools.count(1)

def next_user_id():
    return next(_user_id_counter)

def next_consulta_id_raw() -> int:
    return next(_consulta_id_counter)

def format_consulta_id_display(raw_id: int) -> str:
    # ex: 100123 -> "CIR-100123"
    return f"CIR-{raw_id}"

def next_risk_id():
    return next(_risk_id_counter)

def now_ts():
    # formato legível
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


# ============================================================================
# "BASE DE DADOS" EM MEMÓRIA
# ============================================================================

class User(BaseModel):
    id: int
    name: str
    email: str
    password: str
    role: str  # "admin", "analyst", ...

USERS: Dict[str, User] = {}

def bootstrap_admin():
    # utilizador admin inicial
    if "admin@checkrisk.com" not in USERS:
        USERS["admin@checkrisk.com"] = User(
            id=next_user_id(),
            name="Administrador",
            email="admin@checkrisk.com",
            password="admin123",
            role="admin"
        )
    # utilizador analista inicial
    if "analyst@checkrisk.com" not in USERS:
        USERS["analyst@checkrisk.com"] = User(
            id=next_user_id(),
            name="Analista Técnico",
            email="analyst@checkrisk.com",
            password="analyst123",
            role="analyst"
        )

bootstrap_admin()

# CONSULTAS guarda cada análise feita no dashboard
# chave = consulta_id_raw (int)   valor = dict
CONSULTAS: Dict[int, Dict] = {}

# Base manual de risco gravada na área admin
RISK_DATA_STORE: List[Dict] = []

# Fontes de informação gravadas na área admin
SOURCES_STORE: List[Dict] = []

# garantir pastas
os.makedirs("reports", exist_ok=True)
os.makedirs("uploads", exist_ok=True)


# ============================================================================
# MODELOS Pydantic
# ============================================================================

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    user_name: str
    role: str

class RiskCheckRequest(BaseModel):
    # NIF / BI / NOME / PASSAPORTE / CARTAO_RESIDENTE
    identifier: str
    identifier_type: str  # "NIF"|"BI"|"NOME"|"PASSAPORTE"|"CARTAO_RESIDENTE"

class RiskCheckResponse(BaseModel):
    consulta_id: str           # vamos devolver o "CIR-100123" como o utilizador vê
    consulta_id_raw: int       # ID simples interno
    timestamp: str
    score_final: int
    decisao: str
    justificacao: str
    pep_alert: bool
    sanctions_alert: bool
    benchmark_internacional: str


# ============================================================================
# AUTENTICAÇÃO
# ============================================================================

def get_current_user(authorization: Optional[str] = Header(None)):
    """
    O frontend guarda o access_token = email do user no localStorage (cir_token).
    Aqui validamos.
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


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Check Insurance Risk Backend (Consolidado)",
    version="1.2",
    description="Backend consolidado com área admin, geração de PDF profissional e suporte a passaporte/cartão de residente."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # em produção restringir
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# HEALTHCHECK
# ============================================================================

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ============================================================================
# LOGIN
# ============================================================================

@app.post("/api/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """
    index.html faz POST /api/login.
    Devolvemos access_token = email (cir_token), nome e role.
    """
    user = USERS.get(body.email)
    if not user or user.password != body.password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return LoginResponse(
        access_token=user.email,
        user_name=user.name,
        role=user.role
    )


# ============================================================================
# DASHBOARD: /api/risk-check
# ============================================================================

@app.post("/api/risk-check", response_model=RiskCheckResponse)
def risk_check(body: RiskCheckRequest, current=Depends(get_current_user)):
    """
    Recebe identificador + tipo.
    Gera um resultado técnico mock + guarda consulta.
    Dá tratamento especial se PASSAPORTE ou CARTAO_RESIDENTE:
      -> decisão 'Escalar para Compliance'
    """

    tipo = body.identifier_type.strip().upper()
    ident = body.identifier.strip()

    # baseline
    score_final = 72
    decisao = "Aceitar Risco Técnico"
    justificacao = "Baseline técnico aplicado."
    pep_alert = False
    sanctions_alert = False
    benchmark = "Benchmarks internos e alertas PEP/Sanções UE/FMI."

    # cenários que exigem revisão manual
    if tipo in ["PASSAPORTE", "CARTAO_RESIDENTE"]:
        score_final = 65
        decisao = "Escalar para Compliance"
        justificacao = "Documento de identificação internacional. Rever KYC manualmente."
        benchmark = "Sujeito a validação documental adicional."

    # gera ID interno simples
    consulta_id_raw = next_consulta_id_raw()
    consulta_id_display = format_consulta_id_display(consulta_id_raw)
    ts = now_ts()

    # guarda esta consulta em memória
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
        # informação adicional que pode ir para PDF
        # podemos mais tarde cruzar com RISK_DATA_STORE se quisermos enriquecer
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


# ============================================================================
# PDF REPORT
# ============================================================================

def draw_wrapped_line(c, text, x, y, max_width, leading=14, fontName="Helvetica", fontSize=10):
    """
    Utilitário: escreve texto multi-linha com word wrap básico.
    """
    c.setFont(fontName, fontSize)
    lines = simpleSplit(str(text), fontName, fontSize, max_width)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y

def generate_pdf(consulta_id_raw: int, data: Dict):
    """
    Gera um PDF mais profissional inspirado no modelo que partilhaste
    (blocos 'Dados da Consulta', 'Resumo de Risco', 'Detalhes Técnicos', 'Notas e Conformidade'). :contentReference[oaicite:2]{index=2}
    """
    pdf_path = os.path.join("reports", f"{consulta_id_raw}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4

    y = h - 50

    # Cabeçalho institucional
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "CHECK INSURANCE RISK")
    y -= 16
    c.setFont("Helvetica", 10)
    y = draw_wrapped_line(c,
        "Motor de Compliance e Suporte Técnico de Subscrição",
        40, y, max_width=500, leading=14, fontName="Helvetica", fontSize=10)
    y -= 10

    # Linha separadora
    c.line(40, y, w-40, y)
    y -= 20

    # --- DADOS DA CONSULTA ---
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Dados da Consulta")
    y -= 18

    y = draw_wrapped_line(c, f"Consulta ID: {data.get('consulta_id_display','')}", 40, y, 500)
    y = draw_wrapped_line(c, f"ID Interno: {data.get('consulta_id_raw','')}", 40, y, 500)
    y = draw_wrapped_line(c, f"Data/Hora (UTC): {data.get('timestamp','')}", 40, y, 500)
    y = draw_wrapped_line(c, f"Identificador Analisado: {data.get('identifier','')}", 40, y, 500)
    y = draw_wrapped_line(c, f"Tipo de Identificador: {data.get('identifier_type','')}", 40, y, 500)
    y -= 10

    # --- RESUMO DE RISCO ---
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

    # --- DETALHES TÉCNICOS ---
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Detalhes Técnicos")
    y -= 18

    justificacao = data.get("justificacao", "")
    benchmark = data.get("benchmark_internacional", "")

    y = draw_wrapped_line(c, f"Justificação Técnica: {justificacao}", 40, y, 500)
    y = draw_wrapped_line(c, f"Benchmark / Referência: {benchmark}", 40, y, 500)

    # espaço
    y -= 10

    # podemos enriquecer com histórico da base manual se existir match
    # tentativa simples: procurar na RISK_DATA_STORE quem coincide com o identificador
    match_hist = None
    for rec in RISK_DATA_STORE:
        # tentamos achar por NIF / BI / Passaporte / Cartão de Residente / Nome
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

    # --- NOTAS E CONFORMIDADE ---
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Notas e Conformidade")
    y -= 18

    bloco_conf = (
        "Esta análise resulta da consolidação de fontes internas e externas "
        "autorizadas pela seguradora. O score técnico e a decisão recomendada "
        "servem como apoio à subscrição e compliance e não substituem a avaliação "
        "humana em casos de risco elevado, suspeita de fraude ou quando existam "
        "alertas PEP / sanções.\n\n"
        "Assinatura técnica:\n"
        "Check Insurance Risk — Motor de Compliance\n\n"
        "CONFIDENCIAL • USO INTERNO"
    )
    y = draw_wrapped_line(c, bloco_conf, 40, y, 500)

    c.showPage()
    c.save()
    return pdf_path


@app.get("/api/report/{consulta_id_raw}")
def get_report(consulta_id_raw: int, token: str):
    """
    acesso.html chama:
      /api/report/{consulta_id_raw}?token={cir_token}

    Validamos token, puxamos dados, geramos PDF pro.
    """
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

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename
    )


# ============================================================================
# ÁREA ADMIN: UTILIZADORES
# ============================================================================

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


# ============================================================================
# ÁREA ADMIN: BASE DE RISCO MANUAL
# ============================================================================

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

    # Normalizar alguns campos numéricos
    def as_int_or_none(v):
        v = (v or "").strip()
        return int(v) if v.isdigit() else v

    if id and id.strip():
        # UPDATE
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
                    "sinistros_total": as_int_or_none(sinistros_total) or 0,
                    "sinistros_ult_12m": as_int_or_none(sinistros_ult_12m) or 0,
                    "fraude_suspeita": fraude_suspeita == "1",
                    "comentario_fraude": comentario_fraude,
                    "esg_score": esg_score,
                    "country_risk": country_risk,
                    "credit_rating": credit_rating,
                    "kyc_confidence": kyc_confidence,
                    "last_update": now_ts(),
                })
                return {"id": rec["id"], "status": "updated"}

    # CREATE NOVO
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
        "sinistros_total": as_int_or_none(sinistros_total) or 0,
        "sinistros_ult_12m": as_int_or_none(sinistros_ult_12m) or 0,
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


# ============================================================================
# ÁREA ADMIN: FONTES DE INFORMAÇÃO
# ============================================================================

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
