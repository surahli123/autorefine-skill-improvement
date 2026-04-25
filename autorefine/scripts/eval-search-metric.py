#!/usr/bin/env python3
"""
Evaluate search_retrieval_v1 predictions against query/doc relevance rows.

Gold JSONL rows:
  {"query": "...", "doc_id": "...", "grade": 0..3, "metadata": {... optional}}

Prediction JSONL rows:
  {"query": "...", "doc_ids": ["doc_a", "doc_b"]}
  {"query": "...", "results": [{"doc_id": "doc_a"}, {"doc_id": "doc_b"}]}

Outputs an AutoRefine-friendly metric artifact with aggregate NDCG@5, recall@5,
per-query evidence, and optional judge-vs-metric trust diagnostics.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Iterable


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL row: {exc}") from exc
    return rows


def relevance_by_query(rows: Iterable[dict]) -> dict[str, dict[str, int]]:
    judgments: dict[str, dict[str, int]] = {}
    for index, row in enumerate(rows, start=1):
        query = row.get("query")
        doc_id = row.get("doc_id")
        grade = row.get("grade")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"gold row {index}: query must be a non-empty string")
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError(f"gold row {index}: doc_id must be a non-empty string")
        if not isinstance(grade, int) or isinstance(grade, bool) or grade < 0:
            raise ValueError(f"gold row {index}: grade must be a non-negative integer")
        judgments.setdefault(query, {})[doc_id] = grade
    return judgments


def ranked_doc_ids(prediction: dict) -> list[str]:
    if isinstance(prediction.get("doc_ids"), list):
        doc_ids = prediction["doc_ids"]
    elif isinstance(prediction.get("results"), list):
        doc_ids = [
            result.get("doc_id")
            for result in prediction["results"]
            if isinstance(result, dict)
        ]
    else:
        doc_ids = []

    seen = set()
    ranked = []
    for doc_id in doc_ids:
        if not isinstance(doc_id, str) or not doc_id.strip() or doc_id in seen:
            continue
        seen.add(doc_id)
        ranked.append(doc_id)
    return ranked


def dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(grades))


def score_query(
    query: str,
    predicted_doc_ids: list[str],
    judgments: dict[str, int],
    k: int = 5,
) -> dict:
    ranked = predicted_doc_ids[:k]
    predicted_grades = [judgments.get(doc_id, 0) for doc_id in ranked]
    ideal_grades = sorted(judgments.values(), reverse=True)[:k]
    ideal_dcg = dcg(ideal_grades)
    ndcg = dcg(predicted_grades) / ideal_dcg if ideal_dcg else 0.0

    relevant_doc_ids = {doc_id for doc_id, grade in judgments.items() if grade > 0}
    retrieved_relevant = [doc_id for doc_id in ranked if doc_id in relevant_doc_ids]
    recall = len(retrieved_relevant) / len(relevant_doc_ids) if relevant_doc_ids else 0.0

    missing_relevant = sorted(relevant_doc_ids - set(retrieved_relevant))
    return {
        "query": query,
        "ranked_doc_ids": ranked,
        f"ndcg_at_{k}": round(ndcg, 6),
        f"recall_at_{k}": round(recall, 6),
        "relevant_doc_ids": sorted(relevant_doc_ids),
        "retrieved_relevant_doc_ids": retrieved_relevant,
        "missing_relevant_doc_ids": missing_relevant,
    }


def normalize_judge_diagnostic(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if lowered in {"pass", "passed", "true", "yes"}:
        return "pass"
    if lowered in {"fail", "failed", "false", "no"}:
        return "fail"
    return None


def trust_diagnostic(metric_passed: bool, judge_diagnostic: str | None) -> str:
    if judge_diagnostic == "pass" and not metric_passed:
        return "judge_pass_metric_fail"
    if judge_diagnostic == "fail" and metric_passed:
        return "judge_fail_metric_pass"
    if judge_diagnostic in {"pass", "fail"}:
        return "judge_metric_agree"
    return "metric_only"


def score_predictions(
    gold_rows: list[dict],
    prediction_rows: list[dict],
    k: int = 5,
    threshold_pass: float = 0.65,
    threshold_concern: float = 0.50,
) -> dict:
    judgments = relevance_by_query(gold_rows)
    predictions_by_query = {
        row.get("query"): row
        for row in prediction_rows
        if isinstance(row.get("query"), str)
    }

    per_query = []
    ndcg_key = f"ndcg_at_{k}"
    recall_key = f"recall_at_{k}"
    for query in sorted(judgments):
        prediction = predictions_by_query.get(query, {"query": query, "doc_ids": []})
        row = score_query(query, ranked_doc_ids(prediction), judgments[query], k=k)
        metric_passed = row[ndcg_key] >= threshold_pass
        judge = normalize_judge_diagnostic(prediction.get("judge_diagnostic"))
        row["judge_diagnostic"] = judge
        row["trust_diagnostic"] = trust_diagnostic(metric_passed, judge)
        per_query.append(row)

    continuous_score = (
        sum(row[ndcg_key] for row in per_query) / len(per_query)
        if per_query
        else 0.0
    )
    recall_score = (
        sum(row[recall_key] for row in per_query) / len(per_query)
        if per_query
        else 0.0
    )
    false_pass_count = sum(
        1 for row in per_query if row["trust_diagnostic"] == "judge_pass_metric_fail"
    )
    false_fail_count = sum(
        1 for row in per_query if row["trust_diagnostic"] == "judge_fail_metric_pass"
    )

    status = "pass"
    if continuous_score < threshold_concern:
        status = "fail"
    elif continuous_score < threshold_pass:
        status = "concern"

    return {
        "adapter_id": "search_retrieval_v1",
        "metric_name": f"ndcg_at_{k}",
        "metric_display_name": f"NDCG@{k}",
        "continuous_score": round(continuous_score, 6),
        f"recall_at_{k}": round(recall_score, 6),
        "companion_metric_name": f"recall_at_{k}",
        "threshold_pass": threshold_pass,
        "threshold_concern": threshold_concern,
        "status": status,
        "query_count": len(per_query),
        "false_pass_count": false_pass_count,
        "false_fail_count": false_fail_count,
        "per_query": per_query,
        "evidence": [
            {
                "kind": "metric",
                "source": "domain_eval",
                "locator": row["query"],
                "metric": {
                    "name": f"ndcg_at_{k}",
                    "value": row[ndcg_key],
                    recall_key: row[recall_key],
                },
                "missing_relevant_doc_ids": row["missing_relevant_doc_ids"],
            }
            for row in per_query
        ],
    }


def write_report(result: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ndcg_key = result["metric_name"]
    recall_key = result["companion_metric_name"]
    recall_display = recall_key.replace("_at_", "@").replace("_", " ").title().replace(" ", "")
    lines = [
        "# Search Metric Report",
        "",
        f"Adapter: `{result['adapter_id']}`",
        f"Metric: {result['metric_display_name']}",
        f"Score: {result['continuous_score']}",
        f"{recall_display}: {result[recall_key]}",
        f"Status: {result['status']}",
        f"Queries: {result['query_count']}",
        f"False-pass diagnostics: {result['false_pass_count']}",
        f"False-fail diagnostics: {result['false_fail_count']}",
        "",
        "## Per-query Evidence",
        "",
    ]
    for row in result["per_query"]:
        lines.extend(
            [
                f"- `{row['query']}`: {result['metric_display_name']}={row[ndcg_key]}, "
                f"{recall_display}={row[recall_key]}, "
                f"trust={row['trust_diagnostic']}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score search_retrieval_v1 predictions with NDCG@5 and recall@5."
    )
    parser.add_argument("--gold", required=True, help="Gold/silver relevance JSONL.")
    parser.add_argument("--predictions", required=True, help="Prediction JSONL.")
    parser.add_argument("--output", required=True, help="Output JSON artifact.")
    parser.add_argument("--report", help="Optional markdown report path.")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--threshold-pass", type=float, default=0.65)
    parser.add_argument("--threshold-concern", type=float, default=0.50)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.k < 1:
        raise ValueError("--k must be >= 1")

    result = score_predictions(
        load_jsonl(Path(args.gold)),
        load_jsonl(Path(args.predictions)),
        k=args.k,
        threshold_pass=args.threshold_pass,
        threshold_concern=args.threshold_concern,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.report:
        write_report(result, Path(args.report))


if __name__ == "__main__":
    main()
