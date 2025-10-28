import os
from datetime import timedelta

JWT_SECRET = os.getenv("CIR_JWT_SECRET", "change_me_in_prod")
JWT_ALGO = "HS256"
JWT_EXPIRE_MINUTES = 60  # minutos de sessão

UPLOAD_DIR = os.getenv("CIR_UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_PATH = os.getenv("CIR_DB_PATH", "cir.sqlite3")
