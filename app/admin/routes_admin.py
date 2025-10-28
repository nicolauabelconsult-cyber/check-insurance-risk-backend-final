import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from app.auth.security import get_current_user, require_admin
from app.admin.storage_users import create_user, list_users
from app.admin.storage_audit import list_audit
from app.risk.storage_risk import add_or_update_record, list_records, delete_record
from app.admin.storage_sources import add_source, list_sources, delete_source
from app.config import UPLOAD_DIR
from app.ai.reader_ai import analyze_file

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/users/list")
def users_list(user=Depends(get_current_user)):
    require_admin(user)
    return list_users()

@router.post("/users/create")
def users_create(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...)
, user=Depends(get_current_user)):
    require_admin(user)
    create_user(name, email, password, role)
    return {"ok": True}

@router.get("/audit/list")
def audit_list(user=Depends(get_current_user)):
    require_admin(user)
    return list_audit()

@router.post("/risk-data/add-record")
def risk_add_record(
    id: Optional[str] = Form(None),
    nome: str = Form(""), nif: str = Form(""), bi: str = Form(""), passaporte: str = Form(""), cartao_residente: str = Form(""), 
    score_final: str = Form(""), justificacao: str = Form(""), pep_alert: str = Form("0"), sanctions_alert: str = Form("0"), 
    historico_pagamentos: str = Form(""), sinistros_total: str = Form(""), sinistros_ult_12m: str = Form(""), 
    fraude_suspeita: str = Form("0"), comentario_fraude: str = Form(""), 
    esg_score: str = Form(""), country_risk: str = Form(""), credit_rating: str = Form(""), kyc_confidence: str = Form("")
, user=Depends(get_current_user)):
    require_admin(user)

    data = {
        "id": id,
        "nome": nome,
        "nif": nif,
        "bi": bi,
        "passaporte": passaporte,
        "cartao_residente": cartao_residente,
        "score_final": score_final,
        "justificacao": justificacao,
        "pep_alert": pep_alert == "1",
        "sanctions_alert": sanctions_alert == "1",
        "historico_pagamentos": historico_pagamentos,
        "sinistros_total": sinistros_total,
        "sinistros_ult_12m": sinistros_ult_12m,
        "fraude_suspeita": fraude_suspeita == "1",
        "comentario_fraude": comentario_fraude,
        "esg_score": esg_score,
        "country_risk": country_risk,
        "credit_rating": credit_rating,
        "kyc_confidence": kyc_confidence
    }

    new_id = add_or_update_record(data)
    return {"id": new_id}

@router.get("/risk-data/list")
def risk_list(user=Depends(get_current_user)):
    require_admin(user)
    return list_records()

@router.post("/risk-data/delete-record")
def risk_del(id: str = Form(...), user=Depends(get_current_user)):
    require_admin(user)
    ok = delete_record(id)
    if not ok:
        raise HTTPException(status_code=404, detail="Registo não existe")
    return {"ok": True}

@router.post("/info-sources/upload")
def upload_source_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    require_admin(user)
    filename = file.filename
    dest_path = os.path.join(UPLOAD_DIR, filename)
    with open(dest_path, "wb") as f:
        f.write(file.file.read())
    return {"stored_filename": filename}

@router.post("/info-sources/create")
def create_source(
    title: str = Form(""), description: str = Form(""), url: str = Form(""), directory: str = Form(""), filename: str = Form(""), 
    categoria: str = Form(""), source_owner: str = Form(""), validade: str = Form("")
, user=Depends(get_current_user)):
    require_admin(user)

    if not title or not description:
        raise HTTPException(status_code=422, detail="Campos obrigatórios em falta")

    meta = {
        "title": title,
        "description": description,
        "url": url,
        "directory": directory,
        "filename": filename,
        "categoria": categoria,
        "source_owner": source_owner,
        "validade": validade,
        "uploaded_at": "agora"
    }
    add_source(meta)
    return {"ok": True}

@router.get("/info-sources/list")
def list_sources_api(user=Depends(get_current_user)):
    require_admin(user)
    return list_sources()

@router.post("/info-sources/delete")
def delete_source_api(index: int = Form(...), user=Depends(get_current_user)):
    require_admin(user)
    ok = delete_source(index)
    if not ok:
        raise HTTPException(status_code=404, detail="Índice inválido")
    return {"ok": True}

@router.get("/info-sources/analisar-fonte")
def analisar_fonte(file: str, user=Depends(get_current_user)):
    require_admin(user)
    path = os.path.join(UPLOAD_DIR, file)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Ficheiro não encontrado")
    result = analyze_file(path)
    return result
