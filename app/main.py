from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
from . import models, schemas, utils, risk_engine, pdf_generator
from .auth import router as auth_router
from .storage import router as storage_router

app = FastAPI(
    title="Check Insurance Risk Backend",
    version="1.0",
    description="Motor técnico de avaliação de risco e compliance."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(storage_router, prefix="/api")

@app.post("/api/risk-check", response_model=schemas.RiskCheckResponse)
def risk_check(body: schemas.RiskCheckRequest, current=Depends(utils.get_current_user)):
    match = risk_engine.find_match(body.identifier)
    if not match:
        rid = models.next_risk_id()
        match = models.RiskRecord(
            id=rid,
            nome=None,
            nif=body.identifier if body.identifier_type == "NIF" else None,
            bi=body.identifier if body.identifier_type == "BI" else None,
            passaporte=None,
            cartao_residente=None,
            score_final=72,
            justificacao="Sem histórico interno completo. Aplicado baseline técnico.",
            pep_alert=False,
            sanctions_alert=False,
            historico_pagamentos="Regular",
            sinistros_total=0,
            sinistros_ult_12m=0,
            fraude_suspeita=False,
            comentario_fraude=None,
            esg_score=70,
            country_risk="Moderado",
            credit_rating="BB+",
            kyc_confidence="Médio",
        )
        models.RISK_DB[rid] = match

    (score_final, decisao, justificacao, pep_flag, sanc_flag, bench) = risk_engine.evaluate_risk(match)

    consulta_id = models.next_consulta_id()
    timestamp = models.timestamp_now()

    payload = {
        "consulta_id": consulta_id,
        "timestamp": timestamp,
        "identifier": body.identifier,
        "identifier_type": body.identifier_type,
        "score_final": score_final,
        "decisao": decisao,
        "justificacao": justificacao,
        "pep_alert": pep_flag,
        "sanctions_alert": sanc_flag,
        "benchmark_internacional": bench,
        "historico_pagamentos": match.historico_pagamentos,
        "sinistros_total": match.sinistros_total,
        "sinistros_ult_12m": match.sinistros_ult_12m,
        "fraude_suspeita": match.fraude_suspeita,
        "esg_score": match.esg_score,
        "country_risk": match.country_risk,
        "credit_rating": match.credit_rating,
        "kyc_confidence": match.kyc_confidence,
    }
    models.CONSULTAS[consulta_id] = models.ConsultaCache(consulta_id=consulta_id, payload=payload)

    models.AUDIT_LOG.append(
        models.AuditEntry(
            ts=timestamp,
            user_email=current.email,
            consulta_id=consulta_id,
            identifier=body.identifier,
            identifier_type=body.identifier_type,
            score_final=score_final,
            decisao=decisao
        )
    )

    return {
        "consulta_id": consulta_id,
        "timestamp": timestamp,
        "score_final": score_final,
        "decisao": decisao,
        "justificacao": justificacao,
        "pep_alert": pep_flag,
        "sanctions_alert": sanc_flag,
        "benchmark_internacional": bench,
    }

@app.get("/api/report/{consulta_id}")
def get_report(consulta_id: str, token: str):
    user = models.USERS.get(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    data_cache = models.CONSULTAS.get(consulta_id)
    if not data_cache:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    pdf_path = os.path.join("reports", f"{consulta_id}.pdf")
    if not os.path.exists(pdf_path):
        pdf_generator.generate_pdf(consulta_id, data_cache.payload)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"relatorio_{consulta_id}.pdf"
    )

@app.get("/api/health")
def health():
    return {"status": "ok"}
