from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from storage import ANALYSES_DB, AUDIT_LOG

router = APIRouter(prefix="/api", tags=["risk"])

class RiskCheckRequest(BaseModel):
    identifier: str
    identifier_type: str  # "NIF","BI","PASSAPORTE","CARTAO_RESIDENTE","NOME"

class RiskConfirmRequest(BaseModel):
    match_id: int

# === Simulação de BD ===
def db_find_all_matches(identifier: str, identifier_type: str):
    if identifier_type == "NOME" and identifier.upper() == "JOAO":
        return [
            {"id": 1, "identifier": "JOAO", "identifier_type": "NOME",
             "score_final": 75, "pep_alert": False, "sanctions_alert": False,
             "justificacao": "Bom histórico."},
            {"id": 2, "identifier": "JOAO", "identifier_type": "NOME",
             "score_final": 40, "pep_alert": True, "sanctions_alert": False,
             "justificacao": "Ligação política detectada."}
        ]
    if identifier == "123456789":
        return [{
            "id": 3, "identifier": "123456789", "identifier_type": identifier_type,
            "score_final": 90, "pep_alert": False, "sanctions_alert": False,
            "justificacao": "Risco técnico controlado."
        }]
    return []

def db_get_risk_row_by_id(row_id: int):
    all_data = {
        1: {"id": 1, "identifier": "JOAO", "identifier_type": "NOME",
            "score_final": 75, "pep_alert": False, "sanctions_alert": False,
            "justificacao": "Bom histórico."},
        2: {"id": 2, "identifier": "JOAO", "identifier_type": "NOME",
            "score_final": 40, "pep_alert": True, "sanctions_alert": False,
            "justificacao": "Ligação política detectada."},
        3: {"id": 3, "identifier": "123456789", "identifier_type": "NIF",
            "score_final": 90, "pep_alert": False, "sanctions_alert": False,
            "justificacao": "Risco técnico controlado."}
    }
    return all_data.get(row_id)

def decidir_texto(row: dict) -> str:
    if row.get("sanctions_alert") or row.get("pep_alert"):
        return "Escalar / Risco Elevado"
    score = int(row.get("score_final", 0))
    if score >= 80:
        return "Aceitar"
    if score >= 60:
        return "Aceitar c/ Condições"
    return "Escalar / Risco Elevado"

def _registar_auditoria(analysis_obj: dict, requested_by: str):
    AUDIT_LOG.append({
        "timestamp": analysis_obj["timestamp"],
        "identifier": analysis_obj["identifier"],
        "decisao": analysis_obj["decisao"],
        "score_final": analysis_obj["score_final"],
        "consulta_id": analysis_obj["consulta_id"],
        "requested_by": requested_by,
    })

def _guardar_analysis(analysis_obj: dict):
    ANALYSES_DB[analysis_obj["consulta_id"]] = analysis_obj

def gerar_analysis_final(row: dict, requested_by: str) -> dict:
    consulta_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    decisao_txt = decidir_texto(row)

    analysis_obj = {
        "score_final": int(row.get("score_final", 0)),
        "decisao": decisao_txt,
        "justificacao": row.get("justificacao", "Sem justificação."),
        "sanctions_alert": bool(row.get("sanctions_alert")),
        "pep_alert": bool(row.get("pep_alert")),
        "consulta_id": consulta_id,
        "timestamp": timestamp,
        "identifier": row.get("identifier"),
        "identifier_type": row.get("identifier_type")
    }

    _guardar_analysis(analysis_obj)
    _registar_auditoria(analysis_obj, requested_by=requested_by)
    return analysis_obj

def gerar_resultado_default(payload: RiskCheckRequest, requested_by: str) -> dict:
    consulta_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    analysis_obj = {
        "score_final": 25,
        "decisao": "Escalar / Risco Elevado",
        "justificacao": "Sem dados disponíveis, requer análise manual.",
        "sanctions_alert": False,
        "pep_alert": False,
        "consulta_id": consulta_id,
        "timestamp": timestamp,
        "identifier": payload.identifier,
        "identifier_type": payload.identifier_type,
    }

    _guardar_analysis(analysis_obj)
    _registar_auditoria(analysis_obj, requested_by=requested_by)
    return analysis_obj

# utilizador autenticado "fake" só para demo
def get_current_user():
    class FakeUser:
        email = "analyst@example.com"
        name = "Demo Analyst"
    return FakeUser()

@router.post("/risk-check")
def risk_check(payload: RiskCheckRequest, user=Depends(get_current_user)):
    rows = db_find_all_matches(payload.identifier, payload.identifier_type)

    requested_by = getattr(user, "email", None) or getattr(user, "name", "desconhecido")

    if not rows:
        return gerar_resultado_default(payload, requested_by)

    if len(rows) == 1:
        return gerar_analysis_final(rows[0], requested_by=requested_by)

    matches = []
    for r in rows:
        matches.append({
            "match_id": r["id"],
            "identifier": r["identifier"],
            "identifier_type": r["identifier_type"],
            "score_final": r["score_final"],
            "decisao": decidir_texto(r),
            "justificacao": r["justificacao"],
            "pep_alert": r["pep_alert"],
            "sanctions_alert": r["sanctions_alert"]
        })

    return {"multi_match": True, "matches": matches}

@router.post("/risk-confirm")
def risk_confirm(payload: RiskConfirmRequest, user=Depends(get_current_user)):
    row = db_get_risk_row_by_id(payload.match_id)
    if not row:
        raise HTTPException(status_code=404, detail="Registo não encontrado.")
    requested_by = getattr(user, "email", None) or getattr(user, "name", "desconhecido")
    return gerar_analysis_final(row, requested_by=requested_by)
