# ai_pipeline.py
from __future__ import annotations
import re
from typing import Dict, Optional
from sqlalchemy.orm import Session
from models import InfoSource
from extractors import run_extractor

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _name_match(q: str, candidate: str) -> bool:
    # Match simples: todos os tokens de q existem em candidate
    qt = _norm(q).split()
    ct = _norm(candidate)
    return all(tok in ct for tok in qt if tok)

def build_facts_from_sources(
    db: Session,
    identifier_value: Optional[str] = None,
    identifier_type: Optional[str] = None,
) -> Dict:
    rows = db.query(InfoSource).order_by(InfoSource.id.desc()).all()

    found_pep = None
    # Aqui poderias adicionar sanções no futuro (outro extractor)
    found_san = None

    for src in rows:
        kind = (src.categoria or "").strip().lower()
        url_or_path = src.url or (
            f"{(src.directory or '').rstrip('/')}/{(src.filename or '').lstrip('/')}" if src.directory and src.filename else None
        )
        if not kind or not url_or_path:
            continue

        try:
            facts = run_extractor(kind, url_or_path, hint=src.validade)
        except Exception:
            continue

        # Se a pesquisa for por nome, tenta match
        if (identifier_type or "").lower() in {"nome", "name"} and identifier_value:
            for f in facts:
                if f.get("type") == "person" and _name_match(identifier_value, f.get("value", "")):
                    found_pep = {"value": True, "matched_name": f.get("value"), "source": url_or_path}
                    break
        if found_pep:
            break

    status = "ok" if (found_pep or found_san) else "no_data"
    reason = (
        "Foi possível consultar as fontes configuradas."
        if status == "ok" else
        "Nenhuma fonte válida com dados estruturáveis foi encontrada para esta pesquisa."
    )

    return {
        "ai_status": status,
        "ai_reason": reason,
        "pep": found_pep or {"value": False},
        "sanctions": found_san or {"value": False},
    }
