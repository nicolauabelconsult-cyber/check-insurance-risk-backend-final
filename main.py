from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
import os

app = FastAPI(title="Check Insurance Risk Backend", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Criar pasta reports se não existir
os.makedirs("reports", exist_ok=True)

class LoginRequest(BaseModel):
    email: str
    password: str

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/login")
def login(body: LoginRequest):
    if body.email == "admin@checkrisk.com" and body.password == "admin123":
        return {"access_token": body.email, "user_name": "Administrador", "role": "admin"}
    raise HTTPException(status_code=401, detail="Credenciais inválidas")

@app.get("/api/report/{consulta_id}")
def get_report(consulta_id: str, token: str):
    if token != "admin@checkrisk.com":
        raise HTTPException(status_code=401, detail="Token inválido")
    pdf_path = os.path.join("reports", f"{consulta_id}.pdf")
    with open(pdf_path, "w", encoding="utf-8") as f:
        f.write(f"Relatório Técnico da Consulta {consulta_id}\nGerado em {datetime.utcnow()}")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"relatorio_{consulta_id}.pdf")
