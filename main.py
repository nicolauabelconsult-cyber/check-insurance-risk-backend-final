main_py = r'''
"""
Check Insurance Risk - Sistema de Análise de Risco
FastAPI Backend - Arquivo Principal (versão com /api/auth/me)
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict
import uvicorn
import json
import io
import base64
from datetime import datetime

from auth import verify_token, create_access_token, verify_password
from database import execute_query
from models import (
    LoginRequest,
    RiskCheckRequest,
    DecisionRequest,
    LoginResponse,
    DashboardStats,
    RiskCheckResponse,
    InfoSourceInfo,
    UserInfo,
)
from utils import calculate_risk_score, perform_matching
from reporting import (
    generate_risk_report,
    generate_pdf_report,
    export_to_excel,
    generate_dashboard_charts,
)
from security import get_current_user

app = FastAPI(
    title="Check Insurance Risk API",
    description="Sistema de análise de risco para seguradoras",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # em produção, restringir ao domínio do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Check Insurance Risk API",
        "status": "Online",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# -------------------------------------------------------------------------
# Autenticação
# -------------------------------------------------------------------------
@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login do usuário por username ou email"""
    try:
        query = """
            SELECT id, username, email, password_hash, role, is_active, 
                   last_login, created_at
            FROM users 
            WHERE (username = %s OR email = %s) AND is_active = true
        """
        users = execute_query(query, (request.username, request.username))

        if not users:
            raise HTTPException(status_code=401, detail="Credenciais inválidas")

        user = users[0]

        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Credenciais inválidas")

        execute_query("UPDATE users SET last_login = NOW() WHERE id = %s", (user["id"],))

        token = create_access_token(
            {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
            }
        )

        return {
            "success": True,
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"],
                "last_login": user["last_login"],
                "created_at": user["created_at"],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro no login: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")


@app.get("/api/auth/me", response_model=UserInfo)
async def get_me(current_user: UserInfo = Depends(get_current_user)):
    """Devolver utilizador corrente (usado pelo frontend para validar token)"""
    return current_user


# -------------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------------
@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: UserInfo = Depends(get_current_user)):
    try:
        total = execute_query("SELECT COUNT(*) as count FROM risk_records")[0]["count"]

        pending = execute_query(
            """
            SELECT COUNT(*) as count 
            FROM risk_records 
            WHERE decision = 'UNDER_REVIEW' OR decision IS NULL
        """
        )[0]["count"]

        high_risk = execute_query(
            """
            SELECT COUNT(*) as count 
            FROM risk_records 
            WHERE risk_level IN ('HIGH', 'CRITICAL')
        """
        )[0]["count"]

        sources = execute_query(
            "SELECT COUNT(*) as count FROM info_sources WHERE is_active = true"
        )[0]["count"]

        risk_dist_rows = execute_query(
            """
            SELECT risk_level, COUNT(*) as count
            FROM risk_records
            WHERE risk_level IS NOT NULL
            GROUP BY risk_level
        """
        )
        risk_distribution: Dict[str, int] = {
            row["risk_level"]: row["count"] for row in risk_dist_rows
        }

        recent = execute_query(
            """
            SELECT r.id, r.full_name, r.risk_level, r.risk_score, 
                   r.analyzed_at, r.decision, u.username as analyst_name
            FROM risk_records r
            LEFT JOIN users u ON r.analyzed_by = u.id
            ORDER BY r.analyzed_at DESC 
            LIMIT 10
        """
        )

        return {
            "totalAnalyses": total,
            "pendingReview": pending,
            "highRiskCases": high_risk,
            "activeSources": sources,
            "recentAnalyses": recent,
            "riskDistribution": risk_distribution,
        }

    except Exception as e:
        print(f"Erro dashboard: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")


# -------------------------------------------------------------------------
# Análise de risco
# -------------------------------------------------------------------------
@app.post("/api/risk/check", response_model=RiskCheckResponse)
async def risk_check(
    request: RiskCheckRequest,
    current_user: UserInfo = Depends(get_current_user),
):
    try:
        if not any(
            [request.full_name, request.nif, request.passport, request.resident_card]
        ):
            raise HTTPException(
                status_code=400, detail="Pelo menos um identificador é necessário"
            )

        matches = perform_matching(
            {
                "full_name": request.full_name,
                "nif": request.nif,
                "passport": request.passport,
                "resident_card": request.resident_card,
            }
        )

        risk_data = calculate_risk_score(matches, bool(request.nif))

        query = """
            INSERT INTO risk_records (
                full_name, nif, passport, resident_card, notes,
                risk_score, risk_level, matches, risk_factors,
                analyzed_by, analyzed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, analyzed_at
        """

        result = execute_query(
            query,
            (
                request.full_name,
                request.nif,
                request.passport,
                request.resident_card,
                request.notes,
                risk_data["score"],
                risk_data["level"],
                json.dumps(matches),
                json.dumps(risk_data["factors"]),
                current_user.id,
            ),
        )

        record_id = result[0]["id"]
        analyzed_at = result[0]["analyzed_at"]

        return {
            "success": True,
            "id": record_id,
            "risk_score": risk_data["score"],
            "risk_level": risk_data["level"],
            "matches": matches,
            "risk_factors": risk_data["factors"],
            "analyzed_at": analyzed_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro análise: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")


# -------------------------------------------------------------------------
# Fontes de informação
# -------------------------------------------------------------------------
@app.get("/api/info-sources", response_model=List[InfoSourceInfo])
async def get_info_sources(current_user: UserInfo = Depends(get_current_user)):
    try:
        sources = execute_query(
            """
            SELECT s.*, u.username as uploaded_by_name
            FROM info_sources s
            LEFT JOIN users u ON s.uploaded_by = u.id
            WHERE s.is_active = true
            ORDER BY s.uploaded_at DESC
        """
        )
        return sources
    except Exception as e:
        print(f"Erro fontes: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")


# -------------------------------------------------------------------------
# PDF, Excel, gráficos, decisão e histórico
# -------------------------------------------------------------------------
@app.get("/api/risk/{risk_id}/report/pdf")
async def download_risk_pdf(
    risk_id: int,
    current_user: UserInfo = Depends(get_current_user),
):
    try:
        records = execute_query(
            "SELECT * FROM risk_records WHERE id = %s",
            (risk_id,),
        )
        if not records:
            raise HTTPException(status_code=404, detail="Registo não encontrado")

        risk_record = records[0]
        pdf_info = generate_pdf_report(risk_record)
        if isinstance(pdf_info, dict) and pdf_info.get("error"):
            raise HTTPException(status_code=500, detail=pdf_info["error"])

        pdf_bytes = base64.b64decode(pdf_info["data"])
        filename = pdf_info.get("filename", f"risk_report_{risk_id}.pdf")

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao gerar PDF")


@app.get("/api/risk/export/excel")
async def export_risk_excel(current_user: UserInfo = Depends(get_current_user)):
    try:
        records = execute_query(
            """
            SELECT *
            FROM risk_records
            ORDER BY analyzed_at DESC
        """
        )

        excel_info = export_to_excel(records)
        if isinstance(excel_info, dict) and excel_info.get("error"):
            raise HTTPException(status_code=500, detail=excel_info["error"])

        excel_bytes = base64.b64decode(excel_info["data"])
        filename = excel_info.get(
            "filename",
            f"risk_analysis_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        )

        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro ao exportar Excel: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao exportar Excel")


@app.get("/api/dashboard/charts")
async def get_charts(current_user: UserInfo = Depends(get_current_user)):
    try:
        chart_info = generate_dashboard_charts()
        if isinstance(chart_info, dict) and chart_info.get("error"):
            raise HTTPException(status_code=500, detail=chart_info["error"])
        return chart_info
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro ao gerar gráficos: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao gerar gráficos")


@app.put("/api/risk/{risk_id}/decision")
async def update_risk_decision(
    risk_id: int,
    request: DecisionRequest,
    current_user: UserInfo = Depends(get_current_user),
):
    try:
        result = execute_query(
            """
            UPDATE risk_records
            SET decision = %s,
                analyst_notes = %s
            WHERE id = %s
            RETURNING id, full_name, risk_level, risk_score, 
                      analyzed_at, decision, analyst_notes
        """,
            (
                request.decision,
                request.notes,
                risk_id,
            ),
        )

        if not result:
            raise HTTPException(status_code=404, detail="Registo não encontrado")

        updated = result[0]

        return {
            "success": True,
            "record": updated,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro ao actualizar decisão: {e}")
        raise HTTPException(
            status_code=500, detail="Erro interno ao actualizar decisão de risco"
        )


@app.get("/api/risk/history")
async def get_risk_history(
    full_name: Optional[str] = None,
    nif: Optional[str] = None,
    passport: Optional[str] = None,
    resident_card: Optional[str] = None,
    current_user: UserInfo = Depends(get_current_user),
):
    try:
        if not any([full_name, nif, passport, resident_card]):
            raise HTTPException(
                status_code=400,
                detail="Pelo menos um identificador deve ser fornecido",
            )

        conditions = []
        params = []

        if full_name:
            conditions.append("LOWER(full_name) LIKE LOWER(%s)")
            params.append(f"%{full_name}%")
        if nif:
            conditions.append("nif = %s")
            params.append(nif)
        if passport:
            conditions.append("passport = %s")
            params.append(passport)
        if resident_card:
            conditions.append("resident_card = %s")
            params.append(resident_card)

        where_clause = " OR ".join(conditions)

        query = f"""
            SELECT id, full_name, nif, passport, resident_card,
                   risk_level, risk_score, analyzed_at, decision
            FROM risk_records
            WHERE {where_clause}
            ORDER BY analyzed_at DESC
        """

        history = execute_query(query, tuple(params))

        return {
            "success": True,
            "count": len(history),
            "history": history,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Erro ao obter histórico: {e}")
        raise HTTPException(
            status_code=500, detail="Erro interno ao obter histórico do assegurado"
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
'''

