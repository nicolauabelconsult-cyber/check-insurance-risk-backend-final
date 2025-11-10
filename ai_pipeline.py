# extractors.py
import re
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup

def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', s or '').strip()

def extract_gov_ao_ministros(url: str, hint: Optional[str] = None) -> List[Dict]:
    """
    Lê https://governo.gov.ao/ministro e devolve uma lista de dicts:
    {name, cargo, source}
    """
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()

    # html5lib evita lxml e funciona bem com HTML "imperfeito"
    soup = BeautifulSoup(resp.text, "html5lib")

    items = []
    # Cada ministro aparece num "card"
    cards = soup.select("div.card, div.col-12")
    if not cards:
        # fallback: procurar por headings + links
        cards = soup.select("h3, h4, .title, .ministro, .minister")

    for c in cards:
        text = _norm(c.get_text(" ", strip=True))
        if not text:
            continue

        # Heurísticas simples: linha com nome em MAIÚSCULAS geralmente é o ministro
        # e uma linha próxima com "Ministro" é o cargo
        mname = None
        mcargo = None

        # tentar apanhar texto em destaque
        strongs = [ _norm(x.get_text(" ", strip=True)) for x in c.select("strong, b") ]
        for s in strongs:
            if len(s.split()) >= 2 and s.upper() == s:
                mname = s
                break

        # se não encontrou, usar a primeira linha "marcante"
        if not mname:
            # procurar padrão tipo "MANUEL GOMES DA CONCEIÇÃO HOMEM"
            m = re.search(r'([A-ZÁÂÃÉÊÍÓÔÕÚÇ][A-ZÁÂÃÉÊÍÓÔÕÚÇ\s\-]{8,})', text)
            if m:
                mname = _norm(m.group(1))

        # cargo
        mcargo = None
        cargo_candidates = re.findall(r'(Ministro[a|o]?[^|,\n]+)', text, flags=re.I)
        if cargo_candidates:
            mcargo = _norm(cargo_candidates[0])

        if mname:
            items.append({
                "name": mname,
                "cargo": mcargo or "Ministro",
                "source": url,
            })

    return items

# Router de extractors
def run_extractor(kind: str, url_or_path: str, hint: Optional[str] = None) -> List[Dict]:
    kind = (kind or "").strip().lower()
    if kind in {"gov_ao_ministros", "gov_ao_ministro"}:
        return extract_gov_ao_ministros(url_or_path, hint=hint)
    # adicionar outros extractors conforme necessário
    return []
