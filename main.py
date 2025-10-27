
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import router as auth_router
from admin_routes import router as admin_router
from risk_multimatch_routes import router as risk_router
from reports import router as reports_router

app = FastAPI(title="Check Insurance Risk Backend", version="enterprise-1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(risk_router)
app.include_router(reports_router)

@app.get("/")
def home():
    return {"status": "ok", "service": "check-insurance-risk-backend"}

@app.get("/health")
def health():
    return {"status": "healthy", "version": "enterprise-1.0"}
