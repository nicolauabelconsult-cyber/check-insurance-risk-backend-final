from typing import List, Dict

def ingest_sources(sources: List[Dict]) -> Dict:
    facts = {
        "pep": {"value": False, "confidence": 0.6, "source": "stub"},
        "sanctions": {"value": False, "confidence": 0.6, "source": "stub"},
    }
    return facts
