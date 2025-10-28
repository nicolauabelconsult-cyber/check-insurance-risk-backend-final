from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import os

def generate_pdf(consulta_id: str, data: dict, out_dir: str = "reports"):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{consulta_id}.pdf")

    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    y = h - 50

    lines = [
        "Check Insurance Risk - Relatório Técnico",
        f"Consulta ID: {consulta_id}",
        f"Timestamp: {data.get('timestamp','')}",
        "",
        f"Identificador: {data.get('identifier','')}",
        f"Tipo Identificador: {data.get('identifier_type','')}",
        "",
        f"Score Final: {data.get('score_final','')} /100",
        f"Decisão: {data.get('decisao','')}",
        f"PEP Alert: {data.get('pep_alert','')}",
        f"Sanções Alert: {data.get('sanctions_alert','')}",
        "",
        "Justificação Técnica:",
        data.get("justificacao",""),
        "",
        "Histórico de Pagamentos:",
        data.get("historico_pagamentos",""),
        f"Sinistros Totais: {data.get('sinistros_total','')}",
        f"Sinistros Últimos 12 Meses: {data.get('sinistros_ult_12m','')}",
        f"Fraude Suspeita: {data.get('fraude_suspeita','')}",
        "",
        "ESG / Rating / País / KYC:",
        f"ESG: {data.get('esg_score','')} | Rating: {data.get('credit_rating','')} | País: {data.get('country_risk','')} | KYC: {data.get('kyc_confidence','')}",
        "",
        f"Benchmark Internacional: {data.get('benchmark_internacional','')}",
    ]

    for line in lines:
        c.drawString(40, y, str(line))
        y -= 15
        if y < 80:
            c.showPage()
            y = h - 50

    c.save()
    return path
