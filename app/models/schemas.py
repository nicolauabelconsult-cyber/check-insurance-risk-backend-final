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
    identifier_type: str  # NIF | BI | NOME

class RiskCheckResponse(BaseModel):
    consulta_id: str
    timestamp: str
    score_final: int
    decisao: str
    pep_alert: bool
    sanctions_alert: bool
    justificacao: str
    benchmark_internacional: str
