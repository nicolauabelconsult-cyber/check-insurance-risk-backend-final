# models.py
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(200), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    risk_records = relationship("RiskRecord", back_populates="analyst")


class InfoSource(Base):
    __tablename__ = "info_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    source_type = Column(String(50), nullable=False)  # PEP, SANCTIONS, FRAUD, CLAIMS, OTHER
    description = Column(Text, default="")
    file_path = Column(String(500), nullable=False)
    num_records = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"))


class NormalizedEntity(Base):
    """
    Representa um registo normalizado vindo de uma fonte (pessoa ou entidade).
    Permite pesquisa rápida por nome, nif, passaporte, etc.
    """
    __tablename__ = "normalized_entities"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("info_sources.id"), nullable=False)

    person_name = Column(String(300), index=True, nullable=True)
    person_nif = Column(String(50), index=True, nullable=True)
    person_passport = Column(String(50), index=True, nullable=True)
    residence_card = Column(String(50), index=True, nullable=True)

    role = Column(String(200), nullable=True)
    country = Column(String(100), nullable=True)

    raw_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("InfoSource")

Index("idx_normalized_entities_nif", NormalizedEntity.person_nif)
Index("idx_normalized_entities_name", NormalizedEntity.person_name)


class RiskRecord(Base):
    __tablename__ = "risk_records"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    nif = Column(String(50), nullable=True)
    passport = Column(String(50), nullable=True)
    residence_card = Column(String(50), nullable=True)

    risk_score = Column(Integer, nullable=False)
    risk_level = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    is_pep = Column(Boolean, default=False)
    has_sanctions = Column(Boolean, default=False)

    # Lista completa de matches e factores (JSON serializado)
    matches_json = Column(Text, nullable=False)
    factors_json = Column(Text, nullable=False)

    # Match principal escolhido pelo analista (opcional)
    primary_match_json = Column(Text, nullable=True)

    decision = Column(String(50), nullable=True)  # ACCEPT, CONDITIONAL, REJECT
    analyst_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    analyst_id = Column(Integer, ForeignKey("users.id"))
    analyst = relationship("User", back_populates="risk_records")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(100), nullable=True)
