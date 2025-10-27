
import json, os
from datetime import datetime, timezone

DATA_FILE = "cir_data.json"
UPLOAD_DIR = "uploads_info"
os.makedirs(UPLOAD_DIR, exist_ok=True)

_default_data = {
    "USERS_DB": {
        "admin@checkrisk.com": {
            "password": "admin123",
            "name": "Admin Master",
            "role": "admin",
            "active": True,
        },
        "analyst@checkrisk.com": {
            "password": "analyst123",
            "name": "Analyst Demo",
            "role": "analyst",
            "active": True,
        },
    },
    "RISK_DATA_DB": [],        # lista de perfis de risco
    "ANALYSES_DB": {},         # consulta_id -> analysis_obj
    "AUDIT_LOG": [],
    "INFO_SOURCES": [],
}

def _load():
    if not os.path.exists(DATA_FILE):
        return json.loads(json.dumps(_default_data))
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return json.loads(json.dumps(_default_data))

def _save(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

_data = _load()

def persist():
    _save(_data)

# USERS
def get_users_db():
    return _data["USERS_DB"]

def set_user(email, obj):
    _data["USERS_DB"][email] = obj
    persist()

def disable_user_account(email):
    if email in _data["USERS_DB"]:
        _data["USERS_DB"][email]["active"] = False
        persist()

# RISK
def get_risk_db():
    return _data["RISK_DATA_DB"]

def _next_risk_id():
    db = _data["RISK_DATA_DB"]
    return 1 if not db else max(r["id"] for r in db)+1

def upsert_risk_record(
    rid,
    nome,
    nif,
    bi,
    passaporte,
    cartao_residente,
    ramo,
    finalidade,
    canal,
    score_final,
    justificacao,
    pep_alert,
    sanctions_alert,
    historico_pagamentos,
    sinistros_total,
    sinistros_ult_12m,
    fraude_suspeita,
    comentario_fraude,
    condicoes_sugeridas,
    estado,
):
    if rid is not None:
        for row in _data["RISK_DATA_DB"]:
            if row["id"] == rid:
                row.update({
                    "nome": nome,
                    "nif": nif,
                    "bi": bi,
                    "passaporte": passaporte,
                    "cartao_residente": cartao_residente,
                    "ramo": ramo,
                    "finalidade": finalidade,
                    "canal": canal,
                    "score_final": score_final,
                    "justificacao": justificacao,
                    "pep_alert": pep_alert,
                    "sanctions_alert": sanctions_alert,
                    "historico_pagamentos": historico_pagamentos,
                    "sinistros_total": sinistros_total,
                    "sinistros_ult_12m": sinistros_ult_12m,
                    "fraude_suspeita": fraude_suspeita,
                    "comentario_fraude": comentario_fraude,
                    "condicoes_sugeridas": condicoes_sugeridas,
                    "estado": estado,
                })
                persist()
                return row

    row = {
        "id": _next_risk_id(),
        "nome": nome,
        "nif": nif,
        "bi": bi,
        "passaporte": passaporte,
        "cartao_residente": cartao_residente,
        "ramo": ramo,
        "finalidade": finalidade,
        "canal": canal,
        "score_final": score_final,
        "justificacao": justificacao,
        "pep_alert": pep_alert,
        "sanctions_alert": sanctions_alert,
        "historico_pagamentos": historico_pagamentos,
        "sinistros_total": sinistros_total,
        "sinistros_ult_12m": sinistros_ult_12m,
        "fraude_suspeita": fraude_suspeita,
        "comentario_fraude": comentario_fraude,
        "condicoes_sugeridas": condicoes_sugeridas,
        "estado": estado,
    }
    _data["RISK_DATA_DB"].append(row)
    persist()
    return row

def delete_risk_record(rid):
    db = _data["RISK_DATA_DB"]
    for i, row in enumerate(db):
        if row["id"] == rid:
            db.pop(i)
            persist()
            return True
    return False

def update_risk_estado(rid, novo_estado, user_email):
    for row in _data["RISK_DATA_DB"]:
        if row["id"] == rid:
            row["estado"] = novo_estado
            row["decisao_humana"] = user_email
            row["data_decisao"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            persist()
            return True
    return False

def get_risk_by_id(rid):
    for row in _data["RISK_DATA_DB"]:
        if row["id"] == rid:
            return row
    return None

def find_risk_matches(identifier, identifier_type):
    itype = identifier_type.upper().strip()
    target = identifier.strip().upper()
    out = []
    for row in _data["RISK_DATA_DB"]:
        pairs = [
            ("NOME", row.get("nome","")),
            ("NIF", row.get("nif","")),
            ("BI", row.get("bi","")),
            ("PASSAPORTE", row.get("passaporte","")),
            ("CARTAO_RESIDENTE", row.get("cartao_residente","")),
        ]
        for ctype, cval in pairs:
            if ctype.upper()==itype and str(cval).strip().upper()==target:
                out.append(row)
                break
    return out

# ANALYSIS / AUDIT
def get_analyses_db():
    return _data["ANALYSES_DB"]

def save_analysis(analysis_obj):
    _data["ANALYSES_DB"][analysis_obj["consulta_id"]] = analysis_obj
    persist()

def add_audit_log(entry):
    _data["AUDIT_LOG"].append(entry)
    persist()

def get_audit_logs_list():
    return _data["AUDIT_LOG"]

# INFO SOURCES
def get_info_sources():
    return _data["INFO_SOURCES"]

def add_info_source(
    title, description, url, directory, filename,
    categoria, source_owner, validade, uploaded_at
):
    _data["INFO_SOURCES"].append({
        "title": title,
        "description": description,
        "url": url,
        "directory": directory,
        "filename": filename,
        "categoria": categoria,
        "source_owner": source_owner,
        "validade": validade,
        "uploaded_at": uploaded_at,
    })
    persist()

def update_info_source(
    idx, title=None, description=None, url=None,
    directory=None, filename=None,
    categoria=None, source_owner=None, validade=None
):
    if idx < 0 or idx >= len(_data["INFO_SOURCES"]):
        return False
    row = _data["INFO_SOURCES"][idx]
    if title is not None: row["title"]=title
    if description is not None: row["description"]=description
    if url is not None: row["url"]=url
    if directory is not None: row["directory"]=directory
    if filename is not None: row["filename"]=filename
    if categoria is not None: row["categoria"]=categoria
    if source_owner is not None: row["source_owner"]=source_owner
    if validade is not None: row["validade"]=validade
    persist()
    return True

def delete_info_source(idx):
    if idx < 0 or idx >= len(_data["INFO_SOURCES"]):
        return False
    _data["INFO_SOURCES"].pop(idx)
    persist()
    return True
