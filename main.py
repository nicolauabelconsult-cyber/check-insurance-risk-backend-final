# main.py
import os
import csv
import json
import difflib
from typing import List, Optional, Tuple

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    Query,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import Base, engine
from models import User, InfoSource, NormalizedEntity, RiskRecord, AuditLog
from schemas import (
    LoginRequest,
    LoginResponse,
    UserCreate,
    UserRead,
    RiskCheckRequest,
    RiskCheckResponse,
    Match,
    RiskFactor,
    RiskHistoryItem,
    InfoSourceRead,
    AuditLogRead,
)
from security import (
    get_db,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_admin,
)
from reporting import build_risk_report_pdf
from utils import ensure_dir


# Criar tabelas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Check Insurance Risk Backend", version="1.0.0")


# ---------------------- CORS ----------------------
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------- Utilidades ----------------------

def log_event(
    db: Session,
    action: str,
    user: Optional[User] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    log = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        details=details,
        ip_address=ip_address,
    )
    db.add(log)
    db.commit()


@app.on_event("startup")
def create_initial_admin():
    """
    Cria um utilizador admin inicial (username=admin / password=admin123)
    se ainda não existir. Depois podes alterar pelo módulo de utilizadores.
    """
    db = Session(bind=engine)
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if not existing:
            user = User(
                username="admin",
                full_name="Administrador",
                password_hash=hash_password("admin123"),
                is_admin=True,
                is_active=True,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------- Auth ----------------------

@app.post("/auth/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    token = create_access_token({"sub": user.id})
    ip = request.client.host if request and request.client else None
    log_event(db, "login", user=user, details="Login bem sucedido", ip_address=ip)
    return LoginResponse(access_token=token)


@app.get("/auth/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------- Gestão de utilizadores (Admin) ----------------------

@app.post("/admin/users", response_model=UserRead)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    request: Request = None,
):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username já existe")

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    ip = request.client.host if request and request.client else None
    log_event(db, "create_user", user=admin, details=f"Criou user {user.username}", ip_address=ip)
    return user


@app.get("/admin/users", response_model=List[UserRead])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    return db.query(User).order_by(User.created_at.desc()).all()


@app.patch("/admin/users/{user_id}/status", response_model=UserRead)
def update_user_status(
    user_id: int,
    is_active: bool = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    request: Request = None,
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")

    user.is_active = is_active
    db.commit()
    db.refresh(user)
    ip = request.client.host if request and request.client else None
    log_event(
        db,
        "update_user_status",
        user=admin,
        details=f"Alterou estado de {user.username} para is_active={is_active}",
        ip_address=ip,
    )
    return user


@app.patch("/admin/users/{user_id}/password", response_model=UserRead)
def reset_user_password(
    user_id: int,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    request: Request = None,
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")

    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    ip = request.client.host if request and request.client else None
    log_event(
        db,
        "reset_user_password",
        user=admin,
        details=f"Reset password de {user.username}",
        ip_address=ip,
    )
    return user


# ---------------------- Upload e gestão de fontes ----------------------

UPLOAD_DIR = "data/uploads"
ensure_dir(UPLOAD_DIR)


def guess_mapping(headers: List[str]) -> dict:
    """
    Faz uma tentativa simples de mapear colunas por nome.
    Podes sempre enviar mapping_json explícito no upload.
    """
    lower_headers = {h.lower(): h for h in headers}
    mapping = {}

    # Nome
    for key in ["nome", "name", "full_name", "nome_completo"]:
        if key in lower_headers:
            mapping["name"] = lower_headers[key]
            break

    # NIF
    for key in ["nif", "nif_cliente", "tax_id"]:
        if key in lower_headers:
            mapping["nif"] = lower_headers[key]
            break

    # Passaporte
    for key in ["passaporte", "passport"]:
        if key in lower_headers:
            mapping["passport"] = lower_headers[key]
            break

    # Cartão de residente
    for key in ["cartao_residente", "residence_card", "cartao_residencia"]:
        if key in lower_headers:
            mapping["residence_card"] = lower_headers[key]
            break

    # Cargo / função
    for key in ["cargo", "funcao", "role", "position"]:
        if key in lower_headers:
            mapping["role"] = lower_headers[key]
            break

    # País
    for key in ["pais", "country"]:
        if key in lower_headers:
            mapping["country"] = lower_headers[key]
            break

    return mapping


@app.post("/infosources/upload", response_model=InfoSourceRead)
async def upload_infosource(
    name: str = Form(...),
    source_type: str = Form(...),  # PEP, SANCTIONS, FRAUD, CLAIMS, OTHER
    description: str = Form(""),
    file: UploadFile = File(...),
    mapping_json: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Apenas ficheiros CSV são suportados nesta versão.")

    # Guardar ficheiro
    ensure_dir(UPLOAD_DIR)
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Ler cabeçalho e linhas
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if not headers:
            raise HTTPException(status_code=400, detail="CSV sem cabeçalho.")

        # Determinar mapping
        if mapping_json:
            mapping = json.loads(mapping_json)
        else:
            mapping = guess_mapping(headers)

        if "name" not in mapping:
            raise HTTPException(
                status_code=400,
                detail="Não foi possível identificar a coluna do nome. Envia mapping_json explícito.",
            )

        # Criar InfoSource
        src = InfoSource(
            name=name,
            source_type=source_type.upper(),
            description=description,
            file_path=file_path,
            uploaded_by_id=current_user.id,
        )
        db.add(src)
        db.commit()
        db.refresh(src)

        # Inserir NormalizedEntity
        num_records = 0
        for row in reader:
            person_name = row.get(mapping.get("name", ""), "") or None
            person_nif = row.get(mapping.get("nif", ""), "") or None if mapping.get("nif") else None
            person_passport = row.get(mapping.get("passport", ""), "") or None if mapping.get("passport") else None
            residence_card = row.get(mapping.get("residence_card", ""), "") or None if mapping.get("residence_card") else None
            role = row.get(mapping.get("role", ""), "") or None if mapping.get("role") else None
            country = row.get(mapping.get("country", ""), "") or None if mapping.get("country") else None

            if not any([person_name, person_nif, person_passport, residence_card]):
                continue

            entity = NormalizedEntity(
                source_id=src.id,
                person_name=person_name,
                person_nif=person_nif,
                person_passport=person_passport,
                residence_card=residence_card,
                role=role,
                country=country,
                raw_payload=row,
            )
            db.add(entity)
            num_records += 1

        src.num_records = num_records
        db.commit()
        db.refresh(src)

    ip = request.client.host if request and request.client else None
    log_event(
        db,
        "upload_infosource",
        user=current_user,
        details=f"Fonte {src.name} ({src.source_type}) com {src.num_records} registos",
        ip_address=ip,
    )

    return src


@app.get("/infosources", response_model=List[InfoSourceRead])
def list_infosources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(InfoSource).order_by(InfoSource.created_at.desc()).all()


# ---------------------- Lógica de matching e risco ----------------------

def find_matches(
    db: Session,
    req: RiskCheckRequest,
) -> List[Match]:
    """
    Procura matches nas entidades normalizadas,
    usando NIF, passaporte, cartão e nome.
    """
    matches: List[Match] = []

    q = db.query(NormalizedEntity, InfoSource).join(InfoSource, NormalizedEntity.source_id == InfoSource.id)

    # Se tiver NIF, tentamos primeiro por NIF
    if req.nif:
        candidates = (
            q.filter(func.lower(NormalizedEntity.person_nif) == req.nif.lower())
            .limit(100)
            .all()
        )
    elif req.passport:
        candidates = (
            q.filter(func.lower(NormalizedEntity.person_passport) == req.passport.lower())
            .limit(100)
            .all()
        )
    elif req.residence_card:
        candidates = (
            q.filter(func.lower(NormalizedEntity.residence_card) == req.residence_card.lower())
            .limit(100)
            .all()
        )
    else:
        # Pesquisa por nome aproximado
        name = req.full_name.strip().upper()
        candidates = (
            q.filter(func.upper(NormalizedEntity.person_name).like(f"%{name}%"))
            .limit(100)
            .all()
        )

    def sim(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, (a or "").upper(), (b or "").upper()).ratio()

    for entity, src in candidates:
        similarity = sim(req.full_name, entity.person_name or "")
        # Se estivermos por NIF/passaporte, aceitamos tudo; se for só nome, impomos threshold
        if not any([req.nif, req.passport, req.residence_card]) and similarity < 0.6:
            continue

        identifier = entity.person_nif or entity.person_passport or entity.residence_card or None

        matches.append(
            Match(
                source_id=src.id,
                source_name=src.name,
                source_type=src.source_type,
                match_name=entity.person_name or "",
                match_identifier=identifier,
                similarity=similarity,
                details={
                    "role": entity.role,
                    "country": entity.country,
                },
            )
        )

    return matches


def compute_risk_from_matches(
    req: RiskCheckRequest,
    matches: List[Match],
) -> Tuple[int, str, bool, bool, List[RiskFactor]]:
    factors: List[RiskFactor] = []
    score = 0
    is_pep = False
    has_sanctions = False

    # Regras baseadas nas fontes
    for m in matches:
        st = (m.source_type or "").upper()
        if st == "PEP":
            is_pep = True
            factors.append(RiskFactor(code="PEP", description="Presença em lista PEP", weight=70))
            score += 70
        elif st == "SANCTIONS":
            has_sanctions = True
            factors.append(RiskFactor(code="SANCTIONS", description="Presença em lista de sanções", weight=100))
            score += 100
        elif st == "FRAUD":
            factors.append(RiskFactor(code="FRAUD", description="Registo em base interna de fraude", weight=60))
            score += 60
        elif st == "CLAIMS":
            factors.append(RiskFactor(code="CLAIMS", description="Histórico de sinistros relevante", weight=30))
            score += 30

    # Penalização leve se não houver NIF
    if not req.nif:
        factors.append(RiskFactor(code="NO_NIF", description="NIF não fornecido", weight=10))
        score += 10

    # Se não há matches negativos e há identificação completa, risco baixo
    if score == 0 and req.nif:
        factors.append(RiskFactor(code="CLEAN", description="Sem ocorrências negativas nas fontes", weight=0))

    # Normalizar score (0-100)
    score = max(0, min(score, 100))

    if score <= 30:
        level = "LOW"
    elif score <= 60:
        level = "MEDIUM"
    elif score <= 85:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return score, level, is_pep, has_sanctions, factors


# ---------------------- Análise de risco ----------------------

@app.post("/risk/check", response_model=RiskCheckResponse)
def risk_check(
    payload: RiskCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
):
    if not any([payload.full_name, payload.nif, payload.passport, payload.residence_card]):
        raise HTTPException(status_code=400, detail="Fornece pelo menos um identificador (nome, NIF, passaporte ou cartão).")

    matches = find_matches(db, payload)
    score, level, is_pep, has_sanctions, factors = compute_risk_from_matches(payload, matches)

    record = RiskRecord(
        full_name=payload.full_name,
        nif=payload.nif,
        passport=payload.passport,
        residence_card=payload.residence_card,
        risk_score=score,
        risk_level=level,
        is_pep=is_pep,
        has_sanctions=has_sanctions,
        matches_json=json.dumps([m.dict() for m in matches], ensure_ascii=False),
        factors_json=json.dumps([f.dict() for f in factors], ensure_ascii=False),
        decision=None,
        analyst_notes=payload.extra_info or "",
        analyst_id=current_user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    ip = request.client.host if request and request.client else None
    log_event(
        db,
        "risk_check",
        user=current_user,
        details=f"RiskRecord {record.id} para {record.full_name} (score={record.risk_score})",
        ip_address=ip,
    )

    return RiskCheckResponse(
        id=record.id,
        full_name=record.full_name,
        nif=record.nif,
        passport=record.passport,
        residence_card=record.residence_card,
        risk_score=record.risk_score,
        risk_level=record.risk_level,
        is_pep=record.is_pep,
        has_sanctions=record.has_sanctions,
        matches=matches,
        factors=factors,
        decision=record.decision,
        analyst_notes=record.analyst_notes,
        created_at=record.created_at,
    )


# ---------------------- Histórico ----------------------

@app.get("/risk/history", response_model=List[RiskHistoryItem])
def risk_history(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    qs = (
        db.query(RiskRecord)
        .order_by(RiskRecord.created_at.desc())
        .limit(limit)
        .all()
    )

    resp: List[RiskHistoryItem] = []
    for r in qs:
        resp.append(
            RiskHistoryItem(
                id=r.id,
                full_name=r.full_name,
                nif=r.nif,
                risk_score=r.risk_score,
                risk_level=r.risk_level,
                is_pep=r.is_pep,
                has_sanctions=r.has_sanctions,
                created_at=r.created_at,
            )
        )
    return resp


# ---------------------- PDF do relatório ----------------------

BASE_APP_URL = os.getenv("BASE_APP_URL", "https://teu-front.netlify.app")


@app.get("/risk/{record_id}/report.pdf")
def download_risk_report(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
):
    # Garantir que o registo existe e pertence ao sistema
    record = db.query(RiskRecord).filter(RiskRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Registo de risco não encontrado")

    pdf_path = build_risk_report_pdf(db, record_id, BASE_APP_URL)

    ip = request.client.host if request and request.client else None
    log_event(
        db,
        "download_report",
        user=current_user,
        details=f"Download de relatório PDF para RiskRecord {record_id}",
        ip_address=ip,
    )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"relatorio_risco_{record_id}.pdf",
    )


# ---------------------- Logs / Auditoria ----------------------

@app.get("/admin/logs", response_model=List[AuditLogRead])
def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return logs
