"""
FAISS-backed vector store with metadata persistence.

New indexes use cosine similarity via IndexFlatIP over unit-normalized vectors.
Older L2 indexes still load and are scored correctly, so existing local data does
not have to be deleted.
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_INDEX_DIR = Path(os.getenv("INDEX_DIR", "data/indices"))


class VectorStore:
    """Simple FAISS flat index with parallel metadata storage."""

    FAISS_FILE = "faiss.index"
    META_FILE = "metadata.pkl"

    def __init__(self, index_dir: Path = DEFAULT_INDEX_DIR, dim: int = 384):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.dim = dim
        self._index = None
        self._metadata: List[dict] = []
        self._load_if_exists()

    @property
    def total_chunks(self) -> int:
        return len(self._metadata)

    @property
    def metadata(self) -> List[dict]:
        return list(self._metadata)

    def add(self, embeddings: List[List[float]], metadatas: List[dict]) -> None:
        """Add embeddings and metadata, then persist to disk."""
        import faiss

        if not embeddings:
            return

        vectors = np.array(embeddings, dtype="float32")
        if vectors.ndim != 2:
            raise ValueError("embeddings must be a 2D list or array")
        if vectors.shape[1] != self.dim:
            raise ValueError(f"Embedding dimension mismatch: got {vectors.shape[1]}, expected {self.dim}")

        vectors = self._normalize(vectors)

        if self._index is None:
            self._index = faiss.IndexFlatIP(self.dim)
            logger.info("VectorStore: created new FAISS IndexFlatIP dim=%d", self.dim)

        self._index.add(vectors)
        self._metadata.extend(metadatas)
        self._save()
        logger.info("VectorStore: added %d vectors. Total: %d", len(embeddings), self.total_chunks)

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[dict, float]]:
        """Search for top_k most similar chunks and return similarity scores."""
        if self._index is None or self._index.ntotal == 0:
            logger.warning("VectorStore: index is empty")
            return []

        query = self._normalize(np.array([query_embedding], dtype="float32"))
        k = min(top_k, self._index.ntotal)
        raw_scores, indices = self._index.search(query, k)

        results: List[Tuple[dict, float]] = []
        for raw_score, idx in zip(raw_scores[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            results.append((self._metadata[idx], self._score(float(raw_score))))
        return results

    def has_content_hash(self, content_hash: str) -> bool:
        """Return True when a document hash is already indexed."""
        if not content_hash:
            return False
        return any(m.get("content_hash") == content_hash for m in self._metadata)

    def clear(self) -> None:
        """Wipe the in-memory and persisted index."""
        self._index = None
        self._metadata = []
        self._save()
        logger.info("VectorStore: cleared")

    def _save(self) -> None:
        import faiss

        if self._index is not None:
            faiss.write_index(self._index, str(self.index_dir / self.FAISS_FILE))
        with open(self.index_dir / self.META_FILE, "wb") as f:
            pickle.dump(self._metadata, f, protocol=pickle.HIGHEST_PROTOCOL)

    def _load_if_exists(self) -> None:
        faiss_path = self.index_dir / self.FAISS_FILE
        meta_path = self.index_dir / self.META_FILE

        if not (faiss_path.exists() and meta_path.exists()):
            logger.info("VectorStore: no existing index found at %s", self.index_dir)
            return

        try:
            import faiss

            self._index = faiss.read_index(str(faiss_path))
            with open(meta_path, "rb") as f:
                self._metadata = pickle.load(f)
            if len(self._metadata) != self._index.ntotal:
                logger.warning(
                    "VectorStore: metadata count (%d) does not match FAISS count (%d)",
                    len(self._metadata),
                    self._index.ntotal,
                )
            logger.info("VectorStore: loaded %d vectors from %s", self._index.ntotal, self.index_dir)
        except Exception as exc:
            logger.warning("VectorStore: failed to load existing index (%s). Starting fresh.", exc)
            self._index = None
            self._metadata = []

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.maximum(norms, 1e-12)

    def _score(self, raw_score: float) -> float:
        metric_type = getattr(self._index, "metric_type", None)
        # In common FAISS builds, 1 is L2 and 0 is inner product.
        if metric_type == 1:
            return 1.0 / (1.0 + max(raw_score, 0.0))
        return max(min(raw_score, 1.0), -1.0)
