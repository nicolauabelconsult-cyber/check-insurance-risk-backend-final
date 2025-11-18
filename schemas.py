"""
Schemas de validação
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from models import RoleEnum, SourceTypeEnum, RiskLevelEnum, DecisionEnum

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    password: str = Field(..., min_length=6)
    role: RoleEnum = Field(default=RoleEnum.analyst)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    email: Optional[str] = Field(None, regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None

class InfoSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_type: SourceTypeEnum
    url: Optional[str] = None
    
    @validator('url')
    def validate_url(cls, v):
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('URL deve começar com http:// ou https://')
        return v

class RiskRecordCreate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    nif: Optional[str] = Field(None, max_length=50)
    passport: Optional[str] = Field(None, max_length=50)
    resident_card: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    
    @validator('full_name', 'nif', 'passport', 'resident_card')
    def at_least_one_identifier(cls, v, values):
        if not any([v, values.get('full_name'), values.get('nif'), 
                   values.get('passport'), values.get('resident_card')]):
            raise ValueError('Pelo menos um identificador deve ser fornecido')
        return v

class RiskDecision(BaseModel):
    decision: DecisionEnum
    analyst_notes: Optional[str] = None

class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=100)

class PaginationResponse(BaseModel):
    page: int
    limit: int
    total: int
    totalPages: int
    hasNext: bool
    hasPrev: bool

class ApiResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
