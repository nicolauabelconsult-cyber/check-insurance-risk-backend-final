import os
import time
import datetime as dt
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from database import Base, engine, SessionLocal
from models import User, RiskRecord, InfoSource
from auth import create_token, decode_token, hash_pw, verify_pw
from schemas import LoginReq, LoginResp, RiskCheckReq
from utils import ensure_dir, render_pdf
from security import SecurityHeadersMiddleware
from audit import log, list_logs

# IA / Extractors
from ai_pipeline import build_facts_from_sources, rebuild_watchlist, is_pep_name

# -----------------------------------------------------------------------------
# App & CORS
# -----------------------------------------------------------------------------
app = FastAPI(title="Check Insurance Risk Backend", version="3.0.0")
app.add_middleware(SecurityHeadersMiddleware)

ALLOWED_ORIGINS = [
    "https://checkinsurancerisk.com",
    "https://checkinsurancerisk.netlify.app",
    "http://localhost:5173",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if os.getenv("FRONTEND_ORIGIN") is None else [os.getenv("FRONTEND_ORIGIN")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# DB bootstrap
# -----------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

@app.on_event("startup")
def _startup_build_watchlist():
    \"\"\"Reconstrói a watchlist a partir das fontes na base (não falha o arranque).\"\"\"
    try:
        with SessionLocal() as s:
            rebuild_watchlist(s)
    except Exception:
        # Se falhar, continua — o scraping é on-demand no risk-check
        pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Seed users
with SessionLocal() as s:
    if s.query(User).count() == 0:
        s.add_all([
            User(name="Administrador", email="admin@checkrisk.com",  password=hash_pw("admin123"), role="admin"),
            User(name="Analyst",       email="analyst@checkrisk.com",password=hash_pw("analyst123"), role="analyst"),
            User(name="Auditor",       email="auditor@checkrisk.com",password=hash_pw("auditor123"), role="auditor"),
        ])
        s.commit()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def bearer(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Cabeçalho Authorization inválido")
    token = authorization.split(" ", 1)[1]
    try:
        return decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

@app.exception_handler(Exception)
async def default_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={\"detail\": \"Erro interno\"})

# -----------------------------------------------------------------------------
# Health & meta
# -----------------------------------------------------------------------------
@app.get(\"/\")
def root():
    return {\"ok\": True, \"service\": \"CIR Backend\", \"version\": app.version}

@app.get(\"/health\")
def health():
    return {\"status\": \"ok\"}

@app.get(\"/version\")
def version():
    return {\"service\": \"CIR Backend\", \"version\": app.version}

# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
@app.post(\"/api/login\", response_model=LoginResp)
def login(req: LoginReq, db: Session = Depends(get_db), request: Request = None) -> LoginResp:
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_pw(req.password, user.password):
        raise HTTPException(status_code=401, detail=\"Credenciais inválidas\")
    token = create_token(sub=str(user.id), name=user.name, role=user.role)
    ip = request.client.host if request else None
    log(str(user.id), \"login\", {\"email\": user.email, \"ip\": ip})
    return LoginResp(access_token=token, user_name=user.name, role=user.role)

@app.post(\"/api/auth/login\", response_model=LoginResp)
def auth_login(payload: LoginReq, db: Session = Depends(get_db), request: Request = None) -> LoginResp:
    return login(req=payload, db=db, request=request)

# -----------------------------------------------------------------------------
# Core: Risk Check
# -----------------------------------------------------------------------------
@app.post(\"/api/risk-check\")
def risk_check(req: RiskCheckReq, payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    log(payload.get(\"sub\"), \"risk-check\", {\"identifier\": req.identifier, \"type\": req.identifier_type})

    # 1) dados internos (se existirem)
    rec = db.query(RiskRecord).filter(
        (RiskRecord.nif == req.identifier) |
        (RiskRecord.bi == req.identifier) |
        (RiskRecord.passaporte == req.identifier) |
        (RiskRecord.cartao_residente == req.identifier)
    ).first()

    base_score = 75
    pep = sanc = fraude = False
    justificacao = \"Histórico limpo; critérios de KYC cumpridos.\"

    nome = nif = bi = passaporte = cartao_residente = None
    historico_pagamentos = sinistros_total = sinistros_ult_12m = comentario_fraude = None
    esg_score = country_risk = credit_rating = kyc_confidence = None

    if rec:
        base_score = rec.score_final or base_score
        pep = bool(rec.pep_alert)
        sanc = bool(rec.sanctions_alert)
        fraude = bool(rec.fraude_suspeita)
        justificacao = rec.justificacao or justificacao
        nome = rec.nome
        nif = rec.nif
        bi = rec.bi
        passaporte = rec.passaporte
        cartao_residente = rec.cartao_residente
        historico_pagamentos = rec.historico_pagamentos
        sinistros_total = rec.sinistros_total
        sinistros_ult_12m = rec.sinistros_ult_12m
        comentario_fraude = rec.comentario_fraude
        esg_score = rec.esg_score
        country_risk = rec.country_risk
        credit_rating = rec.credit_rating
        kyc_confidence = rec.kyc_confidence

    # 2) IA / Fontes (on-demand, a partir das InfoSource)
    facts = build_facts_from_sources(
        identifier_value=req.identifier,
        identifier_type=req.identifier_type,
        db=db,
    )

    # 2.1) heurística por nome (watchlist já montada)
    try:
        if (req.identifier_type or \"\").strip().lower() in {\"nome\", \"name\"} and is_pep_name(req.identifier):
            pep = True
            justificacao = f\"{justificacao} | Watchlist indica possível PEP por nome.\"
    except Exception:
        pass

    # 2.2) Sinais do scraping
    if facts.get(\"pep\", {}).get(\"value\"):
        pep = True
        m = facts[\"pep\"]
        try:
            justificacao = (
                f\"{justificacao} | IA: possível PEP "
                f"({m.get('matched_name') or '—'}"
                f\"{' – ' + m.get('cargo') if m.get('cargo') else ''}, "
                f\"fonte {m.get('source') or '—'}, score {m.get('score') if m.get('score') is not None else '—'}).\"
            )
        except Exception:
            pass

    if facts.get(\"sanctions\", {}).get(\"value\"):
        sanc = True
        # (quando tiveres detalhes, podes enriquecer a justificativa aqui)

    # 3) Decisão técnica
    decisao = \"Aceitar com condições\" if (base_score >= 75 and not (pep or sanc or fraude)) else \"Escalar para revisão manual\"
    consulta_id = f\"CIR-{int(time.time())}\"

    return {
        \"consulta_id\": consulta_id,
        \"timestamp\": dt.datetime.utcnow().strftime(\"%Y-%m-%d %H:%M:%S UTC\"),
        \"identifier\": req.identifier,
        \"identifier_type\": req.identifier_type,
        \"score_final\": base_score,
        \"decisao\": decisao,
        \"justificacao\": justificacao,
        \"pep_alert\": pep,
        \"sanctions_alert\": sanc,
        \"fraude_suspeita\": fraude,
        \"benchmark_internacional\": \"OECD KYC Bench v1.2 / FATF rec. 10\",
        \"nome\": nome, \"nif\": nif, \"bi\": bi, \"passaporte\": passaporte, \"cartao_residente\": cartao_residente,
        \"historico_pagamentos\": historico_pagamentos,
        \"sinistros_total\": sinistros_total, \"sinistros_ult_12m\": sinistros_ult_12m,
        \"comentario_fraude\": comentario_fraude,
        \"esg_score\": esg_score, \"country_risk\": country_risk,
        \"credit_rating\": credit_rating, \"kyc_confidence\": kyc_confidence,
        \"ai_status\": facts.get(\"ai_status\"),
        \"ai_reason\": facts.get(\"ai_reason\"),
        \"ai_facts\": {\"pep\": facts.get(\"pep\"), \"sanctions\": facts.get(\"sanctions\")},
    }

# -----------------------------------------------------------------------------
# Report (PDF)
# -----------------------------------------------------------------------------
@app.get(\"/api/report/{consulta_id}\", response_class=StreamingResponse)
def get_report(
    consulta_id: str,
    token: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if token:
        decode_token(token)
    elif authorization:
        bearer(authorization)
    else:
        raise HTTPException(status_code=401, detail=\"Token ausente\")


    meta = {
        \"consulta_id\": consulta_id,
        \"timestamp\": dt.datetime.utcnow().strftime(\"%Y-%m-%d %H:%M:%S UTC\"),
        \"identifier\": \"—\",
        \"identifier_type\": \"—\",
        \"score_final\": 80,
        \"decisao\": \"Aceitar com condições\",
        \"justificacao\": \"Parâmetros técnicos dentro do apetite de risco. Monitorizar 6-12 meses.\",
        \"pep_alert\": False,
        \"sanctions_alert\": False,
        \"benchmark_internacional\": \"OECD KYC Bench v1.2 / FATF rec. 10\",
    }

    ensure_dir(\"reports\")
    pdf_path = f\"reports/{consulta_id}.pdf\"
    render_pdf(pdf_path, meta)

    def it():
        with open(pdf_path, \"rb\") as f:
            while True:
                ch = f.read(8192)
                if not ch:
                    break
                yield ch

    return StreamingResponse(
        it(),
        media_type=\"application/pdf\",
        headers={\"Content-Disposition\": f'inline; filename=\"relatorio_{consulta_id}.pdf\"'},
    )

# -----------------------------------------------------------------------------
# Admin: Users
# -----------------------------------------------------------------------------
@app.post(\"/api/admin/user-add\")
def admin_user_add(
    new_name: str = Form(...),
    new_email: str = Form(...),
    new_password: str = Form(...),
    new_role: str = Form(\"analyst\"),
    payload: dict = Depends(bearer),
    db: Session = Depends(get_db),
):
    if payload.get(\"role\") != \"admin\":
        raise HTTPException(status_code=403, detail=\"Apenas administradores\")
    if db.query(User).filter(User.email == new_email).first():
        raise HTTPException(status_code=400, detail=\"Email já existe\")


    u = User(name=new_name, email=new_email, password=hash_pw(new_password), role=new_role)
    db.add(u)
    db.commit()
    db.refresh(u)
    log(payload.get(\"sub\"), \"user-add\", {\"user\": u.email})
    return {\"status\": \"ok\", \"user\": {\"id\": u.id, \"email\": u.email, \"role\": u.role}}

# -----------------------------------------------------------------------------
# Admin: Risk Data
# -----------------------------------------------------------------------------
@app.post("/api/admin/risk-data/add-record")
def admin_risk_add_record(
    id: str = Form(None),
    nome: str = Form(None),
    nif: str = Form(None),
    bi: str = Form(None),
    passaporte: str = Form(None),
    cartao_residente: str = Form(None),
    score_final: int = Form(0),
    justificacao: str = Form(None),
    pep_alert: str = Form("0"),
    sanctions_alert: str = Form("0"),
    historico_pagamentos: str = Form(None),
    sinistros_total: int = Form(0),
    sinistros_ult_12m: int = Form(0),
    fraude_suspeita: str = Form("0"),
    comentario_fraude: str = Form(None),
    esg_score: int = Form(0),
    country_risk: str = Form(None),
    credit_rating: str = Form(None),
    kyc_confidence: str = Form(None),
    payload: dict = Depends(bearer),
    db: Session = Depends(get_db),
):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores")

    pep_bool = str(pep_alert).lower() in ("1", "true", "yes", "sim")
    sanc_bool = str(sanctions_alert).lower() in ("1", "true", "yes", "sim")
    fraude_bool = str(fraude_suspeita).lower() in ("1", "true", "yes", "sim")

    if id:
        rec = db.query(RiskRecord).filter(RiskRecord.id == int(id)).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Registo inexistente")
    else:
        rec = RiskRecord()

    for k, v in dict(
        nome=nome,
        nif=nif,
        bi=bi,
        passaporte=passaporte,
        cartao_residente=cartao_residente,
        score_final=score_final,
        justificacao=justificacao,
        pep_alert=pep_bool,
        sanctions_alert=sanc_bool,
        historico_pagamentos=historico_pagamentos,
        sinistros_total=sinistros_total,
        sinistros_ult_12m=sinistros_ult_12m,
        fraude_suspeita=fraude_bool,
        comentario_fraude=comentario_fraude,
        esg_score=esg_score,
        country_risk=country_risk,
        credit_rating=credit_rating,
        kyc_confidence=kyc_confidence,
    ).items():
        setattr(rec, k, v)

    db.add(rec)
    db.commit()
    db.refresh(rec)
    log(payload.get("sub"), "risk-save", {"id": rec.id})
    return {"status": "saved", "id": rec.id}


@app.get("/api/admin/risk-data/list")
def admin_risk_list(payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="Apenas administradores/auditores")

    rows = db.query(RiskRecord).order_by(RiskRecord.id.desc()).all()

    def ser(r: RiskRecord):
        return {
            "id": r.id,
            "nome": r.nome,
            "nif": r.nif,
            "bi": r.bi,
            "passaporte": r.passaporte,
            "cartao_residente": r.cartao_residente,
            "score_final": r.score_final,
            "justificacao": r.justificacao,
            "pep_alert": r.pep_alert,
            "sanctions_alert": r.sanctions_alert,
            "historico_pagamentos": r.historico_pagamentos,
            "sinistros_total": r.sinistros_total,
            "sinistros_ult_12m": r.sinistros_ult_12m,
            "fraude_suspeita": r.fraude_suspeita,
            "comentario_fraude": r.comentario_fraude,
            "esg_score": r.esg_score,
            "country_risk": r.country_risk,
            "credit_rating": r.credit_rating,
            "kyc_confidence": r.kyc_confidence,
        }

    return [ser(r) for r in rows]


@app.post("/api/admin/risk-data/delete-record")
def admin_risk_delete(
    id: int = Form(...),
    payload: dict = Depends(bearer),
    db: Session = Depends(get_db),
):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores")

    rec = db.query(RiskRecord).filter(RiskRecord.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Registo inexistente")

    db.delete(rec)
    db.commit()
    log(payload.get("sub"), "risk-delete", {"id": id})
    return {"status": "deleted"}
