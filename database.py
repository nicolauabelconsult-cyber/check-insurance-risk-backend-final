from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
import os

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./cir.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
