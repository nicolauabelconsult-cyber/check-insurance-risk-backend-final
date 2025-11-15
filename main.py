# main.py
import os
import csv
import json
import difflib
import time
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
    Body,
    Response,
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
    RiskDecisionUpdate,
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

app = FastAPI(title="Check Insurance Risk Backend", version="3.0.0")


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
    se ainda não existir.
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas"
        )

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
    log_event(
        db,
        "create_user",
        user=admin,
        details=f"Criou user {user.username}",
        ip_address=ip,
    )
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
    for key in ["nome", "name", "full_name", "nome_completo", "titular"]:
        if key in lower_headers:
            mapping["name"] = lower_headers[key]
            break

    # NIF
    for key in ["nif", "nif_cliente", "tax_id", "nº contribuinte", "num_contribuinte"]:
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
    for key in ["cargo", "funcao", "função", "role", "position"]:
        if key in lower_headers:
            mapping["role"] = lower_headers[key]
            break

    # País
    for key in ["pais", "país", "country"]:
        if key in lower_headers:
            mapping["country"] = lower_headers[key]
            break

    return mapping


def index_tabular_file(
    db: Session,
    src: InfoSource,
    file_path: str,
    mapping_json: Optional[str],
    ext: str,
) -> int:
    """
    Lê um ficheiro tabular (CSV ou Excel), aplica o mapping e cria NormalizedEntity.
    Devolve o número de registos inseridos.
    """
    ext = ext.lower()
    rows: List[dict] = []
    headers: List[str] = []

    # CSV
    if ext == ".csv":
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            if not headers:
                raise HTTPException(status_code=400, detail="CSV sem cabeçalho.")
            for row in reader:
                rows.append(row)

    # Excel
    elif ext in [".xls", ".xlsx"]:
        try:
            import openpyxl  # garantir que está no requirements.txt
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Suporte a Excel não está configurado (falta 'openpyxl' no servidor).",
            )

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        first = True
        for row in ws.iter_rows(values_only=True):
            if first:
                headers = [
                    str(c).strip() if c is not None else "" for c in row
                ]
                first = False
                continue
            values = [str(c).strip() if c is not None else "" for c in row]
            if not any(values):
                continue
            rows.append(dict(zip(headers, values)))
        if not headers:
            raise HTTPException(status_code=400, detail="Excel sem cabeçalho.")

    else:
        raise HTTPException(status_code=400, detail="Formato tabular não suportado.")

    if mapping_json:
        mapping = json.loads(mapping_json)
    else:
        mapping = guess_mapping(headers)

    if "name" not in mapping:
        raise HTTPException(
            status_code=400,
            detail="Não foi possível identificar a coluna do nome. Envia mapping_json explícito.",
        )

    num_records = 0
    for row in rows:
        person_name = row.get(mapping.get("name", ""), "") or None
        person_nif = (
            row.get(mapping.get("nif", ""), "") or None if mapping.get("nif") else None
        )
        person_passport = (
            row.get(mapping.get("passport", ""), "") or None
            if mapping.get("passport")
            else None
        )
        residence_card = (
            row.get(mapping.get("residence_card", ""), "") or None
            if mapping.get("residence_card")
            else None
        )
        role = (
            row.get(mapping.get("role", ""), "") or None
            if mapping.get("role")
            else None
        )
        country = (
            row.get(mapping.get("country", ""), "") or None
            if mapping.get("country")
            else None
        )

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
    return src.num_records


# ---------------------- Extractores HTML / PDF ----------------------


