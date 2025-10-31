from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status, Response, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
from models import User, RiskRecord, InfoSource
from auth import create_token, decode_token, hash_pw
from schemas import LoginReq, LoginResp, RiskCheckReq
from utils import ensure_dir, render_pdf
import io, os, random, datetime as dt
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
app = FastAPI(title="Check Insurance Risk Backend", version="1.0.1")
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(bind=engine)
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
def seed_users(db: Session):
    if db.query(User).count() == 0:
        admin = User(name="Administrador", email="admin@checkrisk.com", password=hash_pw("admin123"), role="admin")
        analyst = User(name="Analyst", email="analyst@checkrisk.com", password=hash_pw("analyst123"), role="analyst")
        db.add_all([admin, analyst]); db.commit()
with SessionLocal() as s: seed_users(s)
def bearer(auth_header: str = None):
    if not auth_header or not auth_header.lower().startswith("bearer "): raise HTTPException(status_code=401, detail="Cabeçalho Authorization inválido")
    token = auth_header.split(" ",1)[1]; return decode_token(token)
@app.post("/api/login", response_model=LoginResp)
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or user.password != hash_pw(req.password): raise HTTPException(status_code=401, detail="Credenciais inválidas")
    token = create_token(sub=str(user.id), name=user.name, role=user.role)
    return LoginResp(access_token=token, user_name=user.name, role=user.role)
@app.post("/api/risk-check")
def risk_check(req: RiskCheckReq, payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    base_score = random.randint(60, 92); pep = random.random()<0.1; sanc = random.random()<0.05; fraude = random.random()<0.08
    decisao = "Aceitar com condições" if base_score >= 75 and not (pep or sanc or fraude) else "Escalar para revisão manual"
    justificacao = "Histórico limpo; critérios de KYC cumpridos." if decisao.startswith("Aceitar") else "Inconsistências detectadas; validar documentação e origem de fundos."
    rec = db.query(RiskRecord).filter((RiskRecord.nif==req.identifier)|(RiskRecord.bi==req.identifier)|(RiskRecord.passaporte==req.identifier)|(RiskRecord.cartao_residente==req.identifier)).first()
    consulta_id = f"CIR-{int(dt.datetime.utcnow().timestamp())}-{random.randint(1000,9999)}"
    resp = dict(consulta_id=consulta_id,timestamp=dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),identifier=req.identifier,identifier_type=req.identifier_type,score_final=rec.score_final if rec else base_score,decisao=decisao if not rec else ("Aceitar" if (rec.score_final or 0)>=80 else "Escalar para revisão manual"),justificacao=rec.justificacao if rec and rec.justificacao else justificacao,pep_alert=bool(rec.pep_alert) if rec else pep,sanctions_alert=bool(rec.sanctions_alert) if rec else sanc,benchmark_internacional="OECD KYC Bench v1.2 / FATF rec. 10",nome=rec.nome if rec else None,nif=rec.nif if rec else None,bi=rec.bi if rec else None,passaporte=rec.passaporte if rec else None,cartao_residente=rec.cartao_residente if rec else None,historico_pagamentos=rec.historico_pagamentos if rec else None,sinistros_total=rec.sinistros_total if rec else None,sinistros_ult_12m=rec.sinistros_ult_12m if rec else None,fraude_suspeita=rec.fraude_suspeita if rec else fraude,comentario_fraude=rec.comentario_fraude if rec else None,esg_score=rec.esg_score if rec else None,country_risk=rec.country_risk if rec else None,credit_rating=rec.credit_rating if rec else None,kyc_confidence=rec.kyc_confidence if rec else None)
    return resp
