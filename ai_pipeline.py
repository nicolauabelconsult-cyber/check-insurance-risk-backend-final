# ai_pipeline.py
import json
import os
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from models import InfoSource
from extractors import run_extractor

WATCHLIST_PATH = os.getenv("WATCHLIST_PATH", "data/watchlist.json")

# ---------------- utils ----------------
def _norm(s: str) -> str:
    s = s or ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    for a, b in (
        ("á","a"),("à","a"),("â","a"),("ã","a"),
        ("é","e"),("ê","e"),
        ("í","i"),
        ("ó","o"),("ô","o"),("õ","o"),
        ("ú","u"),
        ("ç","c"),
    ):
        s = s.replace(a,b)
    return s

def _load_watchlist() -> List[Dict[str, Any]]:
    if os.path.exists(WATCHLIST_PATH):
        try:
            with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_watchlist(rows: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(WATCHLIST_PATH) or ".", exist_ok=True)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

# ---------------- API pública ----------------
def rebuild_watchlist(db: Session) -> int:
    """
    Varre InfoSource e constrói uma watchlist de PEP (nomes/cargos/fonte).
    """
    rows = []
    sources = db.query(InfoSource).all()
    for s in sources:
        kind = (s.categoria or "").strip().lower()
        url_or_path = s.url or (f"{(s.directory or '').rstrip('/')}/{(s.filename or '').lstrip('/')}"
                                if (s.directory and s.filename) else None)
        if not kind or not url_or_path:
            continue
        try:
            facts = run_extractor(kind, url_or_path, hint=s.validade)
            for f in facts:
                nm = f.get("name")
                if nm:
                    rows.append({
                        "name": nm.strip(),
                        "cargo": f.get("cargo"),
                        "source": f.get("source") or url_or_path,
                        "kind": kind,
                    })
        except Exception:
            # não bloqueia
            pass

    # dedup por nome normalizado
    out = []
    seen = set()
    for r in rows:
        k = _norm(r["name"])
        if k and k not in seen:
            seen.add(k)
            out.append(r)

    _save_watchlist(out)
    return len(out)

def is_pep_name(name: str) -> bool:
    q = _norm(name)
    if not q:
        return False
    wl = _load_watchlist()
    return any(_norm(r.get("name")) == q for r in wl)

def _best_name_match(name: str) -> Optional[Dict[str, Any]]:
    q = _norm(name)
    wl = _load_watchlist()
    for r in wl:
        if _norm(r.get("name")) == q:
            return r
    # tentativa fuzzy simples: começa/termina
    for r in wl:
        n = _norm(r.get("name"))
        if q and (q in n or n in q):
            return r
    return None

def build_facts_from_sources(*, identifier_value: str, identifier_type: str, db: Session) -> Dict[str, Any]:
    """
    Executa verificação com base em:
      1) watchlist local (rebuildada no arranque e nos CRUDs)
      2) scraping on-demand das InfoSource (apenas para nome; pode ser estendido)
    """
    out = {"ai_status": "no_data", "ai_reason": "Nenhuma fonte consultada ainda."}

    id_type = (identifier_type or "").strip().lower()
    value = (identifier_value or "").strip()
    if not value:
        out["ai_reason"] = "Identificador vazio."
        return out

    # 1) match na watchlist
    if id_type in {"nome", "name"}:
        match = _best_name_match(value)
        if match:
            out["ai_status"] = "ok"
            out["ai_reason"] = "Match por nome na watchlist."
            out["pep"] = {"value": True, "matched_name": match["name"], "cargo": match.get("cargo"),
                          "source": match.get("source"), "score": 0.95}
        else:
            out["pep"] = {"value": False}
            out["ai_status"] = "no_match"
            out["ai_reason"] = "Nome não encontrado na watchlist."

    # 2) sanções — placeholder (sem fontes ainda)
    out["sanctions"] = {"value": False}

    return out
