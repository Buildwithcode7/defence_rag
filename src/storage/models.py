"""
src/storage/models.py
SQLAlchemy ORM models for all persistent entities.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from config.settings import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


# ── Documents ──────────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(512), nullable=False)
    original_path = Column(String(1024))
    doc_type = Column(String(64), nullable=False, default="unknown")
    issuing_authority = Column(String(256))
    effective_date = Column(String(32))
    version = Column(String(32))
    classification_level = Column(String(32), default="UNCLASSIFIED")
    content_hash = Column(String(64), unique=True, nullable=False)  # SHA-256
    page_count = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    ocr_used = Column(Boolean, default=False)
    index_status = Column(String(32), default="pending")  # pending | indexed | failed
    ingested_at = Column(DateTime, default=datetime.utcnow)
    ingested_by = Column(String(64))
    error_message = Column(Text)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


# ── Chunks ─────────────────────────────────────────────────────────────────────

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)        # position in document
    faiss_id = Column(Integer, unique=True)              # index in FAISS flat array
    text = Column(Text, nullable=False)
    summary = Column(Text)
    page_numbers = Column(String(128))                   # e.g. "12,13"
    section_id = Column(String(256))                     # e.g. "Chapter II > Rule 154"
    clause_id = Column(String(256))
    parent_section_id = Column(String(256))
    token_count = Column(Integer)
    ocr_uncertain = Column(Boolean, default=False)
    entities = Column(JSON, default=list)               # extracted NER entities
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_index", name="uq_doc_chunk"),
    )


# ── Audit Trail ────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64))
    user_id = Column(String(64))
    query = Column(Text, nullable=False)
    query_filters = Column(JSON)
    retrieved_chunk_ids = Column(JSON)                   # list of chunk IDs used
    llm_response = Column(Text)
    compliance_result = Column(JSON)
    confidence_score = Column(Float)
    citation_verified = Column(Boolean)
    unverified_claims = Column(JSON, default=list)
    response_time_ms = Column(Integer)
    entry_hash = Column(String(64))                      # tamper-evident chain
    prev_entry_hash = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)

    def compute_hash(self, seed: str) -> str:
        """Compute SHA-256 hash of this entry for chain integrity."""
        payload = (
            f"{self.id}{self.query}{self.llm_response}"
            f"{self.created_at}{self.prev_entry_hash}{seed}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# ── Feedback ──────────────────────────────────────────────────────────────────

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    audit_id = Column(String(36), ForeignKey("audit_logs.id"))
    rating = Column(Integer)                             # 1-5
    comment = Column(Text)
    submitted_by = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(64), unique=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), default="analyst")         # analyst | admin | auditor
    clearance_level = Column(String(32), default="UNCLASSIFIED")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)


# ── DB engine factory ─────────────────────────────────────────────────────────

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_debug,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False
        )
    return _session_factory


async def init_db():
    """Create all tables. Call once at application startup."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)