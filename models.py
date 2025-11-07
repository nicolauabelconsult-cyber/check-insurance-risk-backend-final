from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120))
    email = Column(String(120), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), default="analyst")

class RiskRecord(Base):
    __tablename__ = "risk_records"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200))
    nif = Column(String(64), index=True)
    bi = Column(String(64), index=True)
    passaporte = Column(String(64), index=True)
    cartao_residente = Column(String(64), index=True)

    score_final = Column(Integer, default=75)
    justificacao = Column(Text)

    pep_alert = Column(Boolean, default=False)
    sanctions_alert = Column(Boolean, default=False)
    fraude_suspeita = Column(Boolean, default=False)
    comentario_fraude = Column(Text)

    historico_pagamentos = Column(Text)  # JSON string
    sinistros_total = Column(Integer, default=0)
    sinistros_ult_12m = Column(Integer, default=0)

    esg_score = Column(Integer, default=0)
    country_risk = Column(String(64))
    credit_rating = Column(String(64))
    kyc_confidence = Column(String(64))

class InfoSource(Base):
    __tablename__ = "info_sources"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200))
    description = Column(Text)
    url = Column(String(500))
    directory = Column(String(200))
    filename = Column(String(200))
    categoria = Column(String(120))
    source_owner = Column(String(120))
    validade = Column(String(40))
    uploaded_at = Column(DateTime, server_default=func.now())
