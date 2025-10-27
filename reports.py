from fastapi import APIRouter, HTTPException, Response, Query, Depends
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from storage import ANALYSES_DB
from auth import get_current_user

router = APIRouter(prefix="/api", tags=["reports"])

@router.get("/report/{consulta_id}")
def get_report(consulta_id: str, token: str = Query(None), user=Depends(get_current_user)):
    analysis = ANALYSES_DB.get(consulta_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")

    pdf_buffer = build_pdf(analysis)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="relatorio_{consulta_id}.pdf"'
        },
    )

def build_pdf(analysis: dict) -> BytesIO:
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    PAGE_W, PAGE_H = A4
    margin_left = 20 * mm
    margin_right = 20 * mm
    cursor_y = PAGE_H - 20 * mm

    header_height = 22 * mm
    p.setFillColorRGB(0.07, 0.1, 0.18)
    p.rect(0, PAGE_H - header_height, PAGE_W, header_height, fill=1, stroke=0)

    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(margin_left, PAGE_H - 10 * mm, "CHECK INSURANCE RISK")

    p.setFont("Helvetica", 8.5)
    p.setFillColorRGB(0.55, 0.8, 1)
    p.drawString(
        margin_left,
        PAGE_H - 14.5 * mm,
        "Motor de Compliance e Suporte Técnico de Subscrição"
    )

    p.setStrokeColorRGB(0.55, 0.8, 1)
    p.setLineWidth(0.6)
    p.line(
        margin_left,
        PAGE_H - header_height,
        PAGE_W - margin_right,
        PAGE_H - header_height
    )

    cursor_y = PAGE_H - header_height - 8 * mm

    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(margin_left, cursor_y, "Dados da Consulta")
    cursor_y -= 6 * mm

    p.setFont("Helvetica", 9)
    meta_lines = [
        f"Consulta ID: {analysis['consulta_id']}",
        f"Data/Hora (UTC): {analysis['timestamp']}",
        f"Identificador analisado: {analysis.get('identifier','-')}",
        f"Tipo de Identificador: {analysis.get('identifier_type','-')}",
    ]
    for line in meta_lines:
        p.drawString(margin_left, cursor_y, line)
        cursor_y -= 5.2 * mm

    cursor_y -= 4 * mm
    p.setStrokeColor(colors.grey)
    p.setLineWidth(0.3)
    p.line(margin_left, cursor_y, PAGE_W - margin_right, cursor_y)
    cursor_y -= 8 * mm

    decisao_txt = (analysis["decisao"] or "").lower()
    if "escalar" in decisao_txt or "elevado" in decisao_txt or "recusar" in decisao_txt:
        box_color = colors.Color(0.95, 0.27, 0.27)
        box_text_color = colors.white
        risco_label = "Risco Elevado"
    elif "condi" in decisao_txt:
        box_color = colors.Color(0.98, 0.87, 0.3)
        box_text_color = colors.black
        risco_label = "Risco Moderado"
    else:
        box_color = colors.Color(0.36, 0.83, 0.50)
        box_text_color = colors.black
        risco_label = "Risco Controlado"

    box_h = 22 * mm
    box_w = PAGE_W - margin_left - margin_right
    box_y = cursor_y - box_h

    p.setFillColor(box_color)
    p.roundRect(
        margin_left, box_y, box_w, box_h,
        4 * mm, fill=1, stroke=0
    )

    p.setFillColor(box_text_color)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(
        margin_left + 6 * mm,
        box_y + box_h - 7 * mm,
        risco_label
    )

    p.setFont("Helvetica", 9)
    p.drawString(
        margin_left + 6 * mm,
        box_y + box_h - 12 * mm,
        f"Score Final: {analysis['score_final']}/100"
    )
    p.drawString(
        margin_left + 6 * mm,
        box_y + box_h - 16.5 * mm,
        f"Decisão Recomendada: {analysis['decisao']}"
    )

    flags_txt = []
    if analysis.get("pep_alert"):
        flags_txt.append("PEP")
    if analysis.get("sanctions_alert"):
        flags_txt.append("Listas de Sanções")
    flags_line = "Sem alertas PEP / Sanções" if not flags_txt else "Alertas: " + " / ".join(flags_txt)

    p.drawString(
        margin_left + 6 * mm,
        box_y + box_h - 21 * mm,
        flags_line
    )

    cursor_y = box_y - 10 * mm

    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(margin_left, cursor_y, "Detalhes Técnicos")
    cursor_y -= 6 * mm

    p.setFont("Helvetica", 9)

    detalhes = [
        ("Score Final", f"{analysis['score_final']}/100"),
        ("Decisão Recomendada", analysis["decisao"]),
        ("Justificação Técnica", analysis.get("justificacao","-")),
        ("Alerta Sanções", "SIM" if analysis.get("sanctions_alert") else "NÃO"),
        ("Alerta PEP / Exposição Política", "SIM" if analysis.get("pep_alert") else "NÃO"),
    ]

    col_key_w = 60 * mm
    col_val_w = PAGE_W - margin_left - margin_right - col_key_w
    row_h = 8 * mm

    for label_text, value_text in detalhes:
        if cursor_y - row_h < 25 * mm:
            _draw_footer(p, PAGE_W, margin_left, margin_right)
            p.showPage()
            cursor_y = PAGE_H - 25 * mm
            p.setFont("Helvetica-Bold", 10)
            p.drawString(margin_left, cursor_y, "Detalhes Técnicos (cont.)")
            cursor_y -= 8 * mm
            p.setFont("Helvetica", 9)

        p.setFillColorRGB(0.11, 0.14, 0.2)
        p.rect(
            margin_left,
            cursor_y - row_h + 1.5 * mm,
            col_key_w,
            row_h,
            fill=1,
            stroke=0
        )
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 8.5)
        p.drawString(
            margin_left + 3 * mm,
            cursor_y - 3 * mm,
            label_text
        )

        p.setFillColorRGB(0.17, 0.2, 0.28)
        p.rect(
            margin_left + col_key_w,
            cursor_y - row_h + 1.5 * mm,
            col_val_w,
            row_h,
            fill=1,
            stroke=0
        )

        p.setFillColor(colors.white)
        p.setFont("Helvetica", 8.5)

        wrapped = wrap_text(str(value_text), max_chars=60)
        line_y = cursor_y - 3 * mm
        for line in wrapped:
            p.drawString(
                margin_left + col_key_w + 3 * mm,
                line_y,
                line
            )
            line_y -= 4 * mm

        cursor_y -= row_h + (max(0, (len(wrapped)-1)) * 4 * mm)
        cursor_y -= 2 * mm

    cursor_y -= 4 * mm
    p.setStrokeColor(colors.grey)
    p.setLineWidth(0.3)
    p.line(margin_left, cursor_y, PAGE_W - margin_right, cursor_y)
    cursor_y -= 8 * mm

    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(margin_left, cursor_y, "Notas e Conformidade")
    cursor_y -= 6 * mm

    p.setFont("Helvetica", 8.5)
    p.setFillColor(colors.black)

    obs_lines = [
        "Esta análise resulta da consolidação de fontes internas e externas autorizadas",
        "pela seguradora. O score técnico e a decisão recomendada servem como apoio à",
        "subscrição e compliance, e não substituem a avaliação humana em casos de risco",
        "elevado ou quando existam alertas PEP / sanções.",
        "",
        "Assinatura técnica:",
        "Check Insurance Risk — Motor de Compliance",
    ]

    for line in obs_lines:
        if cursor_y < 30 * mm:
            _draw_footer(p, PAGE_W, margin_left, margin_right)
            p.showPage()
            cursor_y = PAGE_H - 25 * mm
            p.setFont("Helvetica", 8.5)
            p.setFillColor(colors.black)
        p.drawString(margin_left, cursor_y, line)
        cursor_y -= 5 * mm

    _draw_footer(p, PAGE_W, margin_left, margin_right)

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

def wrap_text(text, max_chars=60):
    if text is None:
        return [""]
    words = str(text).split()
    lines = []
    cur = []
    cur_len = 0
    for w in words:
        wlen = len(w) + 1
        if cur_len + wlen > max_chars:
            lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += wlen
    if cur:
        lines.append(" ".join(cur))
    return lines

def _draw_footer(p, PAGE_W, margin_left, margin_right):
    footer_h = 10 * mm
    footer_y = 10 * mm

    p.setFillColorRGB(0.15, 0.18, 0.25)
    p.rect(0, 0, PAGE_W, footer_h + footer_y, fill=1, stroke=0)

    p.setFillColorRGB(0.55, 0.8, 1)
    p.setFont("Helvetica-Bold", 8)
    p.drawRightString(
        PAGE_W - margin_right,
        footer_y + 3 * mm,
        "CONFIDENCIAL • USO INTERNO"
    )
