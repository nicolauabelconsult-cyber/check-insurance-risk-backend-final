import json, os, re
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from models import InfoSource
from extractors import run_extractor

CACHE = "./watchlist_cache.json"

def _load_cache() -> Dict:
    if os.path.exists(CACHE):
        try:
            with open(CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"pep_names": []}

def _save_cache(obj: Dict):
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _norm_name(s: str) -> str:
    s = (s or "").strip().upper()
    s = re.sub(r"\s+", " ", s)
    return s

def rebuild_watchlist(db: Session):
    """Reconstrói cache de nomes PEP a partir das InfoSources."""
    rows = db.query(InfoSource).all()
    pep: List[str] = []
    for r in rows:
        kind = (r.categoria or "").strip().lower()
        url = (r.url or "").strip()
        if not kind or not url:
            continue
        try:
            facts = run_extractor(kind, url, hint=r.validade)
            for f in facts:
                n = _norm_name(f.get("name"))
                if n and n not in pep:
                    pep.append(n)
        except Exception:
            # ignora falhas pontuais de scraping
            pass
    _save_cache({"pep_names": pep})
    return pep

def is_pep_name(name: str, db: Session = None) -> bool:
    # usa cache; se vazia e temos sessao, tenta reconstruir
    cache = _load_cache()
    pep = cache.get("pep_names", [])
    if not pep and db is not None:
        pep = rebuild_watchlist(db)
    n = _norm_name(name)
    return any(n == p or n in p or p in n for p in pep if p)

def build_facts_from_sources(identifier_value: str, identifier_type: str, db: Session) -> Dict:
    """
    Hoje: só sinaliza PEP por nome através da watchlist/scraping.
    Mantém formato: {'pep': {...}, 'sanctions': {...}, 'ai_status': 'ok'|'no_match'|'no_data', 'ai_reason': str}
    """
    if not (identifier_value and identifier_type):
        return {"ai_status": "no_data", "ai_reason": "Sem identificador."}

    idt = (identifier_type or "").strip().lower()
    if idt not in {"nome", "name"}:
        return {"ai_status": "no_data", "ai_reason": "Análise por fontes só disponível para 'Nome'."}

    name = _norm_name(identifier_value)
    # garante cache
    cache = _load_cache()
    pep_names = cache.get("pep_names", [])
    if not pep_names:
        pep_names = rebuild_watchlist(db)

    for p in pep_names:
        if name == p or name in p or p in name:
            return {
                "ai_status": "ok",
                "ai_reason": "Nome combina com fonte governamental.",
                "pep": {"value": True, "matched_name": p, "source": "watchlist/scraping", "cargo": "Ministro(a)", "score": 0.95},
                "sanctions": {"value": False},
            }

    return {"ai_status": "no_match", "ai_reason": "Nenhuma correspondência nas fontes.", "pep": {"value": False}, "sanctions": {"value": False}}