def extract_entities_from_html_content(
    html: str,
    default_country: str = "Angola",
) -> List[dict]:
    """
    Extrai entidades de uma página HTML (heurística simples).
    Devolve lista de dicts com chaves: person_name, role, country.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Se BeautifulSoup não estiver instalado, não quebrar o backend
        return []

    soup = BeautifulSoup(html, "html.parser")
    entities: List[dict] = []

    # A) Tabelas com cabeçalhos
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [(th.get_text(strip=True) or "").lower() for th in header_cells]
        if not headers:
            continue

        for tr in rows[1:]:
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cols or len(cols) != len(headers):
                continue
            row = dict(zip(headers, cols))

            name = (
                row.get("nome")
                or row.get("name")
                or row.get("titular")
                or row.get("ministro")
            )
            if not name:
                continue

            role = (
                row.get("cargo")
                or row.get("funcao")
                or row.get("função")
                or row.get("role")
                or row.get("posição")
                or row.get("position")
                or ""
            )
            country = (
                row.get("pais")
                or row.get("país")
                or row.get("country")
                or default_country
            )

            entities.append(
                {
                    "person_name": name.strip(),
                    "role": role.strip(),
                    "country": country.strip(),
                }
            )

    # B) Listas simples (ul/li) – ex: "Nome – Ministro de X"
    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)
        lower = text.lower()
        if len(text.split()) < 2:
            continue

        if "ministro" in lower or "secretário" in lower or "governador" in lower:
            # tentar separar em "Nome – Cargo"
            if "–" in text:
                parts = [p.strip() for p in text.split("–", 1)]
            elif "-" in text:
                parts = [p.strip() for p in text.split("-", 1)]
            else:
                parts = [text]

            name = parts[0]
            cargo = parts[1] if len(parts) > 1 else ""

            entities.append(
                {
                    "person_name": name,
                    "role": cargo,
                    "country": default_country,
                }
            )

    # C) Blocos repetidos – heurística simples (divs grandes com "Ministro")
    for div in soup.find_all("div"):
        txt = div.get_text(" ", strip=True)
        lower = txt.lower()
        if "ministro" in lower or "secretário" in lower or "governador" in lower:
            parts = txt.split()
            if len(parts) >= 2:
                name = " ".join(parts[0:3])
                entities.append(
                    {
                        "person_name": name,
                        "role": txt,
                        "country": default_country,
                    }
                )

    # remover duplicados simples por (person_name, role, country)
    unique = {}
    for e in entities:
        key = (
            (e.get("person_name") or "").upper(),
            (e.get("role") or "").upper(),
            (e.get("country") or "").upper(),
        )
        if key not in unique:
            unique[key] = e

    return list(unique.values())


def extract_entities_from_pdf_file(
    file_path: str,
    default_country: str = "Angola",
) -> List[dict]:
    """
    Extrai entidades de um PDF de forma heurística.
    Tenta tabelas primeiro; se não houver, tenta texto corrido.
    """
    try:
        import pdfplumber
    except ImportError:
        # Se pdfplumber não estiver instalado, não quebrar o backend
        return []

    entities: List[dict] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                # 1) tentar tabelas
                table = page.extract_table()
                if table and len(table) > 1:
                    headers = [(h or "").strip().lower() for h in table[0]]
                    for row in table[1:]:
                        if not any(row):
                            continue
                        record = {}
                        for i in range(min(len(headers), len(row))):
                            record[headers[i]] = (row[i] or "").strip()

                        name = (
                            record.get("nome")
                            or record.get("name")
                            or record.get("titular")
                        )
                        if not name:
                            continue

                        role = (
                            record.get("cargo")
                            or record.get("funcao")
                            or record.get("função")
                            or ""
                        )
                        country = (
                            record.get("pais")
                            or record.get("país")
                            or record.get("country")
                            or default_country
                        )

                        entities.append(
                            {
                                "person_name": name,
                                "role": role,
                                "country": country,
                            }
                        )

                # 2) fallback: texto corrido – muito conservador
                text = page.extract_text() or ""
                lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
                for ln in lines:
                    # Exemplo simples: linha com pelo menos 2 palavras e "Ministro"/"Secretário"
                    lower = ln.lower()
                    if (
                        ("ministro" in lower or "secretário" in lower)
                        and len(ln.split()) >= 2
                    ):
                        entities.append(
                            {
                                "person_name": ln.split(" ", 1)[0],
                                "role": ln,
                                "country": default_country,
                            }
                        )

    except Exception:
        # se algo correr mal na leitura do PDF, devolve o que tiver
        pass

    # remover duplicados simples
    unique = {}
    for e in entities:
        key = (
            (e.get("person_name") or "").upper(),
            (e.get("role") or "").upper(),
            (e.get("country") or "").upper(),
        )
        if key not in unique:
            unique[key] = e

    return list(unique.values())


def create_entities_from_extracted(
    db: Session,
    src: InfoSource,
    extracted: List[dict],
) -> int:
    """
    Recebe lista de dicts com chaves (person_name, role, country, opcionalmente nif/passport)
    e cria NormalizedEntity.
    """
    num_records = 0
    for e in extracted:
        name = (e.get("person_name") or "").strip()
        if not name:
            continue

        entity = NormalizedEntity(
            source_id=src.id,
            person_name=name,
            person_nif=(e.get("person_nif") or None),
            person_passport=(e.get("person_passport") or None),
            residence_card=(e.get("residence_card") or None),
            role=(e.get("role") or None),
            country=(e.get("country") or None),
            raw_payload=e,
        )
        db.add(entity)
        num_records += 1

    src.num_records = (src.num_records or 0) + num_records
    db.commit()
    db.refresh(src)
    return num_records


# ---------------------- Endpoints de fontes ----------------------


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
    """
    Upload de fontes:
      - CSV / Excel (.xls, .xlsx) → guardado + indexado para matching
      - PDF → guardado + extraído (heurística) para matching
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".csv", ".xls", ".xlsx", ".pdf"]:
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado. Use ficheiros CSV, Excel ou PDF.",
        )

    ensure_dir(UPLOAD_DIR)
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # Guardar ficheiro
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Criar registo da fonte
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

    # Indexar se for tabular (CSV / Excel)
    if ext in [".csv", ".xls", ".xlsx"]:
        index_tabular_file(db, src, file_path, mapping_json, ext)
    else:
        # PDF: tentar extrair entidades
        extracted = extract_entities_from_pdf_file(file_path)
        if extracted:
            create_entities_from_extracted(db, src, extracted)
        else:
            src.num_records = src.num_records or 0
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


