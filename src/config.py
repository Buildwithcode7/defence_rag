"""
config.py — centralised application settings using pydantic-settings.
Reads from environment variables and .env file.
"""

from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
# try:
#     from pydantic_settings import BaseSettings
# except ImportError:
#     from pydantic import BaseSettings  # pydantic v1 fallback


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    base_dir: Path = Path(__file__).parent.parent
    data_dir: Path = Path("data")
    faiss_index_path: Path = Path("data/indices/faiss_ivfpq.index")
    bm25_index_path: Path = Path("data/indices/bm25_corpus.pkl")
    audit_db_path: Path = Path("data/audit/audit_trail.db")
    raw_data_dir: Path = Path("data/raw")
    processed_data_dir: Path = Path("data/processed")
    models_dir: Path = Path("models")
    compliance_rules_path: Path = Path("config/compliance_rules.json")

    # ------------------------------------------------------------------
    # Embedding model
    # ------------------------------------------------------------------
    embedding_model_name: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_batch_size: int = 256
    embedding_cache_ttl: int = 3600  # seconds

    # ------------------------------------------------------------------
    # FAISS
    # ------------------------------------------------------------------
    faiss_nlist: int = 2048
    faiss_nprobe: int = 64
    faiss_pq_m: int = 64

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    retrieval_dense_top_k: int = 20
    retrieval_sparse_top_k: int = 20
    rrf_alpha: float = 0.6
    reranker_threshold: float = 0.35
    reranker_min_chunks: int = 2

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------
    llm_backend: str = "mock"          # "mock" | "llamacpp" | "mistral"
    llm_model_path: Optional[str] = None
    llm_max_tokens: int = 1024
    llm_context_window: int = 4096

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    allowed_origins: str = "http://localhost:8501"
    enable_docs: bool = True
    jwt_secret_key: str = "CHANGE_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # ------------------------------------------------------------------
    # Redis / task queue
    # ------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379"

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    max_ingest_file_mb: int = 50
    ocr_confidence_threshold: float = 0.7
    chunk_max_tokens: int = 512
    chunk_overlap_tokens: int = 64

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