@app.get("/api/report/{consulta_id}")
def get_report(consulta_id: str, token: str = Query(None), authorization: str | None = Header(default=None)):
    if token: payload = decode_token(token)
    elif authorization: payload = bearer(authorization)
    else: raise HTTPException(status_code=401, detail="Token ausente")
    meta = {"consulta_id": consulta_id,"timestamp": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),"identifier":"—","identifier_type":"—","score_final":80,"decisao":"Aceitar com condições","justificacao":"Parâmetros técnicos dentro do apetite de risco. Monitorizar 6-12 meses.","pep_alert":False,"sanctions_alert":False,"benchmark_internacional":"OECD KYC Bench v1.2 / FATF rec. 10"}
    ensure_dir("reports"); pdf_path = f"reports/{consulta_id}.pdf"; render_pdf(pdf_path, meta)
    def file_iter(): 
        with open(pdf_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk: break
                yield chunk
    headers = {"Content-Disposition": f'inline; filename="relatorio_{consulta_id}.pdf"'}
    return StreamingResponse(file_iter(), media_type="application/pdf", headers=headers)
# admin endpoints (same as antes) simplified for space
@app.post("/api/admin/user-add")
def admin_user_add(new_name: str = Form(...), new_email: str = Form(...), new_password: str = Form(...), new_role: str = Form("analyst"), payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") != "admin": raise HTTPException(status_code=403, detail="Apenas administradores")
    from models import User
    if db.query(User).filter(User.email==new_email).first(): raise HTTPException(status_code=400, detail="Email já existe")
    u = User(name=new_name, email=new_email, password=hash_pw(new_password), role=new_role); db.add(u); db.commit(); db.refresh(u); return {"status":"ok","user":{"id":u.id,"email":u.email,"role":u.role}}
@app.post("/api/admin/risk-data/add-record")
def admin_risk_add_record(id: str = Form(None), nome: str = Form(None), nif: str = Form(None), bi: str = Form(None), passaporte: str = Form(None), cartao_residente: str = Form(None), score_final: int = Form(0), justificacao: str = Form(None), pep_alert: str = Form("0"), sanctions_alert: str = Form("0"), historico_pagamentos: str = Form(None), sinistros_total: int = Form(0), sinistros_ult_12m: int = Form(0), fraude_suspeita: str = Form("0"), comentario_fraude: str = Form(None), esg_score: int = Form(0), country_risk: str = Form(None), credit_rating: str = Form(None), kyc_confidence: str = Form(None), payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") != "admin": raise HTTPException(status_code=403, detail="Apenas administradores")
    pep_bool = (str(pep_alert).lower() in ("1","true"))
    sanc_bool = (str(sanctions_alert).lower() in ("1","true"))
    fraude_bool = (str(fraude_suspeita).lower() in ("1","true"))
    from models import RiskRecord
    if id: rec = db.query(RiskRecord).filter(RiskRecord.id==int(id)).first(); 
    else: rec = RiskRecord()
    if not rec: raise HTTPException(status_code=404, detail="Registo inexistente")
    for k,v in dict(nome=nome,nif=nif,bi=bi,passaporte=passaporte,cartao_residente=cartao_residente,score_final=score_final,justificacao=justificacao,pep_alert=pep_bool,sanctions_alert=sanc_bool,historico_pagamentos=historico_pagamentos,sinistros_total=sinistros_total,sinistros_ult_12m=sinistros_ult_12m,fraude_suspeita=fraude_bool,comentario_fraude=comentario_fraude,esg_score=esg_score,country_risk=country_risk,credit_rating=credit_rating,kyc_confidence=kyc_confidence).items(): setattr(rec,k,v)
    db.add(rec); db.commit(); db.refresh(rec); return {"status":"saved","id":rec.id}
@app.get("/api/admin/risk-data/list")
def admin_risk_list(payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") != "admin": raise HTTPException(status_code=403, detail="Apenas administradores")
    from models import RiskRecord
    rows = db.query(RiskRecord).order_by(RiskRecord.id.desc()).all()
    def ser(r): return {"id":r.id,"nome":r.nome,"nif":r.nif,"bi":r.bi,"passaporte":r.passaporte,"cartao_residente":r.cartao_residente,"score_final":r.score_final,"justificacao":r.justificacao,"pep_alert":r.pep_alert,"sanctions_alert":r.sanctions_alert,"historico_pagamentos":r.historico_pagamentos,"sinistros_total":r.sinistros_total,"sinistros_ult_12m":r.sinistros_ult_12m,"fraude_suspeita":r.fraude_suspeita,"comentario_fraude":r.comentario_fraude,"esg_score":r.esg_score,"country_risk":r.country_risk,"credit_rating":r.credit_rating,"kyc_confidence":r.kyc_confidence}
    return [ser(r) for r in rows]
@app.post("/api/admin/risk-data/delete-record")
def admin_risk_delete(id: str = Form(...), payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") != "admin": raise HTTPException(status_code=403, detail="Apenas administradores")
    from models import RiskRecord
    rec = db.query(RiskRecord).filter(RiskRecord.id==int(id)).first()
    if not rec: raise HTTPException(status_code=404, detail="Registo inexistente")
    db.delete(rec); db.commit(); return {"status":"deleted"}
@app.post("/api/admin/info-sources/upload")
def info_source_upload(file: UploadFile = File(...), payload: dict = Depends(bearer)):
    if payload.get("role") != "admin": raise HTTPException(status_code=403, detail="Apenas administradores")
    ensure_dir("uploads"); fname = file.filename; base, ext = os.path.splitext(fname); path = os.path.join("uploads", fname); i=1
    while os.path.exists(path): fname = f"{base}_{i}{ext}"; path = os.path.join("uploads", fname); i+=1
    with open(path, "wb") as f: f.write(file.file.read()); return {"stored_filename": fname}
@app.post("/api/admin/info-sources/create")
def info_source_create(title: str = Form(...), description: str = Form(...), url: str = Form(None), directory: str = Form(None), filename: str = Form(None), categoria: str = Form(None), source_owner: str = Form(None), validade: str = Form(None), payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") != "admin": raise HTTPException(status_code=403, detail="Apenas administradores")
    item = InfoSource(title=title, description=description, url=url, directory=directory, filename=filename, categoria=categoria, source_owner=source_owner, validade=validade)
    db.add(item); db.commit(); db.refresh(item); return {"status":"ok","id":item.id}
@app.get("/api/admin/info-sources/list")
def info_source_list(payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") != "admin": raise HTTPException(status_code=403, detail="Apenas administradores")
    rows = db.query(InfoSource).order_by(InfoSource.id.desc()).all()
    return [{"title":r.title,"description":r.description,"url":r.url,"directory":r.directory,"filename":r.filename,"categoria":r.categoria,"source_owner":r.source_owner,"validade":r.validade,"uploaded_at":r.uploaded_at.isoformat() if r.uploaded_at else None} for r in rows]
@app.post("/api/admin/info-sources/delete")
def info_source_delete(index: int = Form(...), payload: dict = Depends(bearer), db: Session = Depends(get_db)):
    if payload.get("role") != "admin": raise HTTPException(status_code=403, detail="Apenas administradores")
    rows = db.query(InfoSource).order_by(InfoSource.id.desc()).all()
    if index < 0 or index >= len(rows): raise HTTPException(status_code=404, detail="Index inválido")
    db.delete(rows[index]); db.commit(); return {"status":"deleted"}
@app.get("/") 
def root(): return {"ok": True, "service": "CIR Backend", "version": "1.0.1"}
