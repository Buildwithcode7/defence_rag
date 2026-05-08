"""
CitationVerifier — post-generation hallucination guard.

After the LLM generates a response, this module:
  1. Parses every [SOURCE-N] tag in the response.
  2. Finds the text snippet the LLM claims is from that source.
  3. Does a fuzzy substring match against the actual retrieved chunk.
  4. Tags each citation as VERIFIED or UNVERIFIED.
  5. Returns the annotated response and a verification report.

An UNVERIFIED tag means the LLM fabricated or misquoted content — it must be
flagged visibly in the UI and never silently passed through.
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Regex to find citation tags in the response
_CITATION_RE = re.compile(r"\[SOURCE-(\d+)\]")

# Minimum character-level similarity to count as VERIFIED (Jaccard on trigrams)
VERIFY_THRESHOLD: float = 0.25


@dataclass
class CitationResult:
    source_label: str       # e.g. "SOURCE-1"
    verified: bool
    claim_snippet: str      # text before the citation in LLM response
    source_text: str        # actual chunk text
    similarity: float


@dataclass
class VerificationReport:
    total_citations: int
    verified_count: int
    unverified_count: int
    results: List[CitationResult] = field(default_factory=list)
    annotated_response: str = ""

    @property
    def pass_rate(self) -> float:
        if self.total_citations == 0:
            return 1.0
        return self.verified_count / self.total_citations


class CitationVerifier:
    """
    Verifies that every [SOURCE-N] tag in the LLM response corresponds to
    content actually present in the retrieved source chunk.
    """

    def __init__(self, verify_threshold: float = VERIFY_THRESHOLD):
        self.threshold = verify_threshold

    def verify(
        self,
        llm_response: str,
        source_chunks: list,  # List[SourceChunk] from context_builder
    ) -> VerificationReport:
        """
        Args:
            llm_response: Raw text from the LLM.
            source_chunks: SourceChunk objects used to build the context.

        Returns:
            VerificationReport with per-citation results and annotated response.
        """
        # Map label → chunk text
        chunk_map: Dict[str, str] = {
            chunk.label: chunk.text for chunk in source_chunks
        }

        matches = list(_CITATION_RE.finditer(llm_response))
        results = []

        for match in matches:
            label = f"SOURCE-{match.group(1)}"
            claim_snippet = self._extract_claim(llm_response, match.start())
            source_text = chunk_map.get(label, "")

            if not source_text:
                sim = 0.0
                verified = False
            else:
                sim = self._trigram_similarity(claim_snippet, source_text)
                verified = sim >= self.threshold

            results.append(
                CitationResult(
                    source_label=label,
                    verified=verified,
                    claim_snippet=claim_snippet[:200],
                    source_text=source_text[:200],
                    similarity=round(sim, 3),
                )
            )
            logger.debug(
                "Citation %s: verified=%s sim=%.3f claim=%r",
                label,
                verified,
                sim,
                claim_snippet[:60],
            )

        annotated = self._annotate_response(llm_response, results)
        verified_count = sum(1 for r in results if r.verified)

        report = VerificationReport(
            total_citations=len(results),
            verified_count=verified_count,
            unverified_count=len(results) - verified_count,
            results=results,
            annotated_response=annotated,
        )

        logger.info(
            "CitationVerifier: %d/%d verified (pass_rate=%.2f)",
            verified_count,
            len(results),
            report.pass_rate,
        )
        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_claim(self, text: str, citation_pos: int, window: int = 300) -> str:
        """Extract the sentence or phrase immediately before a citation tag."""
        start = max(0, citation_pos - window)
        snippet = text[start:citation_pos]
        # Take the last sentence
        sentences = re.split(r"(?<=[.!?])\s+", snippet)
        return sentences[-1].strip() if sentences else snippet.strip()

    @staticmethod
    def _trigrams(text: str) -> set:
        text = re.sub(r"\s+", " ", text.lower())
        return {text[i : i + 3] for i in range(len(text) - 2)}

    def _trigram_similarity(self, a: str, b: str) -> float:
        ta, tb = self._trigrams(a), self._trigrams(b)
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    def _annotate_response(
        self, response: str, results: List[CitationResult]
    ) -> str:
        """
        Replace [SOURCE-N] tags with [SOURCE-N ✓] or [SOURCE-N ✗ UNVERIFIED].
        """
        annotated = response

        def replacer(match):
            label = f"SOURCE-{match.group(1)}"
            result = next((r for r in results if r.source_label == label), None)
            if result is None:
                return f"[{label} ✗ UNVERIFIED]"
            return f"[{label} {'✓' if result.verified else '✗ UNVERIFIED'}]"

        return _CITATION_RE.sub(replacer, annotated)