from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/api", tags=["risk"])

class RiskCheckRequest(BaseModel):
    identifier: str
    identifier_type: str  # "NIF", "BI", "PASSAPORTE", "CARTAO_RESIDENTE", "NOME"

class RiskConfirmRequest(BaseModel):
    match_id: int

def db_find_all_matches(identifier: str, identifier_type: str):
    # IMPLEMENTAR com a tua base (SELECT * FROM risk_data WHERE identifier=? AND identifier_type=?)
    raise NotImplementedError

def db_get_risk_row_by_id(row_id: int):
    # IMPLEMENTAR com a tua base (SELECT * FROM risk_data WHERE id=? LIMIT 1)
    raise NotImplementedError

def decidir_texto(row: dict) -> str:
    if row.get("sanctions_alert") or row.get("pep_alert"):
        return "Escalar / Risco Elevado"
    score = int(row.get("score_final", 0))
    if score >= 80:
        return "Aceitar"
    if score >= 60:
        return "Aceitar c/ Condições"
    return "Escalar / Risco Elevado"

def guardar_analysis_memoria(analysis_obj: dict):
    # IMPLEMENTAR: guardar numa estrutura global/dict ou BD temporária indexada por consulta_id
    raise NotImplementedError

def registrar_auditoria(analysis_obj: dict, requested_by: str):
    # IMPLEMENTAR: inserir no audit_log
    raise NotImplementedError

def gerar_analysis_final(row: dict, requested_by: str) -> dict:
    consulta_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    decisao_txt = decidir_texto(row)

    analysis_obj = {
        "score_final": int(row.get("score_final", 0)),
        "decisao": decisao_txt,
        "justificacao": row.get("justificacao", "Sem justificação registada."),
        "sanctions_alert": bool(row.get("sanctions_alert")),
        "pep_alert": bool(row.get("pep_alert")),
        "consulta_id": consulta_id,
        "timestamp": timestamp,
        "identifier": row.get("identifier"),
        "identifier_type": row.get("identifier_type"),
    }

    guardar_analysis_memoria(analysis_obj)
    registrar_auditoria(analysis_obj, requested_by=requested_by)

    return analysis_obj

def gerar_resultado_default(payload: RiskCheckRequest, requested_by: str) -> dict:
    consulta_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    analysis_obj = {
        "score_final": 30,
        "decisao": "Escalar / Risco Elevado",
        "justificacao": "Sem histórico técnico. Avaliação manual recomendada.",
        "sanctions_alert": False,
        "pep_alert": False,
        "consulta_id": consulta_id,
        "timestamp": timestamp,
        "identifier": payload.identifier,
        "identifier_type": payload.identifier_type,
    }

    guardar_analysis_memoria(analysis_obj)
    registrar_auditoria(analysis_obj, requested_by=requested_by)

    return analysis_obj

@router.post("/risk-check")
def risk_check(payload: RiskCheckRequest, user=Depends(...)):
    rows = db_find_all_matches(
        identifier=payload.identifier,
        identifier_type=payload.identifier_type
    )

    requested_by = getattr(user, "email", None) or getattr(user, "name", "desconhecido")

    if not rows:
        return gerar_resultado_default(payload, requested_by)

    if len(rows) == 1:
        return gerar_analysis_final(rows[0], requested_by=requested_by)

    matches = []
    for r in rows:
        matches.append({
            "match_id": r.get("id"),
            "identifier": r.get("identifier"),
            "identifier_type": r.get("identifier_type"),
            "score_final": int(r.get("score_final", 0)),
            "decisao": decidir_texto(r),
            "justificacao": r.get("justificacao", "Sem justificação registada."),
            "pep_alert": bool(r.get("pep_alert")),
            "sanctions_alert": bool(r.get("sanctions_alert")),
        })

    return {
        "multi_match": True,
        "matches": matches
    }

@router.post("/risk-confirm")
def risk_confirm(payload: RiskConfirmRequest, user=Depends(...)):
    row = db_get_risk_row_by_id(payload.match_id)
    if not row:
        raise HTTPException(status_code=404, detail="Registo não encontrado")

    requested_by = getattr(user, "email", None) or getattr(user, "name", "desconhecido")
    analysis_obj = gerar_analysis_final(row, requested_by=requested_by)
    return analysis_obj
