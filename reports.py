from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from jose import JWTError
from auth import get_current_user, verify_token
from risk_engine import get_analysis

router = APIRouter(prefix="/api", tags=["report"])

def build_pdf(analysis) -> BytesIO:
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    lines = [
        "CHECK INSURANCE RISK - RELATÓRIO TÉCNICO",
        "---------------------------------------",
        f"Consulta ID: {analysis.consulta_id}",
        f"Data/Hora (UTC): {analysis.timestamp}",
        f"Identificador: {analysis.identifier}",
        f"Tipo Identificador: {analysis.identifier_type}",
        f"Score Final: {analysis.score_final}/100",
        f"Decisão: {analysis.decisao}",
        f"Justificação: {analysis.justificacao}",
        f"Alerta Sanções: {'SIM' if analysis.sanctions_alert else 'NÃO'}",
        f"Alerta PEP: {'SIM' if analysis.pep_alert else 'NÃO'}",
        "Assinatura técnica: Check Insurance Risk - Motor de Compliance"
    ]
    for line in lines:
        p.drawString(50, y, line); y -= 20
    p.showPage(); p.save(); buffer.seek(0)
    return buffer

@router.get("/report/{consulta_id}")
def get_report(consulta_id: str, request: Request, token: str = None, user=Depends(get_current_user)):
    if not token:
        token = request.query_params.get("token")
    if token:
        try:
            verify_token(token)
        except JWTError:
            raise HTTPException(status_code=401, detail="Token inválido")

    analysis = get_analysis(consulta_id)
    pdf_buffer = build_pdf(analysis)
    headers = {
        "Content-Disposition": f'attachment; filename="relatorio_{consulta_id}.pdf"'
    }
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)
