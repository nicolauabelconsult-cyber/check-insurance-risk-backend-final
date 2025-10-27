
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid, hashlib, json

from auth import get_current_user, has_sensitive_access
from storage import (
    find_risk_matches,
    get_risk_by_id,
    save_analysis,
    add_audit_log,
)

router = APIRouter(prefix="/api", tags=["risk"])

class RiskCheckRequest(BaseModel):
    identifier: str
    identifier_type: str  # "NIF","BI","PASSAPORTE","CARTAO_RESIDENTE","NOME"

class RiskConfirmRequest(BaseModel):
    match_id: int

def decidir_texto(row: dict) -> str:
    if row.get("sanctions_alert") or row.get("pep_alert") or row.get("fraude_suspeita"):
        return "Escalar / Risco Elevado"
    score = int(row.get("score_final", 0))
    if score >= 80:
        return "Aceitar"
    if score >= 60:
        return "Aceitar c/ Condições"
    return "Escalar / Risco Elevado"

def regras_activas(row: dict):
    rules = []
    if row.get("pep_alert"):
        rules.append("PEP detectado (+40 risco)")
    if row.get("sanctions_alert"):
        rules.append("Listas de sanções (+40 risco)")
    if row.get("fraude_suspeita"):
        rules.append("Suspeita de fraude → Escalar")
    if int(row.get("sinistros_ult_12m",0)) >= 2:
        rules.append(">=2 sinistros nos últimos 12m (+20 risco)")
    return rules

def montar_analysis(row: dict, searched_identifier: str, searched_type: str, requested_by: str, include_sensitive: bool):
    consulta_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    decisao_txt = decidir_texto(row)

    analysis_obj = {
        "consulta_id": consulta_id,
        "timestamp": timestamp,
        "identifier": searched_identifier,
        "identifier_type": searched_type,
        "score_final": int(row.get("score_final",0)),
        "decisao": decisao_txt,
        "justificacao": row.get("justificacao","Sem justificação."),

        "ramo": row.get("ramo",""),
        "finalidade": row.get("finalidade",""),
        "canal": row.get("canal",""),

        "sanctions_alert": bool(row.get("sanctions_alert")) if include_sensitive else None,
        "pep_alert": bool(row.get("pep_alert")) if include_sensitive else None,
        "fraude_suspeita": bool(row.get("fraude_suspeita", False)) if include_sensitive else None,
        "comentario_fraude": row.get("comentario_fraude","") if include_sensitive else "",

        "historico_pagamentos": row.get("historico_pagamentos",""),
        "sinistros_total": int(row.get("sinistros_total",0)),
        "sinistros_ult_12m": int(row.get("sinistros_ult_12m",0)),

        "condicoes_sugeridas": row.get("condicoes_sugeridas","") if decisao_txt.startswith("Aceitar c/") else "",
        "estado": row.get("estado","Em análise"),
        "regras_aplicadas": regras_activas(row),
        "decisao_humana": row.get("decisao_humana",""),
        "data_decisao": row.get("data_decisao",""),
        "requested_by": requested_by,
        "motor_versao": "1.0",
    }

    # hash de integridade
    calc_hash = hashlib.sha256(json.dumps(analysis_obj, sort_keys=True).encode()).hexdigest()
    analysis_obj["integridade_hash"] = calc_hash

    return analysis_obj

def registar_auditoria(analysis_obj: dict):
    add_audit_log({
        "timestamp": analysis_obj["timestamp"],
        "identifier": analysis_obj["identifier"],
        "decisao": analysis_obj["decisao"],
        "score_final": analysis_obj["score_final"],
        "consulta_id": analysis_obj["consulta_id"],
        "requested_by": analysis_obj["requested_by"],
        "fraude_suspeita": analysis_obj.get("fraude_suspeita", False),
        "sinistros_ult_12m": analysis_obj.get("sinistros_ult_12m", 0),
    })

@router.post("/risk-check")
def risk_check(payload: RiskCheckRequest, user=Depends(get_current_user)):
    requested_by = getattr(user, "email", None) or getattr(user, "name", "desconhecido")
    rows = find_risk_matches(payload.identifier, payload.identifier_type)

    if not rows:
        dummy = {
            "score_final":25,
            "justificacao":"Sem dados disponíveis, requer análise manual.",
            "sanctions_alert":False,
            "pep_alert":False,
            "fraude_suspeita":False,
            "historico_pagamentos":"Sem registo interno",
            "sinistros_total":0,
            "sinistros_ult_12m":0,
            "comentario_fraude":"",
            "ramo":"",
            "finalidade":"Subscrição",
            "canal":"Interno",
            "condicoes_sugeridas":"",
            "estado":"Em análise",
        }
        analysis_obj = montar_analysis(
            dummy,
            payload.identifier,
            payload.identifier_type,
            requested_by,
            include_sensitive=has_sensitive_access(user)
        )
        save_analysis(analysis_obj)
        registar_auditoria(analysis_obj)
        return analysis_obj

    if len(rows)==1:
        analysis_obj = montar_analysis(
            rows[0],
            payload.identifier,
            payload.identifier_type,
            requested_by,
            include_sensitive=has_sensitive_access(user)
        )
        save_analysis(analysis_obj)
        registar_auditoria(analysis_obj)
        return analysis_obj

    matches = []
    for r in rows:
        matches.append({
            "match_id": r["id"],
            "score_final": r.get("score_final",0),
            "decisao": decidir_texto(r),
            "justificacao": r.get("justificacao",""),
            "pep_alert": r.get("pep_alert", False) if has_sensitive_access(user) else None,
            "sanctions_alert": r.get("sanctions_alert", False) if has_sensitive_access(user) else None,
            "fraude_suspeita": r.get("fraude_suspeita", False) if has_sensitive_access(user) else None,
            "sinistros_ult_12m": r.get("sinistros_ult_12m",0),
            "estado": r.get("estado","Em análise"),
        })
    return {"multi_match": True, "matches": matches}

@router.post("/risk-confirm")
def risk_confirm(payload: RiskConfirmRequest, user=Depends(get_current_user)):
    row = get_risk_by_id(payload.match_id)
    if not row:
        raise HTTPException(status_code=404, detail="Registo não encontrado.")
    requested_by = getattr(user, "email", None) or getattr(user, "name", "desconhecido")
    analysis_obj = montar_analysis(
        row,
        "(seleccionado manualmente)",
        "MULTI",
        requested_by,
        include_sensitive=has_sensitive_access(user)
    )
    save_analysis(analysis_obj)
    registar_auditoria(analysis_obj)
    return analysis_obj
