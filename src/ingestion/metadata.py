"""
src/ingestion/metadata.py
MetadataTagger: classifies document type and extracts structured metadata
from the loaded document content and filename.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import yaml
from loguru import logger

from config.settings import get_settings
from src.ingestion.loader import LoadedDocument

settings = get_settings()


@dataclass
class DocumentMetadata:
    doc_type: str = "unknown"
    issuing_authority: Optional[str] = None
    effective_date: Optional[str] = None
    version: Optional[str] = None
    classification_level: str = "UNCLASSIFIED"
    supersedes: Optional[str] = None
    tags: list[str] = field(default_factory=list)


# ── Pattern library ─────────────────────────────────────────────────────────

_AUTHORITY_PATTERNS = [
    (r"Ministry of Defence", "Ministry of Defence"),
    (r"MoD", "Ministry of Defence"),
    (r"Ministry of Finance", "Ministry of Finance"),
    (r"Comptroller and Auditor General|CAG", "CAG"),
    (r"Defence Acquisition Council|DAC", "Defence Acquisition Council"),
    (r"Department of Defence Production|DDP", "DDP"),
    (r"DRDO", "DRDO"),
    (r"Headquarters Integrated Defence Staff|HQ IDS", "HQ IDS"),
]

_DATE_PATTERNS = [
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    r"\b(\d{4})\b",  # year
    r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
]

_VERSION_PATTERNS = [
    r"DPP[\s-](\d{4})",
    r"DAP[\s-](\d{4})",
    r"GFR[\s-](\d{4})",
    r"Version\s+([\d.]+)",
    r"Rev(?:ision)?\s+([\d.]+)",
    r"Amendment\s+No\.?\s+(\d+)",
]

_CLASSIFICATION_PATTERNS = {
    "SECRET": r"\bSECRET\b",
    "CONFIDENTIAL": r"\bCONFIDENTIAL\b",
    "RESTRICTED": r"\bRESTRICTED\b",
    "UNCLASSIFIED": r"\bUNCLASSIFIED\b",
}

_DOCTYPE_KEYWORDS = {
    "procurement_policy": [
        "defence procurement procedure", "DPP 20", "DAP 20",
        "procurement policy", "acquisition policy",
    ],
    "financial_rules": [
        "general financial rules", "GFR 20", "DFPDS",
        "financial regulations", "financial rules",
    ],
    "ministry_circular": [
        "circular", "office memorandum", "OM No.", "policy circular",
        "government order", "ministry of defence circular",
    ],
    "audit_report": [
        "audit report", "CAG report", "comptroller", "internal audit",
        "audit findings", "compliance audit",
    ],
    "technical_specification": [
        "GSQR", "general staff qualitative requirement",
        "technical specification", "SQR", "qualitative requirement",
    ],
    "contract": [
        "agreement", "contract no.", "memorandum of understanding",
        "MOU", "supply order", "purchase order",
    ],
    "procurement_order": [
        "request for proposal", "RFP", "tender document",
        "notice inviting tender", "NIT", "expression of interest",
    ],
}


class MetadataTagger:
    """
    Classifies document type and extracts structured metadata from content.
    """

    def __init__(self):
        self._doc_types_config = self._load_doc_types()

    def _load_doc_types(self) -> dict:
        path = settings.document_types_path
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)
        return {}

    def tag(self, doc: LoadedDocument) -> DocumentMetadata:
        """Extract metadata from a loaded document."""
        # Use first 3 pages + filename for classification (most metadata is in frontmatter)
        sample_text = doc.filename + "\n" + "\n".join(
            p.text for p in doc.pages[:3]
        )
        sample_lower = sample_text.lower()

        metadata = DocumentMetadata()
        metadata.doc_type = self._classify_doc_type(sample_lower)
        metadata.issuing_authority = self._extract_authority(sample_text)
        metadata.effective_date = self._extract_date(sample_text)
        metadata.version = self._extract_version(sample_text)
        metadata.classification_level = self._extract_classification(sample_text)
        metadata.tags = self._extract_tags(sample_lower, metadata.doc_type)

        logger.info(
            f"Tagged '{doc.filename}': type={metadata.doc_type}, "
            f"authority={metadata.issuing_authority}, date={metadata.effective_date}, "
            f"classification={metadata.classification_level}"
        )
        return metadata

    def _classify_doc_type(self, text_lower: str) -> str:
        scores: dict[str, int] = {}
        for doc_type, keywords in _DOCTYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scores[doc_type] = score
        if not scores:
            return "unknown"
        return max(scores, key=scores.get)

    def _extract_authority(self, text: str) -> Optional[str]:
        for pattern, authority in _AUTHORITY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return authority
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        # Try most specific patterns first
        for pattern in _DATE_PATTERNS:
            match = re.search(pattern, text[:2000])  # only header area
            if match:
                return match.group(1)
        return None

    def _extract_version(self, text: str) -> Optional[str]:
        for pattern in _VERSION_PATTERNS:
            match = re.search(pattern, text[:3000], re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_classification(self, text: str) -> str:
        # Check first 500 chars (usually on header/footer)
        header = text[:500]
        for level in ["SECRET", "CONFIDENTIAL", "RESTRICTED"]:
            if re.search(_CLASSIFICATION_PATTERNS[level], header):
                return level
        return "UNCLASSIFIED"

    def _extract_tags(self, text_lower: str, doc_type: str) -> list[str]:
        tags = [doc_type]
        tag_keywords = {
            "capital_procurement": ["capital procurement", "capital acquisition"],
            "revenue_procurement": ["revenue procurement", "revenue expenditure"],
            "fast_track": ["fast track", "ftp", "emergency procurement"],
            "make_in_india": ["make in india", "make-i", "make-ii", "iddm"],
            "offset": ["offset", "offset obligation"],
            "audit": ["audit", "cag"],
        }
        for tag, keywords in tag_keywords.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)
        return list(set(tags))