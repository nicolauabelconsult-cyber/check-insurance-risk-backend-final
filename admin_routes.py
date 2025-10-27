
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from datetime import datetime, timezone
import os

from storage import (
    get_audit_logs_list,
    get_info_sources,
    add_info_source,
    update_info_source,
    delete_info_source,
    get_risk_db,
    upsert_risk_record,
    delete_risk_record,
    update_risk_estado,
)
from auth import get_current_user, assert_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/audit/logs")
def get_audit_logs(limit: int = 20, user=Depends(get_current_user)):
    assert_admin(user)
    ordered = sorted(get_audit_logs_list(), key=lambda x: x["timestamp"], reverse=True)
    return ordered[:limit]

# ------- BASE RISCO -------
@router.post("/risk-data/add-record")
def add_risk_record(
    id: str = Form(""),
    nome: str = Form(""),
    nif: str = Form(""),
    bi: str = Form(""),
    passaporte: str = Form(""),
    cartao_residente: str = Form(""),
    ramo: str = Form(""),
    finalidade: str = Form("Subscrição"),
    canal: str = Form("Interno"),
    score_final: int = Form(...),
    justificacao: str = Form(...),
    pep_alert: int = Form(...),
    sanctions_alert: int = Form(...),
    historico_pagamentos: str = Form(""),
    sinistros_total: int = Form(0),
    sinistros_ult_12m: int = Form(0),
    fraude_suspeita: int = Form(0),
    comentario_fraude: str = Form(""),
    condicoes_sugeridas: str = Form(""),
    estado: str = Form("Em análise"),
    user=Depends(get_current_user),
):
    assert_admin(user)
    rid = int(id) if id.strip() else None
    row = upsert_risk_record(
        rid=rid,
        nome=nome.strip(),
        nif=nif.strip(),
        bi=bi.strip(),
        passaporte=passaporte.strip(),
        cartao_residente=cartao_residente.strip(),
        ramo=ramo.strip(),
        finalidade=finalidade.strip(),
        canal=canal.strip(),
        score_final=int(score_final),
        justificacao=justificacao,
        pep_alert=bool(int(pep_alert)),
        sanctions_alert=bool(int(sanctions_alert)),
        historico_pagamentos=historico_pagamentos,
        sinistros_total=int(sinistros_total),
        sinistros_ult_12m=int(sinistros_ult_12m),
        fraude_suspeita=bool(int(fraude_suspeita)),
        comentario_fraude=comentario_fraude,
        condicoes_sugeridas=condicoes_sugeridas,
        estado=estado,
    )
    return {"status":"ok","id":row["id"]}

@router.post("/risk-data/delete-record")
def remove_risk_record(id: int = Form(...), user=Depends(get_current_user)):
    assert_admin(user)
    ok = delete_risk_record(id)
    if not ok:
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    return {"status":"ok","deleted":id}

@router.post("/risk-data/update-estado")
def update_estado(
    id: int = Form(...),
    novo_estado: str = Form(...),
    user=Depends(get_current_user)
):
    assert_admin(user)
    ok = update_risk_estado(id, novo_estado, getattr(user,"email","desconhecido"))
    if not ok:
        raise HTTPException(status_code=404, detail="Registo não encontrado")
    return {"status":"ok","updated":id,"estado":novo_estado}

@router.get("/risk-data/list")
def list_risk_data(user=Depends(get_current_user)):
    assert_admin(user)
    return get_risk_db()

# ------- FONTES INFO -------
@router.post("/info-sources/create")
def create_info_source(
    title: str = Form(...),
    description: str = Form(...),
    url: str = Form(""),
    directory: str = Form(""),
    filename: str = Form(""),
    categoria: str = Form("Outro"),
    source_owner: str = Form(""),
    validade: str = Form(""),
    user=Depends(get_current_user),
):
    assert_admin(user)
    add_info_source(
        title=title,
        description=description,
        url=url,
        directory=directory,
        filename=filename,
        categoria=categoria,
        source_owner=source_owner,
        validade=validade,
        uploaded_at=datetime.now(timezone.utc).isoformat()
    )
    return {"status":"ok"}

@router.post("/info-sources/update")
def edit_info_source(
    index: int = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    url: str = Form(""),
    directory: str = Form(""),
    filename: str = Form(""),
    categoria: str = Form(""),
    source_owner: str = Form(""),
    validade: str = Form(""),
    user=Depends(get_current_user),
):
    assert_admin(user)
    ok = update_info_source(
        idx=index,
        title=title,
        description=description,
        url=url,
        directory=directory,
        filename=filename,
        categoria=categoria or None,
        source_owner=source_owner or None,
        validade=validade or None,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Fonte não encontrada")
    return {"status":"ok","updated":index}

@router.post("/info-sources/delete")
def remove_info_source(
    index: int = Form(...),
    user=Depends(get_current_user),
):
    assert_admin(user)
    ok = delete_info_source(index)
    if not ok:
        raise HTTPException(status_code=404, detail="Fonte não encontrada")
    return {"status":"ok","deleted":index}

@router.post("/info-sources/upload")
def upload_info_source_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    assert_admin(user)
    from storage import UPLOAD_DIR
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as f:
        f.write(file.file.read())
    return {"status":"ok","stored_filename":file.filename}

@router.get("/info-sources/list")
def list_info_sources(user=Depends(get_current_user)):
    assert_admin(user)
    return get_info_sources()
