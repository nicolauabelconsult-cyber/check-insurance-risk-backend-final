from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    token: str
    user: dict

class RiskCheckRequest(BaseModel):
    identificador: str

class RiskCheckResponse(BaseModel):
    consulta_id: str
    score_final: int
    decisao: str
    justificacao: str
    sanctions_alert: bool
    sanctions_note: str
    resumo_financeiro: str
    resumo_sinistros: str
    resumo_reputacao: str
    timestamp: datetime

class ContactRequest(BaseModel):
    nome: str
    email: EmailStr
    mensagem: Optional[str] = ""
    assunto: Optional[str] = ""

class ContactResponse(BaseModel):
    status: str
    message: str
