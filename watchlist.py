from typing import List, Dict, Any
from rapidfuzz import fuzz, process
WATCHLIST: List[Dict[str, Any]] = []
def load_items(items: List[Dict[str, Any]]):
    WATCHLIST.clear()
    WATCHLIST.extend(items)
def search_exact(term: str) -> List[Dict[str, Any]]:
    t = term.strip().lower()
    return [x for x in WATCHLIST if t in (x.get("name","").lower(), x.get("id","").lower())]
def search_fuzzy(term: str, limit: int = 5, threshold: int = 86) -> List[Dict[str, Any]]:
    names = [x["name"] for x in WATCHLIST if x.get("name")]
    results = process.extract(term, names, scorer=fuzz.WRatio, limit=limit)
    out = []
    for name, score, idx in results:
        if score >= threshold:
            out.append({**WATCHLIST[idx], "_score": score})
    return out
