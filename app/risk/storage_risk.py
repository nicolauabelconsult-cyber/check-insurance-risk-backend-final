_risk_db = []
_next_id = 1

def add_or_update_record(data: dict):
    global _next_id, _risk_db
    rid = data.get("id")
    if rid:
        for row in _risk_db:
            if str(row["id"]) == str(rid):
                row.update(data)
                return row["id"]
    data_id = _next_id
    _next_id += 1
    data["id"] = data_id
    _risk_db.append(data)
    return data_id

def list_records():
    return _risk_db

def delete_record(id_val: str):
    idx = None
    for i,row in enumerate(_risk_db):
        if str(row["id"]) == str(id_val):
            idx = i
            break
    if idx is not None:
        _risk_db.pop(idx)
        return True
    return False
