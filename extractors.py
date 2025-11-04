# extractors.py
import re
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup

UA = "CIRBot/1.0 (+compliance; contact: admin@checkrisk.com)"
ALLOW_HOSTS = ("https://governo.gov.ao","http://governo.gov.ao")

async def fetch_source(url: str, timeout: int = 25) -> str:
    if not any(url.startswith(h) for h in ALLOW_HOSTS):
        raise ValueError("URL fora da allowlist")
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": UA}) as client:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        return r.text

PEP_TITLES = r"(Ministr[oa]|Secret[áa]ri[oa] de Estado|Governador|Vice[- ]?Ministro|Chefe de|Presidente|Vice[- ]?Presidente)"
NAME_PATTERN = r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇa-zçãõâêôéíóú]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇa-zçãõâêôéíóú]+)+)"
PAG_WORDS = ("atraso","mora","incumprimento","pagamento","regularização")
SANCTION_WORDS = ("sanção","sanções","sanction","OFAC","ONU","EU")

def _clean(s: str) -> str:
    import re as _re
    return _re.sub(r"\s+", " ", (s or "").strip())

def extract_names_roles(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cands = []
    for tag in soup.find_all(["h1","h2","h3","h4"]):
        txt = _clean(tag.get_text(" "))
        import re as _re
        if len(txt.split()) >= 2 and _re.search(NAME_PATTERN, txt):
            role = None
            mrole = _re.search(PEP_TITLES, txt, flags=_re.I)
            if mrole: role = mrole.group(1)
            cands.append({"name": txt, "role": role or "Ministro"})
    for card in soup.select("[class*='ministro'],[class*='profile'],[class*='card'],[class*='team']"):
        txt = _clean(card.get_text(" "))
        import re as _re
        m = _re.search(NAME_PATTERN, txt)
        if m:
            nm = m.group(1)
            role = None
            mrole = _re.search(PEP_TITLES, txt, flags=_re.I)
            if mrole: role = mrole.group(1)
            cands.append({"name": nm, "role": role or "Ministro"})
    for a in soup.select("a"):
        txt = _clean(a.get_text(" "))
        import re as _re
        if len(txt.split()) >= 2 and _re.search(NAME_PATTERN, txt):
            cands.append({"name": txt, "role": "Ministro"})
    out, seen = [], set()
    for it in cands:
        key = it["name"].lower()
        if key in seen: 
            continue
        seen.add(key)
        it["is_pep"] = True
        out.append(it)
    return out

def extract_claims(text: str) -> Dict[str,int]:
    t = text.lower()
    import re as _re
    counts = {"automovel":0,"vida":0,"saude":0,"patrimonial":0}
    auto_hits = len(_re.findall(r"\b(auto|autom[oó]vel|viatura)\b.*\b(sinistro|acidente)\b", t))
    vida_hits = len(_re.findall(r"\b(vida)\b.*\b(sinistro|ocorr[eê]ncia)\b", t))
    saude_hits = len(_re.findall(r"\b(sa[uú]de)\b.*\b(sinistro|ocorr[eê]ncia)\b", t))
    patr_hits = len(_re.findall(r"\b(patrimoni(al|o))\b.*\b(sinistro|ocorr[eê]ncia)\b", t))
    counts.update({"automovel":auto_hits,"vida":vida_hits,"saude":saude_hits,"patrimonial":patr_hits})
    return counts

def extract_payments(text: str) -> Dict[str,Any]:
    t = text.lower()
    delays = sum(1 for w in PAG_WORDS if w in t)
    punctuality = 95 if delays == 0 else 80 if delays == 1 else 65
    last_delay = None
    import re as _re
    m = _re.search(r"(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\s*[\-/]?\s*(20\d{2})", t, flags=_re.I)
    if m: last_delay = f"{m.group(1).title()} {m.group(2)}"
    return {"punctuality_pct": punctuality, "last_delay": last_delay}

def extract_sanctions(text: str) -> Dict[str,Any]:
    t = text.lower()
    mentions = any(w.lower() in t for w in SANCTION_WORDS)
    return {"value": mentions, "confidence": 0.5 if mentions else 0.99, "sources_checked": ["open-web"]}

def extract_facts_from_sources(sources: List[Dict[str,Any]]) -> Dict[str,Any]:
    all_texts = []
    found_peps = []
    for s in sources:
        html = s.get("html") or ""
        txt = s.get("text") or ""
        if html:
            try:
                found_peps.extend(extract_names_roles(html))
                soup = BeautifulSoup(html, "html.parser")
                txt += " " + soup.get_text(" ", strip=True)
            except Exception:
                pass
        if txt:
            all_texts.append(txt)

    joined = " \n ".join(all_texts)[:2000000]

    claims = extract_claims(joined)
    payments = extract_payments(joined)
    sanctions = extract_sanctions(joined)

    base = 82
    if sanctions["value"]: base -= 20
    tot_claims = sum(claims.values())
    base -= min(tot_claims, 10) * 2
    if (payments["punctuality_pct"] or 80) < 85: base -= 10
    score_final = max(0, min(100, base))

    classificacao = "Risco Baixo" if score_final>=85 else "Risco Médio-Baixo" if score_final>=70 else "Risco Médio" if score_final>=55 else "Risco Alto"

    facts = {
        "pep": {"value": True if found_peps else False, "count": len(found_peps), "items": found_peps},
        "sanctions": sanctions,
        "claims": {"by_type": claims, "window_months": 24},
        "payments": {"punctuality_pct": payments["punctuality_pct"], "last_delay": payments["last_delay"]},
        "score_final": score_final,
        "classificacao": classificacao,
        "decisao": "Aceitar com condições e monitorização semestral" if score_final>=70 else "Rever manualmente",
        "justificacao": "Factos agregados automaticamente; validação humana recomendada quando confidence < 0.8."
    }
    return facts
