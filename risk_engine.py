from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict
from models import RiskCheckRequest, RiskCheckResponse, StoredAnalysis
from auth import get_current_user

router = APIRouter(prefix="/api", tags=["risk"])
ANALYSES_DB: Dict[str, StoredAnalysis] = {}

def calcular_score_mock(identifier: str) -> int:
    base = len(identifier) * 7
    score = base % 101
    if score < 20:
        score += 20
    if score > 95:
        score = 95
    return score

def classificar(score: int) -> str:
    if score >= 80:
        return "Aceitar"
    elif score >= 50:
        return "Aceitar c/ Condições"
    else:
        return "Escalar / Risco Elevado"

@router.post("/risk-check", response_model=RiskCheckResponse)
def risk_check(payload: RiskCheckRequest, user_email: str = Depends(get_current_user)):
    score_final = calcular_score_mock(payload.identifier)
    decisao = classificar(score_final)
    sanctions_alert = False
    pep_alert = False
    justificacao = "Risco técnico controlado." if decisao != "Escalar / Risco Elevado" else "Indicadores de risco elevados: revisão manual recomendada."
    consulta_id = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    analysis = StoredAnalysis(
        identifier=payload.identifier,
        identifier_type=payload.identifier_type,
        score_final=score_final,
        decisao=decisao,
        justificacao=justificacao,
        sanctions_alert=sanctions_alert,
        pep_alert=pep_alert,
        consulta_id=consulta_id,
        timestamp=timestamp
    )
    ANALYSES_DB[consulta_id] = analysis
    return RiskCheckResponse(**analysis.model_dump())

def get_analysis(consulta_id: str) -> StoredAnalysis:
    analysis = ANALYSES_DB.get(consulta_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Relatório indisponível")
    return analysis
