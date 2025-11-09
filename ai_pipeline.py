# ai_pipeline.py
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from models import InfoSource
from extractors import extract_governo_ministro
from watchlist import set_pep_list

def build_facts_from_sources(db: Session) -> list[dict]:
    """
    Lê as InfoSource da BD, decide o extrator e popula o watchlist (PEP).
    Retorna a lista de facts agregados.
    """
    sources = db.query(InfoSource).all()
    facts: list[dict] = []

    for s in sources:
        if not s.url:
            continue
        u = urlparse(s.url)
        host = (u.netloc or "").lower()
        path = (u.path or "").lower()

        try:
            if "governo.gov.ao" in host and "ministro" in path:
                facts.extend(extract_governo_ministro(s.url))
            # >>> Aqui adicionas outros mapeamentos (BNA/ARSEG/tribunais/etc)
            # elif "bna.ao" in host: facts.extend(extract_bna(...))
            # elif "arse..." in host: facts.extend(extract_arse...)  etc.
        except Exception:
            # Não quebrar a pipeline por uma fonte defeituosa
            continue

    # Atualiza watchlist PEP global
    set_pep_list([f["name"] for f in facts if f.get("type") == "PEP"])
    return facts
