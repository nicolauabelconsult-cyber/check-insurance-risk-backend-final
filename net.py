# net.py
import requests

DEFAULT_HEADERS = {
    "User-Agent": "CheckInsuranceRiskBot/1.0 (+https://checkinsurancerisk.com)"
}

def fetch(url: str, timeout: float = 30.0):
    """
    Wrapper simples sobre requests.get, com user-agent.
    """
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    return resp
