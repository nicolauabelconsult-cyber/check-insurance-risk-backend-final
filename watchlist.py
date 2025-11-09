# watchlist.py
import re
import unicodedata
from typing import Iterable

_PEP_NORMALIZED: set[str] = set()

def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = " ".join(s.split())
    return s

def set_pep_list(names: Iterable[str]) -> None:
    """Substitui a lista PEP atual por 'names' (em memória)."""
    global _PEP_NORMALIZED
    _PEP_NORMALIZED = {_normalize(n) for n in names if n}

def is_pep_name(name: str) -> bool:
    """True se 'name' estiver na lista PEP atual."""
    return _normalize(name) in _PEP_NORMALIZED
