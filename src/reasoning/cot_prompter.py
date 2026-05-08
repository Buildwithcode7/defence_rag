"""
ChainOfThoughtPrompter — detects complex queries and forces structured CoT decomposition.

Complex query signals:
  - Multiple entities (rule + amount + authority)
  - Words like "what approvals", "all steps", "process for", "procedure to"
  - Conditional structure ("if ... then", "above ... below")

For simple queries, returns the context prompt unchanged.
For complex queries, wraps with a decomposition directive.
"""

from __future__ import annotations
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Phrases that indicate a multi-step procedural answer is required
_COMPLEX_SIGNALS = [
    r"\ball\s+(?:the\s+)?(?:steps|approvals|requirements|conditions)\b",
    r"\bwhat\s+approvals?\b",
    r"\bprocess\s+for\b",
    r"\bprocedure\s+(?:to|for)\b",
    r"\bwho\s+(?:must|should|needs?\s+to)\s+approve\b",
    r"\bif\b.{5,80}\bthen\b",
    r"\babove\b.{2,40}\bbelow\b",
    r"\bstep[s\-]by[- ]step\b",
    r"\beligibility\s+criteria\b",
    r"\bscenario\b",
]

_COMPLEX_RE = re.compile("|".join(_COMPLEX_SIGNALS), re.IGNORECASE)

COT_PREFIX = """Before answering, work through the following steps:

STEP 1 — DECOMPOSE: Break the question into sub-questions (list them).
STEP 2 — ANSWER EACH SUB-QUESTION: For each, cite your source with [SOURCE-N].
STEP 3 — SYNTHESISE: Combine sub-answers into a final coherent response.
STEP 4 — COMPLIANCE CHECK: List any mandatory approvals or prerequisites identified.
STEP 5 — GAPS: State explicitly if any required information is absent from sources.

"""


class ChainOfThoughtPrompter:
    """
    Wraps an assembled context prompt with CoT instructions for complex queries.
    """

    def should_use_cot(self, question: str) -> bool:
        return bool(_COMPLEX_RE.search(question))

    def apply(self, built_context, question: str) -> Tuple[str, bool]:
        """
        Args:
            built_context: BuiltContext from ContextBuilder.
            question: Raw user question.

        Returns:
            (final_prompt, cot_applied)
        """
        if not self.should_use_cot(question):
            logger.debug("CoT not applied for query: %r", question[:60])
            return built_context.full_prompt, False

        # Inject CoT directive between sources and the QUESTION block
        prompt = built_context.full_prompt
        question_marker = "\nQUESTION:"
        idx = prompt.rfind(question_marker)
        if idx == -1:
            # Fallback: prepend CoT at the end
            final = prompt + "\n\n" + COT_PREFIX
        else:
            final = prompt[:idx] + "\n\n" + COT_PREFIX + prompt[idx:]

        logger.info("CoT applied for query: %r", question[:80])
        return final, True