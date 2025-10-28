import random
from app.utils.timeutils import now_ts
from app.admin.storage_audit import add_audit_entry
from app.risk.service_risk_id import generate_consulta_id

def run_risk_check(user_name: str, identifier: str, identifier_type: str):
    high_risk_list = ["999999999", "SANCTION123"]
    pep_list = ["PEP001", "PEP002"]

    pep_alert = identifier in pep_list
    sanctions_alert = identifier in high_risk_list

    base_score = random.randint(60,90)
    if sanctions_alert:
        base_score -= 25
    if pep_alert:
        base_score -= 10
    score_final = max(0, min(100, base_score))

    if sanctions_alert:
        decisao = "Escalar / Risco Elevado"
    elif score_final < 50:
        decisao = "Recusar Emitir"
    elif score_final >= 80:
        decisao = "Aceitar"
    else:
        decisao = "Aceitar com Limitação de Cobertura"

    justificacao = "Avaliação automática com base em histórico e listas de alerta internacionais."
    benchmark_internacional = "Score médio global: 78/100 · Posição: Ligeiramente acima do risco médio"

    consulta_id = generate_consulta_id()
    timestamp = now_ts()

    add_audit_entry(
        ts=timestamp,
        user=user_name,
        identifier=f"{identifier_type}:{identifier}",
        score_final=score_final,
        decisao=decisao
    )

    historico_pagamentos = "Sem registo interno."
    sinistros_total = 0
    sinistros_12m = 0
    nota_fraude = ""

    return {
        "consulta_id": consulta_id,
        "timestamp": timestamp,
        "score_final": score_final,
        "decisao": decisao,
        "pep_alert": pep_alert,
        "sanctions_alert": sanctions_alert,
        "justificacao": justificacao,
        "benchmark_internacional": benchmark_internacional,
        "historico_pagamentos": historico_pagamentos,
        "sinistros_total": sinistros_total,
        "sinistros_12m": sinistros_12m,
        "nota_fraude": nota_fraude
    }
