# """
# src/storage/embedder.py
# EmbeddingService: wraps BGE-M3 sentence transformer with in-memory caching.
# All embeddings are unit-normalised (cosine similarity via inner product).
# """
# from __future__ import annotations

# import hashlib
# from functools import lru_cache
# from typing import Optional

# import numpy as np
# from loguru import logger

# from config.settings import get_settings

# settings = get_settings()


# class EmbeddingService:
#     """
#     Singleton embedding service using BGE-M3.
#     Features:
#     - Lazy model loading (loaded on first use)
#     - LRU in-memory cache for query embeddings (avoid re-embedding identical queries)
#     - Batch encoding for ingestion
#     - L2 normalisation for cosine similarity
#     """

#     _instance: Optional["EmbeddingService"] = None

#     def __new__(cls):
#         if cls._instance is None:
#             cls._instance = super().__new__(cls)
#             cls._instance._model = None
#             cls._instance._cache: dict[str, np.ndarray] = {}
#         return cls._instance

#     def _load_model(self) -> None:
#         if self._model is not None:
#             return
#         logger.info(f"Loading embedding model: {settings.embedding_model}")
#         try:
#             from sentence_transformers import SentenceTransformer
#             self._model = SentenceTransformer(
#                 settings.embedding_model,
#                 device=settings.embedding_device,
#             )
#             # BGE-M3 specific: set to encode with max_length
#             if hasattr(self._model, "max_seq_length"):
#                 self._model.max_seq_length = 512
#             logger.info(f"Embedding model loaded on device: {settings.embedding_device}")
#         except ImportError:
#             raise ImportError("sentence-transformers required: pip install sentence-transformers")
#         except Exception as e:
#             logger.error(f"Failed to load embedding model: {e}")
#             raise

#     def embed_query(self, text: str) -> np.ndarray:
#         """
#         Embed a single query string with caching.
#         Returns L2-normalised 1D float32 array.
#         """
#         # Cache key
#         cache_key = hashlib.md5(text.encode()).hexdigest()
#         if cache_key in self._cache:
#             return self._cache[cache_key]

#         self._load_model()
#         # BGE-M3 performs better with instruction prefix for queries
#         prefixed = f"Represent this sentence for searching relevant passages: {text}"
#         embedding = self._model.encode(
#             prefixed,
#             normalize_embeddings=True,
#             show_progress_bar=False,
#         ).astype(np.float32)

#         self._cache[cache_key] = embedding
#         return embedding

#     def embed_documents(self, texts: list[str]) -> np.ndarray:
#         """
#         Embed a batch of document chunks.
#         Returns L2-normalised 2D float32 array of shape (n, dim).
#         """
#         if not texts:
#             return np.empty((0, 1024), dtype=np.float32)

#         self._load_model()
#         logger.info(f"Embedding {len(texts)} documents in batches of {settings.embedding_batch_size}…")

#         embeddings = self._model.encode(
#             texts,
#             batch_size=settings.embedding_batch_size,
#             normalize_embeddings=True,
#             show_progress_bar=len(texts) > 50,
#             convert_to_numpy=True,
#         ).astype(np.float32)

#         logger.info(f"Embeddings computed: shape={embeddings.shape}")
#         return embeddings

#     def get_dimension(self) -> int:
#         self._load_model()
#         return self._model.get_sentence_embedding_dimension()

#     def clear_cache(self) -> None:
#         self._cache.clear()


# def get_embedder() -> EmbeddingService:
#     """Return the singleton EmbeddingService."""
#     return EmbeddingService()
"""
embedder.py — Embedding service using sentence-transformers.

Model: all-MiniLM-L6-v2 (384-dim, fast, good quality, ~90MB)
Dev fallback: random vectors (so the pipeline runs without any model)

Toggle via env:
  DEV_MODE=true  → random embeddings (no model download needed)
  DEV_MODE=false → real sentence-transformers model
"""

from __future__ import annotations
import logging
import os
import hashlib
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

# Default model — small, fast, good quality
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
EMBEDDING_DIM = 384  # for all-MiniLM-L6-v2


class Embedder:
    """
    Wraps sentence-transformers for text embedding.
    Falls back to random vectors in DEV_MODE.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, dev_mode: bool = DEV_MODE):
        self.model_name = model_name
        self.dev_mode = dev_mode
        self._model = None
        self._cache: dict[str, List[float]] = {}
        self.dim = EMBEDDING_DIM

        if not dev_mode:
            self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            self.dim = self._model.get_sentence_embedding_dimension()
            logger.info("Embedding model loaded. dim=%d", self.dim)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. Falling back to random embeddings.\n"
                "Install with: pip install sentence-transformers"
            )
            self._model = None
        except Exception as exc:
            logger.error("Failed to load embedding model: %s. Using random fallback.", exc)
            self._model = None

    def embed(self, text: str) -> List[float]:
        """Embed a single text string."""
        cache_key = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        embedding = self.embed_batch([text])[0]
        self._cache[cache_key] = embedding
        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts. Returns list of float vectors."""
        if self.dev_mode or self._model is None:
            # Deterministic unit vectors keep dev retrieval reproducible.
            vecs = np.vstack([self._stable_vector(text) for text in texts]).astype("float32")
            return vecs.tolist()

        try:
            embeddings = self._model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return embeddings.astype("float32").tolist()
        except Exception as exc:
            logger.error("Embedding failed: %s. Using random fallback.", exc)
            vecs = np.vstack([self._stable_vector(text) for text in texts]).astype("float32")
            return vecs.tolist()

    def _stable_vector(self, text: str) -> np.ndarray:
        seed = int(hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.dim).astype("float32")
        norm = np.linalg.norm(vec)
        return vec / max(norm, 1e-12)
