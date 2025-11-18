"""
Módulo de relatórios
"""
import json
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64


def _safe_load_json(value, default):
    """
    Helper para carregar JSON vindo do Postgres.

    Aceita:
    - string JSON
    - list/dict já desserializado (json/jsonb)
    - None
    """
    if value is None:
        return default
    # Se já é lista/dict (caso de coluna json/jsonb devolvida como Python)
    if isinstance(value, (list, dict)):
        return value
    # Se for string, tenta fazer json.loads
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    # Qualquer outro tipo inesperado
    return default


def generate_risk_report(risk_record: Dict[str, Any]) -> Dict[str, Any]:
    """Gerar relatório detalhado de análise de risco"""
    try:
        # matches / risk_factors podem vir como jsonb (list/dict) ou como string JSON
        raw_matches = risk_record.get("matches")
        raw_risk_factors = risk_record.get("risk_factors")

        matches = _safe_load_json(raw_matches, [])
        risk_factors = _safe_load_json(raw_risk_factors, [])

        report = {
            "id": risk_record["id"],
            "timestamp": datetime.now().isoformat(),
            "subject": {
                "full_name": risk_record.get("full_name"),
                "nif": risk_record.get("nif"),
                "passport": risk_record.get("passport"),
                "resident_card": risk_record.get("resident_card"),
            },
            "risk_assessment": {
                "score": risk_record.get("risk_score", 0),
                "level": risk_record.get("risk_level", "UNKNOWN"),
                "factors": risk_factors,
                "recommendation": get_risk_recommendation(
                    risk_record.get("risk_level", "UNKNOWN"),
                    risk_record.get("risk_score", 0),
                ),
            },
            "matches_found": len(matches),
            "detailed_matches": matches,
            "analysis_metadata": {
                "analyzed_at": risk_record.get("analyzed_at"),
                "analyzed_by": risk_record.get("analyzed_by"),
                "decision": risk_record.get("decision"),
                "analyst_notes": risk_record.get("analyst_notes"),
            },
        }

        # Adicionar análise de fontes
        source_analysis = analyze_sources(matches)
        report["source_analysis"] = source_analysis

        return report

    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return {"error": str(e)}

# (resto do ficheiro reporting.py mantém-se igual: get_risk_recommendation,
#  analyze_sources, get_match_risk_score, export_to_excel, generate_pdf_report,
#  generate_dashboard_charts, etc.)
