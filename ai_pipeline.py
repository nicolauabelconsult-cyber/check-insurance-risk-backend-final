# ai_pipeline.py
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from models import InfoSource
from extractors import run_extractor


# =========================
# Helpers
# =========================
def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def best_fuzzy_match(target: str, candidates: List[str]) -> Tuple[int, Optional[str]]:
    """
    Devolve (score, candidato) com melhor similaridade para 'target'.
    """
    if not candidates:
        return 0, None
    # usar ratio rápido; podes trocar por token_set_ratio em nomes longos
    best = process.extractOne(target, candidates, scorer=fuzz.QRatio)
    if not best:
        return 0, None
    cand, score, _ = best
    return int(score), cand


# =========================
# Pipeline principal
# =========================
def build_facts_from_sources(
    identifier_value: str,
    identifier_type: str,
    db: Session,
    fuzzy_threshold_pep: int = 90,
    fuzzy_threshold_sanctions: int = 90
) -> Dict[str, Any]:
    """
    Agrega e estrutura 'facts' a partir das fontes configuradas no Admin.
    Usa InfoSource.categoria como 'kind' (sem migração de DB).
    """

    # 1) Carregar fontes
    sources: List[InfoSource] = db.query(InfoSource).all()

    # 2) Executar extractors e juntar resultados
    facts_raw: List[Dict[str, Any]] = []
    for src in sources:
        kind = (src.categoria or "").strip().lower()  # <- "pep_gov_ao", "sanctions_csv", ...
        if not kind:
            continue

        # Determinar caminho/URL que faz sentido para cada fonte
        url_or_path = None
        if src.url:
            url_or_path = src.url.strip()
        elif src.directory and src.filename:
            url_or_path = f"{src.directory.rstrip('/')}/{src.filename.lstrip('/')}"

        if not url_or_path:
            continue

        items = run_extractor(kind, url_or_path, hint=src.validade)  # reuse 'validade' como hint se quiseres
        for it in items:
            it["__kind__"] = kind
        facts_raw.extend(items)

    out: Dict[str, Any] = {
        "ai_status": "no_data",
        "ai_reason": "Nenhuma fonte devolveu dados úteis.",
        "pep": {"value": False, "confidence": 0, "source": None, "matched_name": None},
        "sanctions": {"value": False, "confidence": 0, "source": None, "matched_name": None},
        "raw": facts_raw,  # útil para depuração
    }

    # 3) PEP — fuzzy por nome
    target_name = identifier_value.strip()
    pep_names = [x["name"] for x in facts_raw if x.get("type") == "pep" and x.get("name")]
    pep_score, pep_cand = best_fuzzy_match(target_name, pep_names)
    if pep_score >= fuzzy_threshold_pep and pep_cand:
        src = next((x for x in facts_raw if x.get("type") == "pep" and x.get("name") == pep_cand), None)
        out["pep"] = {
            "value": True,
            "confidence": round(pep_score / 100, 2),
            "source": src.get("source") if src else None,
            "matched_name": pep_cand,
        }

    # 4) Sanções — fuzzy por nome
    sanc_names = [x["name"] for x in facts_raw if x.get("type") == "sanction" and x.get("name")]
    sanc_score, sanc_cand = best_fuzzy_match(target_name, sanc_names)
    if sanc_score >= fuzzy_threshold_sanctions and sanc_cand:
        src = next((x for x in facts_raw if x.get("type") == "sanction" and x.get("name") == sanc_cand), None)
        out["sanctions"] = {
            "value": True,
            "confidence": round(sanc_score / 100, 2),
            "source": src.get("source") if src else None,
            "matched_name": sanc_cand,
        }

    # 5) Status/Reason
    if out["pep"]["value"] or out["sanctions"]["value"]:
        out["ai_status"] = "ok"
        reasons = []
        if out["pep"]["value"]:
            reasons.append(f"Possível PEP (match: {out['pep']['matched_name']}, conf={out['pep']['confidence']})")
        if out["sanctions"]["value"]:
            reasons.append(f"Possível sanção (match: {out['sanctions']['matched_name']}, conf={out['sanctions']['confidence']})")
        out["ai_reason"] = " / ".join(reasons)
    elif facts_raw:
        out["ai_status"] = "no_match"
        out["ai_reason"] = "Fontes consultadas, mas sem correspondência fiável para o identificador."

    return out
