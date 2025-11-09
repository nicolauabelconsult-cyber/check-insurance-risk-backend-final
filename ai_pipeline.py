# ai_pipeline.py
import json
import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models import InfoSource
from extractors import run_extractor

CACHE_DIR = "cache"
PEP_JSON = os.path.join(CACHE_DIR, "watch_pep.json")

def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^\w\s]", " ", s, flags=re.I | re.M)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

def _best_match(name: str, pep_list: List[Dict], cutoff: float = 0.86) -> Optional[Dict]:
    best = None
    best_score = 0.0
    for p in pep_list:
        sc = _ratio(name, p.get("name", ""))
        if sc > best_score:
            best = p
            best_score = sc
    if best and best_score >= cutoff:
        best = dict(best)  # copia
        best["score"] = round(best_score, 2)
        return best
    return None

def rebuild_watchlist(db: Session) -> List[Dict]:
    """
    Lê todas as InfoSource e constrói a watchlist (PEP).
    Guarda em cache/watch_pep.json para uso rápido nas consultas.
    """
    _ensure_cache_dir()
    all_facts: List[Dict] = []
    rows = db.query(InfoSource).all()
    for r in rows:
        kind = (r.categoria or "").strip().lower()
        url_or_path = r.url or (f"{(r.directory or '').rstrip('/')}/{(r.filename or '').lstrip('/')}" if (r.directory and r.filename) else None)
        if not kind or not url_or_path:
            continue
        try:
            facts = run_extractor(kind, url_or_path, hint=r.validade)
            all_facts.extend(facts)
        except Exception:
            # manter robusto mesmo que uma fonte falhe
            continue

    # apenas PEP por agora
    pep_list = [f for f in all_facts if f.get("type") == "pep"]

    with open(PEP_JSON, "w", encoding="utf-8") as f:
        json.dump(pep_list, f, ensure_ascii=False, indent=2)
    return pep_list

def _load_peps() -> List[Dict]:
    if not os.path.exists(PEP_JSON):
        return []
    try:
        with open(PEP_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def is_pep_name(name: str) -> Optional[Dict]:
    """
    Verifica se 'name' corresponde a alguém na watchlist PEP.
    Retorna dict com {matched_name, cargo, source, score} ou None.
    """
    pep_list = _load_peps()
    hit = _best_match(name, pep_list)
    if hit:
        return {
            "matched_name": hit.get("name"),
            "cargo": hit.get("cargo"),
            "source": hit.get("source"),
            "score": hit.get("score", 0.0),
        }
    return None

def build_facts_from_sources(
    identifier_value: str = "",
    identifier_type: str = "",
    db: Optional[Session] = None,
) -> Dict:
    """
    Função chamada durante a consulta técnica.
    Usa cache (watchlist) para PEP; pode evoluir com sanções/reguladores.
    """
    ai_status = "ok"
    ai_reason = ""

    pep = {"value": False}
    sanctions = {"value": False}

    # Apenas por nome, por agora
    if (identifier_type or "").strip().lower() in {"nome", "name"}:
        hit = is_pep_name(identifier_value)
        if hit:
            pep = {"value": True, **hit}
            ai_reason = f"PEP confirmado: {hit['matched_name']} – {hit['cargo']} (fonte: {hit['source']}, score {hit['score']})"
        else:
            ai_reason = "Sem correspondências em fontes oficiais — pode não ser PEP ou nome diferente."

    # Placeholder para sanções (quando adicionares fontes de sanções, ativa aqui)
    # sanctions = {"value": True/False, "matched_name": "...", ...}

    if pep["value"] is False and sanctions["value"] is False:
        ai_status = "no_match"

    return {
        "pep": pep,
        "sanctions": sanctions,
        "ai_status": ai_status,
        "ai_reason": ai_reason,
    }
