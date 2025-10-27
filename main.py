from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from auth import router as auth_router
from risk_engine import router as risk_router
from reports import router as reports_router

app = FastAPI(title="Check Insurance Risk Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(risk_router)
app.include_router(reports_router)

@app.get("/")
def healthcheck():
    return {"status": "ok", "service": "check-insurance-risk-backend"}
