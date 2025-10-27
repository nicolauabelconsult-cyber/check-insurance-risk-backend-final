from fastapi import APIRouter, Depends, Form
from datetime import datetime, timezone

from storage import ANALYSES_DB, AUDIT_LOG, INFO_SOURCES, add_info_source
from auth import get_current_user, assert_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/audit/logs")
def get_audit_logs(limit: int = 20, user=Depends(get_current_user)):
    assert_admin(user)
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

# --------------------------
# Base de Risco (Registo Manual)
# --------------------------

RISK_DATA_DB = []  # cada row é um dict com dados de risco

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
    pep_alert: int = Form(...),          # "1" ou "0"
    sanctions_alert: int = Form(...),    # "1" ou "0"

    historico_pagamentos: str = Form(...),
    sinistros_total: int = Form(...),
    sinistros_ult_12m: int = Form(...),
    fraude_suspeita: int = Form(...),    # "1" ou "0"
    comentario_fraude: str = Form(""),

    user=Depends(get_current_user),
):
    assert_admin(user)

    existing = _find_existing(identifier, identifier_type)
    if existing:
        existing["score_final"] = int(score_final)
        existing["justificacao"] = justificacao
        existing["pep_alert"] = bool(int(pep_alert))
        existing["sanctions_alert"] = bool(int(sanctions_alert))

        existing["historico_pagamentos"] = historico_pagamentos
        existing["sinistros_total"] = int(sinistros_total)
        existing["sinistros_ult_12m"] = int(sinistros_ult_12m)
        existing["fraude_suspeita"] = bool(int(fraude_suspeita))
        existing["comentario_fraude"] = comentario_fraude

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

        "historico_pagamentos": historico_pagamentos,
        "sinistros_total": int(sinistros_total),
        "sinistros_ult_12m": int(sinistros_ult_12m),
        "fraude_suspeita": bool(int(fraude_suspeita)),
        "comentario_fraude": comentario_fraude,
    }
    RISK_DATA_DB.append(row)
    return {"status":"ok", "created": True, "id": new_id}

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
