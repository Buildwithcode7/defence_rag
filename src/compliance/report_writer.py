"""
ComplianceReportWriter — generates a structured compliance report.

Output:
  - List of applicable rules (with citations)
  - List of gaps detected (severity-sorted)
  - Recommended remedial steps
  - Overall status: COMPLIANT / NON-COMPLIANT / REVIEW REQUIRED
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class ComplianceReport:
    status: str                         # "COMPLIANT" | "NON-COMPLIANT" | "REVIEW REQUIRED"
    applicable_rules: List[dict]        # from RuleMapper
    gaps: list                          # List[ComplianceGap]
    remedial_steps: List[str]
    summary: str
    raw_text: str                       # Pre-formatted for display

    @property
    def status_emoji(self) -> str:
        return {
            "COMPLIANT": "✅",
            "NON-COMPLIANT": "🔴",
            "REVIEW REQUIRED": "🟡",
        }.get(self.status, "❓")


class ComplianceReportWriter:
    """Assembles a ComplianceReport from rule-mapper and gap-detector outputs."""

    def write(
        self,
        matched_rules: List[dict],
        gap_result,                     # GapDetectionResult
    ) -> ComplianceReport:
        # Determine overall status
        if not gap_result.gaps:
            status = "COMPLIANT"
        elif gap_result.critical_gaps:
            status = "NON-COMPLIANT"
        else:
            status = "REVIEW REQUIRED"

        remedial_steps = self._collect_remediation(gap_result.gaps)
        summary = self._build_summary(status, matched_rules, gap_result)
        raw_text = self._format_text(status, matched_rules, gap_result, remedial_steps)

        logger.info(
            "ComplianceReport: status=%s rules=%d gaps=%d",
            status,
            len(matched_rules),
            len(gap_result.gaps),
        )

        return ComplianceReport(
            status=status,
            applicable_rules=matched_rules,
            gaps=gap_result.gaps,
            remedial_steps=remedial_steps,
            summary=summary,
            raw_text=raw_text,
        )

    # ------------------------------------------------------------------

    def _collect_remediation(self, gaps: list) -> List[str]:
        steps = []
        for gap in sorted(gaps, key=lambda g: {"CRITICAL": 0, "WARNING": 1, "INFO": 2}.get(g.severity, 3)):
            step = f"[{gap.severity}] {gap.missing_prerequisite}: {gap.remediation}"
            if step not in steps:
                steps.append(step)
        return steps

    def _build_summary(self, status: str, rules: List[dict], gap_result) -> str:
        parts = [f"Status: {status}"]
        parts.append(f"Applicable rules: {len(rules)}")
        parts.append(gap_result.summary())
        return " | ".join(parts)

    def _format_text(
        self, status: str, rules: List[dict], gap_result, remedial_steps: List[str]
    ) -> str:
        lines = []
        lines.append(f"═══ COMPLIANCE REPORT ═══")
        lines.append(f"Overall Status: {status}")
        lines.append("")

        lines.append("── Applicable Rules ──")
        if rules:
            for rule in rules:
                lines.append(
                    f"  • {rule.get('rule_id', 'N/A')} — {rule.get('title', '')} "
                    f"[{rule.get('source_doc', '')}]"
                )
        else:
            lines.append("  No specific rules mapped.")

        lines.append("")
        lines.append("── Compliance Gaps ──")
        if gap_result.gaps:
            for gap in gap_result.gaps:
                lines.append(f"  [{gap.severity}] {gap.description}")
        else:
            lines.append("  ✅ No gaps detected.")

        if remedial_steps:
            lines.append("")
            lines.append("── Remedial Steps ──")
            for i, step in enumerate(remedial_steps, 1):
                lines.append(f"  {i}. {step}")

        return "\n".join(lines)