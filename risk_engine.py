from typing import Tuple, Optional
from . import models

def evaluate_risk(record: models.RiskRecord) -> Tuple[int,str,str,bool,bool,str]:
    base_score = record.score_final if record.score_final is not None else 70
    if record.fraude_suspeita:
        base_score -= 30
    if record.sinistros_ult_12m and record.sinistros_ult_12m > 2:
        base_score -= 10
    if record.historico_pagamentos and "Atras" in record.historico_pagamentos:
        base_score -= 10
    if record.pep_alert:
        base_score -= 15
    if record.sanctions_alert:
        base_score -= 40

    if base_score < 0:
        base_score = 0
    if base_score > 100:
        base_score = 100

    if record.sanctions_alert:
        decisao = "Recusar / Escalar Compliance"
    elif record.pep_alert or record.fraude_suspeita:
        decisao = "Escalar para Revisão Manual"
    elif base_score >= 75:
        decisao = "Aceitar Risco Técnico"
    elif base_score >= 50:
        decisao = "Aceitar com Reservas"
    else:
        decisao = "Recusar / Escalar Compliance"

    justificacao = record.justificacao or "Avaliação automática com base em histórico de sinistros, PEP/Sanções e comportamento financeiro."
    benchmark = "Benchmarks internos e alertas PEP/Sanções UE/FMI."

    return base_score, decisao, justificacao, bool(record.pep_alert), bool(record.sanctions_alert), benchmark

def find_match(identifier: str) -> Optional[models.RiskRecord]:
    for r in models.RISK_DB.values():
        if (
            (r.nif and r.nif == identifier) or
            (r.bi and r.bi == identifier) or
            (r.passaporte and r.passaporte == identifier) or
            (r.cartao_residente and r.cartao_residente == identifier) or
            (r.nome and r.nome.lower() == identifier.lower())
        ):
            return r
    return None
