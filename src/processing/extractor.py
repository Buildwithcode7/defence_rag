"""
src/processing/extractor.py
EntityExtractor: extracts defence-domain entities from chunks.
Uses regex-based patterns (no external spaCy model dependency for portability)
with optional spaCy NER as enhancement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


@dataclass
class Entity:
    text: str
    label: str          # RULE_REF | AMOUNT | AUTHORITY | DATE | CLAUSE | CATEGORY
    start: int
    end: int
    normalized: Optional[str] = None


@dataclass
class ExtractionResult:
    entities: list[Entity] = field(default_factory=list)
    rule_references: list[str] = field(default_factory=list)
    monetary_amounts: list[str] = field(default_factory=list)
    authorities: list[str] = field(default_factory=list)
    procurement_categories: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)


# ── Pattern definitions ────────────────────────────────────────────────────

_RULE_PATTERNS = [
    (re.compile(r"\bRule\s+\d+[A-Z]?\b", re.I), "RULE_REF"),
    (re.compile(r"\bSection\s+\d+[A-Z]?\b", re.I), "RULE_REF"),
    (re.compile(r"\bClause\s+\d+(?:\.\d+)*\b", re.I), "RULE_REF"),
    (re.compile(r"\bPara(?:graph)?\s+\d+(?:\.\d+)*\b", re.I), "RULE_REF"),
    (re.compile(r"\bDPP[-\s]?20\d{2}\b", re.I), "RULE_REF"),
    (re.compile(r"\bGFR[-\s]?20\d{2}\b", re.I), "RULE_REF"),
    (re.compile(r"\bDAP[-\s]?20\d{2}\b", re.I), "RULE_REF"),
    (re.compile(r"\bChapter\s+[IVXivx]+\b", re.I), "RULE_REF"),
    (re.compile(r"\bAppendix\s+[A-Z]\b", re.I), "RULE_REF"),
    (re.compile(r"\bAnnex(?:ure)?\s+[A-Z\d]+\b", re.I), "RULE_REF"),
]

_AMOUNT_PATTERNS = [
    # ₹500 crore, Rs. 500 crore, INR 500 Cr
    (re.compile(
        r"(?:₹|Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*"
        r"(?:crore|crores|cr|lakh|lakhs|thousand|million|billion)?",
        re.I
    ), "AMOUNT"),
    # "above 500 crore", "below 25 lakh"
    (re.compile(
        r"(?:above|below|upto|up to|exceeding|more than|less than)\s+"
        r"(?:₹|Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*"
        r"(?:crore|crores|cr|lakh|lakhs)?",
        re.I
    ), "AMOUNT"),
]

_AUTHORITY_PATTERNS = [
    (re.compile(r"\bRaksha\s+Mantri\b", re.I), "AUTHORITY"),
    (re.compile(r"\bDefence\s+Minister\b", re.I), "AUTHORITY"),
    (re.compile(r"\bCFA\b"), "AUTHORITY"),
    (re.compile(r"\bCompetent\s+Financial\s+Authority\b", re.I), "AUTHORITY"),
    (re.compile(r"\bDAC\b"), "AUTHORITY"),
    (re.compile(r"\bDefence\s+Acquisition\s+Council\b", re.I), "AUTHORITY"),
    (re.compile(r"\bService\s+Chief\b", re.I), "AUTHORITY"),
    (re.compile(r"\bVCOAS\b"), "AUTHORITY"),
    (re.compile(r"\bTPC\b"), "AUTHORITY"),
    (re.compile(r"\bCNC\b"), "AUTHORITY"),
    (re.compile(r"\bDG\s+(?:Acquisition|Acq)\b", re.I), "AUTHORITY"),
    (re.compile(r"\bMoD\b"), "AUTHORITY"),
    (re.compile(r"\bMinistry\s+of\s+Defence\b", re.I), "AUTHORITY"),
    (re.compile(r"\bMinistry\s+of\s+Finance\b", re.I), "AUTHORITY"),
    (re.compile(r"\bCAG\b"), "AUTHORITY"),
    (re.compile(r"\bDRDO\b"), "AUTHORITY"),
]

_CATEGORY_PATTERNS = [
    (re.compile(r"\bIDDM\b"), "PROCUREMENT_CATEGORY"),
    (re.compile(r"\bBuy\s+\(Indian\)", re.I), "PROCUREMENT_CATEGORY"),
    (re.compile(r"\bBuy\s+\(Global\)", re.I), "PROCUREMENT_CATEGORY"),
    (re.compile(r"\bBuy\s+and\s+Make", re.I), "PROCUREMENT_CATEGORY"),
    (re.compile(r"\bMake[-\s]I\b", re.I), "PROCUREMENT_CATEGORY"),
    (re.compile(r"\bMake[-\s]II\b", re.I), "PROCUREMENT_CATEGORY"),
    (re.compile(r"\bFast\s+Track\s+Procedure\b", re.I), "PROCUREMENT_CATEGORY"),
    (re.compile(r"\bFTP\b"), "PROCUREMENT_CATEGORY"),
    (re.compile(r"\bStrategic\s+Partnership\b", re.I), "PROCUREMENT_CATEGORY"),
    (re.compile(r"\bSP\s+Model\b", re.I), "PROCUREMENT_CATEGORY"),
]

_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{4}|"
    r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})\b",
    re.I
)


class EntityExtractor:
    """
    Extracts defence-domain entities from text using compiled regex patterns.
    Optionally enhanced by spaCy if available.
    """

    def __init__(self):
        self._spacy_nlp = self._load_spacy()

    def _load_spacy(self):
        try:
            import spacy
            try:
                nlp = spacy.load("en_core_web_sm")
                logger.info("spaCy en_core_web_sm loaded for enhanced NER")
                return nlp
            except OSError:
                logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
                return None
        except ImportError:
            return None

    def extract(self, text: str) -> ExtractionResult:
        result = ExtractionResult()
        entities: list[Entity] = []

        # Rule references
        for pattern, label in _RULE_PATTERNS:
            for m in pattern.finditer(text):
                e = Entity(text=m.group(), label=label, start=m.start(), end=m.end())
                entities.append(e)
                result.rule_references.append(m.group())

        # Monetary amounts
        for pattern, label in _AMOUNT_PATTERNS:
            for m in pattern.finditer(text):
                e = Entity(text=m.group(), label=label, start=m.start(), end=m.end())
                entities.append(e)
                result.monetary_amounts.append(m.group())

        # Authorities
        for pattern, label in _AUTHORITY_PATTERNS:
            for m in pattern.finditer(text):
                e = Entity(text=m.group(), label=label, start=m.start(), end=m.end())
                entities.append(e)
                result.authorities.append(m.group())

        # Procurement categories
        for pattern, label in _CATEGORY_PATTERNS:
            for m in pattern.finditer(text):
                e = Entity(text=m.group(), label=label, start=m.start(), end=m.end())
                entities.append(e)
                result.procurement_categories.append(m.group())

        # Dates
        for m in _DATE_PATTERN.finditer(text):
            entities.append(Entity(text=m.group(), label="DATE", start=m.start(), end=m.end()))
            result.dates.append(m.group())

        # Deduplicate by (text, label)
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e.text.lower(), e.label)
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)

        result.entities = unique_entities
        result.rule_references = list(set(result.rule_references))
        result.monetary_amounts = list(set(result.monetary_amounts))
        result.authorities = list(set(result.authorities))
        result.procurement_categories = list(set(result.procurement_categories))

        return result

    def to_dict_list(self, result: ExtractionResult) -> list[dict]:
        """Serialise entities to JSON-friendly list for storage."""
        return [
            {"text": e.text, "label": e.label, "start": e.start, "end": e.end}
            for e in result.entities
        ]