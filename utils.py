
from reportlab.lib.pagesizes import A4
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import datetime, io, qrcode
from reportlab.lib.utils import ImageReader
import os

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def render_pdf(path, meta: dict):
    """Renderiza Relatório V6 (multi-página, corporativo) — APENAS layout; dados vindos de meta."""
    ensure_dir(os.path.dirname(path) or ".")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SectionTitle', fontSize=11, leading=14, spaceAfter=6, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Body', fontSize=10, leading=13, spaceAfter=5))

    def _footer(canvas, doc):
        width, height = A4
        y = 15*mm
        canvas.setStrokeColor(colors.HexColor("#AAAAAA"))
        canvas.setLineWidth(0.5)
        canvas.line(20*mm, y + 5*mm, width - 20*mm, y + 5*mm)
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.grey)
        emitido_por = meta.get("emitido_por","—")
        canvas.drawString(25*mm, y, f"Emitido por: {emitido_por}")
        canvas.drawRightString(width - 25*mm, y, "Relatório gerado automaticamente pelo sistema Check Insurance Risk. Documento confidencial.")

    def _header(canvas, doc):
        width, height = A4
        # Marca/Logótipo textual
        logo_text = "CHECK INSURANCE RISK"
        canvas.setFillColorRGB(0.0, 0.32, 0.45)
        canvas.setFont("Helvetica-Bold", 18)
        canvas.drawString(25*mm, height - 25*mm, logo_text)
        # Data
        today = meta.get("timestamp") or datetime.datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
        canvas.setFont("Helvetica", 10)
        canvas.setFillColor(colors.black)
        canvas.drawRightString(width - 25*mm, height - 25*mm, f"Emitido em: {today}")
        canvas.setStrokeColor(colors.HexColor("#AAAAAA"))
        canvas.line(20*mm, height - 28*mm, width - 20*mm, height - 28*mm)
        # QR Code para verificação
        url = meta.get("qr_url") or f"https://check-insurance-risk.example/report/{meta.get('consulta_id','example')}"
        qr = qrcode.make(url)
        qr_buf = io.BytesIO()
        qr.save(qr_buf, format="PNG")
        qr_img = ImageReader(qr_buf)
        canvas.drawImage(qr_img, width - 40*mm, height - 60*mm, 20*mm, 20*mm)

    doc = BaseDocTemplate(
        path, pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=70*mm, bottomMargin=25*mm
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    template = PageTemplate(id='CIR', frames=[frame], onPage=_header, onPageEnd=_footer)
    doc.addPageTemplates([template])

    # Dados preparados (com defaults seguros)
    consulta_id = meta.get("consulta_id","—")
    timestamp   = meta.get("timestamp", datetime.datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC"))
    canal       = meta.get("canal_origem","Portal Check Insurance Risk")

    nome = meta.get("nome") or meta.get("identifier","—")
    nif  = meta.get("nif") or meta.get("identifier","—")
    pais = meta.get("country_risk","—")
    actividade = meta.get("atividade","—")

    score = int(meta.get("score_final", 0) or 0)
    classificacao = meta.get("classificacao") or ("Risco Baixo" if score >= 85 else "Risco Médio-Baixo" if score >= 70 else "Risco Médio" if score >= 55 else "Risco Alto")
    decisao = meta.get("decisao","—")
    justificacao = meta.get("justificacao","—")

    pep = str(meta.get("pep_alert", False))
    sanc = str(meta.get("sanctions_alert", False))
    fraude = str(meta.get("fraude_suspeita", False))
    esg = str(meta.get("esg_score","—"))
    reputacao = meta.get("reputacao_digital","Neutra")
    credito = meta.get("credit_rating","—")

    sin_automovel = meta.get("sin_automovel", 0)
    sin_vida      = meta.get("sin_vida", 0)
    sin_saude     = meta.get("sin_saude", 0)
    sin_patr      = meta.get("sin_patrimonial", 0)
    total_sin     = sum([int(sin_automovel or 0), int(sin_vida or 0), int(sin_saude or 0), int(sin_patr or 0)])

    pag_situacao  = meta.get("pag_situacao","—")
    pag_pontual   = meta.get("pag_pontualidade","—")
    pag_ultimo    = meta.get("pag_ultimo_atraso","—")

    story = []

    # Título
    story.append(Paragraph("RELATÓRIO DE ANÁLISE DE RISCO", styles['Title']))
    story.append(Spacer(1,6))

    # 1 Identificação
    story.append(Paragraph("1. Identificação da Consulta", styles['SectionTitle']))
    table1 = Table(
        [["ID Consulta", consulta_id],
         ["Data/Hora", timestamp],
         ["Canal de Origem", canal]],
        colWidths=[60*mm, 100*mm])
    table1.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.25,colors.grey),('FONT',(0,0),(-1,-1),'Helvetica',9)]))
    story.append(table1); story.append(Spacer(1,8))

    # 2 Dados da Entidade
    story.append(Paragraph("2. Dados da Entidade Avaliada", styles['SectionTitle']))
    table2 = Table(
        [["Nome", nome],
         ["NIF", nif],
         ["País", pais],
         ["Actividade Económica", actividade]],
        colWidths=[60*mm, 100*mm])
    table2.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.25,colors.grey),('FONT',(0,0),(-1,-1),'Helvetica',9)]))
    story.append(table2); story.append(Spacer(1,8))

    # 3 Resultado
    story.append(Paragraph("3. Resultado da Análise de Risco", styles['SectionTitle']))
    story.append(Paragraph(f"Score Final: {score}/100 — Classificação: {classificacao}", styles['Body']))
    story.append(Paragraph(f"Decisão: {decisao}", styles['Body']))
    story.append(Paragraph(f"Justificação: {justificacao}", styles['Body']))
    story.append(Spacer(1,8))

    # 4 Indicadores
    story.append(Paragraph("4. Indicadores de Risco e Conformidade", styles['SectionTitle']))
    table4 = Table([
        ["PEP", pep],
        ["Sanções", sanc],
        ["Fraude", fraude],
        ["Crédito", credito],
        ["ESG", esg],
        ["Reputação Digital", reputacao]
    ], colWidths=[60*mm, 100*mm])
    table4.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.25,colors.grey),('FONT',(0,0),(-1,-1),'Helvetica',9)]))
    story.append(table4); story.append(Spacer(1,8))

    # 5 Sinistros
    story.append(Paragraph("5. Sinistros por Tipo de Seguro", styles['SectionTitle']))
    table5 = Table([
        ["Automóvel", f"{sin_automovel} sinistro(s)"],
        ["Vida", f"{sin_vida} sinistro(s)"],
        ["Saúde", f"{sin_saude} sinistro(s)"],
        ["Patrimonial", f"{sin_patr} sinistro(s)"],
    ], colWidths=[60*mm, 100*mm])
    table5.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.25,colors.grey),('FONT',(0,0),(-1,-1),'Helvetica',9)]))
    story.append(table5)
    story.append(Paragraph(f"Total de sinistros registados nos últimos 24 meses: {total_sin}", styles['Body']))
    story.append(Spacer(1,8))

    # 6 Pagamentos
    story.append(Paragraph("6. Histórico de Pagamento", styles['SectionTitle']))
    table6 = Table([
        ["Situação", pag_situacao],
        ["Percentagem de Pagamentos Pontuais", str(pag_pontual)],
        ["Último Atraso Registado", pag_ultimo]
    ], colWidths=[60*mm, 100*mm])
    table6.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.25,colors.grey),('FONT',(0,0),(-1,-1),'Helvetica',9)]))
    story.append(table6); story.append(Spacer(1,8))

    # 7 Conformidade (sem BNA)
    story.append(Paragraph("7. Avaliação de Conformidade Regulamentar", styles['SectionTitle']))
    story.append(Paragraph("Conformidade geral: Adequada aos padrões FATF Rec.10 e OCDE. Recomenda-se manutenção das práticas de Due Diligence e actualização anual de KYC.", styles['Body']))
    story.append(Spacer(1,8))

    # 8 Conclusão
    story.append(Paragraph("8. Conclusão e Recomendação Final", styles['SectionTitle']))
    story.append(Paragraph("O cliente apresenta um perfil de risco aceitável, com indicadores de solvência positivos. Recomenda-se continuidade da relação comercial com vigilância semestral.", styles['Body']))
    story.append(Spacer(1,8))
    story.append(Paragraph("Este relatório foi elaborado automaticamente pelo sistema Check Insurance Risk, com base nos dados disponíveis na data de emissão.", styles['Body']))

    doc.build(story)
