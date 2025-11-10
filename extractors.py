# extractors.py
import re
from bs4 import BeautifulSoup
from net import fetch  # <— usa o helper

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

# --------- extractores ----------
def _extract_gov_ao_ministros(url: str, hint: str | None = None):
    """
    Extrai nomes/cargos da página de ministros do Gov. Angola.
    Retorna lista de dicts: {name, cargo, source}
    """
    html = fetch(url), timeout=30.0)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html5lib")

    cards = []
    # A página usa cartões com o cargo e o nome em destaque
    # Vamos procurar por regiões com o texto "MINISTROS" e cartões abaixo.
    for card in soup.select("div.card, div.col, article, section"):
        txt = " ".join(card.stripped_strings).lower()
        if not txt:
            continue
        # heurística: contém "ministro" e tem letras suficientes
        if "ministro" in txt and len(txt) > 30:
            # tenta detectar nome em CAIXA/realce (comum na página)
            # fallback: primeira sequência de 3+ palavras todas com inicial maiúscula
            name = None
            # elementos com destaque (strong/h2/h3)
            for el in card.select("strong, b, h2, h3"):
                s = el.get_text(strip=True)
                if s and len(s.split()) >= 2:
                    name = s
                    break
            if not name:
                # fallback bem simples
                m = re.search(r"([A-ZÁÂÃÉÊÍÓÔÕÚÇ]{2,}(?:\s+[A-ZÁÂÃÉÊÍÓÔÕÚÇ]{2,}){1,5})", " ".join(card.stripped_strings))
                if m:
                    name = m.group(1)
            # cargo
            cargo = None
            m2 = re.search(r"(ministro[^\n,.;]*)", txt)
            if m2:
                cargo = m2.group(1).strip()

            if name:
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

def run_extractor(kind: str, url_or_path: str, hint: str | None = None):
    kind = (kind or "").strip().lower()
    if kind in {"gov_ao_ministros", "gov_ao_ministro", "gov_ao"}:
        return _extract_gov_ao_ministros(url_or_path, hint=hint)
    # add outros extractores aqui no futuro
    return []
