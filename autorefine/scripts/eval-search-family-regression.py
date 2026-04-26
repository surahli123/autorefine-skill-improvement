#!/usr/bin/env python3
"""Search family regression gate — CLI wrapper.

Reads gold + baseline + candidate prediction JSONL files, calls the library,
writes a JSON result + optional markdown report, exits with a stable code:

  0 — valid comparison, no blocking family regression
  1 — valid comparison, one or more blocking family regressions
  2 — validation, alignment, JSONL, or usage error

Library: autorefine/lib/search_family_regression.py
Design plan: ../../design_plan.md
"""

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path


# Reuse the library via importlib (file lives at autorefine/lib/, sibling tree)
_LIB_PATH = (
    Path(__file__).resolve().parent.parent / "lib" / "search_family_regression.py"
)
_lib_spec = importlib.util.spec_from_file_location(
    "search_family_regression_for_cli", _LIB_PATH
)
_lib = importlib.util.module_from_spec(_lib_spec)
_lib_spec.loader.exec_module(_lib)


# Reuse the library's already-loaded eval-search-metric module via its lazy
# loader. Avoids a second exec_module of the same file (architect-review fix).
def _load_jsonl(path):
    return _lib._get_eval_mod().load_jsonl(path)


EXIT_PASS = 0
EXIT_BLOCK = 1
EXIT_INVALID = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Per-query-family regression gate for search_retrieval_v1: compare "
            "candidate vs baseline predictions and detect family-level drops."
        )
    )
    parser.add_argument("--gold", required=True, help="Gold/silver relevance JSONL.")
    parser.add_argument(
        "--baseline-predictions",
        required=True,
        help="Baseline (prior kept experiment) prediction JSONL.",
    )
    parser.add_argument(
        "--candidate-predictions",
        required=True,
        help="Candidate (current experiment) prediction JSONL.",
    )
    parser.add_argument(
        "--output", required=True, help="Output JSON artifact path."
    )
    parser.add_argument("--report", help="Optional markdown report path.")
    parser.add_argument("--k", type=int, default=5, help="Top-k cutoff (default 5).")
    parser.add_argument(
        "--ndcg-drop-tolerance",
        type=float,
        default=0.0,
        help="Allow candidate NDCG to drop by at most this much per family (default 0.0).",
    )
    parser.add_argument(
        "--recall-drop-tolerance",
        type=float,
        default=0.0,
        help="Allow candidate recall to drop by at most this much per family (default 0.0).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.k < 1:
        print("--k must be >= 1", file=sys.stderr)
        return EXIT_INVALID

    # Reject non-finite tolerances at the CLI boundary too (the library would
    # also raise, but the CLI promises a clean exit 2 instead of a traceback).
    for label, tol in (
        ("--ndcg-drop-tolerance", args.ndcg_drop_tolerance),
        ("--recall-drop-tolerance", args.recall_drop_tolerance),
    ):
        if not math.isfinite(tol):
            print(f"{label} must be a finite number, got {tol}", file=sys.stderr)
            return EXIT_INVALID

    # Load JSONL inputs.
    # - load_jsonl raises ValueError with path:line on malformed JSON
    # - path.open() raises FileNotFoundError/IsADirectoryError/PermissionError
    # All are tool/input errors → exit 2 with a clean stderr message.
    try:
        gold_rows = _load_jsonl(Path(args.gold))
        baseline_rows = _load_jsonl(Path(args.baseline_predictions))
        candidate_rows = _load_jsonl(Path(args.candidate_predictions))
    except (ValueError, FileNotFoundError, IsADirectoryError, PermissionError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID

    result = _lib.compare_search_family_regression(
        gold_rows,
        baseline_rows,
        candidate_rows,
        k=args.k,
        ndcg_drop_tolerance=args.ndcg_drop_tolerance,
        recall_drop_tolerance=args.recall_drop_tolerance,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_render_report(result), encoding="utf-8")

    status = result["status"]
    if status == "pass":
        return EXIT_PASS
    if status == "block":
        return EXIT_BLOCK
    return EXIT_INVALID


def _render_report(result: dict) -> str:
    """Compact markdown report for human inspection."""
    lines = [
        "# Search Family Regression Report",
        "",
        f"Adapter: `{result['adapter_id']}`",
        f"Schema: `{result['schema_version']}`",
        f"Status: **{result['status']}**",
        f"Regression detected: {result['regression_detected']}",
        f"k: {result['k']}",
        f"Family mode: `{result['family_mode']}`",
        f"Queries: {result['query_count']}",
        f"Families: {result['family_count']}",
        f"Regressed families: {result['regressed_family_count']} "
        f"({result['regressed_family_fraction'] * 100:.1f}%)",
        "",
        "## Thresholds",
        "",
        f"- ndcg_drop_tolerance: {result['thresholds']['ndcg_drop_tolerance']}",
        f"- recall_drop_tolerance: {result['thresholds']['recall_drop_tolerance']}",
        "",
        "## Alignment",
        "",
        f"Status: `{result['alignment']['status']}`",
    ]
    for field in (
        "missing_from_baseline",
        "missing_from_candidate",
        "extra_in_baseline",
        "extra_in_candidate",
    ):
        values = result["alignment"][field]
        if values:
            lines.append(f"- {field}: {values}")
    lines.append("")

    if result["validation_errors"]:
        lines.append("## Validation Errors")
        lines.append("")
        for err in result["validation_errors"]:
            lines.append(f"- {err}")
        lines.append("")

    if result["blocking_families"]:
        lines.append("## Blocking Families")
        lines.append("")
        for fam in result["blocking_families"]:
            lines.append(
                f"- `{fam['query_family_id']}`: reasons={fam['reasons']}, "
                f"ndcg_delta={fam['ndcg_delta']}, recall_delta={fam['recall_delta']}, "
                f"queries={fam['queries']}"
            )
        lines.append("")

    if result["per_family"]:
        lines.append("## Per-Family Detail")
        lines.append("")
        for fam in result["per_family"]:
            lines.append(
                f"- `{fam['query_family_id']}`: ndcg_delta={fam['ndcg_delta']}, "
                f"recall_delta={fam['recall_delta']}, "
                f"worst_q_ndcg_delta={fam['worst_query_ndcg_delta']}, "
                f"worst_q_recall_delta={fam['worst_query_recall_delta']}"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
