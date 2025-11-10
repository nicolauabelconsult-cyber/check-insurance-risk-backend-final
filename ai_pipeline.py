# ai_pipeline.py
from sqlalchemy.orm import Session
from models import InfoSource
from extractors import run_extractor

def build_facts_from_sources(identifier_value: str | None = None,
                             identifier_type: str | None = None,
                             db: Session | None = None) -> dict:
    out = {"ai_status":"no_data","ai_reason":"Sem fontes configuradas.","pep":{}, "sanctions":{}}
    if not db:
        return out

    sources = db.query(InfoSource).all()
    if not sources:
        return out

    found = []
    for s in sources:
        kind = (s.categoria or "").strip().lower()
        url_or_path = s.url or (f"{(s.directory or '').rstrip('/')}/{(s.filename or '').lstrip('/')}" if s.directory and s.filename else None)
        if not kind or not url_or_path:
            continue
        try:
            facts = run_extractor(kind, url_or_path, hint=s.validade)
            found.extend(facts)
        except Exception:
            continue

    if not found:
        out["ai_status"]="no_match"; out["ai_reason"]="Sem correspondências nas fontes."
        return out

    # match muito simples por nome
    name_q = (identifier_value or "").strip().lower()
    for f in found:
        if f.get("type") == "pep" and name_q and name_q in (f.get("name","").lower()):
            out["pep"] = {"value": True, "matched_name": f.get("name"), "cargo": f.get("cargo"), "source": f.get("source"), "score": f.get("score")}
            out["ai_status"]="ok"; out["ai_reason"]="Correspondência encontrada."
            break

    return out

# (opcional)
def rebuild_watchlist(db: Session):  # agora “noop”, mantemos para compatibilidade
    return
