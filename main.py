"""
Check Insurance Risk - Sistema de Análise de Risco
FastAPI Backend - Arquivo Principal (ajustado)
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict
import uvicorn
import os
import json
import io
import base64
from datetime import datetime

# Imports locais
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
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restringe ao teu domínio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check"""
    return {
        "message": "Check Insurance Risk API",
        "status": "Online",
        "version": "1.1.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# -------------------------------------------------------------------------
# Autenticação
# -------------------------------------------------------------------------
@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login do usuário"""
    try:
        # Buscar usuário por username ou email
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

        # Verificar senha
        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Credenciais inválidas")

        # Atualizar last_login
        execute_query("UPDATE users SET last_login = NOW() WHERE id = %s", (user["id"],))

        # Criar token JWT
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


# -------------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------------
@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: UserInfo = Depends(get_current_user)):
    """Estatísticas do dashboard"""
    try:
        # Total de análises
        total = execute_query("SELECT COUNT(*) as count FROM risk_records")[0]["count"]

        # Pendentes
        pending = execute_query(
            """
            SELECT COUNT(*) as count 
            FROM risk_records 
            WHERE decision = 'UNDER_REVIEW' OR decision IS NULL
        """
        )[0]["count"]

        # Alto risco
        high_risk = execute_query(
            """
            SELECT COUNT(*) as count 
            FROM risk_records 
            WHERE risk_level IN ('HIGH', 'CRITICAL')
        """
        )[0]["count"]

        # Fontes ativas
        sources = execute_query(
            "SELECT COUNT(*) as count FROM info_sources WHERE is_active = true"
        )[0]["count"]

        # Distribuição de risco (para DashboardStats.riskDistribution)
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

        # Análises recentes (para DashboardStats.recentAnalyses)
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
# Análise de Risco (multi-match) – alinhado com RiskCheckResponse
# -------------------------------------------------------------------------
@app.post("/api/risk/check", response_model=RiskCheckResponse)
async def risk_check(
    request: RiskCheckRequest,
    current_user: UserInfo = Depends(get_current_user),
):
    """Análise de risco"""
    try:
        # Validar entrada: pelo menos um identificador
        if not any(
            [request.full_name, request.nif, request.passport, request.resident_card]
        ):
            raise HTTPException(
                status_code=400, detail="Pelo menos um identificador é necessário"
            )

        # Buscar matches
        matches = perform_matching(
            {
                "full_name": request.full_name,
                "nif": request.nif,
                "passport": request.passport,
                "resident_card": request.resident_card,
            }
        )

        # Calcular risco
        risk_data = calculate_risk_score(matches, bool(request.nif))

        # Salvar registo e devolver também analyzed_at (para bater com RiskCheckResponse)
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
# Fontes de Informação – alinhado com InfoSourceInfo
# -------------------------------------------------------------------------
@app.get("/api/info-sources", response_model=List[InfoSourceInfo])
async def get_info_sources(current_user: UserInfo = Depends(get_current_user)):
    """Listar fontes de informação ativas"""
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
# Download de PDF de uma análise de risco
# -------------------------------------------------------------------------
@app.get("/api/risk/{risk_id}/report/pdf")
async def download_risk_pdf(
    risk_id: int,
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Download do relatório PDF de uma análise de risco específica.
    """
    try:
        # Buscar registo
        records = execute_query(
            "SELECT * FROM risk_records WHERE id = %s",
            (risk_id,),
        )
        if not records:
            raise HTTPException(status_code=404, detail="Registo não encontrado")

        risk_record = records[0]

        # Gerar PDF (base64) a partir do registo
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


# -------------------------------------------------------------------------
# Exportação Excel das análises de risco
# -------------------------------------------------------------------------
@app.get("/api/risk/export/excel")
async def export_risk_excel(current_user: UserInfo = Depends(get_current_user)):
    """
    Exportar todas as análises de risco para Excel.
    (No futuro podemos adicionar filtros por data, nível de risco, etc.)
    """
    try:
        # Buscar todos os registos de risco
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


# -------------------------------------------------------------------------
# Gráficos do dashboard (base64)
# -------------------------------------------------------------------------
@app.get("/api/dashboard/charts")
async def get_charts(current_user: UserInfo = Depends(get_current_user)):
    """
    Obter gráficos do dashboard em base64 (imagem PNG).
    O frontend pode usar: <img src="data:image/png;base64, {chart}" />
    """
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


# -------------------------------------------------------------------------
# Actualizar decisão de risco (APPROVED / REJECTED / UNDER_REVIEW)
# -------------------------------------------------------------------------
@app.put("/api/risk/{risk_id}/decision")
async def update_risk_decision(
    risk_id: int,
    request: DecisionRequest,
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Actualizar a decisão de uma análise de risco.
    """
    try:
        # Actualizar decisão e notas do analista
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


# -------------------------------------------------------------------------
# Histórico de análises de um assegurado
# -------------------------------------------------------------------------
@app.get("/api/risk/history")
async def get_risk_history(
    full_name: Optional[str] = None,
    nif: Optional[str] = None,
    passport: Optional[str] = None,
    resident_card: Optional[str] = None,
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Listar histórico de análises de um assegurado.
    Pode pesquisar por nome (LIKE), NIF, passaporte ou cartão de residente.
    """
    try:
        if not any([full_name, nif, passport, resident_card]):
            raise HTTPException(
                status_code=400,
                detail="Pelo menos um identificador (nome, NIF, passaporte, cartão de residente) deve ser fornecido",
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
