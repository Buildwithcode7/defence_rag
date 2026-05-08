"""
ingest_corpus.py — Bulk ingest all documents from data/raw/ into the RAG pipeline.

Usage:
    python scripts/ingest_corpus.py --input-dir data/raw/ --doc-type auto
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".docx", ".tiff", ".tif", ".png", ".jpg", ".jpeg"}


def main():
    parser = argparse.ArgumentParser(description="Bulk ingest documents into INICAI Defence RAG")
    parser.add_argument("--input-dir", default="data/raw", help="Directory with source documents")
    parser.add_argument("--doc-type", default="auto")
    parser.add_argument("--classification", default="UNCLASSIFIED")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error("Input directory not found: %s", input_dir)
        sys.exit(1)

    from src.config import get_settings
    from src.pipeline import RAGPipeline

    settings = get_settings()
    pipeline = RAGPipeline.from_config(settings)

    files = [f for f in input_dir.iterdir() if f.suffix.lower() in SUPPORTED]
    logger.info("Found %d documents to ingest", len(files))

    for i, fpath in enumerate(files, 1):
        logger.info("[%d/%d] Ingesting: %s", i, len(files), fpath.name)
        try:
            from src.ingestion.loader import DocumentLoader
            from src.ingestion.validator import DocumentValidator
            from src.ingestion.metadata import MetadataTagger
            from src.processing.chunker import HierarchicalChunker
            from src.processing.extractor import EntityExtractor

            loader = DocumentLoader()
            validator = DocumentValidator()
            tagger = MetadataTagger()
            chunker = HierarchicalChunker()

            doc = loader.load(str(fpath))
            if not validator.validate(doc):
                logger.warning("Skipping %s (validation failed)", fpath.name)
                continue

            doc = tagger.tag(doc, doc_type=args.doc_type, classification_level=args.classification)
            chunks = chunker.chunk(doc)
            logger.info("  → %d chunks created", len(chunks))

            embeddings = [pipeline.embedder.embed(c.text) for c in chunks]
            pipeline.faiss_index.add(embeddings, [c.__dict__ for c in chunks])
            pipeline.bm25_index.add([c.text for c in chunks], [c.__dict__ for c in chunks])

            logger.info("  ✅ %s indexed", fpath.name)
        except Exception as exc:
            logger.error("  ❌ Failed to ingest %s: %s", fpath.name, exc, exc_info=True)

    logger.info("=== Ingestion complete ===")
    pipeline.faiss_index.save()
    pipeline.bm25_index.save()
    logger.info("Indices saved.")


if __name__ == "__main__":
    main()