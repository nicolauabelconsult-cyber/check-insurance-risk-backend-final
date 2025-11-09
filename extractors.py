# extractors.py
import re
import unicodedata
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup

def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _clean_name(s: str) -> str:
    s = _norm_text(s)
    # retirar cargos comuns caso venham “colados”
    s = re.sub(r"^(MINISTRO(A)?( DO| DA| DE)? .+?- )", "", s, flags=re.I)
    return s

def _fetch(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CIRbot/1.0; +https://checkinsurancerisk.com)"
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.text

def _extract_gov_ao_ministros(url: str) -> List[Dict]:
    """
    Extrai nomes/cargos da página oficial https://governo.gov.ao/ministro
    Retorna lista de dicts: {"type":"pep","name":..., "cargo":..., "source":url}
    """
    html = _fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    cards = []
    # Procurar por blocos com foto/nome/cargo – estruturas variam, por isso usamos heurística
    for card in soup.find_all(["article", "div", "li", "section"]):
        txt = " ".join(_norm_text(t.get_text(" ", strip=True)) for t in card.find_all(["h3", "h4", "a", "p", "span"]))
        if not txt:
            continue
        # Heurística: “MINISTRO” aparece na área do cargo
        if re.search(r"\bMINISTR[OA]S?\b", txt, flags=re.I):
            cards.append(card)

    results: List[Dict] = []
    for c in cards:
        # nome em destaque costuma estar em <h3> ou <a> com cor/maiusculas
        name_node = None
        for tag in ["h3", "h4", "a", "strong", "span"]:
            n = c.find(tag)
            if n and len(_norm_text(n.get_text())) > 3:
                name_node = n
                break
        if not name_node:
            continue

        name = _clean_name(name_node.get_text(" ", strip=True))
        if len(name.split()) < 2:
            # alguns cartões têm o nome em <a> seguinte
            a2 = name_node.find_next("a")
            if a2:
                name = _clean_name(a2.get_text(" ", strip=True))

        # cargo: linha onde aparece “MINISTRO…”
        cargo = ""
        cargo_node = None
        for tag in ["h4", "h5", "p", "div", "span", "a"]:
            for n in c.find_all(tag):
                t = _norm_text(n.get_text(" ", strip=True))
                if re.search(r"\bMINISTR[OA]\b", t, flags=re.I):
                    cargo_node = n
                    cargo = t
                    break
            if cargo_node:
                break

        if name:
            results.append({
                "type": "pep",
                "name": name,
                "cargo": cargo or "Ministro (Gov. AO)",
                "source": url
            })

    # remover duplicados por nome
    uniq = {}
    for r in results:
        uniq[_norm_text(r["name"]).lower()] = r
    return list(uniq.values())

def run_extractor(kind: str, url_or_path: str, hint: Optional[str] = None) -> List[Dict]:
    """
    Interface única para os extratores.
    kind = categoria da InfoSource.
    """
    kind = (kind or "").strip().lower()
    if kind == "gov_ao_ministros":
        return _extract_gov_ao_ministros(url_or_path)

    # Outros tipos no futuro: bna_normas, arseg_circulares, tribunais_acordaos, etc.
    return []
