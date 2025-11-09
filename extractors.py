# extractors.py
import re
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).upper()

def extract_gov_ao_ministros(url: str, hint: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lê https://governo.gov.ao/ministro e devolve uma lista de dicts com nomes dos ministros.
    Estrutura de saída:
      [{ "type": "person", "name": "MANUEL GOMES DA CONCEIÇÃO HOMEM", "role": "MINISTRO DO INTERIOR" }, ...]
    """
    res = httpx.get(url, timeout=20)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "lxml")

    items: List[Dict[str, Any]] = []
    # O HTML do site tem cartões dos ministros; vamos procurar por blocos com títulos e nomes
    # Os seletores abaixo são resilientes mas simples; ajusta se o HTML mudar
    cards = soup.select("div.card, div.views-row, div[class*='col']")  # fallback amplo
    if not cards:
        cards = [soup]  # varre globalmente

    seen = set()
    for blk in cards:
        # nome aparece frequentemente em <a> ou <h3>/<h4> com classes visíveis; vamos apanhar links e headings
        cand = []
        cand += [a.get_text(" ", strip=True) for a in blk.select("a")]
        cand += [h.get_text(" ", strip=True) for h in blk.select("h1,h2,h3,h4,h5")]
        # filtra nomes com heurística (muitas letras, espaços, sem URL)
        for txt in cand:
            t = _norm(txt)
            # regras simples para nomes próprios (podes refinar)
            if len(t) >= 10 and "MINISTRO" not in t and not t.startswith("GOVERNO") and not t.endswith("VER MAIS"):
                # valida que parece nome (tem espaços e letras)
                if re.search(r"[A-ZÁÂÃÉÊÍÓÔÕÚÇ]{2,}\s+[A-ZÁÂÃÉÊÍÓÔÕÚÇ]{2,}", t):
                    if t not in seen:
                        seen.add(t)
                        # tentar captar um "role" perto (ex: MINISTRO DO INTERIOR)
                        role = None
                        role_el = blk.find(text=re.compile(r"MINISTRO", re.I))
                        if role_el:
                            role = _norm(str(role_el))
                        items.append({"type": "person", "name": t, "role": role})
    return items

# -------- router --------
def run_extractor(kind: str, url_or_path: str, hint: Optional[str] = None) -> List[Dict[str, Any]]:
    kind = (kind or "").strip().lower()
    if kind == "gov_ao_ministros":
        return extract_gov_ao_ministros(url_or_path, hint=hint)
    # podes acrescentar outros "kind" aqui
    raise ValueError(f"Extractor desconhecido: {kind}")
