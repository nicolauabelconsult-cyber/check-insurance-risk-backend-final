from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth.routes_auth import router as auth_router
from app.risk.routes_risk import router as risk_router
from app.admin.routes_admin import router as admin_router

app = FastAPI(
    title="Check Insurance Risk Backend",
    version="4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(risk_router)
app.include_router(admin_router)

@app.get("/")
def root():
    return {"status":"ok","service":"Check Insurance Risk Backend v4.0"}
