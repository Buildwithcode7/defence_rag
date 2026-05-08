"""
Efficient local RAG pipeline.

This is the production path used by the API in this build:
document -> PyMuPDF/DOCX/TXT loader -> chunker -> sentence-transformer embeddings
-> FAISS dense search + BM25 sparse search -> RRF fusion -> optional LLM answer.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

RRF_K = 60


@dataclass
class SourceChunk:
    label: str
    chunk_id: str
    doc_id: str
    section: str
    page: Optional[int]
    score: float
    text: str


def _get_loader():
    from src.processing.loader import DocumentLoader

    return DocumentLoader()


def _get_chunker():
    from src.processing.chunker import TextChunker

    return TextChunker(
        max_chars=int(os.getenv("CHUNK_MAX_CHARS", "1200")),
        overlap_chars=int(os.getenv("CHUNK_OVERLAP_CHARS", "180")),
    )


def _get_embedder():
    from src.storage.embedder import Embedder

    return Embedder()


def _get_store(dim: int):
    from src.storage.vector_store import VectorStore

    return VectorStore(index_dir=Path(os.getenv("INDEX_DIR", "data/indices")), dim=dim)


_pipeline_instance: Optional["SimpleRAGPipeline"] = None


def get_pipeline() -> "SimpleRAGPipeline":
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = SimpleRAGPipeline()
    return _pipeline_instance


class SimpleRAGPipeline:
    """Stateful RAG pipeline shared across requests."""

    def __init__(self):
        logger.info("Initialising SimpleRAGPipeline")
        self.embedder = _get_embedder()
        self.store = _get_store(dim=self.embedder.dim)
        self.loader = _get_loader()
        self.chunker = _get_chunker()
        self._bm25 = None
        self._bm25_chunk_ids: list[str] = []
        self._bm25_dirty = True
        logger.info("SimpleRAGPipeline ready. Chunks indexed: %d", self.store.total_chunks)

    @property
    def total_chunks(self) -> int:
        return self.store.total_chunks

    def ingest(self, file_path: str, extra_metadata: dict = None) -> Dict:
        """Load, chunk, embed, and index one document."""
        path = Path(file_path)
        metadata = dict(extra_metadata or {})
        doc = self.loader.load(str(path))

        if self.store.has_content_hash(doc.content_hash):
            logger.info("Skipping duplicate document: %s", doc.filename)
            return {
                "doc_id": metadata.get("doc_id", ""),
                "filename": doc.filename,
                "chunks_created": 0,
                "total_store": self.store.total_chunks,
                "duplicate": True,
            }

        doc_id = metadata.get("doc_id") or str(uuid.uuid4())
        metadata.update(
            {
                "doc_id": doc_id,
                "content_hash": doc.content_hash,
                "page_count": doc.page_count,
                **doc.metadata,
            }
        )

        if not doc.text.strip():
            raise ValueError(f"No text extracted from {path.name}. Check the file.")

        chunks = self.chunker.chunk(
            text=doc.text,
            doc_id=doc_id,
            filename=doc.filename,
            extra_metadata=metadata,
        )
        if not chunks:
            raise ValueError(f"No chunks produced from {path.name}.")

        texts = [chunk.text for chunk in chunks]
        logger.info("Embedding %d chunks from %s", len(chunks), doc.filename)
        embeddings = self.embedder.embed_batch(texts)

        metadatas = []
        for chunk in chunks:
            metadatas.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": doc_id,
                    "filename": chunk.filename,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    **chunk.metadata,
                }
            )

        self.store.add(embeddings, metadatas)
        self._bm25_dirty = True

        return {
            "doc_id": doc_id,
            "filename": doc.filename,
            "chunks_created": len(chunks),
            "total_store": self.store.total_chunks,
            "duplicate": False,
        }

    def run(
        self,
        question: str,
        filters: Optional[Dict] = None,
        top_k: int = 5,
        user_id: str = "anonymous",
        session_id: Optional[str] = None,
    ) -> Dict:
        """Compatibility wrapper for the existing query router."""
        return self.query(question=question, filters=filters, top_k=top_k, session_id=session_id)

    def query(
        self,
        question: str,
        filters: Optional[Dict] = None,
        top_k: int = 5,
        session_id: Optional[str] = None,
    ) -> Dict:
        """Retrieve relevant chunks and generate a grounded response."""
        if self.store.total_chunks == 0:
            return self._no_docs_response(question, session_id)

        filters = filters or {}
        retrieval_k = max(top_k * 8, 20)

        query_embedding = self.embedder.embed(question)
        dense_results = self._filter_results(self.store.search(query_embedding, top_k=retrieval_k), filters)
        sparse_results = self._bm25_search(question, retrieval_k, filters)
        fused = self._fuse_results(dense_results, sparse_results, top_k=top_k)

        if not fused:
            return self._no_docs_response(question, session_id)

        answer, citations, source_chunks = self._build_answer(question, fused)
        confidence = self._confidence(fused)

        return {
            "answer": answer,
            "annotated_answer": answer,
            "citations": citations,
            "source_chunks": source_chunks,
            "compliance_status": "REVIEW REQUIRED",
            "compliance_gaps": [],
            "applicable_rules": [],
            "confidence_score": confidence,
            "confidence_level": self._confidence_level(confidence),
            "cot_applied": False,
            "audit_id": str(uuid.uuid4()),
            "session_id": session_id,
        }

    def _filter_results(self, results: List[Tuple[dict, float]], filters: Dict) -> List[Tuple[dict, float]]:
        if not filters:
            return results

        filtered: List[Tuple[dict, float]] = []
        for meta, score in results:
            if all(str(meta.get(key, "")).lower() == str(value).lower() for key, value in filters.items()):
                filtered.append((meta, score))
        return filtered

    def _bm25_search(self, question: str, top_k: int, filters: Dict) -> List[Tuple[dict, float]]:
        metadata = self.store.metadata
        if not metadata:
            return []

        self._ensure_bm25(metadata)
        query_tokens = _tokenize(question)
        if not query_tokens:
            return []

        by_id = {m.get("chunk_id"): m for m in metadata}
        scores: list[tuple[str, float]] = []

        if self._bm25 is not None:
            raw_scores = self._bm25.get_scores(query_tokens)
            scores = [
                (chunk_id, float(score))
                for chunk_id, score in zip(self._bm25_chunk_ids, raw_scores)
                if score > 0
            ]
        else:
            qset = set(query_tokens)
            for meta in metadata:
                tokens = set(_tokenize(meta.get("text", "")))
                score = len(qset & tokens) / max(len(qset), 1)
                if score > 0:
                    scores.append((meta.get("chunk_id", ""), float(score)))

        scores.sort(key=lambda item: item[1], reverse=True)
        max_score = scores[0][1] if scores else 1.0

        results: List[Tuple[dict, float]] = []
        for chunk_id, score in scores:
            meta = by_id.get(chunk_id)
            if not meta:
                continue
            if filters and not all(str(meta.get(k, "")).lower() == str(v).lower() for k, v in filters.items()):
                continue
            results.append((meta, score / max(max_score, 1e-9)))
            if len(results) >= top_k:
                break
        return results

    def _ensure_bm25(self, metadata: List[dict]) -> None:
        if not self._bm25_dirty and len(self._bm25_chunk_ids) == len(metadata):
            return

        tokenized = [_tokenize(m.get("text", "")) for m in metadata]
        self._bm25_chunk_ids = [m.get("chunk_id", "") for m in metadata]
        try:
            from rank_bm25 import BM25Okapi

            self._bm25 = BM25Okapi(tokenized)
            logger.info("BM25 index rebuilt over %d chunks", len(tokenized))
        except ImportError:
            self._bm25 = None
            logger.warning("rank-bm25 not installed; using lightweight keyword scoring")
        self._bm25_dirty = False

    def _fuse_results(
        self,
        dense_results: List[Tuple[dict, float]],
        sparse_results: List[Tuple[dict, float]],
        top_k: int,
    ) -> List[Tuple[dict, float]]:
        dense_weight = float(os.getenv("RRF_DENSE_WEIGHT", "0.6"))
        by_id: dict[str, dict] = {}
        scores: dict[str, float] = {}

        for rank, (meta, score) in enumerate(dense_results, start=1):
            chunk_id = meta.get("chunk_id", "")
            by_id[chunk_id] = meta
            scores[chunk_id] = scores.get(chunk_id, 0.0) + dense_weight * (1.0 / (RRF_K + rank))

        for rank, (meta, score) in enumerate(sparse_results, start=1):
            chunk_id = meta.get("chunk_id", "")
            by_id[chunk_id] = meta
            scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 - dense_weight) * (1.0 / (RRF_K + rank))

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
        if not ranked:
            return []
        max_rrf = ranked[0][1]
        return [(by_id[chunk_id], score / max(max_rrf, 1e-12)) for chunk_id, score in ranked]

    def _build_answer(
        self,
        question: str,
        results: List[Tuple[dict, float]],
    ) -> Tuple[str, List[dict], List[SourceChunk]]:
        citations: list[dict] = []
        source_chunks: list[SourceChunk] = []
        context_parts: list[str] = []

        for idx, (meta, score) in enumerate(results, start=1):
            label = f"SOURCE-{idx}"
            text = meta.get("text", "")
            source = SourceChunk(
                label=label,
                chunk_id=meta.get("chunk_id", ""),
                doc_id=meta.get("doc_id", ""),
                section=meta.get("filename", ""),
                page=meta.get("chunk_index"),
                score=round(score, 4),
                text=text,
            )
            source_chunks.append(source)
            citations.append(
                {
                    "label": label,
                    "chunk_id": source.chunk_id,
                    "doc_id": source.doc_id,
                    "section": source.section,
                    "page": source.page,
                    "score": source.score,
                    "text_snippet": text[:300],
                }
            )
            context_parts.append(f"[{label}] {source.section}\n{text}")

        context = "\n\n---\n\n".join(context_parts)
        llm_answer = self._call_llm(question, context)
        if llm_answer:
            return llm_answer, citations, source_chunks
        return self._template_answer(question, results), citations, source_chunks

    def _call_llm(self, question: str, context: str) -> Optional[str]:
        backend = os.getenv("LLM_BACKEND", "none").lower()
        if backend == "ollama":
            return self._call_ollama(question, context)
        if backend in {"openai", "openai_compatible"}:
            return self._call_openai_compatible(question, context)
        return None

    def _call_ollama(self, question: str, context: str) -> Optional[str]:
        try:
            import requests

            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            model = os.getenv("OLLAMA_MODEL", "mistral")
            resp = requests.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": _build_prompt(question, context), "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip() or None
        except Exception as exc:
            logger.warning("Ollama call failed: %s", exc)
            return None

    def _call_openai_compatible(self, question: str, context: str) -> Optional[str]:
        try:
            import requests

            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                return None
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            resp = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": _build_prompt(question, context)}],
                    "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "1024")),
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip() or None
        except Exception as exc:
            logger.warning("OpenAI-compatible call failed: %s", exc)
            return None

    def _template_answer(self, question: str, results: List[Tuple[dict, float]]) -> str:
        lines = [
            f"**Query:** {question}",
            "",
            f"**Retrieved {len(results)} relevant passage(s) from your documents:**",
        ]
        for idx, (meta, score) in enumerate(results, start=1):
            text = meta.get("text", "")[:700]
            lines.append(
                f"\n---\n**[SOURCE-{idx}]** `{meta.get('filename', 'unknown')}` "
                f"(chunk {meta.get('chunk_index', 0)}, score: {score:.3f})\n\n{text}..."
            )
        lines.append(
            "\n---\nConfigure `LLM_BACKEND=ollama` or `LLM_BACKEND=openai` for synthesized answers."
        )
        return "\n".join(lines)

    def _no_docs_response(self, question: str, session_id: Optional[str] = None) -> Dict:
        answer = (
            "No matching indexed document chunks were found. Upload policy documents from the "
            "Admin Panel, or loosen the active filters and try again."
        )
        return {
            "answer": answer,
            "annotated_answer": answer,
            "citations": [],
            "source_chunks": [],
            "compliance_status": "INSUFFICIENT_BASIS",
            "compliance_gaps": [],
            "applicable_rules": [],
            "confidence_score": 0.0,
            "confidence_level": "LOW",
            "cot_applied": False,
            "audit_id": str(uuid.uuid4()),
            "session_id": session_id,
        }

    @staticmethod
    def _confidence(results: List[Tuple[dict, float]]) -> float:
        if not results:
            return 0.0
        return round(sum(score for _, score in results) / len(results), 3)

    @staticmethod
    def _confidence_level(score: float) -> str:
        if score >= 0.7:
            return "HIGH"
        if score >= 0.45:
            return "MEDIUM"
        return "LOW"


def _tokenize(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(tok) > 1]


def _build_prompt(question: str, context: str) -> str:
    return f"""You are a Defence Procurement Policy Analyst.
Answer using only the source passages below. Cite every factual claim with source labels like [SOURCE-1].
If the sources do not contain the answer, say that the answer is not present in the ingested documents.

SOURCE PASSAGES:
{context}

QUESTION:
{question}

ANSWER:"""
