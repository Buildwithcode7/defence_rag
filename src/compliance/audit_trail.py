"""
AuditTrailWriter — append-only tamper-evident audit log with SHA-256 hash chaining.

Every entry hashes (its own content + previous entry's hash), creating a chain.
Any modification to a historical entry invalidates all subsequent hashes.

Schema per entry:
  audit_id, timestamp, user_id, session_id, query, retrieved_chunk_ids,
  llm_response_hash, compliance_status, confidence_score, prev_hash, entry_hash
"""

from __future__ import annotations
import hashlib
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(os.getenv("AUDIT_DB_PATH", "data/audit/audit_trail.db"))

# Seed for the genesis block hash — set from environment in production
GENESIS_SEED = os.getenv("AUDIT_GENESIS_SEED", "INICAI_DEFENCE_RAG_GENESIS_2024")


class AuditTrailWriter:
    """
    Append-only, hash-chained audit trail stored in SQLite.
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_query(
        self,
        user_id: str,
        session_id: str,
        query: str,
        retrieved_chunk_ids: List[str],
        llm_response: str,
        compliance_status: str,
        confidence_score: float,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Append a query event to the audit trail.

        Returns:
            audit_id (UUID string) for this entry.
        """
        audit_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        response_hash = hashlib.sha256(llm_response.encode()).hexdigest()
        prev_hash = self._get_last_hash()

        entry_data = {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "user_id": user_id,
            "session_id": session_id,
            "query": query,
            "retrieved_chunk_ids": json.dumps(retrieved_chunk_ids),
            "llm_response_hash": response_hash,
            "compliance_status": compliance_status,
            "confidence_score": round(confidence_score, 4),
            "metadata": json.dumps(metadata or {}),
            "prev_hash": prev_hash,
        }
        entry_hash = self._compute_hash(entry_data)
        entry_data["entry_hash"] = entry_hash

        self._insert(entry_data)
        logger.info(
            "AuditTrail: logged audit_id=%s user=%s confidence=%.3f",
            audit_id,
            user_id,
            confidence_score,
        )
        return audit_id

    def get_entry(self, audit_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM audit_trail WHERE audit_id = ?", (audit_id,)
            ).fetchone()
            return dict(row) if row else None

    def verify_chain_integrity(self) -> bool:
        """
        Walk the full chain and verify hash consistency.
        Returns True if chain is intact, False if tampering detected.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM audit_trail ORDER BY rowid ASC"
            ).fetchall()

        for row in rows:
            entry = dict(row)
            stored_hash = entry.pop("entry_hash")
            expected = self._compute_hash(entry)
            if expected != stored_hash:
                logger.error(
                    "Chain integrity FAILED at audit_id=%s", entry.get("audit_id")
                )
                return False
        logger.info("Audit chain integrity verified: %d entries OK", len(rows))
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_trail (
                    rowid       INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id    TEXT UNIQUE NOT NULL,
                    timestamp   TEXT NOT NULL,
                    user_id     TEXT NOT NULL,
                    session_id  TEXT,
                    query       TEXT NOT NULL,
                    retrieved_chunk_ids TEXT,
                    llm_response_hash   TEXT NOT NULL,
                    compliance_status   TEXT,
                    confidence_score    REAL,
                    metadata    TEXT,
                    prev_hash   TEXT NOT NULL,
                    entry_hash  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_trail(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_trail(timestamp)"
            )
            conn.commit()

    def _get_last_hash(self) -> str:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT entry_hash FROM audit_trail ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            if row:
                return row[0]
            # Genesis block: hash of the seed
            return hashlib.sha256(GENESIS_SEED.encode()).hexdigest()

    def _compute_hash(self, entry: dict) -> str:
        # Deterministic JSON serialisation for hashing
        canonical = json.dumps(entry, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def _insert(self, entry: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_trail
                  (audit_id, timestamp, user_id, session_id, query,
                   retrieved_chunk_ids, llm_response_hash, compliance_status,
                   confidence_score, metadata, prev_hash, entry_hash)
                VALUES
                  (:audit_id, :timestamp, :user_id, :session_id, :query,
                   :retrieved_chunk_ids, :llm_response_hash, :compliance_status,
                   :confidence_score, :metadata, :prev_hash, :entry_hash)
                """,
                entry,
            )
            conn.commit()