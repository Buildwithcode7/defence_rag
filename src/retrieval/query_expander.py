"""
QueryExpander — produces three query variants for improved retrieval recall.
  (a) original query
  (b) HyDE: hypothetical document embedding (hypothetical clause that would answer this)
  (c) entity-focused variant extracted by NER
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# Defence-domain entity patterns (rule refs, amounts, authorities)
_RULE_PATTERN = re.compile(
    r"(Rule\s+\d+[\w\-]*|Chapter\s+[IVXivx\d]+|Para\s+\d+[\.\d]*|"
    r"DPP\s+\d{4}|GFR\s+\d+|CVC\s+\w+)",
    re.IGNORECASE,
)
_AMOUNT_PATTERN = re.compile(
    r"₹\s*[\d,]+(?:\.\d+)?\s*(?:crore|lakh|Cr|L)?|"
    r"Rs\.?\s*[\d,]+(?:\.\d+)?\s*(?:crore|lakh|Cr|L)?",
    re.IGNORECASE,
)
_AUTHORITY_PATTERN = re.compile(
    r"(CFA|DAC|DPB|TPC|AoN|MoD|Raksha Mantri|VCOAS|CNS|CAS|"
    r"Ministry of (?:Defence|Finance)|Fast Track Procedure|FTP|"
    r"Make in India|DPSU|OFB)",
    re.IGNORECASE,
)


@dataclass
class ExpandedQuery:
    original: str
    hyde: str
    entity_focused: str
    entities: dict = field(default_factory=dict)

    def all_variants(self) -> List[str]:
        return [self.original, self.hyde, self.entity_focused]


class QueryExpander:
    """
    Expands a raw user query into three variants.
    HyDE variant is generated via the LLM; entity variant is rule-extracted.
    """

    def __init__(self, llm_service=None):
        """
        Args:
            llm_service: Optional LLMService instance for HyDE generation.
                         If None, falls back to a template-based approximation.
        """
        self.llm = llm_service

    def expand(self, query: str) -> ExpandedQuery:
        entities = self._extract_entities(query)
        hyde = self._generate_hyde(query)
        entity_focused = self._build_entity_query(query, entities)

        logger.info(
            "QueryExpander: original=%r | entities=%s | hyde_len=%d",
            query[:80],
            entities,
            len(hyde),
        )
        return ExpandedQuery(
            original=query,
            hyde=hyde,
            entity_focused=entity_focused,
            entities=entities,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_entities(self, query: str) -> dict:
        rules = _RULE_PATTERN.findall(query)
        amounts = _AMOUNT_PATTERN.findall(query)
        authorities = _AUTHORITY_PATTERN.findall(query)
        return {
            "rules": list(set(rules)),
            "amounts": list(set(amounts)),
            "authorities": list(set(authorities)),
        }

    def _generate_hyde(self, query: str) -> str:
        """
        Generate a hypothetical policy clause that would answer the query.
        Uses the LLM if available; otherwise falls back to a structured template.
        """
        if self.llm is not None:
            try:
                prompt = (
                    "You are a defence procurement policy writer. "
                    "Write ONE short policy clause (2-3 sentences) from an official "
                    "document that would directly answer the following query. "
                    "Do NOT add any preamble.\n\nQuery: " + query
                )
                return self.llm.complete(prompt, max_tokens=150)
            except Exception as exc:
                logger.warning("HyDE LLM call failed (%s); using template fallback", exc)

        # Template fallback — wraps the query in procurement-register language
        return (
            f"According to the Defence Procurement Procedure, "
            f"the provisions relating to {query.lower().rstrip('?')} "
            f"are governed by the applicable rules and financial limits "
            f"as prescribed by the competent financial authority."
        )

    def _build_entity_query(self, query: str, entities: dict) -> str:
        """
        Build a query that foregrounds extracted entities for BM25 matching.
        Example: 'Fast Track Procedure financial limit' → stronger BM25 signal.
        """
        parts = [query]
        for rule in entities["rules"]:
            if rule.lower() not in query.lower():
                parts.append(rule)
        for auth in entities["authorities"]:
            if auth.lower() not in query.lower():
                parts.append(auth)
        return " ".join(parts)