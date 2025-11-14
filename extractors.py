# extractors.py
import re
from bs4 import BeautifulSoup
from net import fetch  # usa o helper HTTP

# --------- util de normalização de nome ----------
def _norm(s: str) -> str:
    s = s or ""
    s = s.strip().lower()
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

# --------- extractor gov.ao ministros ----------
def _extract_gov_ao_ministros(url: str, hint: str | None = None):
    """
    Extrai nomes/cargos da página de ministros do Gov. Angola.
    Retorna lista de dicts: {name, cargo, source}
    """
    try:
        # <-- AQUI estava o erro antes: agora está correcto
        resp = fetch(url, timeout=30.0)
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Falha ao obter página de ministros: {e}") from e

    # usar parser padrão da stdlib (html.parser) para evitar erro do html5lib
    soup = BeautifulSoup(resp.text, "html.parser")

    cards = []

    # Heurística: procurar blocos com texto que contenha "ministro"
    for card in soup.select("article, div.card, div.col, section"):
        txt_full = " ".join(card.stripped_strings)
        if not txt_full:
            continue
        txt_lower = txt_full.lower()
        if "ministro" not in txt_lower:
            continue

        # 1) tentamos apanhar nome em elementos de destaque
        name = None
        for el in card.select("strong, b, h2, h3"):
            s = el.get_text(strip=True)
            if s and len(s.split()) >= 2:
                name = s
                break

        # 2) fallback: sequência de 2–6 palavras com iniciais maiúsculas
        if not name:
            m = re.search(
                r"([A-ZÁÂÃÉÊÍÓÔÕÚÇ][^\s,]{2,}(?:\s+[A-ZÁÂÃÉÊÍÓÔÕÚÇ][^\s,]{2,}){1,5})",
                txt_full,
            )
            if m:
                name = m.group(1)

        if not name:
            continue

        cargo = None
        m2 = re.search(r"(ministro[^\n.,;]*)", txt_lower)
        if m2:
            cargo = m2.group(1).strip()

        cards.append({
            "name": name.strip(),
            "cargo": cargo or "ministro",
            "source": url,
        })

    # dedup simples por nome normalizado
    out = []
    seen = set()
    for c in cards:
        k = _norm(c["name"])
        if k and k not in seen:
            seen.add(k)
            out.append(c)
    return out

# --------- router de extractores ----------
def run_extractor(kind: str, url_or_path: str, hint: str | None = None):
    kind = (kind or "").strip().lower()
    if kind in {"gov_ao_ministros", "gov_ao_ministro", "gov_ao"}:
        return _extract_gov_ao_ministros(url_or_path, hint=hint)

    # no futuro: adicionar outros tipos
    return []
