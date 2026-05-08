"""
src/retrieval/hybrid_fuser.py
HybridRetriever: fuses FAISS dense + BM25 sparse results via Reciprocal Rank Fusion.
Followed by cross-encoder reranking.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from loguru import logger

from config.settings import get_settings
from src.storage.bm25_index import BM25SparseIndex
from src.storage.embedder import get_embedder
from src.storage.faiss_index import FAISSIndex

settings = get_settings()

RRF_K = 60  # standard RRF constant


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    section_id: str
    clause_id: str
    doc_id: str
    doc_filename: str
    page_numbers: list[int]
    ocr_uncertain: bool
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    faiss_rank: int = 0
    bm25_rank: int = 0


class HybridRetriever:
    """
    Three-stage retrieval:
    1. Dense (FAISS) + Sparse (BM25) search in parallel
    2. Reciprocal Rank Fusion with α=0.6 toward dense
    3. Cross-encoder reranking of top-20 candidates → top-5
    """

    def __init__(
        self,
        faiss_index: FAISSIndex,
        bm25_index: BM25SparseIndex,
        db_session_factory,
    ):
        self._faiss = faiss_index
        self._bm25 = bm25_index
        self._db_factory = db_session_factory
        self._reranker = None
        self._embedder = get_embedder()

    def _load_reranker(self):
        if self._reranker is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
            self._reranker = CrossEncoder(
                settings.reranker_model,
                device=settings.embedding_device,
            )
            logger.info(f"Cross-encoder reranker loaded: {settings.reranker_model}")
        except ImportError:
            logger.warning("sentence-transformers not available; reranker disabled")

    async def retrieve(
        self,
        query: str,
        top_k_final: int = None,
        doc_type_filter: Optional[str] = None,
        classification_filter: Optional[str] = None,
    ) -> list[RetrievedChunk]:
        """
        Main retrieval entry point.
        Returns reranked chunks sorted by rerank_score descending.
        """
        if top_k_final is None:
            top_k_final = settings.retrieval_top_k_final

        # Step 1: Query expansion
        query_variants = self._expand_query(query)
        logger.info(f"Query variants: {len(query_variants)} (original + HyDE + entity)")

        # Step 2: Dense retrieval (all variants)
        dense_results: dict[str, tuple[float, int]] = {}  # chunk_id -> (score, rank)
        for variant in query_variants:
            emb = self._embedder.embed_query(variant)
            variant_results = self._faiss.search(emb, k=settings.retrieval_top_k_dense)
            for rank, (cid, score) in enumerate(variant_results):
                if cid not in dense_results or dense_results[cid][0] < score:
                    dense_results[cid] = (score, rank + 1)

        # Step 3: Sparse BM25 retrieval
        sparse_results: dict[str, tuple[float, int]] = {}
        for variant in query_variants:
            variant_sparse = self._bm25.search(variant, k=settings.retrieval_top_k_sparse)
            for rank, (cid, score) in enumerate(variant_sparse):
                if cid not in sparse_results or sparse_results[cid][0] < score:
                    sparse_results[cid] = (score, rank + 1)

        # Step 4: RRF fusion
        alpha = 0.6  # weight toward dense
        candidate_ids = set(dense_results) | set(sparse_results)

        rrf_scores: dict[str, float] = {}
        for cid in candidate_ids:
            dense_rrf = 1.0 / (RRF_K + dense_results[cid][1]) if cid in dense_results else 0.0
            sparse_rrf = 1.0 / (RRF_K + sparse_results[cid][1]) if cid in sparse_results else 0.0
            rrf_scores[cid] = alpha * dense_rrf + (1 - alpha) * sparse_rrf

        # Top-20 by RRF score for reranking
        top_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:20]

        if not top_candidates:
            logger.warning("No candidates retrieved")
            return []

        # Step 5: Fetch chunk texts from database
        candidate_ids_list = [cid for cid, _ in top_candidates]
        chunks_data = await self._fetch_chunks(
            candidate_ids_list, doc_type_filter, classification_filter
        )

        if not chunks_data:
            return []

        # Step 6: Assemble RetrievedChunk objects
        retrieved = []
        for cid, rrf_score in top_candidates:
            if cid not in chunks_data:
                continue
            cd = chunks_data[cid]
            retrieved.append(RetrievedChunk(
                chunk_id=cid,
                text=cd["text"],
                section_id=cd.get("section_id", ""),
                clause_id=cd.get("clause_id", ""),
                doc_id=cd.get("doc_id", ""),
                doc_filename=cd.get("doc_filename", ""),
                page_numbers=cd.get("page_numbers", []),
                ocr_uncertain=cd.get("ocr_uncertain", False),
                dense_score=dense_results.get(cid, (0, 0))[0],
                sparse_score=sparse_results.get(cid, (0, 0))[0],
                rrf_score=rrf_score,
            ))

        # Step 7: Cross-encoder reranking
        if retrieved:
            retrieved = self._rerank(query, retrieved)

        # Step 8: Apply threshold and return top-k
        final = [r for r in retrieved if r.rerank_score >= settings.reranker_threshold]
        final = final[:top_k_final]

        logger.info(
            f"Retrieval complete: {len(candidate_ids)} candidates → "
            f"{len(retrieved)} after fetch → {len(final)} after rerank threshold"
        )
        return final

    def _expand_query(self, query: str) -> list[str]:
        """Generate query variants: original + HyDE hypothesis + entity-focused."""
        variants = [query]

        # HyDE: create a hypothetical policy answer
        hyde_prompt = (
            f"A defence procurement policy passage that answers: '{query}' would state: "
            f"According to the relevant rules and regulations,"
        )
        variants.append(hyde_prompt)

        # Entity-focused: extract key terms for BM25 boosting
        import re
        rule_matches = re.findall(r"Rule\s+\d+[A-Z]?|GFR|DPP|DAP|GFR\s+\d+", query, re.I)
        amount_matches = re.findall(r"(?:₹|Rs\.?|crore|lakh)\s*\d+", query, re.I)
        if rule_matches or amount_matches:
            entity_query = " ".join(rule_matches + amount_matches + [query])
            variants.append(entity_query)

        return variants

    def _rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Apply cross-encoder reranking. Falls back to RRF score if reranker unavailable."""
        self._load_reranker()

        if self._reranker is None:
            # Fallback: use RRF score as rerank score
            for chunk in chunks:
                chunk.rerank_score = chunk.rrf_score
            return sorted(chunks, key=lambda x: x.rerank_score, reverse=True)

        pairs = [(query, chunk.text[:512]) for chunk in chunks]
        try:
            scores = self._reranker.predict(pairs)
            for chunk, score in zip(chunks, scores):
                chunk.rerank_score = float(score)
        except Exception as e:
            logger.error(f"Reranker failed: {e}. Falling back to RRF scores.")
            for chunk in chunks:
                chunk.rerank_score = chunk.rrf_score

        return sorted(chunks, key=lambda x: x.rerank_score, reverse=True)

    async def _fetch_chunks(
        self,
        chunk_ids: list[str],
        doc_type_filter: Optional[str],
        classification_filter: Optional[str],
    ) -> dict[str, dict]:
        """Fetch chunk details from SQLite by IDs."""
        from sqlalchemy import select
        from src.storage.models import Chunk, Document

        async with self._db_factory() as session:
            stmt = (
                select(Chunk, Document)
                .join(Document, Chunk.doc_id == Document.id)
                .where(Chunk.id.in_(chunk_ids))
            )
            if doc_type_filter:
                stmt = stmt.where(Document.doc_type == doc_type_filter)
            if classification_filter:
                stmt = stmt.where(Document.classification_level == classification_filter)

            result = await session.execute(stmt)
            rows = result.all()

        chunks_data = {}
        for chunk, doc in rows:
            # Parse page numbers
            pages = []
            if chunk.page_numbers:
                try:
                    pages = [int(p) for p in chunk.page_numbers.split(",") if p.strip()]
                except ValueError:
                    pages = []

            chunks_data[chunk.id] = {
                "text": chunk.text,
                "section_id": chunk.section_id or "",
                "clause_id": chunk.clause_id or "",
                "doc_id": chunk.doc_id,
                "doc_filename": doc.filename,
                "page_numbers": pages,
                "ocr_uncertain": chunk.ocr_uncertain,
            }
        return chunks_data