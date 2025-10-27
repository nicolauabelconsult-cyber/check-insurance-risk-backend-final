from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import router as auth_router
from risk_engine import router as risk_router
from reports import router as reports_router
from admin_routes import router as admin_router
from db import init_db

app = FastAPI(
    title="Check Insurance Risk Backend",
    version="3.0.0",
    description="Motor de compliance, scoring técnico e administração interna."
)

# inicializar base de dados / tabelas / admin inicial
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # em produção podes restringir ao domínio Netlify
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(risk_router)
app.include_router(reports_router)
app.include_router(admin_router)

@app.get("/")
def healthcheck():
    return {"status": "ok", "service": "check-insurance-risk-backend"}
