"""
CrossEncoderReranker — scores query-candidate pairs and filters low-confidence chunks.
Uses cross-encoder/ms-marco-MiniLM-L6-v2 (FP16, GPU if available).
Falls back to a keyword-overlap heuristic when the model is unavailable.
"""

from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Minimum score to keep a chunk; below this it's dropped entirely
RERANKER_THRESHOLD: float = float(os.getenv("RERANKER_THRESHOLD", "0.35"))
# Minimum chunks required to return an answer; below this → insufficient-basis response
MIN_CHUNKS_REQUIRED: int = int(os.getenv("MIN_CHUNKS_REQUIRED", "2"))


@dataclass
class RankedChunk:
    chunk_id: str
    text: str
    score: float
    metadata: dict


class CrossEncoderReranker:
    """
    Reranks candidate chunks using a cross-encoder model.
    Strips chunks below RERANKER_THRESHOLD.
    """

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L6-v2"

    def __init__(self):
        self._model = None
        self._load_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        candidates: List[dict],
        top_k: int = 5,
    ) -> Tuple[List[RankedChunk], bool]:
        """
        Args:
            query: The user query string.
            candidates: List of dicts with keys {chunk_id, text, metadata}.
            top_k: Maximum chunks to return after reranking.

        Returns:
            (ranked_chunks, sufficient_basis)
            sufficient_basis is False when fewer than MIN_CHUNKS_REQUIRED pass threshold.
        """
        if not candidates:
            return [], False

        pairs = [(query, c["text"]) for c in candidates]
        scores = self._score_pairs(pairs)

        ranked = sorted(
            [
                RankedChunk(
                    chunk_id=c["chunk_id"],
                    text=c["text"],
                    score=float(s),
                    metadata=c.get("metadata", {}),
                )
                for c, s in zip(candidates, scores)
            ],
            key=lambda x: x.score,
            reverse=True,
        )

        # Apply threshold filter
        filtered = [r for r in ranked if r.score >= RERANKER_THRESHOLD]

        logger.info(
            "Reranker: %d candidates → %d above threshold %.2f → top_%d returned",
            len(candidates),
            len(filtered),
            RERANKER_THRESHOLD,
            top_k,
        )

        result = filtered[:top_k]
        sufficient = len(result) >= MIN_CHUNKS_REQUIRED
        return result, sufficient

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self):
        try:
            from sentence_transformers import CrossEncoder
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = CrossEncoder(
                self.MODEL_NAME,
                device=device,
                # FP16 on GPU to cut memory usage by ~50 %
                automodel_args={"torch_dtype": "auto"} if device == "cuda" else {},
            )
            logger.info("CrossEncoder loaded on %s", device)
        except Exception as exc:
            logger.warning(
                "CrossEncoder model unavailable (%s). Using keyword-overlap fallback.", exc
            )
            self._model = None

    def _score_pairs(self, pairs: List[Tuple[str, str]]) -> List[float]:
        if self._model is not None:
            try:
                scores = self._model.predict(pairs, show_progress_bar=False)
                # Normalise logits to [0, 1] via sigmoid
                import math

                return [1 / (1 + math.exp(-float(s))) for s in scores]
            except Exception as exc:
                logger.error("CrossEncoder prediction failed: %s", exc)

        # Fallback: keyword overlap (Jaccard-like)
        return [self._keyword_overlap(q, d) for q, d in pairs]

    @staticmethod
    def _keyword_overlap(query: str, document: str) -> float:
        q_tokens = set(query.lower().split())
        d_tokens = set(document.lower().split())
        if not q_tokens:
            return 0.0
        return len(q_tokens & d_tokens) / len(q_tokens)