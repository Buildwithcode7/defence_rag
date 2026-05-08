"""
embedder.py — Sentence Transformers embedding wrapper
"""

from __future__ import annotations
import logging
from typing import List

logger = logging.getLogger(__name__)


class Embedder:
    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            self.dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Embedder loaded (dim={self.dim})")

        except Exception as e:
            logger.warning(f"Embedding model failed, using fallback: {e}")
            self.model = None
            self.dim = 384

    def embed(self, text: str) -> List[float]:
        if self.model:
            return self.model.encode(text).tolist()
        return self._fallback(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if self.model:
            return self.model.encode(texts).tolist()
        return [self._fallback(t) for t in texts]

    def _fallback(self, text: str) -> List[float]:
        # simple fallback (not good but avoids crash)
        import random
        return [random.random() for _ in range(self.dim)]