@app.post("/infosources/from-url", response_model=InfoSourceRead)
def create_infosource_from_url(
    name: str = Body(...),
    source_type: str = Body(...),  # PEP, SANCTIONS, FRAUD, CLAIMS, OTHER
    url: str = Body(...),
    description: str = Body(""),
    mapping_json: Optional[dict] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
):
    """
    Cria uma fonte a partir de um link (URL).
    Casos:
      - URL termina em .csv / .xls / .xlsx → download + indexar tabular
      - URL termina em .pdf → download + extrair PDF
      - URL sem extensão conhecida → assume HTML e extrai entidades da página
    """
    try:
        import requests
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Dependência 'requests' não está instalada no servidor.",
        )

    try:
        resp = requests.get(url, timeout=30)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Não foi possível obter o conteúdo da URL."
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=400, detail="Não foi possível obter o conteúdo da URL."
        )

    # Remover querystring para detecção de extensão
    clean_url = url.split("?", 1)[0]
    ext = os.path.splitext(clean_url)[1].lower()

    ensure_dir(UPLOAD_DIR)
    # Definir um nome base para o ficheiro local
    timestamp = int(time.time())

    # Criar registo da fonte primeiro
    src = InfoSource(
        name=name,
        source_type=source_type.upper(),
        description=description,
        file_path=None,
        uploaded_by_id=current_user.id,
    )
    db.add(src)
    db.commit()
    db.refresh(src)

    # Caso 1: CSV / Excel / PDF
    if ext in [".csv", ".xls", ".xlsx", ".pdf"]:
        filename = f"url_{timestamp}{ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(resp.content)

        src.file_path = file_path
        db.commit()
        db.refresh(src)

        if ext in [".csv", ".xls", ".xlsx"]:
            mapping_str = json.dumps(mapping_json) if mapping_json is not None else None
            index_tabular_file(db, src, file_path, mapping_str, ext)
        elif ext == ".pdf":
            extracted = extract_entities_from_pdf_file(file_path)
            if extracted:
                create_entities_from_extracted(db, src, extracted)
            else:
                src.num_records = src.num_records or 0
                db.commit()
                db.refresh(src)

    else:
        # Caso 2: HTML (sem extensão conhecida)
        html = resp.text or ""
        extracted = extract_entities_from_html_content(html, default_country="Angola")

        # guardar um snapshot opcional do HTML
        filename = f"url_{timestamp}.html"
        file_path = os.path.join(UPLOAD_DIR, filename)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html)
            src.file_path = file_path
        except Exception:
            src.file_path = None

        if extracted:
            create_entities_from_extracted(db, src, extracted)
        else:
            src.num_records = src.num_records or 0
            db.commit()
            db.refresh(src)

    ip = request.client.host if request and request.client else None
    log_event(
        db,
        "upload_infosource_url",
        user=current_user,
        details=f"Fonte {src.name} ({src.source_type}) via URL com {src.num_records} registos",
        ip_address=ip,
    )

    return src


@app.get("/infosources", response_model=List[InfoSourceRead])
def list_infosources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(InfoSource).order_by(InfoSource.created_at.desc()).all()


