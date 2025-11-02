import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def _h(text, size=12):
    return Paragraph(f"<para spaceAfter=6><font size='{size}'><b>{text}</b></font></para>", getSampleStyleSheet()['Normal'])

def _table(rows):
    t = Table(rows, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.25,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('FONT',(0,0),(-1,-1),'Helvetica',9),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white, colors.HexColor('#F7F7F7')])
    ]))
    return t

def render_pdf(path, meta: dict):
    ensure_dir(os.path.dirname(path) or ".")
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=18*mm, bottomMargin=18*mm)
    story = []
    styles = getSampleStyleSheet()
    story += [Paragraph("<b>Check Insurance Risk • Relatório de Due Diligence</b>", styles['Title']), Spacer(1,6)]
    id_rows = [["ID Consulta", meta.get("consulta_id","—")],["Data/Hora", meta.get("timestamp","—")],
               ["Identificador", meta.get("identifier","—")],["Tipo", meta.get("identifier_type","—")]]
    story += [_h("1. Identificação"), _table(id_rows), Spacer(1,6)]
    res_rows = [["Score Final", str(meta.get("score_final","—"))],["Decisão", meta.get("decisao","—")],
                ["Justificação", meta.get("justificacao","—")]]
    story += [_h("2. Resultado & Decisão"), _table(res_rows), Spacer(1,6)]
    risco_rows = [["PEP", str(meta.get("pep_alert"))],["Sanções", str(meta.get("sanctions_alert"))],
                  ["Fraude Suspeita", str(meta.get("fraude_suspeita"))],
                  ["Histórico Pagamentos", meta.get("historico_pagamentos","—")],
                  ["Sinistros (total / 12m)", f"{meta.get('sinistros_total','—')} / {meta.get('sinistros_ult_12m','—')}"],
                  ["ESG Score", str(meta.get("esg_score","—"))],["País (Risco)", meta.get("country_risk","—")],
                  ["Rating Crédito", meta.get("credit_rating","—")],["Confiança KYC", meta.get("kyc_confidence","—")]]
    story += [_h("3. Indicadores de Risco"), _table(risco_rows), Spacer(1,6)]
    comp_rows = [["Benchmarks", meta.get("benchmark_internacional","—")],
                 ["Referências", "FATF Rec.10, OECD KYC, BODIVA Market Rules (quando aplicável)"]]
    story += [_h("4. Conformidade & Benchmarks"), _table(comp_rows), Spacer(1,12)]
    story += [Paragraph("<font size=9>Gerado automaticamente pelo CIR. Sujeito a validação humana.</font>", styles['Normal'])]
    doc.build(story)
