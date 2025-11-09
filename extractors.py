# extractors.py
from __future__ import annotations
import os
import io
import csv
from typing import List, Dict, Any, Optional

import httpx
from bs4 import BeautifulSoup


# =========================
# Helpers
# =========================
def _read_text_from(url_or_path: str) -> str:
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        r = httpx.get(url_or_path, timeout=30)
        r.raise_for_status()
        return r.text
    # caminho local (ex.: "uploads/ficheiro.csv" guardado pelo admin)
    with open(url_or_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _read_bytes_from(url_or_path: str) -> bytes:
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        r = httpx.get(url_or_path, timeout=30)
        r.raise_for_status()
        return r.content
    with open(url_or_path, "rb") as f:
        return f.read()


# =========================
# Extractors
# =========================
def extract_pep_gov_ao(url: str, hint: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Extrai nomes de PEPs a partir do site do Governo de Angola.
    Ajusta os seletores de acordo com o HTML real da página.
    """
    html = _read_text_from(url)
    soup = BeautifulSoup(html, "html.parser")

    items: List[Dict[str, Any]] = []

    # Seletores comuns - troca se necessário conforme o HTML real
    candidates = soup.select("h1, h2, h3, .card-title, .minister-name, .ministro, a")

    for node in candidates:
        name = (node.get_text() or "").strip()
        # heurística simples para filtrar ruído
        if name and len(name.split()) >= 2 and 4 <= len(name) <= 80:
            items.append({
                "type": "pep",
                "name": name,
                "source": url,
            })

    return items


def extract_sanctions_csv(url_or_path: str, hint: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lê CSV de sanções (remoto ou local) com cabeçalho:
      name, list, country  (campos adicionais são ignorados)
    """
    content = _read_bytes_from(url_or_path).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    out: List[Dict[str, Any]] = []
    for row in reader:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "type": "sanction",
            "name": name,
            "list": (row.get("list") or "").strip() or None,
            "country": (row.get("country") or "").strip() or None,
            "source": url_or_path,
        })
    return out


# (Opcional) Extractor genérico muito simples para HTML (fallback)
def extract_html_generic(url: str, hint: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Busca possíveis nomes próprios em headings/links. É fraco, serve como fallback.
    """
    html = _read_text_from(url)
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict[str, Any]] = []
    for node in soup.select("h1, h2, h3, a, strong, b"):
        txt = (node.get_text() or "").strip()
        if txt and len(txt.split()) >= 2 and 4 <= len(txt) <= 80:
            out.append({"type": "text", "value": txt, "source": url})
    return out


# =========================
# Registry + Runner
# =========================
EXTRACTORS = {
    "pep_gov_ao": extract_pep_gov_ao,
    "sanctions_csv": extract_sanctions_csv,
    "html_generic": extract_html_generic,  # fallback manual, se quiseres
}


def run_extractor(kind: str, url_or_path: str, hint: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Executa o extractor pelo 'kind' (categoria). Se não existir, devolve vazio.
    """
    fn = EXTRACTORS.get(kind)
    if not fn:
        return []
    try:
        return fn(url_or_path, hint)
    except Exception as e:
        # Nunca deitar abaixo a pipeline por falha numa fonte
        return [{"type": "error", "error": str(e), "source": url_or_path, "kind": kind}]
