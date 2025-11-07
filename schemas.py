from pydantic import BaseModel, EmailStr

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
