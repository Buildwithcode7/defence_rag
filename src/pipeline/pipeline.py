"""
pipeline.py — RAGPipeline: central orchestrator that wires all modules together.

Usage:
    pipeline = RAGPipeline.from_config(settings)
    result = pipeline.run(question="...", filters={}, top_k=5, user_id="u1")
"""

from __future__ import annotations
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Orchestrates the full Defence RAG pipeline in a single .run() call.
    """

    def __init__(
        self,
        embedder,
        faiss_index,
        bm25_index,
        query_expander,
        hybrid_fuser,
        reranker,
        context_builder,
        cot_prompter,
        llm_service,
        citation_verifier,
        confidence_scorer,
        rule_mapper,
        gap_detector,
        report_writer,
        audit_trail,
    ):
        self.embedder = embedder
        self.faiss_index = faiss_index
        self.bm25_index = bm25_index
        self.query_expander = query_expander
        self.hybrid_fuser = hybrid_fuser
        self.reranker = reranker
        self.context_builder = context_builder
        self.cot_prompter = cot_prompter
        self.llm = llm_service
        self.citation_verifier = citation_verifier
        self.confidence_scorer = confidence_scorer
        self.rule_mapper = rule_mapper
        self.gap_detector = gap_detector
        self.report_writer = report_writer
        self.audit_trail = audit_trail

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        question: str,
        filters: Optional[Dict] = None,
        top_k: int = 5,
        user_id: str = "anonymous",
        session_id: Optional[str] = None,
    ) -> dict:
        # 1. Query expansion
        expanded = self.query_expander.expand(question)

        # 2. Embed all query variants
        variant_embeddings = [
            self.embedder.embed(v) for v in expanded.all_variants()
        ]

        # 3. Hybrid retrieval (FAISS + BM25) with RRF fusion
        candidates = self.hybrid_fuser.retrieve(
            query_embeddings=variant_embeddings,
            queries=expanded.all_variants(),
            filters=filters,
            top_k=20,
        )

        # 4. Rerank and filter
        ranked_chunks, sufficient = self.reranker.rerank(
            query=question,
            candidates=candidates,
            top_k=top_k,
        )

        # 5. Insufficient-basis guard
        if not sufficient:
            answer = (
                "INSUFFICIENT BASIS — the relevant policy document may not be ingested. "
                "Consult the relevant authority or upload the applicable DPP/GFR document."
            )
            audit_id = self.audit_trail.log_query(
                user_id=user_id,
                session_id=session_id or "",
                query=question,
                retrieved_chunk_ids=[],
                llm_response=answer,
                compliance_status="INSUFFICIENT_BASIS",
                confidence_score=0.0,
            )
            return {
                "answer": answer,
                "annotated_answer": answer,
                "source_chunks": [],
                "compliance_status": "INSUFFICIENT_BASIS",
                "compliance_gaps": [],
                "applicable_rules": [],
                "confidence_score": 0.0,
                "confidence_level": "LOW",
                "cot_applied": False,
                "audit_id": audit_id,
            }

        # 6. Build context
        built_context = self.context_builder.build(
            question=question,
            ranked_chunks=ranked_chunks,
        )

        # 7. Chain-of-thought prompt wrapping
        final_prompt, cot_applied = self.cot_prompter.apply(built_context, question)

        # 8. LLM generation
        llm_response = self.llm.complete(final_prompt, max_tokens=1024)

        # 9. Citation verification (hallucination guard)
        verification = self.citation_verifier.verify(
            llm_response=llm_response,
            source_chunks=built_context.source_chunks,
        )

        # 10. Confidence scoring
        confidence = self.confidence_scorer.score(
            ranked_chunks=ranked_chunks,
            verification_report=verification,
            llm_response=llm_response,
        )

        # 11. Compliance mapping + gap detection
        matched_rules = self.rule_mapper.map_rules(
            query=question,
            llm_response=llm_response,
            retrieved_chunks=ranked_chunks,
        )
        gap_result = self.gap_detector.detect(
            matched_rules=matched_rules,
            query=question,
            llm_response=llm_response,
        )
        compliance_report = self.report_writer.write(
            matched_rules=matched_rules,
            gap_result=gap_result,
        )

        # 12. Audit trail
        audit_id = self.audit_trail.log_query(
            user_id=user_id,
            session_id=session_id or "",
            query=question,
            retrieved_chunk_ids=[c.chunk_id for c in ranked_chunks],
            llm_response=llm_response,
            compliance_status=compliance_report.status,
            confidence_score=confidence.score,
            metadata={"cot_applied": cot_applied},
        )

        logger.info(
            "Pipeline complete: audit=%s confidence=%s compliance=%s",
            audit_id,
            confidence.level,
            compliance_report.status,
        )

        return {
            "answer": llm_response,
            "annotated_answer": verification.annotated_response,
            "source_chunks": built_context.source_chunks,
            "compliance_status": compliance_report.status,
            "compliance_gaps": gap_result.gaps,
            "applicable_rules": matched_rules,
            "confidence_score": confidence.score,
            "confidence_level": confidence.level,
            "cot_applied": cot_applied,
            "compliance_report": compliance_report,
            "audit_id": audit_id,
        }

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, settings) -> "RAGPipeline":
        """
        Instantiate all pipeline components from application settings.
        """
        from src.retrieval.embedder import EmbeddingService
        from src.storage.faiss_index import FAISSIndex
        from src.storage.bm25_index import BM25Index
        from src.retrieval.query_expander import QueryExpander
        from src.retrieval.hybrid_fuser import HybridFuser
        from src.retrieval.reranker import CrossEncoderReranker
        from src.reasoning.context_builder import ContextBuilder
        from src.reasoning.cot_prompter import ChainOfThoughtPrompter
        from src.reasoning.citation_verifier import CitationVerifier
        from src.reasoning.confidence_scorer import ConfidenceScorer
        from src.compliance.rule_mapper import RuleMapper
        from src.compliance.gap_detector import GapDetector
        from src.compliance.report_writer import ComplianceReportWriter
        from src.compliance.audit_trail import AuditTrailWriter
        from src.reasoning.llm_service import LLMService

        logger.info("Initialising RAGPipeline components...")

        embedder = EmbeddingService()
        faiss_idx = FAISSIndex(index_path=settings.faiss_index_path)
        bm25_idx = BM25Index(index_path=settings.bm25_index_path)
        llm = LLMService(backend=settings.llm_backend, model_path=settings.llm_model_path)

        return cls(
            embedder=embedder,
            faiss_index=faiss_idx,
            bm25_index=bm25_idx,
            query_expander=QueryExpander(llm_service=llm),
            hybrid_fuser=HybridFuser(faiss_index=faiss_idx, bm25_index=bm25_idx, embedder=embedder),
            reranker=CrossEncoderReranker(),
            context_builder=ContextBuilder(),
            cot_prompter=ChainOfThoughtPrompter(),
            llm_service=llm,
            citation_verifier=CitationVerifier(),
            confidence_scorer=ConfidenceScorer(),
            rule_mapper=RuleMapper(),
            gap_detector=GapDetector(),
            report_writer=ComplianceReportWriter(),
            audit_trail=AuditTrailWriter(db_path=settings.audit_db_path),
        )