# ai_pipeline.py
from typing import Dict, Optional
from sqlalchemy.orm import Session
from models import InfoSource
from extractors import run_extractor

def rebuild_watchlist(db: Session) -> None:
    # opcional: se quiser pré-carregar para cache/ficheiro; não obrigatório
    pass

def build_facts_from_sources(
    identifier_value: Optional[str] = None,
    identifier_type: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict:
    """
    Se 'identifier_type' for 'Nome', tenta encontrar correspondência PEP nas fontes.
    """
    out = {
        "ai_status": "no_data",
        "ai_reason": "Sem fontes configuradas ou sem resultados.",
        "pep": {"value": False},
        "sanctions": {"value": False},
    }
    if db is None:
        return out

    sources = db.query(InfoSource).order_by(InfoSource.id.desc()).all()
    if not sources:
        out["ai_reason"] = "Nenhuma fonte registada."
        return out

    name = (identifier_value or "").strip()
    t = (identifier_type or "").strip().lower()
    any_hits = False

    for s in sources:
        kind = (s.categoria or "").strip().lower()
        url_or_path = s.url or (
            f"{(s.directory or '').rstrip('/')}/{(s.filename or '').lstrip('/')}"
            if s.directory and s.filename else None
        )
        if not kind or not url_or_path:
            continue

        try:
            facts = run_extractor(kind, url_or_path, hint=s.validade)
        except Exception:
            continue

        # matching simples por igualdade (normalizar maiúsculas/mínusculas e espaços)
        if name and t in {"nome", "name"}:
            for f in facts:
                cand = (f.get("name") or "").strip().lower()
                if cand and cand == name.strip().lower():
                    out["pep"] = {
                        "value": True,
                        "matched_name": f.get("name"),
                        "cargo": f.get("cargo"),
                        "score": 0.95,
                        "source": s.title or s.url or s.filename,
                    }
                    any_hits = True
                    break

    out["ai_status"] = "ok" if any_hits else "no_match"
    out["ai_reason"] = "Correspondência exata por nome." if any_hits else "Nenhuma correspondência pelo nome."
    return out

# opcional, se quiser chamar diretamente
def is_pep_name(name: str, db: Session) -> bool:
    res = build_facts_from_sources(identifier_value=name, identifier_type="Nome", db=db)
    return bool(res.get("pep", {}).get("value"))
