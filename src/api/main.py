"""
main.py — FastAPI application entrypoint.

Startup sequence:
  1. Load settings
  2. Initialise RAGPipeline (loads all models)
  3. Connect audit trail
  4. Register routers
  5. Attach rate limiter and CORS middleware
"""

from __future__ import annotations
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routers import query as query_router
from src.api.routers import ingest as ingest_router
from src.api.routers import audit as audit_router
from src.api.schemas import HealthResponse, TokenResponse, LoginRequest
from src.api.auth import create_access_token, Role

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load all models and components at startup; clean up on shutdown."""
    logger.info("=== INICAI Defence RAG — Starting Up ===")

    from src.config import get_settings
    settings = get_settings()

    from src.pipeline.simple_rag import get_pipeline
    from src.compliance.audit_trail import AuditTrailWriter

    app.state.settings = settings
    app.state.audit_trail = AuditTrailWriter(db_path=settings.audit_db_path)

    try:
        app.state.pipeline = get_pipeline()
        logger.info("SimpleRAGPipeline loaded successfully")
    except Exception as exc:
        logger.error("Failed to load RAGPipeline: %s", exc, exc_info=True)
        app.state.pipeline = None

    # Optional: Celery/RQ task queue
    try:
        from rq import Queue
        from redis import Redis
        redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        app.state.task_queue = Queue(connection=redis_conn)
        logger.info("Task queue connected")
    except Exception:
        logger.warning("Redis/RQ not available — ingestion will run synchronously")
        app.state.task_queue = None

    logger.info("=== Startup complete ===")
    yield

    # Shutdown
    logger.info("=== INICAI Defence RAG — Shutting Down ===")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="INICAI Defence RAG API",
        description="Procurement & Policy Reasoning for the Indian Navy",
        version="1.0.0",
        docs_url="/docs" if os.getenv("ENABLE_DOCS", "true").lower() == "true" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS — restrict to internal subnet in production
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Rate limiting via slowapi
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.util import get_remote_address
        from slowapi.errors import RateLimitExceeded

        limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        logger.info("Rate limiter active: 200/min global")
    except ImportError:
        logger.warning("slowapi not installed — rate limiting disabled")

    # Request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{(time.time() - start)*1000:.1f}ms"
        return response

    # Routers
    app.include_router(query_router.router)
    app.include_router(ingest_router.router)
    app.include_router(audit_router.router)

    # ---------------------------------------------------------------------------
    # Health check
    # ---------------------------------------------------------------------------

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
    async def health(request: Request):
        pipeline = getattr(request.app.state, "pipeline", None)
        audit = getattr(request.app.state, "audit_trail", None)

        faiss_ok = False
        bm25_ok = False
        llm_ok = False
        embed_ok = False
        rerank_ok = False

        if pipeline:
            faiss_ok = getattr(pipeline.store, "_index", None) is not None
            bm25_ok = getattr(pipeline, "_bm25", None) is not None or pipeline.total_chunks > 0
            llm_ok = os.getenv("LLM_BACKEND", "none").lower() in {"ollama", "openai", "openai_compatible"}
            embed_ok = pipeline.embedder is not None
            rerank_ok = True

        audit_ok = audit is not None

        healthy = all([embed_ok, audit_ok])

        response = HealthResponse(
            status="healthy" if healthy else "degraded",
            faiss_index_loaded=faiss_ok,
            bm25_index_loaded=bm25_ok,
            llm_service_ready=llm_ok,
            embedding_model_ready=embed_ok,
            reranker_ready=rerank_ok,
            audit_db_connected=audit_ok,
        )
        data = response.model_dump()
        data["total_chunks_indexed"] = pipeline.total_chunks if pipeline else 0
        return data

    # ---------------------------------------------------------------------------
    # Auth / login (demo — in production connect to LDAP/PKI)
    # ---------------------------------------------------------------------------

    @app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["auth"])
    async def login(body: LoginRequest):
        """
        Demo login endpoint. In production, replace with LDAP/PKI authentication.
        """
        DEMO_USERS = {
            "analyst": ("analyst123", Role.ANALYST),
            "admin": ("admin123", Role.ADMIN),
            "auditor": ("auditor123", Role.AUDITOR),
        }
        user = DEMO_USERS.get(body.username)
        if not user or user[0] != body.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        role = user[1]
        token = create_access_token(user_id=body.username, role=role)
        from src.api.auth import JWT_EXPIRE_MINUTES
        return TokenResponse(
            access_token=token,
            role=role.value,
            expires_in_minutes=JWT_EXPIRE_MINUTES,
        )

    return app


app = create_app()
