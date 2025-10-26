from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
import io

from models import (
    LoginRequest, LoginResponse,
    RiskCheckRequest, RiskCheckResponse,
    ContactRequest, ContactResponse
)
from services import (
    authenticate,
    analisar_risco,
    gerar_pdf_relatorio,
    registar_contacto
)

app = FastAPI(
    title="Check Insurance Risk API",
    version="1.0.0",
    description="API demo para scoring de risco e geração de relatório PDF."
)

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Check Insurance Risk backend vivo",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/login", response_model=LoginResponse)
def api_login(payload: LoginRequest):
    token = authenticate(payload.email, payload.password)
    return {
        "token": token,
        "user": {"email": payload.email}
    }

@app.post("/api/risk-check", response_model=RiskCheckResponse)
def api_risk_check(body: RiskCheckRequest):
    resultado = analisar_risco(body.identificador)
    return resultado

@app.get("/api/report/{consulta_id}")
def api_report(consulta_id: str):
    pdf_bytes = gerar_pdf_relatorio(consulta_id)
    if pdf_bytes is None:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="relatorio_{consulta_id}.pdf"'
        },
    )

@app.post("/api/contact", response_model=ContactResponse)
def api_contact(body: ContactRequest):
    registar_contacto(
        body.nome,
        body.email,
        body.mensagem,
        body.assunto
    )
    return {
        "status": "ok",
        "message": "Pedido registado"
    }
