# ai_pipeline.py
from typing import Dict, Any, Optional
from rapidfuzz import fuzz, process
from models import InfoSource
from extractors import run_extractor

def _norm(s: str) -> str:
    import re
    return re.sub(r"\s+", " ", (s or "").strip()).upper()

def _best_name_match(target: str, names: list[str]) -> Optional[tuple[str, int]]:
    if not target or not names:
        return None
    targetN = _norm(target)
    # usa ratio parcial para apanhar nomes parciais
    match = process.extractOne(targetN, [_norm(n) for n in names], scorer=fuzz.partial_ratio)
    if not match:
        return None
    cand, score, _ = match
    return cand, score

def build_facts_from_sources(identifier_value: str, identifier_type: str, db) -> Dict[str, Any]:
    out: Dict[str, Any] = {"ai_status": "no_data", "ai_reason": "Sem fontes úteis"}
    ident_type = (identifier_type or "").strip().lower()
    ident_val  = (identifier_value or "").strip()

    rows = db.query(InfoSource).all()
    if not rows:
        out["ai_reason"] = "Não há fontes registadas."
        return out

    people_names: list[str] = []

    for r in rows:
        kind = (r.categoria or "").strip().lower()
        url_or_path = r.url or (f"{(r.directory or '').rstrip('/')}/{(r.filename or '').lstrip('/')}" if (r.directory and r.filename) else None)
        if not kind or not url_or_path:
            continue
        try:
            facts = run_extractor(kind, url_or_path, hint=r.validade)
        except Exception as e:
            # ignora fonte com erro, mas continua
            continue

        # agrega nomes (para PEP)
        for f in facts or []:
            if (f or {}).get("type") == "person":
                nm = (f.get("name") or "").strip()
                if nm:
                    people_names.append(nm)

    if not people_names:
        out["ai_status"] = "no_match"
        out["ai_reason"] = "Não encontrei nomes nas fontes."
        return out

    out["ai_status"] = "ok"
    out["ai_reason"] = f"{len(people_names)} nomes agregados."

    # Sinais: PEP via nomes
    out["pep"] = {"value": False}
    if ident_type in {"nome", "name"} and ident_val:
        best = _best_name_match(ident_val, people_names)
        if best:
            cand, score = best
            if score >= 85:  # limiar
                out["pep"] = {"value": True, "matched_name": cand, "score": score}
            else:
                out["pep"] = {"value": False, "matched_name": cand, "score": score}

    # (Exemplo) sanções pode usar outras fontes/categorias
    out["sanctions"] = {"value": False}

    return out
