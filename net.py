# net.py
def fetch(url: str, timeout: int = 20) -> str:
    """
    Tenta httpx; se falhar, tenta requests; faz raise com detalhe se tudo falhar.
    Evita NameError porque importa dentro da função.
    """
    last_err = None
    try:
        import httpx  # lazy import
        r = httpx.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        last_err = e

    try:
        import requests  # fallback
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        last_err = e

    raise RuntimeError(f"fetch failed for {url}: {last_err}")
