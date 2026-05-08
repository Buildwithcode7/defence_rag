"""
ConfidenceScorer — produces a 0–1 confidence score for each LLM response.

Score components:
  1. Reranker score   (40 %): avg score of retrieved chunks used
  2. Citation pass    (40 %): fraction of citations that verified
  3. Uncertainty      (20 %): penalty for hedging language in response

Score < 0.6 → response is rendered with a RED WARNING in the UI.
Score 0.6–0.80 → AMBER caution.
Score > 0.80 → GREEN confident.
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# Words/phrases that signal the LLM is uncertain
_UNCERTAINTY_SIGNALS = [
    r"\bmay\b",
    r"\bmight\b",
    r"\bpossibly\b",
    r"\bperhaps\b",
    r"\bi am not (?:certain|sure)\b",
    r"\bunclear\b",
    r"\bnot explicitly stated\b",
    r"\bcannot confirm\b",
    r"\binsufficient basis\b",
    r"\bno information\b",
]
_UNCERTAINTY_RE = re.compile("|".join(_UNCERTAINTY_SIGNALS), re.IGNORECASE)


@dataclass
class ConfidenceResult:
    score: float            # 0.0–1.0
    level: str              # "HIGH" | "MEDIUM" | "LOW"
    reranker_component: float
    citation_component: float
    uncertainty_component: float
    uncertainty_signals_found: List[str]

    @property
    def color(self) -> str:
        return {"HIGH": "green", "MEDIUM": "orange", "LOW": "red"}[self.level]

    @property
    def banner_message(self) -> Optional[str]:
        if self.level == "LOW":
            return (
                "⚠️  LOW CONFIDENCE — This response has limited source support. "
                "Verify against original policy documents before acting."
            )
        if self.level == "MEDIUM":
            return (
                "⚡ MEDIUM CONFIDENCE — Some citations could not be fully verified. "
                "Cross-check key claims."
            )
        return None


class ConfidenceScorer:
    """Composite confidence scoring for RAG responses."""

    WEIGHTS = {
        "reranker": 0.40,
        "citation": 0.40,
        "uncertainty": 0.20,
    }

    def score(
        self,
        ranked_chunks: list,          # List[RankedChunk]
        verification_report,           # VerificationReport
        llm_response: str,
    ) -> ConfidenceResult:
        # Component 1: Average reranker score (already 0–1 from sigmoid)
        if ranked_chunks:
            reranker_comp = sum(c.score for c in ranked_chunks) / len(ranked_chunks)
        else:
            reranker_comp = 0.0

        # Component 2: Citation pass rate
        citation_comp = getattr(verification_report, "pass_rate", 1.0)

        # Component 3: Uncertainty penalty (inverse of signal density)
        signals = _UNCERTAINTY_RE.findall(llm_response)
        signal_density = min(len(signals) / 5.0, 1.0)  # cap at 5 signals
        uncertainty_comp = 1.0 - signal_density

        score = (
            self.WEIGHTS["reranker"] * reranker_comp
            + self.WEIGHTS["citation"] * citation_comp
            + self.WEIGHTS["uncertainty"] * uncertainty_comp
        )
        score = round(min(max(score, 0.0), 1.0), 3)

        level = "HIGH" if score > 0.80 else ("MEDIUM" if score >= 0.60 else "LOW")

        logger.info(
            "ConfidenceScorer: score=%.3f level=%s "
            "(reranker=%.3f citation=%.3f uncertainty=%.3f signals=%d)",
            score,
            level,
            reranker_comp,
            citation_comp,
            uncertainty_comp,
            len(signals),
        )

        return ConfidenceResult(
            score=score,
            level=level,
            reranker_component=round(reranker_comp, 3),
            citation_component=round(citation_comp, 3),
            uncertainty_component=round(uncertainty_comp, 3),
            uncertainty_signals_found=list(set(s.lower() for s in signals)),
        )