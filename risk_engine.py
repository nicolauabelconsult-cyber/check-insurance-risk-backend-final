from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict

from models import RiskCheckRequest, RiskCheckResponse, StoredAnalysis
from auth import get_current_user
from db import get_conn

router = APIRouter(prefix="/api", tags=["risk"])

ANALYSES_DB: Dict[str, StoredAnalysis] = {}

def consulta_risco_na_bd(identifier: str, identifier_type: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT score_final, justificacao, pep_alert, sanctions_alert
        FROM risk_data
        WHERE identifier = ? AND identifier_type = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (identifier, identifier_type)
    )
    row = cur.fetchone()
    conn.close()
    return row

def classificar(score: int) -> str:
    if score >= 80:
        return "Aceitar"
    elif score >= 50:
        return "Aceitar c/ Condições"
    else:
        return "Escalar / Risco Elevado"

@router.post("/risk-check", response_model=RiskCheckResponse)
def risk_check(payload: RiskCheckRequest, user=Depends(get_current_user)):
    row = consulta_risco_na_bd(payload.identifier, payload.identifier_type)

    if row:
        score_final = int(row["score_final"])
        justificacao = row["justificacao"]
        pep_alert = bool(row["pep_alert"])
        sanctions_alert = bool(row["sanctions_alert"])
        decisao = classificar(score_final)
    else:
        score_final = 30
        justificacao = "Sem registo interno. Avaliação manual recomendada."
        pep_alert = False
        sanctions_alert = False
        decisao = "Escalar / Risco Elevado"

    consulta_id = str(uuid4())
    timestamp_iso = datetime.now(timezone.utc).isoformat()

    analysis = StoredAnalysis(
        identifier=payload.identifier,
        identifier_type=payload.identifier_type,
        score_final=score_final,
        decisao=decisao,
        justificacao=justificacao,
        sanctions_alert=sanctions_alert,
        pep_alert=pep_alert,
        consulta_id=consulta_id,
        timestamp=timestamp_iso
    )
    ANALYSES_DB[consulta_id] = analysis

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO audit_log
        (consulta_id, identifier, decisao, score_final, requested_by, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            consulta_id,
            payload.identifier,
            decisao,
            score_final,
            user["email"],
            timestamp_iso
        )
    )
    conn.commit()
    conn.close()

    return RiskCheckResponse(
        score_final=analysis.score_final,
        decisao=analysis.decisao,
        justificacao=analysis.justificacao,
        sanctions_alert=analysis.sanctions_alert,
        pep_alert=analysis.pep_alert,
        consulta_id=analysis.consulta_id,
        timestamp=analysis.timestamp
    )

def get_analysis(consulta_id: str) -> StoredAnalysis:
    analysis = ANALYSES_DB.get(consulta_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Relatório indisponível")
    return analysis
