from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(32), default="analyst")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RiskRecord(Base):
    __tablename__ = "risk_records"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120))
    nif = Column(String(64))
    bi = Column(String(64))
    passaporte = Column(String(64))
    cartao_residente = Column(String(64))
    score_final = Column(Integer, default=0)
    justificacao = Column(Text)
    pep_alert = Column(Boolean, default=False)
    sanctions_alert = Column(Boolean, default=False)
    historico_pagamentos = Column(String(120))
    sinistros_total = Column(Integer, default=0)
    sinistros_ult_12m = Column(Integer, default=0)
    fraude_suspeita = Column(Boolean, default=False)
    comentario_fraude = Column(Text)
    esg_score = Column(Integer, default=0)
    country_risk = Column(String(120))
    credit_rating = Column(String(64))
    kyc_confidence = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class InfoSource(Base):
    __tablename__ = "info_sources"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200))
    description = Column(Text)
    url = Column(String(300))
    directory = Column(String(300))
    filename = Column(String(200))
    categoria = Column(String(64))
    source_owner = Column(String(120))
    validade = Column(String(120))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
