"""
src/ingestion/validator.py
DocumentValidator: pre-ingestion checks before any processing occurs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from config.settings import get_settings

settings = get_settings()


@dataclass
class ValidationResult:
    valid: bool
    reason: Optional[str] = None
    content_hash: Optional[str] = None
    file_size_mb: float = 0.0


class DocumentValidator:
    """
    Validates incoming files before ingestion.
    Checks: file integrity, format whitelist, size limit, deduplication.
    """

    def __init__(self):
        self._doc_types_config = self._load_doc_types()
        self._allowed_mimes = set(self._doc_types_config.get("allowed_mime_types", []))
        self._max_size_mb = self._doc_types_config.get("max_file_size_mb", 50)

    def _load_doc_types(self) -> dict:
        path = settings.document_types_path
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)
        return {}

    def validate(
        self,
        file_path: Path,
        content_hash: str,
        mime_type: str,
        existing_hashes: set[str],
    ) -> ValidationResult:
        """
        Run all pre-ingestion checks.
        Returns ValidationResult with valid=False and reason on any failure.
        """
        file_path = Path(file_path)

        # 1. File existence
        if not file_path.exists():
            return ValidationResult(valid=False, reason="File does not exist")

        # 2. File size
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self._max_size_mb:
            return ValidationResult(
                valid=False,
                reason=f"File size {size_mb:.1f}MB exceeds limit of {self._max_size_mb}MB",
                file_size_mb=size_mb,
            )

        # 3. MIME type whitelist
        if self._allowed_mimes and mime_type not in self._allowed_mimes:
            return ValidationResult(
                valid=False,
                reason=f"MIME type '{mime_type}' is not in the allowed whitelist",
                file_size_mb=size_mb,
            )

        # 4. Deduplication
        if content_hash in existing_hashes:
            return ValidationResult(
                valid=False,
                reason=f"Document already ingested (hash={content_hash[:12]}…). Skipping duplicate.",
                content_hash=content_hash,
                file_size_mb=size_mb,
            )

        # 5. File readability (attempt open)
        try:
            with open(file_path, "rb") as f:
                f.read(512)  # read first 512 bytes as sanity check
        except OSError as e:
            return ValidationResult(
                valid=False,
                reason=f"Cannot read file: {e}",
                file_size_mb=size_mb,
            )

        logger.info(f"Validation passed: {file_path.name} ({size_mb:.2f} MB, {mime_type})")
        return ValidationResult(
            valid=True,
            content_hash=content_hash,
            file_size_mb=size_mb,
        )