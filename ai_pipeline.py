# ai_pipeline.py
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from models import InfoSource
from extractors import run_extractor
import re

# mesma normalização de nomes que no extractor
def _norm(s: str) -> str:
    s = s or ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    repl = (
        ("á", "a"), ("à", "a"), ("â", "a"), ("ã", "a"),
        ("é", "e"), ("ê", "e"),
        ("í", "i"),
        ("ó", "o"), ("ô", "o"), ("õ", "o"),
        ("ú", "u"),
        ("ç", "c"),
    )
    for a, b in repl:
        s = s.replace(a, b)
    return s

# watchlist em memória (reconstruída no startup ou quando crias/apagas fontes)
_watchlist: list[dict[str, Any]] = []

def rebuild_watchlist(db: Session) -> None:
    """
    Lê todas as InfoSource e constrói uma watchlist em memória com nomes PEP.
    """
    global _watchlist
    _watchlist = []

    sources = db.query(InfoSource).all()
    for src in sources:
        kind = (src.categoria or "").strip().lower()
        url_or_path = src.url or (
            f"{(src.directory or '').rstrip('/')}/{(src.filename or '').lstrip('/')}"
            if (src.directory and src.filename) else None
        )
        if not kind or not url_or_path:
            continue

        try:
            facts = run_extractor(kind, url_or_path, hint=src.validade)
        except Exception:
            # se uma fonte falhar, ignoramos essa e seguimos
            continue

        for f in facts:
            name = f.get("name")
            if not name:
                continue
            _watchlist.append({
                "norm": _norm(name),
                "name": name,
                "cargo": f.get("cargo"),
                "source": f.get("source") or url_or_path,
            })

    # dedup por nome normalizado
    seen = set()
    dedup = []
    for item in _watchlist:
        if item["norm"] in seen:
            continue
        seen.add(item["norm"])
        dedup.append(item)
    _watchlist = dedup

def is_pep_name(name: str) -> bool:
    """
    Verifica se o nome já existe na watchlist em memória.
    """
    n = _norm(name)
    return any(item["norm"] == n for item in _watchlist)

def build_facts_from_sources(
    identifier_value: str,
    identifier_type: Optional[str],
    db: Session,
) -> Dict[str, Any]:
    """
    Enriquecimento on-demand: lê as InfoSource e tenta encontrar PEP/sanções.
    Neste momento só faz match por NOME em fontes gov_ao_ministros.
    """
    result: Dict[str, Any] = {
        "ai_status": "no_data",
        "ai_reason": "Sem fontes configuradas.",
        "pep": {},
        "sanctions": {},
    }

    sources = db.query(InfoSource).all()
    if not sources:
        return result

    id_type = (identifier_type or "").strip().lower()
    if id_type not in {"nome", "name"}:
        result["ai_status"] = "no_match"
        result["ai_reason"] = "No momento as fontes configuradas só suportam pesquisa por nome."
        return result

    name_norm = _norm(identifier_value)
    best_match: Optional[Dict[str, Any]] = None

    for src in sources:
        kind = (src.categoria or "").strip().lower()
        url_or_path = src.url or (
            f"{(src.directory or '').rstrip('/')}/{(src.filename or '').lstrip('/')}"
            if (src.directory and src.filename) else None
        )
        if not kind or not url_or_path:
            continue

        try:
            facts = run_extractor(kind, url_or_path, hint=src.validade)
        except Exception as e:
            # devolve erro legível para o frontend
            result["ai_status"] = "error"
            result["ai_reason"] = f"Erro ao ler fonte '{src.title}': {e}"
            return result

        for f in facts:
            cand_name = f.get("name")
            if not cand_name:
                continue
            if _norm(cand_name) == name_norm:
                best_match = {
                    "value": True,
                    "matched_name": cand_name,
                    "cargo": f.get("cargo"),
                    "source": f.get("source") or url_or_path,
                    "score": 1.0,  # por enquanto, match exacto = 1.0
                }
                break

        if best_match:
            break

    if best_match:
        result["ai_status"] = "ok"
        result["ai_reason"] = "Nome encontrado nas fontes configuradas."
        result["pep"] = best_match
    else:
        result["ai_status"] = "no_match"
        result["ai_reason"] = "Nenhum match exacto encontrado nas fontes configuradas."

    return result
