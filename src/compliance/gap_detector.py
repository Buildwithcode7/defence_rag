"""
GapDetector — checks whether all prerequisite steps for matched rules are evidenced.

For each matched rule, checks its 'prerequisites' list against the query+answer context.
If a prerequisite is absent → COMPLIANCE GAP is raised with rule citation and severity.
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class ComplianceGap:
    rule_id: str
    rule_title: str
    missing_prerequisite: str
    description: str
    severity: str           # "CRITICAL" | "WARNING" | "INFO"
    remediation: str


@dataclass
class GapDetectionResult:
    gaps: List[ComplianceGap] = field(default_factory=list)
    is_compliant: bool = True

    @property
    def critical_gaps(self) -> List[ComplianceGap]:
        return [g for g in self.gaps if g.severity == "CRITICAL"]

    @property
    def warning_gaps(self) -> List[ComplianceGap]:
        return [g for g in self.gaps if g.severity == "WARNING"]

    def summary(self) -> str:
        if self.is_compliant:
            return "✅ No compliance gaps detected."
        parts = []
        if self.critical_gaps:
            parts.append(f"🔴 {len(self.critical_gaps)} CRITICAL gap(s)")
        if self.warning_gaps:
            parts.append(f"🟡 {len(self.warning_gaps)} WARNING gap(s)")
        info_gaps = [g for g in self.gaps if g.severity == "INFO"]
        if info_gaps:
            parts.append(f"🔵 {len(info_gaps)} INFO item(s)")
        return " | ".join(parts)


class GapDetector:
    """
    Detects missing compliance prerequisites for each mapped rule.
    """

    def detect(
        self,
        matched_rules: List[dict],
        query: str,
        llm_response: str,
    ) -> GapDetectionResult:
        """
        Args:
            matched_rules: Rules returned by RuleMapper.map_rules().
            query: Original user query.
            llm_response: LLM-generated answer.

        Returns:
            GapDetectionResult with any detected compliance gaps.
        """
        text_corpus = (query + " " + llm_response).lower()
        gaps = []

        for rule in matched_rules:
            prerequisites = rule.get("prerequisites", [])
            for prereq in prerequisites:
                if not self._prerequisite_evidenced(prereq, text_corpus):
                    gaps.append(
                        ComplianceGap(
                            rule_id=rule.get("rule_id", "UNKNOWN"),
                            rule_title=rule.get("title", ""),
                            missing_prerequisite=prereq.get("name", ""),
                            description=(
                                f"COMPLIANCE GAP: {prereq.get('name', '')} "
                                f"({rule.get('rule_id', '')}, {rule.get('source_doc', '')}) "
                                f"not evidenced in the query context."
                            ),
                            severity=prereq.get("severity", "WARNING"),
                            remediation=prereq.get("remediation", "Consult the relevant authority."),
                        )
                    )

        is_compliant = not any(g.severity in ("CRITICAL", "WARNING") for g in gaps)

        if gaps:
            logger.warning(
                "GapDetector: %d gap(s) found (%d critical)",
                len(gaps),
                sum(1 for g in gaps if g.severity == "CRITICAL"),
            )
        else:
            logger.info("GapDetector: no gaps found")

        return GapDetectionResult(gaps=gaps, is_compliant=is_compliant)

    # ------------------------------------------------------------------

    def _prerequisite_evidenced(self, prereq: dict, text: str) -> bool:
        """
        A prerequisite is 'evidenced' if any of its evidence_keywords appear in text.
        """
        keywords = prereq.get("evidence_keywords", [])
        if not keywords:
            return True  # No evidence required → assume satisfied
        return any(re.search(re.escape(kw.lower()), text) for kw in keywords)