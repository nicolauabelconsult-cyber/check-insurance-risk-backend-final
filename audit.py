from datetime import datetime
from typing import List, Dict
from jose import JWTError, jwt

_logs: List[Dict] = []

def log(user_id: str | None, action: str, meta: dict | None = None):
    _logs.append({
        "ts": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "action": action,
        "meta": meta or {}
    })

def list_logs():
    return list(_logs)
