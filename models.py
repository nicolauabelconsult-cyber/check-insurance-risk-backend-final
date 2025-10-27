from pydantic import BaseModel

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    role: str          # 'admin' ou 'analyst'

class RiskCheckRequest(BaseModel):
    identifier: str
    identifier_type: str

class RiskCheckResponse(BaseModel):
    score_final: int
    decisao: str
    justificacao: str
    sanctions_alert: bool
    pep_alert: bool
    consulta_id: str
    timestamp: str

class ErrorResponse(BaseModel):
    detail: str

class StoredAnalysis(BaseModel):
    identifier: str
    identifier_type: str
    score_final: int
    decisao: str
    justificacao: str
    sanctions_alert: bool
    pep_alert: bool
    consulta_id: str
    timestamp: str

class CreateUserRequest(BaseModel):
    email: str
    name: str
    password: str
    role: str  # 'admin' ou 'analyst'
