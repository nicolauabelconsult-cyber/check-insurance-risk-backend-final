# schemas.py
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ---------- Users & Auth ----------

class UserBase(BaseModel):
    username: str
    full_name: str
    is_admin: bool
    is_active: bool


class UserCreate(BaseModel):
    username: str
    full_name: str
    password: str
    is_admin: bool = False


class UserRead(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Risk check ----------

class RiskCheckRequest(BaseModel):
    full_name: str = Field(..., description="Nome completo do cliente")
    nif: Optional[str] = None
    passport: Optional[str] = None
    residence_card: Optional[str] = None
    extra_info: Optional[str] = None


class Match(BaseModel):
    source_id: int
    source_name: str
    source_type: str
    match_name: str
    match_identifier: Optional[str] = None
    similarity: float
    details: dict


class RiskFactor(BaseModel):
    code: str
    description: str
    weight: int


class RiskCheckResponse(BaseModel):
    id: int
    full_name: str
    nif: Optional[str]
    passport: Optional[str]
    residence_card: Optional[str]
    risk_score: int
    risk_level: str
    is_pep: bool
    has_sanctions: bool
    matches: List[Match]
    factors: List[RiskFactor]
    decision: Optional[str]
    analyst_notes: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class RiskHistoryItem(BaseModel):
    id: int
    full_name: str
    nif: Optional[str]
    risk_score: int
    risk_level: str
    is_pep: bool
    has_sanctions: bool
    created_at: datetime

    class Config:
        orm_mode = True


class RiskDecisionUpdate(BaseModel):
    decision: str  # ACCEPT, CONDITIONAL, REJECT
    analyst_notes: Optional[str] = None
    primary_match_index: Optional[int] = Field(
        default=None,
        description="Índice do match escolhido como principal (0, 1, 2, ...). Opcional."
    )


# ---------- Info Sources ----------

class InfoSourceRead(BaseModel):
    id: int
    name: str
    source_type: str
    description: str
    num_records: int
    created_at: datetime

    class Config:
        orm_mode = True


# ---------- Audit Logs ----------

class AuditLogRead(BaseModel):
    id: int
    timestamp: datetime
    username: Optional[str]
    action: str
    details: Optional[str]
    ip_address: Optional[str]

    class Config:
        orm_mode = True
