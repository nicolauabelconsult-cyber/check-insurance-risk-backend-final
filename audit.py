import json, os, time
from typing import Any, Dict, List

LOG_PATH = os.getenv("AUDIT_LOG", "./audit.log")

def log(user_id: str, action: str, details: Dict[str, Any]):
    rec = {"ts": int(time.time()), "user": user_id, "action": action, "details": details}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def list_logs(limit: int = 200) -> List[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    rows = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f.readlines()[-limit:]:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows[::-1]
