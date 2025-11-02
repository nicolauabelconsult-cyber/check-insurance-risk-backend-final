from pydantic import BaseModel, field_validator, EmailStr
class LoginReq(BaseModel):
    email: EmailStr
    password: str
class LoginResp(BaseModel):
    access_token: str
    user_name: str
    role: str
class RiskCheckReq(BaseModel):
    identifier: str
    identifier_type: str
    @field_validator("identifier_type")
    @classmethod
    def normalize_type(cls, v):
        v = v.upper()
        allowed = {"NIF", "BI", "PASSAPORTE", "CARTAO_RESIDENTE", "NOME"}
        if v not in allowed:
            raise ValueError("identifier_type inválido")
        return v
