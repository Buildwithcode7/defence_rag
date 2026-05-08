"""
chunker.py — Splits document text into overlapping chunks for embedding.

Strategy:
  1. Split on paragraph boundaries first (double newline)
  2. If a paragraph exceeds max_chars, split on sentence boundaries
  3. Merge short paragraphs together until max_chars is reached
  4. Overlap: last N chars of previous chunk prepended to next chunk
"""

from __future__ import annotations
import re
import logging
import uuid
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

# Defaults — tune for your domain
DEFAULT_MAX_CHARS = 1000     # ~200-250 tokens
DEFAULT_OVERLAP_CHARS = 150  # ~30-40 tokens


@dataclass
class TextChunk:
    chunk_id: str
    text: str
    doc_id: str
    filename: str
    chunk_index: int
    char_start: int
    char_end: int
    metadata: dict = field(default_factory=dict)


class TextChunker:
    """
    Splits a document's text into overlapping chunks.
    """

    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
        overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    ):
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, text: str, doc_id: str, filename: str, extra_metadata: dict = None) -> List[TextChunk]:
        """
        Split text into overlapping chunks.

        Returns:
            List of TextChunk objects.
        """
        paragraphs = self._split_paragraphs(text)
        raw_chunks = self._merge_paragraphs(paragraphs)
        chunks = self._apply_overlap(raw_chunks)

        result = []
        char_pos = 0
        for i, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            result.append(
                TextChunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    doc_id=doc_id,
                    filename=filename,
                    chunk_index=i,
                    char_start=char_pos,
                    char_end=char_pos + len(chunk_text),
                    metadata={
                        "doc_id": doc_id,
                        "filename": filename,
                        "chunk_index": i,
                        "total_chunks": 0,  # filled below
                        **(extra_metadata or {}),
                    },
                )
            )
            char_pos += len(chunk_text) - self.overlap_chars

        # Fill in total_chunks
        for chunk in result:
            chunk.metadata["total_chunks"] = len(result)

        logger.info(
            "Chunker: %d chunks from %s (max_chars=%d overlap=%d)",
            len(result), filename, self.max_chars, self.overlap_chars,
        )
        return result

    # ------------------------------------------------------------------

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split on double newlines, then on sentences if too long."""
        raw = re.split(r"\n\n+", text)
        result = []
        for para in raw:
            para = para.strip()
            if not para:
                continue
            if len(para) <= self.max_chars:
                result.append(para)
            else:
                # Split long paragraph on sentence boundaries
                sentences = re.split(r"(?<=[.!?])\s+", para)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= self.max_chars:
                        current = (current + " " + sent).strip()
                    else:
                        if current:
                            result.append(current)
                        current = sent
                if current:
                    result.append(current)
        return result

    def _merge_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """Merge short paragraphs until max_chars is reached."""
        chunks = []
        current = ""
        for para in paragraphs:
            if not current:
                current = para
            elif len(current) + len(para) + 2 <= self.max_chars:
                current = current + "\n\n" + para
            else:
                chunks.append(current)
                current = para
        if current:
            chunks.append(current)
        return chunks

    def _apply_overlap(self, chunks: List[str]) -> List[str]:
        """Prepend the tail of the previous chunk to each chunk."""
        if len(chunks) <= 1:
            return chunks
        result = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-self.overlap_chars:]
            result.append(tail + "\n\n" + chunks[i])
        return result