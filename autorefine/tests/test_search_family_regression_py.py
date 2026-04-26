"""Tests for search_family_regression library + CLI.

Mirrors the importlib pattern from test_eval_search_metric_py.py:7-14 so the
library and the hyphenated CLI script can both be loaded regardless of pytest
CWD.
"""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "autorefine" / "lib"
SCRIPTS_DIR = REPO_ROOT / "autorefine" / "scripts"

_lib_spec = importlib.util.spec_from_file_location(
    "search_family_regression",
    LIB_DIR / "search_family_regression.py",
)
_lib = importlib.util.module_from_spec(_lib_spec)
sys.modules["search_family_regression"] = _lib
_lib_spec.loader.exec_module(_lib)

_cli_spec = importlib.util.spec_from_file_location(
    "eval_search_family_regression_cli",
    SCRIPTS_DIR / "eval-search-family-regression.py",
)
_cli = importlib.util.module_from_spec(_cli_spec)
sys.modules["eval_search_family_regression_cli"] = _cli
_cli_spec.loader.exec_module(_cli)


# ---------------------------------------------------------------------------
# Fixture helpers — keep test bodies focused on behavior, not setup
# ---------------------------------------------------------------------------

def _gold_row(query: str, doc_id: str, grade: int, family_id: str | None = None) -> dict:
    metadata = {}
    if family_id is not None:
        metadata["query_family_id"] = family_id
    return {"query": query, "doc_id": doc_id, "grade": grade, "metadata": metadata}


def _prediction(query: str, doc_ids: list[str]) -> dict:
    return {"query": query, "doc_ids": doc_ids}


# ---------------------------------------------------------------------------
# Library tests
# ---------------------------------------------------------------------------

def test_blocks_family_ndcg_drop():
    """Single family with NDCG drop blocks the gate."""
    gold = [
        _gold_row("q1", "doc_a", 3, "fam_a"),
        _gold_row("q1", "doc_b", 2, "fam_a"),
    ]
    baseline = [_prediction("q1", ["doc_a", "doc_b"])]  # perfect ordering, NDCG=1.0
    candidate = [_prediction("q1", ["doc_b", "doc_a"])]  # misordered, NDCG~0.835

    result = _lib.compare_search_family_regression(gold, baseline, candidate)

    assert result["status"] == "block"
    assert result["regression_detected"] is True
    assert result["regressed_family_count"] == 1
    assert result["regressed_family_fraction"] == 1.0
    blocking = result["blocking_families"]
    assert len(blocking) == 1
    assert blocking[0]["query_family_id"] == "fam_a"
    assert "ndcg_drop" in blocking[0]["reasons"]
    assert blocking[0]["ndcg_delta"] < 0


def test_blocks_family_recall_drop():
    """NDCG-tolerant scenario where candidate misses a relevant doc still blocks on recall."""
    gold = [
        _gold_row("q1", "doc_a", 3, "fam_a"),
        _gold_row("q1", "doc_b", 2, "fam_a"),
    ]
    baseline = [_prediction("q1", ["doc_a", "doc_b"])]  # recall=1.0
    candidate = [_prediction("q1", ["doc_a", "doc_x"])]  # recall=0.5, but NDCG of top doc preserved

    result = _lib.compare_search_family_regression(gold, baseline, candidate)

    assert result["status"] == "block"
    blocking = result["blocking_families"]
    assert len(blocking) == 1
    assert "recall_drop" in blocking[0]["reasons"]
    assert blocking[0]["recall_delta"] < 0


def test_passes_when_all_family_deltas_non_negative():
    """No family regresses → status pass, regression_detected False.

    Tightened per codex review #4: assert exact family count and per-family
    deltas are non-negative, not just "at least one family present".
    """
    gold = [
        _gold_row("q1", "doc_a", 3, "fam_a"),
        _gold_row("q1", "doc_b", 2, "fam_a"),
        _gold_row("q2", "doc_c", 3, "fam_b"),  # second family to make count meaningful
    ]
    # Both baseline and candidate have the same perfect ordering
    baseline = [_prediction("q1", ["doc_a", "doc_b"]), _prediction("q2", ["doc_c"])]
    candidate = [_prediction("q1", ["doc_a", "doc_b"]), _prediction("q2", ["doc_c"])]

    result = _lib.compare_search_family_regression(gold, baseline, candidate)

    assert result["status"] == "pass"
    assert result["regression_detected"] is False
    assert result["regressed_family_count"] == 0
    assert result["regressed_family_fraction"] == 0.0
    assert result["blocking_families"] == []
    assert result["family_count"] == 2
    assert len(result["per_family"]) == 2
    for fam in result["per_family"]:
        assert fam["reasons"] == []
        assert fam["ndcg_delta"] >= 0
        assert fam["recall_delta"] >= 0


