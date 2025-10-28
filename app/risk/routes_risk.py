from fastapi import APIRouter, Depends, HTTPException, Response, Form
from app.auth.security import get_current_user, decode_token
from app.risk.service_risk import run_risk_check
from app.utils.pdf import build_pdf_bytes

router = APIRouter(prefix="/api", tags=["risk"])

_cached_reports = {}

@router.post("/risk-check")
def risk_check(
    identifier: str = Form(...),
    identifier_type: str = Form(...),
    user = Depends(get_current_user)
):
    result = run_risk_check(
        user_name=user["name"],
        identifier=identifier,
        identifier_type=identifier_type
    )
    _cached_reports[result["consulta_id"]] = result
    return result

@router.get("/report/{consulta_id}")
def get_report_pdf(consulta_id: str, token: str):
    try:
        decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

    rep = _cached_reports.get(consulta_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    pdf_bytes = build_pdf_bytes(rep)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="relatorio_{consulta_id}.pdf"'
        }
    )
