from fastapi import APIRouter, Depends, Form, HTTPException
from datetime import datetime, timezone

from storage import ANALYSES_DB, AUDIT_LOG, INFO_SOURCES, add_info_source
from auth import get_current_user, assert_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/audit/logs")
def get_audit_logs(limit: int = 20, user=Depends(get_current_user)):
    assert_admin(user)
    # devolver últimos 'limit' eventos mais recentes primeiro
    ordered = sorted(AUDIT_LOG, key=lambda x: x["timestamp"], reverse=True)
    return ordered[:limit]

@router.post("/info-sources/create")
def create_info_source(
    title: str = Form(...),
    description: str = Form(...),
    url: str = Form(""),
    directory: str = Form(""),
    filename: str = Form(""),
    user=Depends(get_current_user),
):
    assert_admin(user)
    add_info_source(
        title=title,
        description=description,
        url=url,
        directory=directory,
        filename=filename,
        uploaded_at=datetime.now(timezone.utc).isoformat()
    )
    return {"status":"ok"}

@router.get("/info-sources/list")
def list_info_sources(user=Depends(get_current_user)):
    assert_admin(user)
    return INFO_SOURCES

# --- Risk data manual insert/update ---
#
# Para suportar o formulário "Base de Risco (Registo Manual)" no admin.html
# Vamos manter uma BD em memória chamada RISK_DATA_DB.
#
RISK_DATA_DB = []  # lista de dicts {id, identifier, identifier_type, score_final, justificacao, pep_alert, sanctions_alert}

def _find_existing(identifier, identifier_type):
    for row in RISK_DATA_DB:
        if row["identifier"] == identifier and row["identifier_type"] == identifier_type:
            return row
    return None

@router.post("/risk-data/add-record")
def add_risk_record(
    identifier: str = Form(...),
    identifier_type: str = Form(...),
    score_final: int = Form(...),
    justificacao: str = Form(...),
    pep_alert: int = Form(...),          # "1" or "0"
    sanctions_alert: int = Form(...),    # "1" or "0"
    user=Depends(get_current_user),
):
    assert_admin(user)

    existing = _find_existing(identifier, identifier_type)
    if existing:
        existing["score_final"] = int(score_final)
        existing["justificacao"] = justificacao
        existing["pep_alert"] = bool(int(pep_alert))
        existing["sanctions_alert"] = bool(int(sanctions_alert))
        return {"status":"ok", "updated": True, "id": existing["id"]}

    new_id = len(RISK_DATA_DB)+1
    row = {
        "id": new_id,
        "identifier": identifier,
        "identifier_type": identifier_type,
        "score_final": int(score_final),
        "justificacao": justificacao,
        "pep_alert": bool(int(pep_alert)),
        "sanctions_alert": bool(int(sanctions_alert)),
    }
    RISK_DATA_DB.append(row)
    return {"status":"ok", "created": True, "id": new_id}

# Tornamos estas estruturas acessíveis por outras rotas (risk)
def get_all_matches(identifier: str, identifier_type: str):
    out = []
    for row in RISK_DATA_DB:
        if row["identifier"].upper() == identifier.upper() and row["identifier_type"] == identifier_type:
            out.append(row)
    return out

def get_by_id(row_id: int):
    for row in RISK_DATA_DB:
        if row["id"] == row_id:
            return row
    return None
