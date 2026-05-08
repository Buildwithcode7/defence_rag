"""
src/storage/bm25_index.py
BM25SparseIndex: keyword-exact retrieval to anchor semantic search.
Critical for queries referencing specific rule numbers (e.g. "Rule 154 GFR").
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import get_settings

settings = get_settings()


def _tokenize(text: str) -> list[str]:
    """Simple tokeniser: lowercase, remove punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [tok for tok in text.split() if len(tok) > 1]


class BM25SparseIndex:
    """
    BM25Okapi index over all document chunks.
    Supports incremental adds and serialised persistence.
    """

    def __init__(self):
        self._corpus_tokens: list[list[str]] = []
        self._chunk_ids: list[str] = []
        self._bm25 = None
        self._path = settings.bm25_index_path
        self._dirty = False  # needs rebuild if True

        if self._path.exists():
            self._load()

    def add_chunks(self, texts: list[str], chunk_ids: list[str]) -> None:
        """Add new chunks to the BM25 index. Marks index as dirty (needs rebuild)."""
        assert len(texts) == len(chunk_ids)
        for text, cid in zip(texts, chunk_ids):
            tokens = _tokenize(text)
            self._corpus_tokens.append(tokens)
            self._chunk_ids.append(cid)
        self._dirty = True
        logger.info(f"BM25: added {len(texts)} chunks (total={len(self._chunk_ids)})")

    def _rebuild(self) -> None:
        """Rebuild BM25 model from corpus. Required after any add_chunks call."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            raise ImportError("rank-bm25 is required: pip install rank-bm25")

        if not self._corpus_tokens:
            self._bm25 = None
            return

        self._bm25 = BM25Okapi(self._corpus_tokens)
        self._dirty = False
        logger.info(f"BM25 index rebuilt: {len(self._corpus_tokens)} documents")

    def search(self, query: str, k: int = 20) -> list[tuple[str, float]]:
        """
        Search for top-k chunks by BM25 score.
        Returns list of (chunk_id, score) sorted by score descending.
        """
        if not self._chunk_ids:
            return []

        if self._dirty or self._bm25 is None:
            self._rebuild()

        if self._bm25 is None:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # Pair with chunk IDs and sort
        paired = [(self._chunk_ids[i], float(s)) for i, s in enumerate(scores)]
        paired.sort(key=lambda x: x[1], reverse=True)

        # Filter zero-score results
        results = [(cid, score) for cid, score in paired[:k] if score > 0.0]
        return results

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self) -> None:
        """Serialise corpus tokens and chunk IDs to disk."""
        import os
        os.makedirs(self._path.parent, exist_ok=True)

        # Always rebuild before saving so the loaded version is ready
        if self._dirty:
            self._rebuild()

        data = {
            "corpus_tokens": self._corpus_tokens,
            "chunk_ids": self._chunk_ids,
        }
        with open(self._path, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"BM25 index saved: {len(self._chunk_ids)} documents at {self._path}")

    def _load(self) -> None:
        """Deserialise from disk and rebuild BM25 model."""
        try:
            with open(self._path, "rb") as f:
                data = pickle.load(f)
            self._corpus_tokens = data["corpus_tokens"]
            self._chunk_ids = data["chunk_ids"]
            self._dirty = True  # Force rebuild of BM25 model from tokens
            logger.info(f"BM25 corpus loaded: {len(self._chunk_ids)} documents")
        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}. Starting fresh.")
            self._corpus_tokens = []
            self._chunk_ids = []

    @property
    def total_documents(self) -> int:
        return len(self._chunk_ids)