auth_py = r'''
"""
Módulo de autenticação
"""
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import os

SECRET_KEY = os.getenv("AUTH_SECRET", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )
'''

database_py = r'''
"""
Módulo de conexão com banco de dados
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Erro ao conectar com o banco: {e}")
        raise

def execute_query(query: str, params=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        upper = query.strip().upper()
        if upper.startswith('SELECT'):
            result = cursor.fetchall()
        else:
            conn.commit()
            if 'RETURNING' in upper:
                result = cursor.fetchall()
            else:
                result = cursor.rowcount
        return result
    except Exception as e:
        conn.rollback()
        print(f"Erro na query: {e}")
        raise
    finally:
        conn.close()
'''

models_py = r'''
"""
Modelos Pydantic (requests/responses principais)
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class RoleEnum(str, Enum):
    admin = "admin"
    analyst = "analyst"

class SourceTypeEnum(str, Enum):
    PEP = "PEP"
    SANCTIONS = "SANCTIONS"
    FRAUD = "FRAUD"
    CLAIMS = "CLAIMS"
    OTHER = "OTHER"

class RiskLevelEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class DecisionEnum(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    UNDER_REVIEW = "UNDER_REVIEW"

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)

class RiskCheckRequest(BaseModel):
    full_name: Optional[str] = None
    nif: Optional[str] = None
    passport: Optional[str] = None
    resident_card: Optional[str] = None
    notes: Optional[str] = None

class DecisionRequest(BaseModel):
    decision: DecisionEnum
    notes: Optional[str] = None

class InfoSourceRequest(BaseModel):
    name: str = Field(..., max_length=255)
    source_type: SourceTypeEnum

class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    role: RoleEnum
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None

class LoginResponse(BaseModel):
    success: bool
    token: str
    user: UserInfo

class RiskAnalysisInfo(BaseModel):
    id: int
    full_name: Optional[str] = None
    risk_level: Optional[RiskLevelEnum] = None
    risk_score: Optional[int] = None
    analyzed_at: Optional[datetime] = None
    decision: Optional[DecisionEnum] = None
    analyst_name: Optional[str] = None

class DashboardStats(BaseModel):
    totalAnalyses: int
    pendingReview: int
    highRiskCases: int
    activeSources: int
    recentAnalyses: List[RiskAnalysisInfo]
    riskDistribution: Optional[Dict[str, int]] = None

class RiskCheckResponse(BaseModel):
    success: bool
    id: int
    risk_score: int
    risk_level: RiskLevelEnum
    matches: List[Dict[str, Any]]
    risk_factors: List[str]
    analyzed_at: datetime

class InfoSourceInfo(BaseModel):
    id: int
    name: str
    source_type: SourceTypeEnum
    file_type: Optional[str] = None
    num_records: int = 0
    uploaded_at: datetime
    uploaded_by_name: Optional[str] = None
    is_active: bool = True
'''

