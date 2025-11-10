# extractors.py
import re
import requests
from bs4 import BeautifulSoup

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def run_extractor(kind: str, url_or_path: str, hint: str | None = None) -> list[dict]:
    kind = (kind or "").strip().lower()
    if kind == "gov_ao_ministros":
        return _extract_gov_ao_ministros(url_or_path)
    # pode adicionar outros kinds aqui…
    return []

def _extract_gov_ao_ministros(url: str) -> list[dict]:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html5lib")

    # cada cartão de ministro
    cards = soup.select("div.card-ministro, div.views-row, div.ministro, div.card") or soup.select("div[class*='ministro']")
    results = []

    for card in cards:
        name = None
        # tentativas: títulos em H3/H4 ou links destacados
        for sel in ("h3", "h4", "a", "strong", "div.titulo", ".titulo"):
            el = card.select_one(sel)
            if el:
                name = _norm(el.get_text())
                break
        if not name:
            continue

        # cargo (se existir)
        cargo_el = card.select_one(".cargo, .ministry, .role, .view-content, .views-field")
        cargo = _norm(cargo_el.get_text()) if cargo_el else "Ministro"

        results.append({
            "type": "pep",
            "name": name,
            "cargo": cargo,
            "source": url,
            "score": 0.92,  # heurística simples
        })

    return results
