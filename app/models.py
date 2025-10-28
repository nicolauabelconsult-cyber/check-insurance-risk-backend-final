from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel
import itertools

_user_id_counter = itertools.count(1)
_risk_id_counter = itertools.count(1)
_source_id_counter = itertools.count(1)
_consulta_id_counter = itertools.count(100000)

class User(BaseModel):
    id: int
    name: str
    email: str
    password: str
    role: str  # 'admin', 'analyst', 'fraude', 'compliance'

class RiskRecord(BaseModel):
    id: int
    nome: Optional[str] = None
    nif: Optional[str] = None
    bi: Optional[str] = None
    passaporte: Optional[str] = None
    cartao_residente: Optional[str] = None
    score_final: Optional[int] = None
    justificacao: Optional[str] = None
    pep_alert: bool = False
    sanctions_alert: bool = False
    historico_pagamentos: Optional[str] = None
    sinistros_total: Optional[int] = None
    sinistros_ult_12m: Optional[int] = None
    fraude_suspeita: bool = False
    comentario_fraude: Optional[str] = None
    esg_score: Optional[int] = None
    country_risk: Optional[str] = None
    credit_rating: Optional[str] = None
    kyc_confidence: Optional[str] = None

class InfoSource(BaseModel):
    id: int
    title: str
    description: str
    categoria: Optional[str] = None
    url: Optional[str] = None
    directory: Optional[str] = None
    filename: Optional[str] = None
    source_owner: Optional[str] = None
    validade: Optional[str] = None
    uploaded_at: str

class AuditEntry(BaseModel):
    ts: str
    user_email: str
    consulta_id: str
    identifier: str
    identifier_type: str
    score_final: int
    decisao: str

class ConsultaCache(BaseModel):
    consulta_id: str
    payload: Dict

USERS: Dict[str, User] = {}
RISK_DB: Dict[int, RiskRecord] = {}
INFO_SOURCES: List[InfoSource] = []
AUDIT_LOG: List[AuditEntry] = []
CONSULTAS: Dict[str, ConsultaCache] = {}

def next_user_id():
    return next(_user_id_counter)

def next_risk_id():
    return next(_risk_id_counter)

def next_source_id():
    return next(_source_id_counter)

def next_consulta_id():
    return str(next(_consulta_id_counter))

def timestamp_now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def bootstrap():
    if "admin@checkrisk.com" not in USERS:
        USERS["admin@checkrisk.com"] = User(
            id=next_user_id(),
            name="Administrador",
            email="admin@checkrisk.com",
            password="admin123",  # ALTERAR EM PRODUÇÃO
            role="admin"
        )

bootstrap()
