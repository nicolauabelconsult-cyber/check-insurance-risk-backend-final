# extractors.py
from __future__ import annotations
import httpx
from bs4 import BeautifulSoup

def _fetch_html(url: str) -> BeautifulSoup:
    headers = {
        "User-Agent": "CIRBot/1.0 (+https://checkinsurancerisk.com)",
        "Accept": "text/html,application/xhtml+xml",
    }
    r = httpx.get(url, headers=headers, timeout=20.0, follow_redirects=True)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def extract_governo_ministro(url: str) -> list[dict]:
    """
    Extrai nomes de ministros da página governo.gov.ao/ministro.
    Heurísticas robustas: links para perfis, headings em cartões, etc.
    Retorna uma lista de facts do tipo {'type':'PEP','name':..., 'source':url}.
    """
    soup = _fetch_html(url)
    names = set()

    # 1) anchors com caminho típico de perfis
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").lower()
        txt = (a.get_text(" ", strip=True) or "").strip()
        if not txt:
            continue
        if "/ministro" in href or "/ministr" in href or "/perfil" in href:
            names.add(txt)

    # 2) headings de cartões (muitos sites usam h3/h4)
    for h in soup.select("h2, h3, h4"):
        txt = (h.get_text(" ", strip=True) or "").strip()
        if txt and len(txt.split()) >= 2:
            # muitos nomes aparecem em CAIXA ALTA; aceitamos ambos
            names.add(txt)

    facts = []
    for n in sorted(names):
        facts.append({
            "type": "PEP",
            "name": n,
            "source": url,
            "jurisdiction": "AO",
        })
    return facts
