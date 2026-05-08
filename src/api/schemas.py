"""
schemas.py — Pydantic models for all API request/response contracts.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator


# ---------------------------------------------------------------------------
# Query endpoint
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000, description="User query")
    filters: Optional[Dict[str, str]] = Field(
        default=None,
        description="Metadata filters e.g. {'doc_type': 'procurement_policy'}",
    )
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    top_k: int = Field(default=5, ge=1, le=10, description="Max source chunks to use")

    @validator("question")
    def sanitise_question(cls, v):
        # Strip prompt injection attempts at the schema level
        blocked = ["ignore all previous", "disregard", "jailbreak", "system:"]
        v_lower = v.lower()
        for phrase in blocked:
            if phrase in v_lower:
                raise ValueError("Query contains disallowed content")
        return v.strip()


class CitationItem(BaseModel):
    label: str
    chunk_id: str
    doc_id: str
    section: str
    page: Optional[int]
    score: float
    text_snippet: str   # First 300 chars of the chunk


class ComplianceGapItem(BaseModel):
    rule_id: str
    severity: str
    description: str
    remediation: str


class QueryResponse(BaseModel):
    answer: str
    annotated_answer: str           # With ✓/✗ citation markers
    citations: List[CitationItem]
    compliance_status: str          # COMPLIANT | NON-COMPLIANT | REVIEW REQUIRED
    compliance_gaps: List[ComplianceGapItem]
    applicable_rules: List[str]
    confidence_score: float
    confidence_level: str           # HIGH | MEDIUM | LOW
    cot_applied: bool
    audit_id: str
    session_id: Optional[str]


# ---------------------------------------------------------------------------
# Ingest endpoint
# ---------------------------------------------------------------------------

class IngestResponse(BaseModel):
    job_id: str
    filename: str
    status: str     # "queued" | "processing" | "complete" | "failed"
    message: str
    doc_id: Optional[str] = None
    chunks_created: Optional[int] = None
    total_store: Optional[int] = None
    duplicate: bool = False


class IngestStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_pct: Optional[int]
    chunks_created: Optional[int]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Audit endpoint
# ---------------------------------------------------------------------------

class AuditEntry(BaseModel):
    audit_id: str
    timestamp: str
    user_id: str
    session_id: Optional[str]
    query: str
    compliance_status: str
    confidence_score: float
    entry_hash: str


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str             # "healthy" | "degraded" | "unhealthy"
    faiss_index_loaded: bool
    bm25_index_loaded: bool
    llm_service_ready: bool
    embedding_model_ready: bool
    reranker_ready: bool
    audit_db_connected: bool
    version: str = "1.0.0"
    total_chunks_indexed: int = 0


# ---------------------------------------------------------------------------
# Feedback endpoint
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    audit_id: str
    rating: int = Field(..., ge=1, le=5, description="1=poor, 5=excellent")
    comment: Optional[str] = Field(default=None, max_length=500)
    correct_answer: Optional[str] = Field(
        default=None, description="Ground truth for RLHF data collection"
    )


class FeedbackResponse(BaseModel):
    feedback_id: str
    message: str


# ---------------------------------------------------------------------------
# Auth endpoint
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in_minutes: int
