"""
Check Insurance Risk - Sistema de Análise de Risco
FastAPI Backend - Arquivo Principal
"""
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict
import uvicorn
import os
import json
from datetime import datetime

# Imports locais
from auth import verify_token, create_access_token, verify_password
from database import execute_query
from models import LoginRequest, RiskCheckRequest, DecisionRequest
from utils import calculate_risk_score, perform_matching
from reporting import generate_risk_report
from security import get_current_user

app = FastAPI(
    title="Check Insurance Risk API",
    description="Sistema de análise de risco para seguradoras",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure para seu domínio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

@app.get("/")
async def root():
    """Health check"""
    return {
        "message": "Check Insurance Risk API",
        "status": "Online",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Login do usuário"""
    try:
        # Buscar usuário
        query = """
            SELECT id, username, email, password_hash, role, is_active, last_login
            FROM users 
            WHERE (username = %s OR email = %s) AND is_active = true
        """
        users = execute_query(query, (request.username, request.username))
        
        if not users:
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        
        user = users[0]
        
        # Verificar senha
        if not verify_password(request.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        
        # Atualizar last_login
        execute_query("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))
        
        # Criar token
        token = create_access_token({
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "role": user['role']
        })
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "email": user['email'],
                "role": user['role']
            }
        }
        
    except Exception as e:
        print(f"Erro no login: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Estatísticas do dashboard"""
    try:
        verify_token(credentials.credentials)
        
        # Total de análises
        total = execute_query("SELECT COUNT(*) as count FROM risk_records")[0]['count']
        
        # Pendentes
        pending = execute_query(
            "SELECT COUNT(*) as count FROM risk_records WHERE decision = 'UNDER_REVIEW' OR decision IS NULL"
        )[0]['count']
        
        # Alto risco
        high_risk = execute_query(
            "SELECT COUNT(*) as count FROM risk_records WHERE risk_level IN ('HIGH', 'CRITICAL')"
        )[0]['count']
        
        # Fontes ativas
        sources = execute_query(
            "SELECT COUNT(*) as count FROM info_sources WHERE is_active = true"
        )[0]['count']
        
        # Análises recentes
        recent = execute_query("""
            SELECT r.id, r.full_name, r.risk_level, r.risk_score, 
                   r.analyzed_at, r.decision, u.username as analyst_name
            FROM risk_records r
            LEFT JOIN users u ON r.analyzed_by = u.id
            ORDER BY r.analyzed_at DESC LIMIT 10
        """)
        
        return {
            "totalAnalyses": total,
            "pendingReview": pending,
            "highRiskCases": high_risk,
            "activeSources": sources,
            "recentAnalyses": recent
        }
        
    except Exception as e:
        print(f"Erro dashboard: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")

@app.post("/api/risk/check")
async def risk_check(request: RiskCheckRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Análise de risco"""
    try:
        user_data = verify_token(credentials.credentials)
        
        # Validar entrada
        if not any([request.full_name, request.nif, request.passport, request.resident_card]):
            raise HTTPException(status_code=400, detail="Pelo menos um identificador é necessário")
        
        # Buscar matches
        matches = perform_matching({
            "full_name": request.full_name,
            "nif": request.nif,
            "passport": request.passport,
            "resident_card": request.resident_card
        })
        
        # Calcular risco
        risk_data = calculate_risk_score(matches, bool(request.nif))
        
        # Salvar registro
        query = """
            INSERT INTO risk_records (
                full_name, nif, passport, resident_card, notes,
                risk_score, risk_level, matches, risk_factors,
                analyzed_by, analyzed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        
        result = execute_query(query, (
            request.full_name, request.nif, request.passport, request.resident_card,
            request.notes, risk_data['score'], risk_data['level'],
            json.dumps(matches), json.dumps(risk_data['factors']),
            user_data['id']
        ))
        
        return {
            "success": True,
            "id": result[0]['id'],
            "risk_score": risk_data['score'],
            "risk_level": risk_data['level'],
            "matches": matches,
            "risk_factors": risk_data['factors']
        }
        
    except Exception as e:
        print(f"Erro análise: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")

@app.get("/api/info-sources")
async def get_info_sources(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Listar fontes de informação"""
    try:
        verify_token(credentials.credentials)
        
        sources = execute_query("""
            SELECT s.*, u.username as uploaded_by_name
            FROM info_sources s
            LEFT JOIN users u ON s.uploaded_by = u.id
            WHERE s.is_active = true
            ORDER BY s.uploaded_at DESC
        """)
        
        return sources
        
    except Exception as e:
        print(f"Erro fontes: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
