from pydantic import BaseModel
from typing import Optional, List

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    user_name: str
    role: str

class RiskCheckRequest(BaseModel):
    identifier: str
    identifier_type: str

class RiskCheckResponse(BaseModel):
    consulta_id: str
    timestamp: str
    score_final: int
    decisao: str
    justificacao: str
    pep_alert: bool
    sanctions_alert: bool
    benchmark_internacional: Optional[str] = None

class RiskRecordOut(BaseModel):
    id: int
    nome: Optional[str]
    nif: Optional[str]
    bi: Optional[str]
    passaporte: Optional[str]
    cartao_residente: Optional[str]
    score_final: Optional[int]
    pep_alert: bool
    sanctions_alert: bool
    fraude_suspeita: bool
    esg_score: Optional[int]
    credit_rating: Optional[str]
    kyc_confidence: Optional[str]

class InfoSourceOut(BaseModel):
    title: str
    description: str
    categoria: Optional[str]
    url: Optional[str]
    directory: Optional[str]
    filename: Optional[str]
    source_owner: Optional[str]
    validade: Optional[str]
    uploaded_at: str
