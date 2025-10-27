from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from risk_multimatch_routes import router as risk_router
from reports import router as reports_router

app = FastAPI(title="Check Insurance Risk Backend", version="7.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(risk_router)
app.include_router(reports_router)

@app.get("/")
def home():
    return {"status": "ok", "service": "check-insurance-risk-backend"}

@app.get("/health")
def health():
    return {"status": "healthy", "version": "7.0"}
