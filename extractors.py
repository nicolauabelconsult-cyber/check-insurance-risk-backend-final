# extractors.py
import re
from bs4 import BeautifulSoup
from net import fetch  # helper que devolve HTML (str)

# --------- util de normalização de nome ----------
def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    # remove acentos básicos
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

# --------- extractores ----------
def _extract_gov_ao_ministros(url: str, hint: str | None = None):
    """
    Extrai nomes/cargos da página de ministros do Gov. Angola.
    Retorna lista de dicts: {name, cargo, source}
    """
    # CORREÇÃO: fetch devolve HTML (str). Nada de 'resp' nem 'raise_for_status'.
    html = fetch(url, timeout=30.0)

    # Usa o parser nativo do Python (evita dependência extra).
    soup = BeautifulSoup(html, "html.parser")

    cards = []

    # Heurística: procurar blocos com textos longos que contenham "ministro"
    for card in soup.select("div, article, section"):
        txt_full = " ".join(card.stripped_strings)
        if not txt_full:
            continue

        txt_lower = txt_full.lower()
        if "ministro" not in txt_lower or len(txt_full) < 30:
            continue

        # Tenta obter o nome por elementos de destaque
        name = None
        for el in card.select("strong, b, h1, h2, h3, .titulo, .title"):
            s = el.get_text(strip=True)
            if s and len(s.split()) >= 2:
                name = s
                break

        # Fallback: sequência em MAIÚSCULAS com 2–6 palavras
        if not name:
            m = re.search(
                r"([A-ZÁÂÃÉÊÍÓÔÕÚÇ]{2,}(?:\s+[A-ZÁÂÃÉÊÍÓÔÕÚÇ]{2,}){1,5})",
                txt_full
            )
            if m:
                name = m.group(1)

        # Captura um cargo simples
        cargo = None
        m2 = re.search(r"(ministro[^\n,.;]*)", txt_lower)
        if m2:
            cargo = m2.group(1).strip()

        if name:
            cards.append({
                "name": name.strip(),
                "cargo": cargo or "ministro",
                "source": url,
            })

    # Dedup por nome normalizado
    out, seen = [], set()
    for c in cards:
        key = _norm(c["name"])
        if key and key not in seen:
            seen.add(key)
            out.append(c)

    return out

def run_extractor(kind: str, url_or_path: str, hint: str | None = None):
    kind = (kind or "").strip().lower()
    if kind in {"gov_ao_ministros", "gov_ao_ministro", "gov_ao"}:
        return _extract_gov_ao_ministros(url_or_path, hint=hint)
    # futuros extractores aqui
    return []
