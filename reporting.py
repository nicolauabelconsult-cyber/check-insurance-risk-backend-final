# reporting.py
import os
import json
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors

from sqlalchemy.orm import Session
from models import RiskRecord
from utils import ensure_dir


REPORTS_DIR = "data/reports"


def build_risk_report_pdf(db: Session, record_id: int, base_app_url: str) -> str:
    """
    Gera um PDF interactivo e fácil de interpretar para o RiskRecord dado.
    base_app_url: ex. "https://check-insurance-risk.netlify.app"
    Retorna o caminho do ficheiro PDF gerado.
    """
    ensure_dir(REPORTS_DIR)

    record: RiskRecord = db.query(RiskRecord).filter(RiskRecord.id == record_id).first()
    if not record:
        raise ValueError("RiskRecord não encontrado")

    matches = json.loads(record.matches_json)
    factors = json.loads(record.factors_json)

    file_path = os.path.join(REPORTS_DIR, f"risk_report_{record.id}.pdf")

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Relatório de Risco #{record.id}",
        author=record.analyst.full_name if record.analyst else "Check Insurance Risk",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=1))
    styles.add(ParagraphStyle(name="SectionTitle", parent=styles["Heading2"], spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=9))

    elements: List = []

    # --- Cabeçalho / página 1 ---
    elements.append(Paragraph("Relatório de Análise de Risco", styles["TitleCenter"]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph(f"ID da Consulta: <b>{record.id}</b>", styles["Normal"]))
    elements.append(Paragraph(f"Data/Hora: {record.created_at.isoformat()}", styles["Normal"]))
    if record.analyst:
        elements.append(Paragraph(f"Analista: {record.analyst.full_name} ({record.analyst.username})", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    # Link clicável de volta ao sistema (interactivo)
    report_url = f"{base_app_url}/reports/{record.id}"
    elements.append(
        Paragraph(
            f'Consulta online: <a href="{report_url}">{report_url}</a>',
            styles["Small"],
        )
    )
    elements.append(Spacer(1, 0.5 * cm))

    # --- Identificação do cliente ---
    elements.append(Paragraph("1. Identificação do Cliente", styles["SectionTitle"]))

    client_table_data = [
        ["Nome completo", record.full_name],
        ["NIF", record.nif or "-"],
        ["Passaporte", record.passport or "-"],
        ["Cartão de Residente", record.residence_card or "-"],
    ]
    client_table = Table(client_table_data, hAlign="LEFT", colWidths=[4 * cm, 10 * cm])
    client_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(client_table)
    elements.append(Spacer(1, 0.5 * cm))

    # --- Resumo executivo ---
    elements.append(Paragraph("2. Resumo Executivo de Risco", styles["SectionTitle"]))

    elements.append(
        Paragraph(
            f"Score de risco global: <b>{record.risk_score}</b> "
            f"({record.risk_level})",
            styles["Normal"],
        )
    )

    pep_txt = "SIM" if record.is_pep else "NÃO"
    sanc_txt = "SIM" if record.has_sanctions else "NÃO"

    elements.append(Paragraph(f"PEP: <b>{pep_txt}</b>", styles["Normal"]))
    elements.append(Paragraph(f"Presença em listas de sanções: <b>{sanc_txt}</b>", styles["Normal"]))
    elements.append(Spacer(1, 0.3 * cm))

    # Factores principais
    if factors:
        elements.append(Paragraph("Principais factores de risco:", styles["Normal"]))
        for f in factors:
            elements.append(
                Paragraph(f"• {f['description']} (peso: {f['weight']})", styles["Normal"])
            )
    else:
        elements.append(Paragraph("Não foram identificados factores de risco relevantes.", styles["Normal"]))

    elements.append(Spacer(1, 0.5 * cm))

    # Decisão
    if record.decision:
        decision_map = {
            "ACCEPT": "Aceitar",
            "CONDITIONAL": "Aceitar com condições",
            "REJECT": "Recusar",
        }
        decision_label = decision_map.get(record.decision, record.decision)
        elements.append(
            Paragraph(f"Decisão do analista: <b>{decision_label}</b>", styles["Normal"])
        )
    if record.analyst_notes:
        elements.append(Spacer(1, 0.2 * cm))
        elements.append(
            Paragraph(f"Observações do analista: {record.analyst_notes}", styles["Normal"])
        )

    elements.append(Spacer(1, 0.8 * cm))

    # --- Detalhe dos matches ---
    elements.append(Paragraph("3. Registos encontrados nas fontes", styles["SectionTitle"]))

    if matches:
        matches_table_data = [
            ["Fonte", "Tipo", "Nome encontrado", "Identificador", "Similaridade"]
        ]
        for m in matches:
            matches_table_data.append(
                [
                    m.get("source_name"),
                    m.get("source_type"),
                    m.get("match_name"),
                    m.get("match_identifier") or "-",
                    f"{m.get('similarity', 0)*100:.1f}%",
                ]
            )

        matches_table = Table(matches_table_data, hAlign="LEFT")
        matches_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(matches_table)
    else:
        elements.append(
            Paragraph("Não foram encontrados registos relevantes nas fontes consultadas.", styles["Normal"])
        )

    elements.append(Spacer(1, 0.8 * cm))

    # --- Rodapé / nota legal ---
    elements.append(Paragraph("4. Nota de enquadramento", styles["SectionTitle"]))
    elements.append(
        Paragraph(
            "Este relatório foi gerado automaticamente pelo sistema Check Insurance Risk "
            "com base nas fontes de informação disponíveis à data da consulta. As conclusões "
            "são indicativas e devem ser enquadradas com a política de risco da seguradora.",
            styles["Small"],
        )
    )

    doc.build(elements)
    return file_path
