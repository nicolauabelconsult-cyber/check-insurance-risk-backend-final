# net.py
from typing import Optional

def fetch(url: str, timeout: float = 30.0) -> str:
    """
    Faz GET e devolve o HTML como string.
    1) tenta httpx
    2) tenta requests
    3) fallback para urllib (stdlib)
    Importações são "lazy" p/ evitar ModuleNotFoundError no import do módulo.
    """
    last_err: Optional[Exception] = None

    # 1) httpx
    try:
        import httpx  # type: ignore
        r = httpx.get(url, timeout=timeout, headers={"User-Agent": "CIRBot/1.0"})
        r.raise_for_status()
        return r.text
    except Exception as e:
        last_err = e

    # 2) requests
    try:
        import requests  # type: ignore
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "CIRBot/1.0"})
        r.raise_for_status()
        return r.text
    except Exception as e:
        last_err = e

    # 3) urllib (stdlib)
    import ssl
    from urllib import request as _req
    try:
        ctx = ssl.create_default_context()
        req = _req.Request(url, headers={"User-Agent": "CIRBot/1.0"})
        with _req.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            try:
                return raw.decode("utf-8", errors="ignore")
            except Exception:
                return raw.decode("latin-1", errors="ignore")
    except Exception as e:
        last_err = e
        raise RuntimeError(f"fetch failed for {url}: {last_err!r}")