def test_query_family_id_grouping_uses_gold_metadata():
    """Two queries sharing query_family_id aggregate into ONE family."""
    gold = [
        _gold_row("q1", "doc_a", 3, "fam_shared"),
        _gold_row("q2", "doc_b", 3, "fam_shared"),
    ]
    baseline = [
        _prediction("q1", ["doc_a"]),
        _prediction("q2", ["doc_b"]),
    ]
    candidate = [
        _prediction("q1", ["doc_a"]),
        _prediction("q2", ["doc_b"]),
    ]

    result = _lib.compare_search_family_regression(gold, baseline, candidate)

    assert result["family_mode"] == "query_family_id"
    assert result["family_count"] == 1
    assert result["query_count"] == 2
    assert len(result["per_family"]) == 1


def test_conflicting_family_id_for_query_is_invalid():
    """Same query mapped to two different family_ids must short-circuit to invalid."""
    gold = [
        _gold_row("q1", "doc_a", 3, "fam_a"),
        _gold_row("q1", "doc_b", 2, "fam_b"),  # conflicting family_id
    ]
    baseline = [_prediction("q1", ["doc_a", "doc_b"])]
    candidate = [_prediction("q1", ["doc_a", "doc_b"])]

    result = _lib.compare_search_family_regression(gold, baseline, candidate)

    assert result["status"] == "invalid"
    assert result["per_family"] == []
    error_kinds = {err["kind"] for err in result["validation_errors"]}
    assert "inconsistent_query_family_id" in error_kinds


def test_missing_family_id_falls_back_to_query_family():
    """No metadata.query_family_id anywhere → fallback mode, gate still works."""
    gold = [
        _gold_row("q1", "doc_a", 3),  # no family_id
        _gold_row("q2", "doc_b", 3),
    ]
    baseline = [
        _prediction("q1", ["doc_a"]),
        _prediction("q2", ["doc_b"]),
    ]
    candidate = [
        _prediction("q1", ["doc_a"]),
        _prediction("q2", ["doc_b"]),
    ]

    result = _lib.compare_search_family_regression(gold, baseline, candidate)

    assert result["family_mode"] == "query_fallback"
    assert result["family_count"] == 2  # one family per query
    assert result["status"] == "pass"


def test_prediction_artifact_requires_exact_gold_query_coverage():
    """Mismatched/missing/extra/duplicate prediction queries → invalid."""
    gold = [
        _gold_row("q1", "doc_a", 3, "fam_a"),
        _gold_row("q2", "doc_b", 3, "fam_b"),
    ]

    # Case A: candidate missing q2
    res_a = _lib.compare_search_family_regression(
        gold,
        baseline_prediction_rows=[_prediction("q1", ["doc_a"]), _prediction("q2", ["doc_b"])],
        candidate_prediction_rows=[_prediction("q1", ["doc_a"])],
    )
    assert res_a["status"] == "invalid"
    assert res_a["alignment"]["status"] == "invalid"
    assert "q2" in res_a["alignment"]["missing_from_candidate"]

    # Case B: baseline has extra q3
    res_b = _lib.compare_search_family_regression(
        gold,
        baseline_prediction_rows=[
            _prediction("q1", ["doc_a"]),
            _prediction("q2", ["doc_b"]),
            _prediction("q3", ["doc_x"]),
        ],
        candidate_prediction_rows=[_prediction("q1", ["doc_a"]), _prediction("q2", ["doc_b"])],
    )
    assert res_b["status"] == "invalid"
    assert "q3" in res_b["alignment"]["extra_in_baseline"]

    # Case C: duplicate query in baseline
    res_c = _lib.compare_search_family_regression(
        gold,
        baseline_prediction_rows=[
            _prediction("q1", ["doc_a"]),
            _prediction("q1", ["doc_b"]),  # dup
            _prediction("q2", ["doc_b"]),
        ],
        candidate_prediction_rows=[_prediction("q1", ["doc_a"]), _prediction("q2", ["doc_b"])],
    )
    assert res_c["status"] == "invalid"
    error_kinds = {err["kind"] for err in res_c["validation_errors"]}
    assert "duplicate_query" in error_kinds


