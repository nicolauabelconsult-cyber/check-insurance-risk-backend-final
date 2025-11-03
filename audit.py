import datetime as dt
from typing import List, Dict, Any
AUDIT: List[Dict[str, Any]] = []
def log(actor: str, action: str, details: Dict[str, Any]):
    AUDIT.append({
        "ts": dt.datetime.utcnow().isoformat(),
        "actor": actor, "action": action, "details": details
    })
def list_logs(limit: int = 200):
    return AUDIT[-limit:]
