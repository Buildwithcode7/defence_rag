"""
audit.py — /api/v1/audit router.
Auditor and admin roles can read audit trail entries.
"""

from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.auth import TokenData, require_permission
from src.api.schemas import AuditEntry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["audit"])


def get_audit_trail(request: Request):
    return request.app.state.audit_trail


@router.get("/audit/{audit_id}", response_model=AuditEntry)
async def get_audit_entry(
    audit_id: str,
    token: TokenData = Depends(require_permission("audit_read")),
    audit_trail=Depends(get_audit_trail),
):
    """Retrieve a single audit trail entry by ID. Requires: auditor | admin role."""
    entry = audit_trail.get_entry(audit_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit entry {audit_id} not found",
        )
    return AuditEntry(
        audit_id=entry["audit_id"],
        timestamp=entry["timestamp"],
        user_id=entry["user_id"],
        session_id=entry.get("session_id"),
        query=entry["query"],
        compliance_status=entry.get("compliance_status", ""),
        confidence_score=entry.get("confidence_score", 0.0),
        entry_hash=entry["entry_hash"],
    )


@router.get("/audit/verify/chain")
async def verify_chain(
    token: TokenData = Depends(require_permission("audit_read")),
    audit_trail=Depends(get_audit_trail),
):
    """Verify the tamper-evident hash chain integrity of the entire audit trail."""
    intact = audit_trail.verify_chain_integrity()
    return {
        "chain_intact": intact,
        "message": "Audit chain verified" if intact else "⚠️ CHAIN INTEGRITY FAILURE DETECTED",
    }