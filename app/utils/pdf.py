from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

def build_pdf_bytes(risk_report: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    h1 = styles["Heading1"]
    h1.textColor = colors.HexColor("#0f172a")
    story.append(Paragraph("CHECK INSURANCE RISK", h1))
    story.append(Paragraph("<b>Motor de Compliance e Suporte Técnico de Subscrição</b>", styles["Heading3"]))
    story.append(Spacer(1, 12))

    info_table = [
        ["Consulta ID:", risk_report.get("consulta_id", "")],
        ["Data/Hora:", risk_report.get("timestamp", "")],
        ["Score Final:", f"{risk_report.get('score_final','')} / 100"],
        ["Decisão Recomendada:", risk_report.get("decisao", "")],
        ["Alerta PEP:", "Sim" if risk_report.get("pep_alert") else "Não"],
        ["Alerta Sanções:", "Sim" if risk_report.get("sanctions_alert") else "Não"],
        ["Justificação Técnica:", risk_report.get("justificacao", "")],
        ["Benchmark Internacional:", risk_report.get("benchmark_internacional", "")],
    ]

    table = Table(info_table, colWidths=[5*cm, 10*cm])
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
        ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(table)
    story.append(Spacer(1, 18))

    block_details = f"""
    <b>Detalhes Técnicos</b><br/>
    Score Final: {risk_report.get('score_final','')} /100<br/>
    Decisão Recomendada: {risk_report.get('decisao','')}<br/>
    Justificação Técnica: {risk_report.get('justificacao','')}<br/>
    Alerta Sanções: {"Sim" if risk_report.get("sanctions_alert") else "Não"}<br/>
    Alerta PEP / Exposição Política: {"Sim" if risk_report.get("pep_alert") else "Não"}<br/>
    Histórico de Pagamentos: {risk_report.get("historico_pagamentos","Sem registo interno.")}<br/>
    Sinistros Totais: {risk_report.get("sinistros_total","0")}<br/>
    Sinistros Últimos 12 Meses: {risk_report.get("sinistros_12m","0")}<br/>
    Nota de Fraude / Abuso: {risk_report.get("nota_fraude","")}<br/>
    """
    story.append(Paragraph(block_details, styles["Normal"]))
    story.append(Spacer(1, 12))

    block_hist = f"""
    <b>Histórico de Comportamento e Sinistros</b><br/>
    Pagamentos: {risk_report.get("historico_pagamentos","Sem registo interno.")}<br/>
    Sinistros registados: {risk_report.get("sinistros_total","0")} no total,
    {risk_report.get("sinistros_12m","0")} nos últimos 12 meses.<br/>
    Não existem indicadores activos de fraude.<br/>
    """
    story.append(Paragraph(block_hist, styles["Normal"]))
    story.append(Spacer(1, 12))

    block_conf = """
    <b>Notas e Conformidade</b><br/>
    Esta análise resulta da consolidação de fontes internas e externas autorizadas pela seguradora.
    O score técnico e a decisão recomendada servem como apoio à subscrição e compliance e não
    substituem a avaliação humana em casos de risco elevado, suspeita de fraude ou quando existam
    alertas PEP / sanções.
    """
    story.append(Paragraph(block_conf, styles["Normal"]))
    story.append(Spacer(1, 24))

    footer_text = (
        "<b>Assinatura Técnica</b><br/>"
        "Check Insurance Risk — Motor de Compliance<br/>"
        "CONFIDENCIAL • USO INTERNO"
    )
    story.append(Paragraph(footer_text, styles["Normal"]))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