security_py = r'''
"""
Módulo de segurança
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth import verify_token
from database import execute_query
from models import UserInfo, RoleEnum

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInfo:
    try:
        token = credentials.credentials
        payload = verify_token(token)
        query = """
            SELECT id, username, email, role, is_active, last_login, created_at
            FROM users WHERE id = %s AND is_active = true
        """
        users = execute_query(query, (payload['id'],))
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado"
            )
        user = users[0]
        return UserInfo(
            id=user['id'],
            username=user['username'],
            email=user['email'],
            role=user['role'],
            last_login=user['last_login'],
            created_at=user['created_at']
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )

async def get_admin_user(
    current_user: UserInfo = Depends(get_current_user)
) -> UserInfo:
    if current_user.role != RoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: permissões de administrador necessárias"
        )
    return current_user
'''

utils_py = r'''
"""
Utilitários de análise de risco (matching e score)
"""
import re
from typing import Dict, List, Any
from database import execute_query
import unicodedata

def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = unicodedata.normalize('NFD', name)
    name = ''.join(char for char in name if unicodedata.category(char) != 'Mn')
    name = re.sub(r'\s+', ' ', name.upper().strip())
    return name

def calculate_similarity(name1: str, name2: str) -> float:
    name1 = normalize_name(name1)
    name2 = normalize_name(name2)
    if not name1 or not name2:
        return 0.0
    words1 = set(name1.split())
    words2 = set(name2.split())
    if len(words1) == 0 or len(words2) == 0:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)

def perform_matching(search_data: Dict[str, str]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    try:
        if search_data.get('full_name'):
            name_matches = execute_query("""
                SELECT 
                    ne.id, ne.full_name, ne.nif, ne.passport, ne.resident_card, 
                    ne.position, ne.country, ne.additional_info,
                    s.name as source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true
                AND LOWER(ne.full_name) LIKE LOWER(%s)
            """, (f"%{search_data['full_name']}%",))
            for match in name_matches:
                similarity = calculate_similarity(search_data['full_name'], match['full_name'])
                if similarity > 0.3:
                    matches.append({
                        'type': 'name_match',
                        'similarity': similarity,
                        'source': match['source_name'],
                        'source_type': match['source_type'],
                        'full_name': match['full_name'],
                        'nif': match['nif'],
                        'passport': match['passport'],
                        'resident_card': match['resident_card'],
                        'position': match['position'],
                        'country': match['country'],
                        'additional_info': match['additional_info']
                    })

        if search_data.get('nif'):
            nif_matches = execute_query("""
                SELECT 
                    ne.*, s.name as source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true AND ne.nif = %s
            """, (search_data['nif'],))
            for match in nif_matches:
                matches.append({
                    'type': 'nif_match',
                    'similarity': 1.0,
                    'source': match['source_name'],
                    'source_type': match['source_type'],
                    'full_name': match['full_name'],
                    'nif': match['nif'],
                    'passport': match.get('passport'),
                    'resident_card': match.get('resident_card'),
                    'position': match['position'],
                    'country': match['country']
                })

        if search_data.get('passport'):
            passport_matches = execute_query("""
                SELECT 
                    ne.*, s.name as source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true AND ne.passport = %s
            """, (search_data['passport'],))
            for match in passport_matches:
                matches.append({
                    'type': 'passport_match',
                    'similarity': 1.0,
                    'source': match['source_name'],
                    'source_type': match['source_type'],
                    'full_name': match['full_name'],
                    'nif': match.get('nif'),
                    'passport': match['passport'],
                    'resident_card': match.get('resident_card'),
                    'position': match['position'],
                    'country': match['country']
                })

        if search_data.get('resident_card'):
            card_matches = execute_query("""
                SELECT 
                    ne.*, s.name as source_name, s.source_type
                FROM normalized_entities ne
                JOIN info_sources s ON ne.source_id = s.id
                WHERE s.is_active = true AND ne.resident_card = %s
            """, (search_data['resident_card'],))
            for match in card_matches:
                matches.append({
                    'type': 'resident_card_match',
                    'similarity': 1.0,
                    'source': match['source_name'],
                    'source_type': match['source_type'],
                    'full_name': match['full_name'],
                    'nif': match.get('nif'),
                    'passport': match.get('passport'),
                    'resident_card': match['resident_card'],
                    'position': match['position'],
                    'country': match['country']
                })
    
    except Exception as e:
        print(f"Erro na busca por matches: {e}")
    
    return matches

def calculate_risk_score(matches: List[Dict[str, Any]], has_nif: bool = False) -> Dict[str, Any]:
    base_score = 0
    risk_factors: List[str] = []
    
    if not matches:
        return {
            'score': 10,
            'level': 'LOW',
            'factors': ['Nenhum match encontrado nas bases de dados']
        }
    
    for match in matches:
        match_type = match.get('type', '')
        source_type = match.get('source_type', '')
        similarity = match.get('similarity', 0.0)
        
        if source_type == 'PEP':
            base_score += 40
            risk_factors.append(f"Match em lista PEP: {match.get('full_name', 'N/A')}")
        elif source_type == 'SANCTIONS':
            base_score += 50
            risk_factors.append(f"Match em lista de sanções: {match.get('full_name', 'N/A')}")
        elif source_type == 'FRAUD':
            base_score += 60
            risk_factors.append(f"Match em lista de fraude: {match.get('full_name', 'N/A')}")
        elif source_type == 'CLAIMS':
            base_score += 30
            risk_factors.append(f"Histórico de sinistros: {match.get('full_name', 'N/A')}")
        
        if match_type in ['nif_match', 'passport_match', 'resident_card_match']:
            base_score += 20
        elif match_type == 'name_match' and similarity > 0.8:
            base_score += 15
        elif match_type == 'name_match' and similarity > 0.5:
            base_score += 10
    
    if has_nif:
        base_score += 5
       
