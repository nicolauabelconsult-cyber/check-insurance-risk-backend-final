from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List
import os
from . import models, schemas, utils

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/admin/risk-data/add-record")
def add_or_update_risk(
    id: str = Form(""),
    nome: str = Form(""),
    nif: str = Form(""),
    bi: str = Form(""),
    passaporte: str = Form(""),
    cartao_residente: str = Form(""),
    score_final: str = Form(""),
    justificacao: str = Form(""),
    pep_alert: str = Form("0"),
    sanctions_alert: str = Form("0"),
    historico_pagamentos: str = Form(""),
    sinistros_total: str = Form(""),
    sinistros_ult_12m: str = Form(""),
    fraude_suspeita: str = Form("0"),
    comentario_fraude: str = Form(""),
    esg_score: str = Form(""),
    country_risk: str = Form(""),
    credit_rating: str = Form(""),
    kyc_confidence: str = Form(""),
    current=Depends(utils.get_current_user)
):
    utils.require_admin(current)

    if id:
        rid = int(id)
        rec = models.RISK_DB.get(rid)
        if not rec:
            raise HTTPException(status_code=404, detail="Registo não encontrado")
    else:
        rid = models.next_risk_id()
        rec = models.RiskRecord(id=rid)

    rec.nome = nome or rec.nome
    rec.nif = nif or rec.nif
    rec.bi = bi or rec.bi
    rec.passaporte = passaporte or rec.passaporte
    rec.cartao_residente = cartao_residente or rec.cartao_residente

    rec.score_final = int(score_final) if score_final else rec.score_final
    rec.justificacao = justificacao or rec.justificacao
    rec.pep_alert = (pep_alert == "1")
    rec.sanctions_alert = (sanctions_alert == "1")

    rec.historico_pagamentos = historico_pagamentos or rec.historico_pagamentos
    rec.sinistros_total = int(sinistros_total) if sinistros_total else rec.sinistros_total
    rec.sinistros_ult_12m = int(sinistros_ult_12m) if sinistros_ult_12m else rec.sinistros_ult_12m
    rec.fraude_suspeita = (fraude_suspeita == "1")
    rec.comentario_fraude = comentario_fraude or rec.comentario_fraude

    rec.esg_score = int(esg_score) if esg_score else rec.esg_score
    rec.country_risk = country_risk or rec.country_risk
    rec.credit_rating = credit_rating or rec.credit_rating
    rec.kyc_confidence = kyc_confidence or rec.kyc_confidence

    models.RISK_DB[rid] = rec
    return {"status":"ok","id": rid}

@router.get("/admin/risk-data/list", response_model=List[schemas.RiskRecordOut])
def list_risk(current=Depends(utils.get_current_user)):
    utils.require_admin(current)
    out = []
    for rec in models.RISK_DB.values():
        out.append({
            "id": rec.id,
            "nome": rec.nome,
            "nif": rec.nif,
            "bi": rec.bi,
            "passaporte": rec.passaporte,
            "cartao_residente": rec.cartao_residente,
            "score_final": rec.score_final,
            "pep_alert": rec.pep_alert,
            "sanctions_alert": rec.sanctions_alert,
            "fraude_suspeita": rec.fraude_suspeita,
            "esg_score": rec.esg_score,
            "credit_rating": rec.credit_rating,
            "kyc_confidence": rec.kyc_confidence,
        })
    return out

@router.post("/admin/risk-data/delete-record")
def delete_risk(id: str = Form(...), current=Depends(utils.get_current_user)):
    utils.require_admin(current)
    rid = int(id)
    if rid in models.RISK_DB:
        del models.RISK_DB[rid]
        return {"status":"deleted"}
    raise HTTPException(status_code=404, detail="Registo não encontrado")

@router.post("/admin/info-sources/upload")
def upload_info_source_file(file: UploadFile = File(...), current=Depends(utils.get_current_user)):
    utils.require_admin(current)
    stored_name = file.filename
    dest_path = os.path.join(UPLOAD_DIR, stored_name)
    with open(dest_path, "wb") as f:
        f.write(file.file.read())
    return {"stored_filename": stored_name}

@router.post("/admin/info-sources/create")
def create_info_source(
    title: str = Form(""),
    description: str = Form(""),
    url: str = Form(""),
    directory: str = Form(""),
    filename: str = Form(""),
    categoria: str = Form(""),
    source_owner: str = Form(""),
    validade: str = Form(""),
    current=Depends(utils.get_current_user)
):
    utils.require_admin(current)
    if not title or not description:
        raise HTTPException(status_code=422, detail="Título e Descrição obrigatórios")

    src = models.InfoSource(
        id=models.next_source_id(),
        title=title,
        description=description,
        categoria=categoria or None,
        url=url or None,
        directory=directory or None,
        filename=filename or None,
        source_owner=source_owner or None,
        validade=validade or None,
        uploaded_at=models.timestamp_now()
    )
    models.INFO_SOURCES.append(src)
    return {"status":"ok","id": src.id}

@router.get("/admin/info-sources/list", response_model=List[schemas.InfoSourceOut])
def list_info_sources(current=Depends(utils.get_current_user)):
    utils.require_admin(current)
    return [
        {
            "title": s.title,
            "description": s.description,
            "categoria": s.categoria,
            "url": s.url,
            "directory": s.directory,
            "filename": s.filename,
            "source_owner": s.source_owner,
            "validade": s.validade,
            "uploaded_at": s.uploaded_at,
        }
        for s in models.INFO_SOURCES
    ]

@router.post("/admin/info-sources/delete")
def delete_info_source(index: str = Form(...), current=Depends(utils.get_current_user)):
    utils.require_admin(current)
    idx = int(index)
    if 0 <= idx < len(models.INFO_SOURCES):
        models.INFO_SOURCES.pop(idx)
        return {"status":"deleted"}
    raise HTTPException(status_code=404, detail="Fonte não encontrada")

@router.get("/admin/audit/list")
def list_audit(current=Depends(utils.get_current_user)):
    utils.require_admin(current)
    return [a.dict() for a in models.AUDIT_LOG]