def test_invalid_gold_returns_structured_error():
    """Bad gold row (negative grade) returns structured error, not raw exception."""
    gold = [
        _gold_row("q1", "doc_a", 3, "fam_a"),
        {"query": "q2", "doc_id": "doc_b", "grade": -1, "metadata": {}},  # invalid grade
    ]
    baseline = [_prediction("q1", ["doc_a"]), _prediction("q2", ["doc_b"])]
    candidate = [_prediction("q1", ["doc_a"]), _prediction("q2", ["doc_b"])]

    result = _lib.compare_search_family_regression(gold, baseline, candidate)

    assert result["status"] == "invalid"
    error_kinds = {err["kind"] for err in result["validation_errors"]}
    assert "gold_validation" in error_kinds


# ---------------------------------------------------------------------------
# CLI tests — main([args]) returns int exit code (0/1/2)
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_cli_exit_codes(tmp_path):
    """CLI exits 0 for pass, 1 for block, 2 for invalid."""
    gold = [
        _gold_row("q1", "doc_a", 3, "fam_a"),
        _gold_row("q1", "doc_b", 2, "fam_a"),
    ]
    gold_path = tmp_path / "gold.jsonl"
    _write_jsonl(gold_path, gold)

    # PASS case
    base_pass = tmp_path / "base_pass.jsonl"
    cand_pass = tmp_path / "cand_pass.jsonl"
    _write_jsonl(base_pass, [_prediction("q1", ["doc_a", "doc_b"])])
    _write_jsonl(cand_pass, [_prediction("q1", ["doc_a", "doc_b"])])
    out_pass = tmp_path / "out_pass.json"
    code = _cli.main([
        "--gold", str(gold_path),
        "--baseline-predictions", str(base_pass),
        "--candidate-predictions", str(cand_pass),
        "--output", str(out_pass),
    ])
    assert code == 0

    # BLOCK case (NDCG drop)
    base_block = tmp_path / "base_block.jsonl"
    cand_block = tmp_path / "cand_block.jsonl"
    _write_jsonl(base_block, [_prediction("q1", ["doc_a", "doc_b"])])
    _write_jsonl(cand_block, [_prediction("q1", ["doc_b", "doc_a"])])
    out_block = tmp_path / "out_block.json"
    code = _cli.main([
        "--gold", str(gold_path),
        "--baseline-predictions", str(base_block),
        "--candidate-predictions", str(cand_block),
        "--output", str(out_block),
    ])
    assert code == 1

    # INVALID case (candidate has missing coverage)
    base_inv = tmp_path / "base_inv.jsonl"
    cand_inv = tmp_path / "cand_inv.jsonl"
    _write_jsonl(base_inv, [_prediction("q1", ["doc_a", "doc_b"])])
    _write_jsonl(cand_inv, [_prediction("q2", ["doc_a"])])  # wrong query, mismatch
    out_inv = tmp_path / "out_inv.json"
    code = _cli.main([
        "--gold", str(gold_path),
        "--baseline-predictions", str(base_inv),
        "--candidate-predictions", str(cand_inv),
        "--output", str(out_inv),
    ])
    assert code == 2


def test_cli_writes_json_and_markdown_report(tmp_path):
    """CLI writes both --output JSON and --report markdown."""
    gold = [
        _gold_row("q1", "doc_a", 3, "fam_a"),
        _gold_row("q1", "doc_b", 2, "fam_a"),
    ]
    gold_path = tmp_path / "gold.jsonl"
    _write_jsonl(gold_path, gold)

    base = tmp_path / "base.jsonl"
    cand = tmp_path / "cand.jsonl"
    _write_jsonl(base, [_prediction("q1", ["doc_a", "doc_b"])])
    _write_jsonl(cand, [_prediction("q1", ["doc_a", "doc_b"])])

    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    code = _cli.main([
        "--gold", str(gold_path),
        "--baseline-predictions", str(base),
        "--candidate-predictions", str(cand),
        "--output", str(out_json),
        "--report", str(out_md),
    ])

    assert code == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["adapter_id"] == "search_retrieval_v1"
    assert payload["schema_version"] == "search_family_regression_v1"

    report = out_md.read_text(encoding="utf-8")
    # Sanity: report mentions the adapter and the decision
    assert "search_retrieval_v1" in report
    assert "pass" in report.lower()


# ---------------------------------------------------------------------------
# Review-feedback fix coverage (P1 + P2)
# ---------------------------------------------------------------------------

