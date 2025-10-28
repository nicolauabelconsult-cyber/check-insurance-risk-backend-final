_audit_log = []

def add_audit_entry(ts: str, user: str, identifier: str, score_final: int, decisao: str):
    _audit_log.insert(0, {
        "ts": ts,
        "user": user,
        "identifier": identifier,
        "score_final": score_final,
        "decisao": decisao
    })
    if len(_audit_log) > 200:
        _audit_log.pop()

def list_audit():
    return _audit_log
