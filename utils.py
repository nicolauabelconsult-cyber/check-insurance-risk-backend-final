import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def render_pdf(path, meta: dict):
    c = canvas.Canvas(path, pagesize=A4)
    W, H = A4
    x, y = 20*mm, H - 20*mm
    c.setFont("Helvetica-Bold", 14); c.drawString(x, y, "Check Insurance Risk • Relatório Técnico")
    y -= 10*mm; c.setFont("Helvetica", 10)

    def line(label, val):
        nonlocal y
        wrap = simpleSplit(str(val), "Helvetica", 10, W - 40*mm)
        c.setFont("Helvetica-Bold", 10); c.drawString(x, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(x + 45*mm, y, wrap[0] if wrap else "")
        y -= 6*mm
        for w in wrap[1:]:
            c.drawString(x + 45*mm, y, w)
            y -= 6*mm

    order = [
        "consulta_id","timestamp","identifier","identifier_type","nome","nif","bi","passaporte","cartao_residente",
        "score_final","decisao","justificacao","pep_alert","sanctions_alert","historico_pagamentos","sinistros_total",
        "sinistros_ult_12m","fraude_suspeita","comentario_fraude","esg_score","country_risk","credit_rating",
        "kyc_confidence","benchmark_internacional"
    ]
    for k in order:
        if k in meta and meta[k] is not None:
            line(k.replace("_", " ").title(), meta[k])

    c.showPage(); c.save()