@app.patch("/infosources/{source_id}", response_model=InfoSourceRead)
def update_infosource(
    source_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    request: Request = None,
):
    """
    Edita nome / tipo / descrição de uma fonte existente (apenas admin).
    """
    src = db.query(InfoSource).filter(InfoSource.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Fonte não encontrada")

    for field in ["name", "source_type", "description"]:
        if field in payload and payload[field] is not None:
            setattr(src, field, payload[field])

    db.commit()
    db.refresh(src)

    ip = request.client.host if request and request.client else None
    log_event(
        db,
        "update_infosource",
        user=admin,
        details=f"Actualizou fonte {src.id} ({src.name})",
        ip_address=ip,
    )

    return src


@app.delete("/infosources/{source_id}", status_code=204)
def delete_infosource(
    source_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    request: Request = None,
):
    """
    Apaga uma fonte e os registos normalizados associados (apenas admin).
    """
    src = db.query(InfoSource).filter(InfoSource.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Fonte não encontrada")

    # Apagar entidades normalizadas associadas
    db.query(NormalizedEntity).filter(
        NormalizedEntity.source_id == src.id
    ).delete()

    # Tentar remover o ficheiro físico
    if src.file_path:
        try:
            os.remove(src.file_path)
        except FileNotFoundError:
            pass

    db.delete(src)
    db.commit()

    ip = request.client.host if request and request.client else None
    log_event(
        db,
        "delete_infosource",
        user=admin,
        details=f"Apagou fonte {source_id}",
        ip_address=ip,
    )

    return Response(status_code=204)


# ---------------------- Lógica de matching e risco ----------------------


def find_matches(
    db: Session,
    req: RiskCheckRequest,
) -> List[Match]:
    """
    Procura matches nas entidades normalizadas,
    usando NIF, passaporte, cartão e nome aproximado.
    """
    matches: List[Match] = []

    q = db.query(NormalizedEntity, InfoSource).join(
        InfoSource, NormalizedEntity.source_id == InfoSource.id
    )

    if req.nif:
        candidates = (
            q.filter(func.lower(NormalizedEntity.person_nif) == req.nif.lower())
            .limit(200)
            .all()
        )
    elif req.passport:
        candidates = (
            q.filter(
                func.lower(NormalizedEntity.person_passport) == req.passport.lower()
            )
            .limit(200)
            .all()
        )
    elif req.residence_card:
        candidates = (
            q.filter(
                func.lower(NormalizedEntity.residence_card)
                == req.residence_card.lower()
            )
            .limit(200)
            .all()
        )
    else:
        name = req.full_name.strip().upper()
        candidates = (
            q.filter(func.upper(NormalizedEntity.person_name).like(f"%{name}%"))
            .limit(200)
            .all()
        )

    def sim(a: str, b: str) -> float:
        return difflib.SequenceMatcher(
            None, (a or "").upper(), (b or "").upper()
        ).ratio()

    for entity, src in candidates:
        similarity = sim(req.full_name, entity.person_name or "")
        if not any([req.nif, req.passport, req.residence_card]) and similarity < 0.6:
            continue

        identifier = (
            entity.person_nif or entity.person_passport or entity.residence_card or None
        )

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

    for m in matches:
        st = (m.source_type or "").upper()
        if st == "PEP":
            is_pep = True
            factors.append(
                RiskFactor(code="PEP", description="Presença em lista PEP", weight=70)
            )
            score += 70
        elif st == "SANCTIONS":
            has_sanctions = True
            factors.append(
                RiskFactor(
                    code="SANCTIONS",
                    description="Presença em lista de sanções",
                    weight=100,
                )
            )
            score += 100
        elif st == "FRAUD":
            factors.append(
                RiskFactor(
                    code="FRAUD",
                    description="Registo em base interna de fraude",
                    weight=60,
                )
            )
            score += 60
        elif st == "CLAIMS":
            factors.append(
                RiskFactor(
                    code="CLAIMS",
                    description="Histórico de sinistros relevante",
                    weight=30,
                )
            )
            score += 30

    if not req.nif:
        factors.append(
            RiskFactor(code="NO_NIF", description="NIF não fornecido", weight=10)
        )
        score += 10

    if score == 0 and req.nif:
        factors.append(
            RiskFactor(
                code="CLEAN",
                description="Sem ocorrências negativas nas fontes",
                weight=0,
            )
        )

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
    if not any(
        [payload.full_name, payload.nif, payload.passport, payload.residence_card]
    ):
        raise HTTPException(
            status_code=400,
            detail="Fornece pelo menos um identificador (nome, NIF, passaporte ou cartão).",
        )

    matches = find_matches(db, payload)
    score, level, is_pep, has_sanctions, factors = compute_risk_from_matches(
        payload, matches
    )

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
        primary_match_json=None,
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


# ---------------------- Decisão do analista ----------------------


@app.patch("/risk/{record_id}/decision", response_model=RiskCheckResponse)
def update_risk_decision(
    record_id: int,
    payload: RiskDecisionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
):
    record = db.query(RiskRecord).filter(RiskRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Registo de risco não encontrado")

    if record.analyst_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Apenas o analista criador ou um admin pode alterar a decisão.",
        )

    record.decision = payload.decision
    if payload.analyst_notes is not None:
        record.analyst_notes = payload.analyst_notes

    matches = json.loads(record.matches_json)

    if payload.primary_match_index is not None:
        idx = payload.primary_match_index
        if 0 <= idx < len(matches):
            record.primary_match_json = json.dumps(matches[idx], ensure_ascii=False)
        else:
            raise HTTPException(
                status_code=400, detail="primary_match_index fora de intervalo."
            )
    db.commit()
    db.refresh(record)

    ip = request.client.host if request and request.client else None
    log_event(
        db,
        "update_risk_decision",
        user=current_user,
        details=f"Actualizou decisão de RiskRecord {record.id} para {record.decision}",
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
        matches=[Match(**m) for m in matches],
        factors=[RiskFactor(**f) for f in json.loads(record.factors_json)],
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
