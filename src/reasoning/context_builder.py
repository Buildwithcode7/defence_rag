"""
ContextBuilder — assembles the LLM context window in strict order:
  1. System prompt (role, constraints, anti-hallucination instructions)
  2. Retrieved chunks with [SOURCE-N] labels
  3. Compliance rules summary
  4. User question

Enforces a hard token budget so the context never overflows the LLM window.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# System prompt — non-negotiable for defence deployment
# -----------------------------------------------------------------------
SYSTEM_PROMPT = """You are a Defence Procurement Policy Analyst for the Indian Navy.

STRICT RULES — YOU MUST FOLLOW THESE AT ALL TIMES:
1. Answer ONLY from the provided SOURCE passages below.
2. Every factual claim MUST be followed by its citation tag [SOURCE-N].
3. If the answer is not present in the sources, respond EXACTLY:
   "INSUFFICIENT BASIS — the relevant policy document may not be ingested. Consult [relevant authority]."
4. Do NOT infer, extrapolate, combine, or paraphrase rules not explicitly present in sources.
5. Do NOT use your parametric (training) memory for procurement facts, rules, or limits.
6. If you are uncertain about any part of the answer, state your uncertainty explicitly.
7. Structure your answer clearly: first state the direct answer, then cite each supporting rule.

COMPLIANCE AWARENESS:
- Identify all applicable rules mentioned in the sources.
- Flag any missing approvals or prerequisite steps explicitly.
- Use precise regulatory language (e.g. "as per Rule 154 GFR [SOURCE-2]").
"""

# -----------------------------------------------------------------------
# Dataclasses
# -----------------------------------------------------------------------

@dataclass
class SourceChunk:
    label: str          # e.g. "SOURCE-1"
    chunk_id: str
    text: str
    doc_id: str
    section: str
    page: Optional[int] = None
    score: float = 0.0


@dataclass
class BuiltContext:
    system_prompt: str
    source_chunks: List[SourceChunk]
    compliance_summary: str
    question: str
    full_prompt: str
    token_estimate: int


class ContextBuilder:
    """
    Assembles the full LLM prompt from ranked chunks.
    Hard token budget: 3800 tokens for context (reserves 1200 for generation).
    """

    MAX_CONTEXT_TOKENS: int = 3800
    # Rough chars-per-token estimate for English legal text
    CHARS_PER_TOKEN: float = 3.8

    def __init__(self, max_context_tokens: int = 3800):
        self.MAX_CONTEXT_TOKENS = max_context_tokens

    def build(
        self,
        question: str,
        ranked_chunks: list,
        compliance_rules_summary: str = "",
    ) -> BuiltContext:
        """
        Args:
            question: Raw user question.
            ranked_chunks: List of RankedChunk objects (from reranker).
            compliance_rules_summary: Short summary of applicable compliance rules.

        Returns:
            BuiltContext with the assembled prompt and metadata.
        """
        source_chunks = self._label_chunks(ranked_chunks)
        sources_block = self._format_sources(source_chunks)
        compliance_block = self._format_compliance(compliance_rules_summary)
        question_block = f"\nQUESTION:\n{question}\n\nANSWER:"

        # Assemble in strict order
        full_prompt = (
            SYSTEM_PROMPT
            + "\n\n"
            + sources_block
            + "\n"
            + compliance_block
            + question_block
        )

        token_est = self._estimate_tokens(full_prompt)
        if token_est > self.MAX_CONTEXT_TOKENS:
            logger.warning(
                "Context token estimate %d exceeds budget %d; truncating sources.",
                token_est,
                self.MAX_CONTEXT_TOKENS,
            )
            source_chunks, sources_block = self._truncate_sources(
                source_chunks, question, compliance_block, question_block
            )
            full_prompt = (
                SYSTEM_PROMPT
                + "\n\n"
                + sources_block
                + "\n"
                + compliance_block
                + question_block
            )
            token_est = self._estimate_tokens(full_prompt)

        logger.info(
            "ContextBuilder: %d source chunks, ~%d tokens",
            len(source_chunks),
            token_est,
        )

        return BuiltContext(
            system_prompt=SYSTEM_PROMPT,
            source_chunks=source_chunks,
            compliance_summary=compliance_rules_summary,
            question=question,
            full_prompt=full_prompt,
            token_estimate=token_est,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _label_chunks(self, ranked_chunks: list) -> List[SourceChunk]:
        result = []
        for i, chunk in enumerate(ranked_chunks, start=1):
            result.append(
                SourceChunk(
                    label=f"SOURCE-{i}",
                    chunk_id=getattr(chunk, "chunk_id", str(i)),
                    text=getattr(chunk, "text", ""),
                    doc_id=getattr(chunk, "metadata", {}).get("doc_id", "unknown"),
                    section=getattr(chunk, "metadata", {}).get("section", ""),
                    page=getattr(chunk, "metadata", {}).get("page", None),
                    score=getattr(chunk, "score", 0.0),
                )
            )
        return result

    def _format_sources(self, chunks: List[SourceChunk]) -> str:
        lines = ["RETRIEVED SOURCE PASSAGES:"]
        lines.append("=" * 60)
        for chunk in chunks:
            header = f"[{chunk.label}] | Doc: {chunk.doc_id}"
            if chunk.section:
                header += f" | Section: {chunk.section}"
            if chunk.page:
                header += f" | Page: {chunk.page}"
            lines.append(header)
            lines.append(chunk.text.strip())
            lines.append("-" * 60)
        return "\n".join(lines)

    def _format_compliance(self, summary: str) -> str:
        if not summary:
            return ""
        return f"\nCOMPLIANCE CONTEXT:\n{summary}\n"

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text) / self.CHARS_PER_TOKEN)

    def _truncate_sources(
        self,
        chunks: List[SourceChunk],
        question: str,
        compliance_block: str,
        question_block: str,
    ):
        """Remove chunks from the tail until budget is met."""
        overhead = self._estimate_tokens(
            SYSTEM_PROMPT + compliance_block + question_block
        )
        budget = self.MAX_CONTEXT_TOKENS - overhead
        kept = []
        used = 0
        for chunk in chunks:
            chunk_tokens = self._estimate_tokens(chunk.text)
            if used + chunk_tokens > budget:
                break
            kept.append(chunk)
            used += chunk_tokens
        return kept, self._format_sources(kept)