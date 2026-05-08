"""
api_client.py — Thin HTTP client wrapping the FastAPI backend for Streamlit use.
"""

from __future__ import annotations
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000", token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._session = requests.Session()

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def login(self, username: str, password: str) -> dict:
        try:
            r = self._session.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"username": username, "password": password},
                timeout=100,
            )
            return r.json() if r.status_code == 200 else {}
        except Exception as e:
            logger.error("Login failed: %s", e)
            return {}

    def query(
        self,
        question: str,
        filters: Optional[dict] = None,
        top_k: int = 5,
        session_id: Optional[str] = None,
    ) -> dict:
        payload = {
            "question": question,
            "filters": filters,
            "top_k": top_k,
            "session_id": session_id,
        }
        r = self._session.post(
            f"{self.base_url}/api/v1/query",
            json=payload,
            headers=self._headers(),
            timeout=None,
        )
        r.raise_for_status()
        return r.json()

    def ingest(self, file_bytes: bytes, filename: str, metadata: dict) -> dict:
        r = self._session.post(
            f"{self.base_url}/api/v1/ingest",
            files={"file": (filename, file_bytes)},
            data=metadata,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=None,
        )
        r.raise_for_status()
        return r.json()

    def get_ingest_status(self, job_id: str) -> dict:
        r = self._session.get(
            f"{self.base_url}/api/v1/ingest/status/{job_id}",
            headers=self._headers(),
            timeout=None,
        )
        return r.json() if r.ok else {}

    def get_audit_entry(self, audit_id: str) -> dict:
        r = self._session.get(
            f"{self.base_url}/api/v1/audit/{audit_id}",
            headers=self._headers(),
            timeout=None,
        )
        return r.json() if r.ok else {}

    def verify_audit_chain(self) -> dict:
        r = self._session.get(
            f"{self.base_url}/api/v1/audit/verify/chain",
            headers=self._headers(),
            timeout=None,
        )
        return r.json() if r.ok else {}

    def get_health(self) -> dict:
        r = self._session.get(
            f"{self.base_url}/api/v1/health",
            timeout=None,
        )
        return r.json() if r.ok else {}