def test_library_rejects_nan_tolerance():
    """NaN tolerance silently disables drop checks — must hard-fail (P1, codex)."""
    import math
    gold = [_gold_row("q1", "doc_a", 3, "fam_a")]
    baseline = [_prediction("q1", ["doc_a"])]
    candidate = [_prediction("q1", ["doc_a"])]

    import pytest
    with pytest.raises(ValueError, match="finite"):
        _lib.compare_search_family_regression(
            gold, baseline, candidate, ndcg_drop_tolerance=math.nan
        )
    with pytest.raises(ValueError, match="finite"):
        _lib.compare_search_family_regression(
            gold, baseline, candidate, recall_drop_tolerance=math.inf
        )


def test_cli_returns_exit_2_on_missing_input_file(tmp_path):
    """Missing input path must exit 2 cleanly, not raise FileNotFoundError (P1, architect+codex)."""
    gold = [_gold_row("q1", "doc_a", 3, "fam_a")]
    gold_path = tmp_path / "gold.jsonl"
    _write_jsonl(gold_path, gold)

    base_path = tmp_path / "base.jsonl"
    _write_jsonl(base_path, [_prediction("q1", ["doc_a"])])

    missing = tmp_path / "does_not_exist.jsonl"
    out = tmp_path / "out.json"

    code = _cli.main([
        "--gold", str(gold_path),
        "--baseline-predictions", str(base_path),
        "--candidate-predictions", str(missing),
        "--output", str(out),
    ])
    assert code == 2


def test_cli_rejects_nan_tolerance(tmp_path):
    """CLI rejects non-finite tolerances at the boundary, exit 2 (P1, codex)."""
    gold = [_gold_row("q1", "doc_a", 3, "fam_a")]
    gold_path = tmp_path / "gold.jsonl"
    _write_jsonl(gold_path, gold)

    base = tmp_path / "base.jsonl"
    cand = tmp_path / "cand.jsonl"
    _write_jsonl(base, [_prediction("q1", ["doc_a"])])
    _write_jsonl(cand, [_prediction("q1", ["doc_a"])])
    out = tmp_path / "out.json"

    code = _cli.main([
        "--gold", str(gold_path),
        "--baseline-predictions", str(base),
        "--candidate-predictions", str(cand),
        "--output", str(out),
        "--ndcg-drop-tolerance", "nan",
    ])
    assert code == 2


def test_cli_rejects_invalid_k(tmp_path):
    """CLI rejects --k 0 with exit 2 (P3 / Q2 from code-review)."""
    gold = [_gold_row("q1", "doc_a", 3, "fam_a")]
    gold_path = tmp_path / "gold.jsonl"
    _write_jsonl(gold_path, gold)

    base = tmp_path / "base.jsonl"
    cand = tmp_path / "cand.jsonl"
    _write_jsonl(base, [_prediction("q1", ["doc_a"])])
    _write_jsonl(cand, [_prediction("q1", ["doc_a"])])
    out = tmp_path / "out.json"

    code = _cli.main([
        "--gold", str(gold_path),
        "--baseline-predictions", str(base),
        "--candidate-predictions", str(cand),
        "--output", str(out),
        "--k", "0",
    ])
    assert code == 2


def test_empty_doc_ids_is_valid_empty_result():
    """Explicit doc_ids: [] is valid and represents an empty retrieval (P2, code-reviewer).

    Codifies the validator's "empty result allowed" docstring claim so it can't
    be accidentally broken. Empty result scores 0.0 NDCG/recall — if baseline
    had a hit, this is a regression.
    """
    gold = [_gold_row("q1", "doc_a", 3, "fam_a")]
    baseline = [_prediction("q1", ["doc_a"])]   # NDCG=1.0, recall=1.0
    candidate = [_prediction("q1", [])]          # empty result, NDCG=0.0, recall=0.0

    result = _lib.compare_search_family_regression(gold, baseline, candidate)

    # Validation passed (no shape errors), gate runs and detects regression
    assert result["status"] == "block"
    assert result["per_family"][0]["candidate_ndcg_at_5"] == 0.0
    assert "ndcg_drop" in result["per_family"][0]["reasons"]


def test_results_format_predictions_are_accepted():
    """Predictions in {results: [{doc_id}]} form must work end-to-end (P2, code-reviewer)."""
    gold = [_gold_row("q1", "doc_a", 3, "fam_a")]
    baseline = [{"query": "q1", "results": [{"doc_id": "doc_a"}]}]
    candidate = [{"query": "q1", "results": [{"doc_id": "doc_a"}]}]

    result = _lib.compare_search_family_regression(gold, baseline, candidate)

    assert result["status"] == "pass"
    assert result["per_family"][0]["candidate_ndcg_at_5"] == 1.0
