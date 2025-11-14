import os
import time
import datetime as dt
from typing import Optional, List

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    Query,
    Header,
    Request,
)
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
from ai_pipeline import build_facts_from_sources, rebuild_watchlist, is_pep_name
from extractors import run_extractor

# -----------------------------------------------------------------------------
# App & Middleware
# -----------------------------------------------------------------------------
app = FastAPI(title="Check Insurance Risk Backend", version="3.0.0")
app.add_middleware(SecurityHeadersMiddleware)

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# DB dependency
# -----------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Auth helpers (sem usar Depends(Request))
# -----------------------------------------------------------------------------
def _get_token_from_header(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1]


def _get_user_by_id(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency que obtém o utilizador atual com base no token JWT.
    NOTA: aqui NÃO usamos Request com Depends, apenas Header e DB.
    """
    token = _get_token_from_header(authorization)
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return _get_user_by_id(db, user_id)


# -----------------------------------------------------------------------------
# Startup
# -----------------------------------------------------------------------------
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_dir("data/uploads")
    ensure_dir("data/reports")


# -----------------------------------------------------------------------------
# Healthcheck
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": dt.datetime.utcnow().isoformat() + "Z"}


# -----------------------------------------------------------------------------
# Auth endpoints
# -----------------------------------------------------------------------------
@app.post("/auth/register", response_model=LoginResp)
def register(
    req: LoginReq,
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=req.username,
        password_hash=hash_pw(req.password),
        is_admin=req.is_admin or False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token({"sub": user.id, "username": user.username})
    log(db, actor=user.username, action="user_register", details=f"User {user.username} created")
    return LoginResp(access_token=token, token_type="bearer")


@app.post("/auth/login", response_model=LoginResp)
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_pw(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"sub": user.id, "username": user.username})
    log(db, actor=user.username, action="user_login", details="Successful login")
    return LoginResp(access_token=token, token_type="bearer")


@app.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "is_admin": current_user.is_admin,
    }


# -----------------------------------------------------------------------------
# InfoSource (fontes de informação)
# -----------------------------------------------------------------------------
@app.post("/infosources/upload")
async def upload_infosource(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    upload_dir = "data/uploads"
    ensure_dir(upload_dir)

    ts = int(time.time())
    filename = f"{ts}_{file.filename}"
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    # extrair registos (IA / extractors)
    num_records = run_extractor(filepath, db=db)

    src = InfoSource(
        name=name,
        description=description,
        file_path=filepath,
        num_records=num_records,
        uploaded_by_id=current_user.id,
    )
    db.add(src)
    db.commit()
    db.refresh(src)

    # reconstruir factos em memória
    build_facts_from_sources(db)

    log(
        db,
        actor=current_user.username,
        action="infosource_upload",
        details=f"Uploaded source {src.id} ({name}), records={num_records}",
    )

    return {"id": src.id, "name": src.name, "num_records": src.num_records}


@app.get("/infosources", response_model=List[dict])
def list_infosources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sources = db.query(InfoSource).order_by(InfoSource.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "num_records": s.num_records,
            "created_at": s.created_at.isoformat(),
        }
        for s in sources
    ]


# -----------------------------------------------------------------------------
# Consulta de risco / relatório
# -----------------------------------------------------------------------------
@app.post("/risk/check")
def risk_check(
    req: RiskCheckReq,
    generate_pdf: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Endpoint principal chamado pelo frontend ao clicar em 'Analisar Risco'.
    Pode, opcionalmente, devolver um PDF do relatório.
    """

    # Chama a pequena IA / motor de matching
    matches = build_facts_from_sources(db, query=req)  # assumindo que aceita RiskCheckReq
    pep_flag = any(is_pep_name(m["name"]) for m in matches)

    risk_score = 0
    if pep_flag:
        risk_score += 70
    risk_score += min(len(matches) * 5, 30)

    record = RiskRecord(
        analyst_id=current_user.id,
        full_name=req.full_name,
        nif=req.nif,
        passport=req.passport,
        residence_card=req.residence_card,
        risk_score=risk_score,
        is_pep=pep_flag,
        raw_matches=matches,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    log(
        db,
        actor=current_user.username,
        action="risk_check",
        details=f"Risk check {record.id} for {record.full_name} (score={risk_score})",
    )

    summary = {
        "id": record.id,
        "full_name": record.full_name,
        "nif": record.nif,
        "risk_score": record.risk_score,
        "is_pep": record.is_pep,
        "matches": matches,
        "created_at": record.created_at.isoformat(),
    }

    if not generate_pdf:
        return summary

    # gerar PDF
    pdf_path = render_pdf(record, matches)
    pdf_file = open(pdf_path, "rb")

    filename = f"relatorio_risco_{record.id}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(pdf_file, media_type="application/pdf", headers=headers)


# -----------------------------------------------------------------------------
# Dashboard / histórico
# -----------------------------------------------------------------------------
@app.get("/risk/history")
def risk_history(
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    qs = (
        db.query(RiskRecord)
        .order_by(RiskRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "full_name": r.full_name,
            "nif": r.nif,
            "risk_score": r.risk_score,
            "is_pep": r.is_pep,
            "created_at": r.created_at.isoformat(),
        }
        for r in qs
    ]


# -----------------------------------------------------------------------------
# Admin: logs & watchlist
# -----------------------------------------------------------------------------
@app.get("/admin/logs")
def get_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")

    entries = list_logs(db)
    return entries


@app.post("/admin/rebuild-watchlist")
def admin_rebuild_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")

    rebuild_watchlist(db)
    log(
        db,
        actor=current_user.username,
        action="rebuild_watchlist",
        details="Manual rebuild of watchlist",
    )
    return {"status": "ok"}


# -----------------------------------------------------------------------------
# Handler para erros genéricos
# -----------------------------------------------------------------------------
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # aqui usamos Request normalmente, SEM Depends
    # podes personalizar o log conforme a tua tabela de auditoria
    try:
        db = SessionLocal()
        log(db, actor="system", action="error", details=str(exc))
    except Exception:
        # evitar que um erro no log cause outro erro
        pass
    finally:
        try:
            db.close()
        except Exception:
            pass

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
