# extractors.py
from __future__ import annotations
import re
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup

def _fetch(url: str, timeout: float = 20.0) -> str:
    # httpx com timeouts e follow_redirects
    with httpx.Client(timeout=timeout, follow_redirects=True) as c:
        r = c.get(url, headers={"User-Agent": "CIR/1.0"})
        r.raise_for_status()
        return r.text

def _norm_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u00A0", " ")
    return s

def ext_gov_ao_ministros(url: str, hint: Optional[str] = None) -> List[Dict]:
    """
    Extrai nomes da página de Ministros do site do Governo de Angola.
    Retorna lista de dicts com {type, value, source, extra}
    """
    html = _fetch(url)
    soup = BeautifulSoup(html, "html5lib")

    facts: List[Dict] = []

    # Regras simples e robustas: títulos com palavra "MINISTRO" e blocos de cartão
    cards = soup.select("div.card, div.views-row, div[class*='ministro'], article")
    if not cards:
        # fallback: procurar links e headings com padrões
        cards = soup.find_all(["div", "article", "section"])

    for blk in cards:
        txt = " ".join(t.get_text(" ", strip=True) for t in blk.find_all(["h1","h2","h3","h4","a","p","span"])[:6])
        if not txt:
            continue
        if re.search(r"\b(MINISTRO|MINISTRA|MINISTROS)\b", txt, re.I):
            # tenta encontrar o nome destacado no bloco
            # heurística: palavras todas em maiúsculas / realce
            name_candidates = re.findall(r"[A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÜÇ\s\-']{5,}", txt)
            for nm in name_candidates:
                nm = _norm_name(nm.title())
                if len(nm.split()) >= 2:
                    facts.append({
                        "type": "person",
                        "value": nm,
                        "source": url,
                        "extra": {"role": "Ministro/Ministra"}
                    })

    # Se não apanhou nada pelos cartões, tenta headings globais como fallback
    if not facts:
        for h in soup.find_all(["h2","h3","h4","a","strong","b"]):
            t = _norm_name(h.get_text(" ", strip=True))
            if re.search(r"\b(MINISTRO|MINISTRA)\b", t, re.I):
                facts.append({"type": "person", "value": t, "source": url, "extra": {"role": "Ministro/Ministra"}})

    # de-duplicar por nome
    uniq = {}
    for f in facts:
        uniq[f["value"]] = f
    return list(uniq.values())

# Dispatcher simples
def run_extractor(kind: str, url_or_path: str, hint: Optional[str] = None) -> List[Dict]:
    kind = (kind or "").strip().lower()
    if kind in {"gov_ao_ministros", "gov-ao-ministros", "govao_ministros"}:
        return ext_gov_ao_ministros(url_or_path, hint)
    # por omissão: nada
    return []
