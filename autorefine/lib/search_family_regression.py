"""Search family regression gate (v1).

Pure-function library: takes gold + baseline + candidate prediction rows in
memory and returns a regression decision. No filesystem I/O, no state mutation.

Design plan: ../../design_plan.md (rev 6 + 5 review fixes).

Reuses the existing search metric scorer:
  autorefine/scripts/eval-search-metric.py:128-205  score_predictions
  autorefine/scripts/eval-search-metric.py:37-50   relevance_by_query (gold validation)

Loaded via importlib because the script is hyphenated.
"""

import importlib.util
import math
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Reuse score_predictions + relevance_by_query from the existing metric script.
# Lazy-loaded so importing this library does not crash when the sibling script
# is missing — the call sites raise a clear ImportError on first use instead.
# Lazy load also lets the CLI consume the same module reference (no duplicate
# exec_module of eval-search-metric.py).
# ---------------------------------------------------------------------------

_EVAL_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "eval-search-metric.py"
_eval_mod = None  # populated by _get_eval_mod() on first use


def _get_eval_mod():
    """Return the lazily-loaded eval-search-metric module.

    Raises ImportError with a precise message if the sibling script is missing.
    """
    global _eval_mod
    if _eval_mod is not None:
        return _eval_mod
    if not _EVAL_SCRIPT.exists():
        raise ImportError(
            f"search_family_regression requires sibling script {_EVAL_SCRIPT}; not found"
        )
    spec = importlib.util.spec_from_file_location(
        "eval_search_metric_internal", _EVAL_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _eval_mod = module
    return _eval_mod


SCHEMA_VERSION = "search_family_regression_v1"
ADAPTER_ID = "search_retrieval_v1"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def query_family_map(
    gold_rows: list[dict],
) -> tuple[dict[str, str], str, list[dict]]:
    """Build {query -> family_id} from gold rows.

    Returns (mapping, family_mode, errors).

    family_mode:
      - "query_family_id"          every gold query has metadata.query_family_id
      - "mixed_with_query_fallback" some have it, some don't (fallback applied)
      - "query_fallback"           none have it (every family is "query:<query>")

    A query that appears in multiple gold rows with conflicting family_ids
    yields an "inconsistent_query_family_id" error (the caller decides what to
    do with errors; this function still returns a usable map).
    """
    seen_family_ids: dict[str, set[str]] = {}
    all_queries: set[str] = set()

    for row in gold_rows:
        if not isinstance(row, dict):
            continue
        query = row.get("query")
        if not isinstance(query, str) or not query.strip():
            continue
        all_queries.add(query)
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        family_id = metadata.get("query_family_id")
        if isinstance(family_id, str) and family_id.strip():
            seen_family_ids.setdefault(query, set()).add(family_id)

    errors: list[dict] = []
    for query, ids in seen_family_ids.items():
        if len(ids) > 1:
            errors.append(
                {
                    "kind": "inconsistent_query_family_id",
                    "query": query,
                    "ids": sorted(ids),
                }
            )

    mapping: dict[str, str] = {}
    queries_with_family_id: set[str] = set()
    for query in all_queries:
        ids = seen_family_ids.get(query)
        if ids:
            # On conflict, pick the lexicographically first ID for determinism.
            # Errors list still flags the conflict; caller blocks via "invalid".
            mapping[query] = sorted(ids)[0]
            queries_with_family_id.add(query)
        else:
            mapping[query] = f"query:{query}"

    if not all_queries or not queries_with_family_id:
        family_mode = "query_fallback"
    elif queries_with_family_id == all_queries:
        family_mode = "query_family_id"
    else:
        family_mode = "mixed_with_query_fallback"

    return mapping, family_mode, errors


def validate_prediction_artifact(
    prediction_rows: list[dict],
    expected_queries: set[str],
    *,
    artifact_label: str,
) -> list[dict]:
    """Row-level validation for a prediction artifact.

    Returns a list of structured errors (empty list = OK). Caller decides how
    to surface them.

    Rules (per design plan §Canonical Prediction Artifact Contract):
      - query must be a non-empty string
      - no duplicate query keys
      - has either doc_ids (list of non-empty strings) or results (list of
        {doc_id} objects with non-empty doc_id)
      - empty result is allowed via doc_ids: []
      - missing/extra coverage relative to expected_queries

    Coverage errors are also reflected in the alignment field of the final
    result. Validator emits both for explicitness.
    """
    errors: list[dict] = []
    seen_queries: set[str] = set()

    for idx, row in enumerate(prediction_rows):
        if not isinstance(row, dict):
            errors.append(
                {"kind": "row_not_dict", "artifact": artifact_label, "row_index": idx}
            )
            continue

        query = row.get("query")
        if not isinstance(query, str) or not query.strip():
            errors.append(
                {"kind": "missing_query", "artifact": artifact_label, "row_index": idx}
            )
            continue

        if query in seen_queries:
            errors.append(
                {"kind": "duplicate_query", "artifact": artifact_label, "query": query}
            )
            continue
        seen_queries.add(query)

        has_doc_ids = "doc_ids" in row
        has_results = "results" in row
        if not has_doc_ids and not has_results:
            errors.append(
                {
                    "kind": "invalid_doc_ids_shape",
                    "artifact": artifact_label,
                    "query": query,
                    "details": "missing both doc_ids and results",
                }
            )
            continue

        if has_doc_ids:
            doc_ids = row.get("doc_ids")
            if not isinstance(doc_ids, list) or not all(
                isinstance(d, str) and d.strip() for d in doc_ids
            ):
                errors.append(
                    {
                        "kind": "invalid_doc_ids_shape",
                        "artifact": artifact_label,
                        "query": query,
                        "details": "doc_ids must be list of non-empty strings",
                    }
                )
                continue

        if has_results:
            results = row.get("results")
            if not isinstance(results, list) or not all(
                isinstance(r, dict)
                and isinstance(r.get("doc_id"), str)
                and r["doc_id"].strip()
                for r in results
            ):
                errors.append(
                    {
                        "kind": "invalid_doc_ids_shape",
                        "artifact": artifact_label,
                        "query": query,
                        "details": "results must be list of {doc_id: non-empty string}",
                    }
                )
                continue

    # Coverage check (only for rows that survived structural validation)
    missing = expected_queries - seen_queries
    extra = seen_queries - expected_queries
    for query in sorted(missing):
        errors.append(
            {"kind": "missing_query_coverage", "artifact": artifact_label, "query": query}
        )
    for query in sorted(extra):
        errors.append(
            {"kind": "extra_query", "artifact": artifact_label, "query": query}
        )

    return errors


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compare_search_family_regression(
    gold_rows: list[dict],
    baseline_prediction_rows: list[dict],
    candidate_prediction_rows: list[dict],
    *,
    k: int = 5,
    ndcg_drop_tolerance: float = 0.0,
    recall_drop_tolerance: float = 0.0,
) -> dict:
    """Compare candidate vs baseline predictions per query family.

    Decision precedence (design plan §Decision Precedence):
      1. Gold validation fails              → status="invalid", exit 2
      2. Prediction validation fails        → status="invalid", exit 2
      3. Alignment fails                    → status="invalid", exit 2
      4. Any family meets blocking condition → status="block",   exit 1
      5. Otherwise                          → status="pass",    exit 0
    """
    if not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    # Reject non-finite tolerances. NaN silently disables every drop check
    # (NaN comparisons return False), and inf disables blocking too plus
    # produces non-standard JSON. Either would let real regressions pass.
    for label, tol in (
        ("ndcg_drop_tolerance", ndcg_drop_tolerance),
        ("recall_drop_tolerance", recall_drop_tolerance),
    ):
        if not isinstance(tol, (int, float)) or not math.isfinite(tol):
            raise ValueError(f"{label} must be a finite number, got {tol!r}")

    ndcg_key = f"ndcg_at_{k}"
    recall_key = f"recall_at_{k}"

    result = {
        "schema_version": SCHEMA_VERSION,
        "adapter_id": ADAPTER_ID,
        "status": "pass",
        "regression_detected": False,
        "metric_names": [ndcg_key, recall_key],
        "k": k,
        "thresholds": {
            "ndcg_drop_tolerance": ndcg_drop_tolerance,
            "recall_drop_tolerance": recall_drop_tolerance,
        },
        "family_mode": "query_fallback",
        "query_count": 0,
        "family_count": 0,
        "regressed_family_count": 0,
        "regressed_family_fraction": 0.0,
        "alignment": {
            "status": "aligned",
            "missing_from_baseline": [],
            "missing_from_candidate": [],
            "extra_in_baseline": [],
            "extra_in_candidate": [],
        },
        "blocking_families": [],
        "per_family": [],
        "validation_errors": [],
    }

    # Step 1: Gold validation. relevance_by_query raises ValueError on bad rows.
    # Also build the family map (which checks for inconsistent family_ids).
    family_errors: list[dict] = []
    try:
        _get_eval_mod().relevance_by_query(gold_rows)
    except ValueError as exc:
        result["status"] = "invalid"
        result["validation_errors"].append(
            {"kind": "gold_validation", "message": str(exc)}
        )
        return result

    family_map, family_mode, family_errors = query_family_map(gold_rows)
    result["family_mode"] = family_mode
    if family_errors:
        result["status"] = "invalid"
        result["validation_errors"].extend(family_errors)
        return result

    gold_queries: set[str] = set(family_map.keys())
    result["query_count"] = len(gold_queries)

    # Step 2: Prediction validation
    base_errors = validate_prediction_artifact(
        baseline_prediction_rows, gold_queries, artifact_label="baseline"
    )
    cand_errors = validate_prediction_artifact(
        candidate_prediction_rows, gold_queries, artifact_label="candidate"
    )

    # Step 3: Alignment (computed from query sets, denormalized view of coverage)
    base_queries = _query_set(baseline_prediction_rows)
    cand_queries = _query_set(candidate_prediction_rows)
    alignment = {
        "status": "aligned",
        "missing_from_baseline": sorted(gold_queries - base_queries),
        "missing_from_candidate": sorted(gold_queries - cand_queries),
        "extra_in_baseline": sorted(base_queries - gold_queries),
        "extra_in_candidate": sorted(cand_queries - gold_queries),
    }
    if any(
        alignment[field]
        for field in (
            "missing_from_baseline",
            "missing_from_candidate",
            "extra_in_baseline",
            "extra_in_candidate",
        )
    ):
        alignment["status"] = "invalid"
    result["alignment"] = alignment

    if base_errors or cand_errors or alignment["status"] == "invalid":
        result["status"] = "invalid"
        result["validation_errors"].extend(base_errors + cand_errors)
        return result

    # Step 4: Score baseline + candidate via the existing metric runner
    try:
        base_eval = _get_eval_mod().score_predictions(
            gold_rows, baseline_prediction_rows, k=k
        )
        cand_eval = _get_eval_mod().score_predictions(
            gold_rows, candidate_prediction_rows, k=k
        )
    except ValueError as exc:
        # Defensive: relevance_by_query already validated gold once, but if
        # score_predictions raises for any other reason, surface it as invalid.
        result["status"] = "invalid"
        result["validation_errors"].append(
            {"kind": "scoring_error", "message": str(exc)}
        )
        return result

    base_per_q = {row["query"]: row for row in base_eval["per_query"]}
    cand_per_q = {row["query"]: row for row in cand_eval["per_query"]}

    # Step 5+6: Group queries by family, compute deltas
    family_to_queries: dict[str, list[str]] = {}
    for query, family_id in family_map.items():
        family_to_queries.setdefault(family_id, []).append(query)

    per_family: list[dict] = []
    blocking: list[dict] = []
    for family_id in sorted(family_to_queries):
        queries = sorted(family_to_queries[family_id])
        base_ndcgs = [base_per_q[q][ndcg_key] for q in queries]
        cand_ndcgs = [cand_per_q[q][ndcg_key] for q in queries]
        base_recalls = [base_per_q[q][recall_key] for q in queries]
        cand_recalls = [cand_per_q[q][recall_key] for q in queries]

        baseline_ndcg = _mean(base_ndcgs)
        candidate_ndcg = _mean(cand_ndcgs)
        baseline_recall = _mean(base_recalls)
        candidate_recall = _mean(cand_recalls)

        ndcg_delta = candidate_ndcg - baseline_ndcg
        recall_delta = candidate_recall - baseline_recall
        # worst_query_*_delta = min over the per-query (candidate - baseline)
        # deltas, NOT the minimum candidate score. Diagnostic field only;
        # blocking decision uses mean family deltas (above), not these.
        worst_ndcg_delta = min(c - b for c, b in zip(cand_ndcgs, base_ndcgs))
        worst_recall_delta = min(c - b for c, b in zip(cand_recalls, base_recalls))

        reasons: list[str] = []
        # Block condition (design plan §Scoring Semantics step 7):
        # candidate + tolerance < baseline (i.e., candidate is worse by more than tolerance)
        if candidate_ndcg + ndcg_drop_tolerance < baseline_ndcg:
            reasons.append("ndcg_drop")
        if candidate_recall + recall_drop_tolerance < baseline_recall:
            reasons.append("recall_drop")

        record = {
            "query_family_id": family_id,
            "reasons": reasons,
            f"baseline_{ndcg_key}": _round(baseline_ndcg),
            f"candidate_{ndcg_key}": _round(candidate_ndcg),
            "ndcg_delta": _round(ndcg_delta),
            f"baseline_{recall_key}": _round(baseline_recall),
            f"candidate_{recall_key}": _round(candidate_recall),
            "recall_delta": _round(recall_delta),
            "worst_query_ndcg_delta": _round(worst_ndcg_delta),
            "worst_query_recall_delta": _round(worst_recall_delta),
            "queries": queries,
        }
        per_family.append(record)
        if reasons:
            blocking.append(record)

    result["family_count"] = len(per_family)
    result["regressed_family_count"] = len(blocking)
    result["regressed_family_fraction"] = (
        _round(len(blocking) / len(per_family)) if per_family else 0.0
    )
    result["per_family"] = per_family
    result["blocking_families"] = blocking

    if blocking:
        result["status"] = "block"
        result["regression_detected"] = True
    else:
        result["status"] = "pass"

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _query_set(prediction_rows: list[dict]) -> set[str]:
    """Extract the set of query strings from prediction rows, ignoring malformed."""
    queries: set[str] = set()
    for row in prediction_rows:
        if isinstance(row, dict):
            query = row.get("query")
            if isinstance(query, str) and query.strip():
                queries.add(query)
    return queries


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _round(value: float, places: int = 6) -> float:
    return round(float(value), places)
