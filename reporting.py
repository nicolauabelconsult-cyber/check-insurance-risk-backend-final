
import base64
import io
from datetime import datetime
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from database import execute_query


def export_to_excel(data: List[Dict[str, Any]], filename: str = None) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        if filename is None:
            filename = f"risk_analysis_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Risk Analysis", index=False)
            workbook = writer.book
            worksheet = writer.sheets["Risk Analysis"]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value is not None and len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except Exception:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

        buffer.seek(0)
        excel_data = buffer.read()
        excel_base64 = base64.b64encode(excel_data).decode("utf-8")
        return {
            "filename": filename,
            "data": excel_base64,
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
    except Exception as e:
        print(f"Erro ao exportar Excel: {e}")
        return {"error": str(e)}


def generate_pdf_report(risk_record: Dict[str, Any]) -> Dict[str, Any]:
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story: List[Any] = []

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=30,
            textColor=colors.HexColor("#2563EB"),
        )
        story.append(Paragraph("Relatório de Análise de Risco", title_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Dados do Analisado", styles["Heading2"]))
        subject_data = [
            ["Nome Completo:", risk_record.get("full_name", "N/A")],
            ["NIF:", risk_record.get("nif", "N/A")],
            ["Passaporte:", risk_record.get("passport", "N/A")],
            ["Cartão Residente:", risk_record.get("resident_card", "N/A")],
        ]
        subject_table = Table(subject_data, colWidths=[2 * inch, 4 * inch])
        subject_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.grey),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("BACKGROUND", (1, 0), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        story.append(subject_table)
        story.append(Spacer(1, 12))

        story.append(Paragraph("Resultado da Análise", styles["Heading2"]))
        risk_level = risk_record.get("risk_level", "UNKNOWN")
        risk_score = risk_record.get("risk_score", 0)

        level_colors = {
            "LOW": colors.green,
            "MEDIUM": colors.orange,
            "HIGH": colors.red,
            "CRITICAL": colors.darkred,
        }
        level_color = level_colors.get(risk_level, colors.grey)

        result_data = [
            ["Nível de Risco:", risk_level],
            ["Score de Risco:", str(risk_score)],
            ["Data da Análise:", risk_record.get("analyzed_at", "N/A")],
        ]
        result_table = Table(result_data, colWidths=[2 * inch, 4 * inch])
        result_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.grey),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("BACKGROUND", (1, 1), (1, 1), level_color),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        story.append(result_table)
        story.append(Spacer(1, 12))

        doc.build(story)
        buffer.seek(0)
        pdf_data = buffer.read()
        pdf_base64 = base64.b64encode(pdf_data).decode("utf-8")
        return {
            "filename": f"risk_report_{risk_record['id']}.pdf",
            "data": pdf_base64,
            "content_type": "application/pdf",
        }
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        return {"error": str(e)}


def generate_dashboard_charts() -> Dict[str, str]:
    try:
        rows = execute_query(
            """
            SELECT risk_level, COUNT(*) AS count
            FROM risk_records
            WHERE risk_level IS NOT NULL
            GROUP BY risk_level
            """
        )
        levels = [r["risk_level"] for r in rows]
        counts = [r["count"] for r in rows]

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(levels, counts)
        ax.set_title("Distribuição de Níveis de Risco")
        ax.set_xlabel("Nível de Risco")
        ax.set_ylabel("Quantidade")

        buffer = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
        buffer.seek(0)
        chart_data = base64.b64encode(buffer.read()).decode("utf-8")
        plt.close(fig)

        return {"chart": chart_data, "content_type": "image/png"}
    except Exception as e:
        print(f"Erro ao gerar gráficos: {e}")
        return {"error": str(e)}
