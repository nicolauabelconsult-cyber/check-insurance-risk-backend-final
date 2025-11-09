import os, datetime as dt, json, time
from typing import Optional

from watchlist import is_pep_name
from ai_pipeline import build_facts_from_sources  # << único import deste

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
from ai_pipeline import build_facts_from_sources

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

# ---------- DB bootstrap ----------
Base.metadata.create_all(bind=engine)

# Popular a watchlist PEP a partir das InfoSource existentes
with SessionLocal() as s:
    try:
        build_facts_from_sources(s)
    except Exception:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

with SessionLocal() as s:
    if s.query(User).count() == 0:
        s.add_all([
            User(name="Administrador", email="admin@checkrisk.com", password=hash_pw("admin123"), role="admin"),
            User(name="Analyst",       email="analyst@checkrisk.com", password=hash_pw("analyst123"), role="analyst"),
            User(name="Auditor",       email="auditor@checkrisk.com", password=hash_pw("auditor123"), role="auditor"),
        ])
        s.commit()

# ---------- Auth helper ----------
def bearer(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Cabeçalho Authorization inválido")
    token = authorization.split(" ", 1)[1]
    try:
        return decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

# ---------- Global error handler ----------
@app.exception_handler(Exception)
async def default_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Erro interno"})

# ---------- Health & meta ----------
@app.get("/")
def root():
    return {"ok": True, "service": "CIR Backend", "version": app.version}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/version")
def version():
    return {"service": "CIR Backend", "version": app.version}

# ---------- Auth ----------
@app.post("/api/login", response_model=LoginResp)
def login(req: LoginReq, db: Session = Depends(get_db), request: Request = None) -> LoginResp:
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_pw(req.password, user.password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    token = create_token(sub=str(user.id), name=user.name, role=user.role)
    ip = request.client.host if request else None
    log(str(user.id), "login", {"email": user.email, "ip": ip})
    return LoginResp(access_token=token, user_name=user.name, role=user.role)

@app.post("/api/auth/login", response_model=LoginResp)
def auth_login(payload: LoginReq, db: Session = Depends(get_db), request: Request = None) -> LoginResp:
    # Reutiliza a mesma lógica do /api/login
    return login(req=payload, db=db, request=request)

@app.post("/api/risk-check")
def risk_check(req: RiskCheckReq, payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    # Log
    log(payload.get("sub"), "risk-check", {"identifier": req.identifier, "type": req.identifier_type})

    # 1) Tenta registo interno
    rec = db.query(RiskRecord).filter(
        (RiskRecord.nif == req.identifier) |
        (RiskRecord.bi == req.identifier) |
        (RiskRecord.passaporte == req.identifier) |
        (RiskRecord.cartao_residente == req.identifier)
    ).first()

    # Fallbacks base
    base_score = 75
    pep = sanc = fraude = False
    justificacao = "Histórico limpo; critérios de KYC cumpridos."

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

    # 2) Sinal PEP por nome (watchlist em memória)
    if (req.identifier_type or "").strip().lower() in {"nome", "name"}:
        try:
            if is_pep_name(req.identifier):
                pep = True
                justificacao = f"{justificacao} | Nome coincide com PEP (watchlist)."
        except Exception:
            # não falha a request por causa da verificação de PEP
            pass

    # 3) Enriquecer com fontes (PEP/sanções, etc.)
    facts = build_facts_from_sources(
        identifier_value=req.identifier,
        identifier_type=req.identifier_type,
        db=db,
    ) or {}

    # Aplicar sinais encontrados
    if facts.get("pep", {}).get("value"):
        pep = True
        match_name = facts["pep"].get("matched_name")
        if match_name:
            justificacao = f"{justificacao} | IA: possível PEP ({match_name})."

    if facts.get("sanctions", {}).get("value"):
        sanc = True
        match_name = facts["sanctions"].get("matched_name")
        if match_name:
            justificacao = f"{justificacao} | IA: possível sanção ({match_name})."

    # 4) Decisão técnica
    decisao = "Aceitar com condições" if (base_score >= 75 and not (pep or sanc or fraude)) else "Escalar para revisão manual"
    consulta_id = f"CIR-{int(time.time())}"

    return {
        "consulta_id": consulta_id,
        "timestamp": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "identifier": req.identifier,
        "identifier_type": req.identifier_type,

        "score_final": base_score,
        "decisao": decisao,
        "justificacao": justificacao,

        "pep_alert": pep,
        "sanctions_alert": sanc,
        "fraude_suspeita": fraude,

        "benchmark_internacional": "OECD KYC Bench v1.2 / FATF rec. 10",

        # Campos do registo (quando existir)
        "nome": nome, "nif": nif, "bi": bi, "passaporte": passaporte, "cartao_residente": cartao_residente,
        "historico_pagamentos": historico_pagamentos,
        "sinistros_total": sinistros_total, "sinistros_ult_12m": sinistros_ult_12m,
        "comentario_fraude": comentario_fraude,
        "esg_score": esg_score, "country_risk": country_risk,
        "credit_rating": credit_rating, "kyc_confidence": kyc_confidence,

        # Estado das fontes para a UI
        "ai_status": facts.get("ai_status"),   # ok | no_match | no_data
        "ai_reason": facts.get("ai_reason"),   # explicação humana
        "ai_facts": {
            "pep": facts.get("pep"),
            "sanctions": facts.get("sanctions"),
        },
    }

# ---------- Report (PDF) ----------
@app.get("/api/report/{consulta_id}", response_class=StreamingResponse)
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
        raise HTTPException(status_code=401, detail="Token ausente")

    meta = {
        "consulta_id": consulta_id,
        "timestamp": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "identifier": "—",
        "identifier_type": "—",
        "score_final": 80,
        "decisao": "Aceitar com condições",
        "justificacao": "Parâmetros técnicos dentro do apetite de risco. Monitorizar 6-12 meses.",
        "pep_alert": False,
        "sanctions_alert": False,
        "benchmark_internacional": "OECD KYC Bench v1.2 / FATF rec. 10",
    }

    ensure_dir("reports")
    pdf_path = f"reports/{consulta_id}.pdf"
    render_pdf(pdf_path, meta)

    def it():
        with open(pdf_path, "rb") as f:
            while True:
                ch = f.read(8192)
                if not ch:
                    break
                yield ch

    return StreamingResponse(
        it(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="relatorio_{consulta_id}.pdf"'},
    )

# ---------- Admin: Users ----------
@app.post("/api/admin/user-add")
def admin_user_add(
    new_name: str = Form(...),
    new_email: str = Form(...),
    new_password: str = Form(...),
    new_role: str = Form("analyst"),
    payload: dict = Depends(bearer),
    db: Session = Depends(get_db),
):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores")
    if db.query(User).filter(User.email == new_email).first():
        raise HTTPException(status_code=400, detail="Email já existe")

    u = User(name=new_name, email=new_email, password=hash_pw(new_password), role=new_role)
    db.add(u)
    db.commit()
    db.refresh(u)
    log(payload.get("sub"), "user-add", {"user": u.email})
    return {"status": "ok", "user": {"id": u.id, "email": u.email, "role": u.role}}

# ---------- Admin: Risk Data ----------
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

    pep_bool = (str(pep_alert).lower() in ("1", "true", "yes", "sim"))
    sanc_bool = (str(sanctions_alert).lower() in ("1", "true", "yes", "sim"))
    fraude_bool = (str(fraude_suspeita).lower() in ("1", "true", "yes", "sim"))

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
def admin_risk_delete(id: int = Form(...), payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores")
    rec = db.query(RiskRecord).filter(RiskRecord.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Registo inexistente")
    db.delete(rec)
    db.commit()
    log(payload.get("sub"), "risk-delete", {"id": id})
    return {"status": "deleted"}

# ---------- Admin: Info Sources ----------
@app.post("/api/admin/info-sources/upload")
def info_source_upload(file: UploadFile = File(...), payload: dict = Depends(bearer)):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores")
    ensure_dir("uploads")
    fname = file.filename
    base, ext = os.path.splitext(fname)
    path = os.path.join("uploads", fname)
    i = 1
    while os.path.exists(path):
        fname = f"{base}_{i}{ext}"
        path = os.path.join("uploads", fname)
        i += 1
    with open(path, "wb") as f:
        f.write(file.file.read())
    return {"stored_filename": fname}

@app.post("/api/admin/info-sources/create")
def info_source_create(
    title: str = Form(...),
    description: str = Form(...),
    url: str = Form(None),
    directory: str = Form(None),
    filename: str = Form(None),
    categoria: str = Form(None),
    source_owner: str = Form(None),
    validade: str = Form(None),
    payload: dict = Depends(bearer),
    db: Session = Depends(get_db),
):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores")

    item = InfoSource(
        title=title,
        description=description,
        url=url,
        directory=directory,
        filename=filename,
        categoria=categoria,
        source_owner=source_owner,
        validade=validade,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    log(payload.get("sub"), "source-create", {"id": item.id})

    # 🔁 Recarrega as fontes e atualiza watchlist PEP
    try:
        from ai_pipeline import build_facts_from_sources
        build_facts_from_sources(db=db, identifier_value="", identifier_type="")
    except Exception as e:
        print("⚠️ Erro ao atualizar fontes:", e)

    return {"status": "ok", "id": item.id}

@app.get("/api/admin/info-sources/list")
def info_source_list(payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="Apenas administradores/auditores")
    rows = db.query(InfoSource).order_by(InfoSource.id.desc()).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "url": r.url,
            "directory": r.directory,
            "filename": r.filename,
            "categoria": r.categoria,
            "source_owner": r.source_owner,
            "validade": r.validade,
            "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
        }
        for r in rows
    ]

@app.post("/api/admin/info-sources/delete")
def info_source_delete(
    id: int = Form(...),
    payload: dict = Depends(bearer),
    db: Session = Depends(get_db),
):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas administradores")

    item = db.query(InfoSource).filter(InfoSource.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fonte inexistente")

    db.delete(item)
    db.commit()
    log(payload.get("sub"), "source-delete", {"id": id})

    # refresca a watchlist/IA a partir das fontes atuais
    try:
        build_facts_from_sources(db)
    except Exception:
        pass

    return {"status": "deleted"}

# ---------- Auditoria ----------
@app.get("/api/admin/audit/list")
def audit_list(payload: dict = Depends(bearer)):
    if payload.get("role") not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="Apenas administradores/auditores")
    return list_logs()

@app.get("/api/ai/test-source")
def ai_test_source(id: int, payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="Apenas administradores/auditores")
    src = db.query(InfoSource).filter(InfoSource.id == id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Fonte inexistente")

    # usa 'categoria' como 'kind'
    kind = (src.categoria or "").strip().lower()
    if not kind:
        return {"count": 0, "sample": [], "message": "A categoria (kind) da fonte não foi definida."}

    from extractors import run_extractor
    url_or_path = src.url or (f"{src.directory.rstrip('/')}/{src.filename.lstrip('/')}" if src.directory and src.filename else None)
    if not url_or_path:
        return {"count": 0, "sample": [], "message": "Fonte sem URL nem ficheiro associado."}

    facts = run_extractor(kind, url_or_path, hint=src.validade)
    return {"count": len(facts), "sample": facts[:20]}

