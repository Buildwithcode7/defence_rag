"""
Document ingestion router.

Uploads are saved to data/raw and processed immediately by the active local RAG
pipeline. The in-memory status map is intentionally simple for this desktop
build; Redis/RQ can replace it later without changing the response contract.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from src.api.auth import TokenData, require_permission
from src.api.schemas import IngestResponse, IngestStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ingest"])

RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_SIZE_MB = int(os.getenv("MAX_INGEST_FILE_MB", "50"))

INGEST_STATUS: dict[str, dict] = {}


def get_pipeline(request: Request):
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="RAG pipeline is not ready")
    return pipeline


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    doc_type: str = Form(default="auto"),
    classification_level: str = Form(default="UNCLASSIFIED"),
    issuing_authority: str = Form(default=""),
    effective_date: str = Form(default=""),
    token: TokenData = Depends(require_permission("ingest")),
    pipeline=Depends(get_pipeline),
):
    """Upload and index a supported document."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{suffix}' not supported. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {size_mb:.1f} MB exceeds limit of {MAX_FILE_SIZE_MB} MB",
        )

    job_id = str(uuid.uuid4())
    safe_name = f"{job_id}_{Path(file.filename or 'document').name}"
    dest_path = RAW_DATA_DIR / safe_name
    dest_path.write_bytes(content)

    metadata = {
        "doc_type": doc_type,
        "classification_level": classification_level,
        "issuing_authority": issuing_authority,
        "effective_date": effective_date,
        "uploaded_by": token.user_id,
        "original_filename": file.filename,
    }

    logger.info("Ingest: user=%s file=%s size=%.2fMB job_id=%s", token.user_id, file.filename, size_mb, job_id)

    try:
        result = pipeline.ingest(str(dest_path), extra_metadata=metadata)
    except Exception as exc:
        logger.error("Ingest failed for job_id=%s: %s", job_id, exc, exc_info=True)
        INGEST_STATUS[job_id] = {
            "status": "failed",
            "filename": file.filename,
            "chunks_created": None,
            "error": str(exc),
        }
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {exc}")

    status_text = "complete"
    duplicate = bool(result.get("duplicate"))
    message = "Document already indexed; duplicate upload skipped." if duplicate else "Document ingested successfully."
    INGEST_STATUS[job_id] = {"status": status_text, "filename": file.filename, "error": None, **result}

    return IngestResponse(
        job_id=job_id,
        filename=file.filename or "unknown",
        status=status_text,
        message=message,
        doc_id=result.get("doc_id"),
        chunks_created=result.get("chunks_created"),
        total_store=result.get("total_store"),
        duplicate=duplicate,
    )


@router.get("/ingest/status/{job_id}", response_model=IngestStatusResponse)
async def ingest_status(
    job_id: str,
    token: TokenData = Depends(require_permission("ingest")),
):
    """Check ingestion status."""
    job = INGEST_STATUS.get(job_id)
    if job is None:
        return IngestStatusResponse(
            job_id=job_id,
            status="unknown",
            progress_pct=None,
            chunks_created=None,
            error="Job not found",
        )

    return IngestStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        progress_pct=100 if job.get("status") == "complete" else None,
        chunks_created=job.get("chunks_created"),
        error=job.get("error"),
    )
