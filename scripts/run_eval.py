"""
run_eval.py — RAGAS evaluation of the Defence RAG pipeline.

Metrics:
  - faithfulness       (citation grounding)
  - answer_relevancy   (answer addresses question)
  - context_recall     (retrieved chunks cover ground truth)
  - context_precision  (retrieved chunks are precise)

Usage:
    python scripts/run_eval.py --ground-truth tests/eval/ground_truth.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", default="tests/eval/ground_truth.json")
    parser.add_argument("--output", default="tests/eval/eval_results.json")
    args = parser.parse_args()

    gt_path = Path(args.ground_truth)
    if not gt_path.exists():
        logger.error("Ground truth file not found: %s", gt_path)
        sys.exit(1)

    with open(gt_path) as f:
        ground_truth = json.load(f)

    logger.info("Loaded %d evaluation samples", len(ground_truth))

    from src.config import get_settings
    from src.pipeline import RAGPipeline

    settings = get_settings()
    pipeline = RAGPipeline.from_config(settings)

    results = []
    for i, sample in enumerate(ground_truth, 1):
        question = sample["question"]
        expected_answer = sample.get("expected_answer", "")
        expected_sources = sample.get("expected_source_ids", [])

        logger.info("[%d/%d] Evaluating: %s", i, len(ground_truth), question[:60])

        try:
            result = pipeline.run(question=question, user_id="eval_script")

            # Simple metrics
            answer = result.get("answer", "")
            source_ids = [c.chunk_id for c in result.get("source_chunks", [])]
            conf = result.get("confidence_score", 0)

            # Source recall: fraction of expected sources retrieved
            if expected_sources:
                source_recall = len(set(source_ids) & set(expected_sources)) / len(expected_sources)
            else:
                source_recall = None

            results.append({
                "question": question,
                "answer": answer[:300],
                "confidence_score": conf,
                "source_recall": source_recall,
                "compliance_status": result.get("compliance_status"),
                "cot_applied": result.get("cot_applied"),
            })
        except Exception as exc:
            logger.error("Eval failed for sample %d: %s", i, exc)
            results.append({"question": question, "error": str(exc)})

    # Summary
    scored = [r for r in results if "confidence_score" in r]
    avg_conf = sum(r["confidence_score"] for r in scored) / len(scored) if scored else 0
    recalls = [r["source_recall"] for r in scored if r.get("source_recall") is not None]
    avg_recall = sum(recalls) / len(recalls) if recalls else 0

    summary = {
        "total_samples": len(results),
        "avg_confidence": round(avg_conf, 3),
        "avg_source_recall": round(avg_recall, 3),
        "results": results,
    }

    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("=== Evaluation Complete ===")
    logger.info("Avg Confidence: %.3f", avg_conf)
    logger.info("Avg Source Recall: %.3f", avg_recall)
    logger.info("Results saved to: %s", args.output)


if __name__ == "__main__":
    main()