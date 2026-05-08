"""
src/storage/faiss_index.py
FAISSIndex: manages the IVF-PQ dense vector index.
Handles creation, incremental updates, persistence, and search.
"""
from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

from config.settings import get_settings

settings = get_settings()


class FAISSIndex:
    """
    Wraps a FAISS IndexIVFPQ index with metadata linking.

    Index strategy:
    - IndexFlatL2 is used as the quantiser for IVF training.
    - IVF-PQ reduces memory: 1024d float32 → ~16 bytes per vector at M=32.
    - For small corpora (<10K chunks), automatically uses IndexFlatIP (exact search).
    - `faiss_id` in the metadata store maps to the sequential position in this index.
    """

    def __init__(self):
        self._index = None
        self._dimension = 1024  # BGE-M3 output dimension
        self._id_to_chunk_id: list[str] = []  # faiss_id -> chunk UUID
        self._chunk_id_to_faiss_id: dict[str, int] = {}
        self._is_trained = False
        self._use_exact = False

        self._index_path = settings.faiss_index_path
        self._meta_path = settings.faiss_metadata_path

        # Try to load existing index
        if self._index_path.exists():
            self._load()

    # ── Index initialisation ──────────────────────────────────────────────────

    def _create_index(self, n_vectors: int = 0):
        """Create a new index. Uses flat exact search for small corpora."""
        try:
            import faiss
        except ImportError:
            raise ImportError("faiss-cpu is required: pip install faiss-cpu")

        if n_vectors < 1000:
            # Too few vectors for IVF; use exact flat index
            self._index = faiss.IndexFlatIP(self._dimension)
            self._use_exact = True
            self._is_trained = True
            logger.info(f"Created FAISS IndexFlatIP (exact, n_vectors={n_vectors})")
        else:
            nlist = min(settings.faiss_nlist, max(1, n_vectors // 39))
            quantiser = faiss.IndexFlatL2(self._dimension)
            self._index = faiss.IndexIVFPQ(
                quantiser,
                self._dimension,
                nlist,
                settings.faiss_m,
                settings.faiss_nbits,
            )
            self._index.nprobe = settings.faiss_nprobe
            self._use_exact = False
            logger.info(
                f"Created FAISS IndexIVFPQ: dim={self._dimension}, "
                f"nlist={nlist}, M={settings.faiss_m}, nbits={settings.faiss_nbits}"
            )

    def _ensure_index(self, n_vectors: int = 0):
        if self._index is None:
            self._create_index(n_vectors)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_vectors(self, embeddings: np.ndarray, chunk_ids: list[str]) -> list[int]:
        """
        Add embeddings to the index.
        Returns list of assigned faiss_ids (sequential positions).
        """
        import faiss

        assert len(embeddings) == len(chunk_ids), "embeddings and chunk_ids must have same length"
        assert embeddings.ndim == 2 and embeddings.shape[1] == self._dimension

        # Normalise for cosine similarity (inner product on unit vectors = cosine)
        faiss.normalize_L2(embeddings)

        self._ensure_index(len(self._id_to_chunk_id) + len(chunk_ids))

        # If IVF index needs training and we have enough vectors
        if not self._is_trained and not self._use_exact:
            if len(embeddings) >= 256:
                logger.info(f"Training FAISS IVF index on {len(embeddings)} vectors…")
                self._index.train(embeddings)
                self._is_trained = True
            else:
                # Fall back to flat index for small batches
                import faiss as _faiss
                self._index = _faiss.IndexFlatIP(self._dimension)
                self._use_exact = True
                self._is_trained = True

        if not self._is_trained:
            logger.warning("FAISS index not yet trained — using flat exact search as fallback")
            import faiss as _faiss
            self._index = _faiss.IndexFlatIP(self._dimension)
            self._use_exact = True
            self._is_trained = True

        start_id = len(self._id_to_chunk_id)
        self._index.add(embeddings)

        assigned_ids = list(range(start_id, start_id + len(chunk_ids)))
        self._id_to_chunk_id.extend(chunk_ids)
        for faiss_id, chunk_id in zip(assigned_ids, chunk_ids):
            self._chunk_id_to_faiss_id[chunk_id] = faiss_id

        logger.info(f"Added {len(chunk_ids)} vectors to FAISS index (total={len(self._id_to_chunk_id)})")
        return assigned_ids

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 20,
        filter_faiss_ids: Optional[list[int]] = None,
    ) -> list[tuple[str, float]]:
        """
        Search for top-k nearest neighbours.
        Returns list of (chunk_id, score) sorted by score descending.
        """
        import faiss

        if self._index is None or len(self._id_to_chunk_id) == 0:
            logger.warning("FAISS index is empty")
            return []

        # Normalise query
        q = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(q)

        actual_k = min(k, len(self._id_to_chunk_id))
        scores, faiss_ids = self._index.search(q, actual_k)

        results = []
        for score, fid in zip(scores[0], faiss_ids[0]):
            if fid == -1:
                continue
            if filter_faiss_ids is not None and fid not in filter_faiss_ids:
                continue
            chunk_id = self._id_to_chunk_id[fid]
            results.append((chunk_id, float(score)))

        return results

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist index and metadata to disk."""
        import faiss

        if self._index is None:
            logger.warning("No index to save")
            return

        os.makedirs(self._index_path.parent, exist_ok=True)

        faiss.write_index(self._index, str(self._index_path))

        meta = {
            "id_to_chunk_id": self._id_to_chunk_id,
            "chunk_id_to_faiss_id": self._chunk_id_to_faiss_id,
            "dimension": self._dimension,
            "is_trained": self._is_trained,
            "use_exact": self._use_exact,
        }
        with open(self._meta_path, "w") as f:
            json.dump(meta, f)

        logger.info(f"FAISS index saved: {len(self._id_to_chunk_id)} vectors at {self._index_path}")

    def _load(self) -> None:
        """Load index and metadata from disk."""
        try:
            import faiss

            self._index = faiss.read_index(str(self._index_path))
            with open(self._meta_path) as f:
                meta = json.load(f)
            self._id_to_chunk_id = meta["id_to_chunk_id"]
            self._chunk_id_to_faiss_id = meta["chunk_id_to_faiss_id"]
            self._dimension = meta.get("dimension", 1024)
            self._is_trained = meta.get("is_trained", True)
            self._use_exact = meta.get("use_exact", False)
            logger.info(f"FAISS index loaded: {len(self._id_to_chunk_id)} vectors")
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}. Starting fresh.")
            self._index = None
            self._id_to_chunk_id = []
            self._chunk_id_to_faiss_id = {}

    @property
    def total_vectors(self) -> int:
        return len(self._id_to_chunk_id)

    @property
    def is_ready(self) -> bool:
        return self._index is not None and self._is_trained