"""
query.py — /api/v1/query router.

Orchestrates the full RAG pipeline:
  QueryExpander → HybridFuser → Reranker → ContextBuilder →
  CoTPrompter → LLM → CitationVerifier → ConfidenceScorer →
  RuleMapper → GapDetector → ComplianceReportWriter → AuditTrail
"""

from __future__ import annotations
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.auth import TokenData, require_permission
from src.api.schemas import (
    CitationItem,
    ComplianceGapItem,
    QueryRequest,
    QueryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["query"])


# ---------------------------------------------------------------------------
# Dependency: pipeline components injected via app.state
# ---------------------------------------------------------------------------

def get_pipeline(request: Request):
    return request.app.state.pipeline


# ---------------------------------------------------------------------------
# POST /api/v1/query
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    token: TokenData = Depends(require_permission("query")),
    pipeline=Depends(get_pipeline),
):
    """
    Main RAG query endpoint.
    Requires: analyst | admin role.
    """
    logger.info(
        "Query: user=%s session=%s question=%r",
        token.user_id,
        body.session_id,
        body.question[:80],
    )

    try:
        result = pipeline.run(
            question=body.question,
            filters=body.filters,
            top_k=body.top_k,
            user_id=token.user_id,
            session_id=body.session_id or token.session_id,
        )
    except Exception as exc:
        logger.error("Pipeline error for user=%s: %s", token.user_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query pipeline encountered an internal error. Please try again.",
        )

    # Build citation items
    citations = [
        CitationItem(
            label=chunk.label,
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            section=chunk.section,
            page=chunk.page,
            score=round(chunk.score, 4),
            text_snippet=chunk.text[:300],
        )
        for chunk in result.get("source_chunks", [])
    ]

    # Build compliance gap items
    gaps = [
        ComplianceGapItem(
            rule_id=g.rule_id,
            severity=g.severity,
            description=g.description,
            remediation=g.remediation,
        )
        for g in result.get("compliance_gaps", [])
    ]

    applicable_rules = [
        f"{r.get('rule_id', '')} — {r.get('title', '')}"
        for r in result.get("applicable_rules", [])
    ]

    return QueryResponse(
        answer=result["answer"],
        annotated_answer=result["annotated_answer"],
        citations=citations,
        compliance_status=result["compliance_status"],
        compliance_gaps=gaps,
        applicable_rules=applicable_rules,
        confidence_score=result["confidence_score"],
        confidence_level=result["confidence_level"],
        cot_applied=result.get("cot_applied", False),
        audit_id=result["audit_id"],
        session_id=body.session_id,
    )