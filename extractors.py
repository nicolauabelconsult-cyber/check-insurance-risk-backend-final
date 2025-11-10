import re, requests
from bs4 import BeautifulSoup

def _norm(s: str) -> str:
    return " ".join(re.sub(r"\s+", " ", s or "").strip().split()).upper()

def extract_gov_ao_ministros(url: str):
    """
    Extrai nomes de ministros do portal Governo de Angola.
    Heurística robusta: pega textos em CAPS das "cards".
    """
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html5lib")

    # 1) todos os títulos/link-text dentro de cards contendo 'MINISTRO'
    cards = soup.select("div.card, div[class*=card], article, .ministro, .ministros")
    texts = []
    for c in cards:
        for el in c.find_all(["h1","h2","h3","h4","a","strong","div","span"]):
            t = _norm(el.get_text(" "))
            if len(t) >= 8 and any(word in t for word in ["MINISTRO", "MINISTRA"]) or re.search(r"[A-Z]{2,}\s[A-Z]{2,}", t):
                texts.append(t)

    # 2) heurística: manter linhas com 2+ palavras em caps (potenciais nomes)
    names = set()
    for t in texts:
        # remove prefixos tipo "MINISTRO DO INTERIOR"
        t = re.sub(r"\bMINISTROS?\b.*", "", t).strip()
        # mantém padrões com espaços e letras
        if re.search(r"[A-Z]{2,}\s+[A-Z]{2,}", t):
            # corta sufixos comuns
            t = re.sub(r"\bDATA DE NOMEAÇÃO.*", "", t).strip(" -:•")
            if 6 < len(t) < 80:
                names.add(t)

    # alguns sites usam cards muito “ricos”; como salvaguarda, tenta links <a> com caps
    if not names:
        for a in soup.find_all("a"):
            t = _norm(a.get_text(" "))
            if re.search(r"[A-Z]{2,}\s+[A-Z]{2,}", t):
                names.add(t)
    return sorted(names)

def run_extractor(kind: str, url_or_path: str, hint: str = None):
    kind = (kind or "").strip().lower()
    if kind == "gov_ao_ministros":
        return [{"name": n, "source": url_or_path, "cargo": "Ministro(a)", "score": 0.95} for n in extract_gov_ao_ministros(url_or_path)]
    # outros kinds podem ser implementados aqui
    return []
