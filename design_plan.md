# Design Plan: Search Family Regression Gate

## Status / Scope / Out Of Scope

**Status:** Buildable implementation plan for a small deterministic regression gate.

**Scope:** Add one importable library module, one thin CLI wrapper, focused tests, and one Phase 7 documentation note. Target size: ~150-300 production LOC plus tests.

**In scope:**
- Deterministic paired comparison of baseline vs candidate `search_retrieval_v1` predictions.
- Per-query-family regression detection using existing NDCG@k / recall@k scoring.
- Canonical prediction artifact validation.
- Agent-friendly CLI exit codes and JSON output.
- Optional markdown report for humans.

**Out of scope:**
- No Python Phase 7 orchestrator.
- No integration with `run-campaign.py`; that script is plan/handoff-oriented before phase execution (`autorefine/scripts/run-campaign.py:3-8`).
- No integration with `prepare-gulf-gate-pack.py`; it is preauthorization and does not execute Phase 7 (`autorefine/scripts/prepare-gulf-gate-pack.py:3-7`).
- No `mutation_stage_split_access_policy` enforcer. The policy is documented and persisted as a Phase 7 read gate (`autorefine/references.md:443-483`), but this plan only consumes already-supplied gold/prediction rows.
- No judge-diagnostic or explanation-quality gate. `judge_diagnostic` is only normalized when present in prediction rows (`autorefine/scripts/eval-search-metric.py:107-151`); the regression gate ignores it.

## Context

AutoRefine already has a deterministic search metric runner. It accepts gold rows shaped as `{query, doc_id, grade, metadata}` and prediction rows shaped as either `{query, doc_ids:[...]}` or `{query, results:[{doc_id:...}]}` (`autorefine/scripts/eval-search-metric.py:5-10`). `score_predictions(gold_rows, prediction_rows, k=5, ...)` returns aggregate NDCG/recall plus `per_query` rows (`autorefine/scripts/eval-search-metric.py:128-205`).

The missing primitive is not another judge framework. The current gap is paired comparison: aggregates can improve while one query family regresses. Phase 7 already has a regression-check contract before user presentation (`autorefine/references/gulf3-generalization.md:165`; schema detail at `autorefine/references.md:4283-4301`). This plan adds a deterministic tool that any Phase 7 agent or future runner can call.

This uses the existing adapter paradigm:
- Domain metrics are binary gate components with continuous scores preserved as evidence (`autorefine/references/gulf3-generalization.md:132-140`).
- For `search_retrieval_v1`, retrieval quality is primary and explanation/rationale quality is secondary (`autorefine/references/gulf3-generalization.md:144-147`).
- Silver builder already emits `metadata.query_family_id` on positive and hard-negative rows (`autorefine/scripts/build-search-silver.py:210-267`).

## Goal

Given one gold/silver relevance set, one baseline prediction artifact, and one candidate prediction artifact, determine whether the candidate regresses any query family versus the baseline.

The gate must answer:

```text
Did candidate NDCG@k or recall@k drop for any query family beyond configured tolerance?
```

Default tolerance: `0.0` for both metrics. Any negative family delta blocks.

## Design

### Files

Add:

```text
autorefine/lib/search_family_regression.py
autorefine/scripts/eval-search-family-regression.py
autorefine/tests/test_search_family_regression_py.py
```

Do not refactor `eval-search-metric.py` in v1. The library loads and reuses its existing `score_predictions` function. Existing tests already use `importlib.util.spec_from_file_location` to import hyphenated scripts (`autorefine/tests/test_eval_search_metric_py.py:7-14`), so this is an established local pattern.

### Library API

```python
def compare_search_family_regression(
    gold_rows: list[dict],
    baseline_prediction_rows: list[dict],
    candidate_prediction_rows: list[dict],
    *,
    k: int = 5,
    ndcg_drop_tolerance: float = 0.0,
    recall_drop_tolerance: float = 0.0,
) -> dict:
    ...
```

Note: `score_predictions` accepts `threshold_pass` and `threshold_concern`, but they only affect its own absolute pass/concern/fail status field, which the regression gate ignores. They are intentionally NOT exposed on this API to avoid implying they affect the gate decision.

Validation helpers:

```python
def validate_prediction_artifact(
    prediction_rows: list[dict],
    expected_queries: set[str],
    *,
    artifact_label: str,
) -> list[dict]:
    ...
```

```python
def query_family_map(gold_rows: list[dict]) -> tuple[dict[str, str], str, list[dict]]:
    ...
```

### Canonical Prediction Artifact Contract

A prediction artifact is JSONL. Each non-empty line is one object.

Accepted row forms, matching the existing metric runner (`autorefine/scripts/eval-search-metric.py:8-10`):

```json
{"query":"...", "doc_ids":["doc_a","doc_b"]}
```

or:

```json
{"query":"...", "results":[{"doc_id":"doc_a"},{"doc_id":"doc_b"}]}
```

Rules:
- `query` must be a non-empty string.
- Each gold query must appear exactly once in baseline predictions and exactly once in candidate predictions.
- Extra prediction queries are validation errors.
- Missing prediction queries are validation errors. A real empty retrieval result must be represented explicitly as `"doc_ids":[]`.
- Duplicate prediction rows for the same query are validation errors.
- `judge_diagnostic` is ignored by this gate.

This closes the brittle-agent problem: a wrong or partial file fails validation with exit code `2` instead of silently becoming a regression or false pass.

### Family Mapping

For each gold row:
- Read `metadata.query_family_id` when present and non-empty.
- All rows with the same `query` must map to the same non-empty family ID.
- If one query has conflicting family IDs, return validation error `inconsistent_query_family_id`.
- If a query has no family ID on any gold row, fallback family ID is `query:<query>`.

Output `family_mode` reflects which mapping path was taken across the gold set:

| Value | Fires when |
|---|---|
| `"query_family_id"` | Every gold query has a non-empty `metadata.query_family_id` on at least one row |
| `"mixed_with_query_fallback"` | Some queries have `metadata.query_family_id`, others don't (fallback applied to the gaps) |
| `"query_fallback"` | No gold query has any `metadata.query_family_id` (every family is `query:<query>`) |

This makes production gold sets without family metadata usable while preserving the stronger grouping emitted by `build-search-silver.py` (`autorefine/scripts/build-search-silver.py:223-231`).

### Alignment Semantics

The gate aligns by `query`, not `input_id`.

Reason: the existing search metric runner keys judgments and predictions by query (`autorefine/scripts/eval-search-metric.py:37-50`, `autorefine/scripts/eval-search-metric.py:135-147`), and silver rows carry query/doc relevance with family metadata (`autorefine/scripts/build-search-silver.py:232-266`). `input_id` alignment remains correct for generic version comparison (`autorefine/references.md:622-685`), but this adapter's scoring primitive is query identity.

Hard stop:
- If baseline/candidate prediction query sets do not exactly match the gold query set, status is `invalid`.
- Do not emit normal `per_family` deltas on invalid alignment.

### Scoring Semantics

Implementation steps:
1. Validate gold rows. `relevance_by_query` (`autorefine/scripts/eval-search-metric.py:37-50`) raises `ValueError` mid-loop on bad rows. The library wraps this call and converts the `ValueError` into a single structured `validation_errors[]` entry of `kind: "gold_validation"` plus the original `path:line` message. The library still returns a result dict (with `status: "invalid"`) rather than re-raising. The CLI also prints the original message to stderr (matching existing `load_jsonl` behavior at `eval-search-metric.py:23-34`) before exiting `2`.
2. Validate baseline and candidate prediction artifacts against the canonical contract.
3. Build `query -> family_id`.
4. Call existing `score_predictions(...)` for baseline and candidate.
5. Index each result's `per_query[]` by `query`.
6. For each family:
   - collect member queries
   - compute mean baseline NDCG@k
   - compute mean candidate NDCG@k
   - compute mean baseline recall@k
   - compute mean candidate recall@k
   - compute deltas
   - compute worst per-query NDCG delta and worst per-query recall delta
7. Block if any family has:
   - `candidate_ndcg + ndcg_drop_tolerance < baseline_ndcg`, or
   - `candidate_recall + recall_drop_tolerance < baseline_recall`

Recall is a real gate by default because the user problem is aggregate NDCG/recall masking family regressions.

### Decision Precedence

The library evaluates these in order; the first matching condition determines `status` and exit code:

1. Gold validation fails (step 1) → `status: "invalid"`, exit `2`.
2. Prediction validation fails (step 2 — either baseline or candidate has any error) → `status: "invalid"`, exit `2`.
3. Alignment fails (prediction query sets do not exactly equal gold query set) → `status: "invalid"`, exit `2`.
4. Any family meets a blocking condition (step 7) → `status: "block"`, exit `1`.
5. Otherwise → `status: "pass"`, exit `0`.

`per_family[]` is populated only when steps 1-3 all pass.

### Output Shape

```json
{
  "schema_version": "search_family_regression_v1",
  "adapter_id": "search_retrieval_v1",
  "status": "pass|block|invalid",
  "regression_detected": false,
  "metric_names": ["ndcg_at_5", "recall_at_5"],
  "k": 5,
  "thresholds": {
    "ndcg_drop_tolerance": 0.0,
    "recall_drop_tolerance": 0.0
  },
  "family_mode": "query_family_id",
  "query_count": 12,
  "family_count": 4,
  "regressed_family_count": 1,
  "regressed_family_fraction": 0.25,
  "alignment": {
    "status": "aligned|invalid",
    "missing_from_baseline": [],
    "missing_from_candidate": [],
    "extra_in_baseline": [],
    "extra_in_candidate": []
  },
  "blocking_families": [
    {
      "query_family_id": "synthetic:doc:slug:abc123",
      "reasons": ["ndcg_drop", "recall_drop"],
      "baseline_ndcg_at_5": 1.0,
      "candidate_ndcg_at_5": 0.5,
      "ndcg_delta": -0.5,
      "baseline_recall_at_5": 1.0,
      "candidate_recall_at_5": 0.0,
      "recall_delta": -1.0
    }
  ],
  "per_family": [],
  "validation_errors": []
}
```

`per_family[]` is always present on valid comparisons. `validation_errors[]` is non-empty on invalid output.

### CLI

```bash
python3 autorefine/scripts/eval-search-family-regression.py \
  --gold golden-set.jsonl \
  --baseline-predictions baseline-predictions.jsonl \
  --candidate-predictions candidate-predictions.jsonl \
  --output regression-gate.json \
  --report regression-gate.md \
  --k 5 \
  --ndcg-drop-tolerance 0.0 \
  --recall-drop-tolerance 0.0
```

Exit codes:
- `0`: valid comparison, no blocking family regression.
- `1`: valid comparison, one or more blocking family regressions.
- `2`: validation, alignment, JSONL, or usage error.

The CLI must always write `--output` when it can parse enough input to produce structured diagnostics. For malformed JSONL before structured output is possible, print the existing-style path/line error and exit `2`; `load_jsonl` already reports invalid rows with path and line (`autorefine/scripts/eval-search-metric.py:23-34`).

No path conventions are invented. The caller supplies all artifact paths.

### Phase 7 Consumer Contract

Add a short note near Phase 7 step 2c:

For `selected_adapter_id = "search_retrieval_v1"`, after scoring the candidate and before presenting results, call the search family regression gate with:
- the same gold/silver relevance rows used by the search metric,
- the prior kept experiment's explicit prediction artifact,
- the current candidate's explicit prediction artifact.

Skip this paired gate for experiments 0 and 1, matching the existing regression schema (`autorefine/references.md:4291-4294`).

If exit `1`, treat as regression detected and surface `blocking_families` in the existing `regression_check` record. If exit `2`, treat as a tool/input error, not as an automatic discard.

Unknown — verify before build: whether current Phase 7 search runs already persist explicit prediction artifact refs in experiment records. If not, the first implementation still remains buildable because the CLI accepts explicit paths; persistence can be a separate caller responsibility.

## Phasing

1. **TDD: library contract tests**
   - Add failing tests for family regression, no regression, recall-only regression, validation errors, and fallback family mode.

2. **Implement library**
   - Add `search_family_regression.py`.
   - Reuse `score_predictions`.
   - Keep all comparison logic pure: no filesystem writes, no state mutations.

3. **Add CLI wrapper**
   - Parse paths and thresholds.
   - Load JSONL.
   - Call library.
   - Write JSON output and optional markdown report.
   - Map exit codes exactly.

4. **Add Phase 7 doc note**
   - Patch only the regression-check paragraph or a nearby short subsection.
   - Do not describe a Python Phase 7 runner.
   - Do not invent artifact paths.

5. **Verification**
   - Run focused pytest for new tests and existing search metric tests.
   - Run full `autorefine/tests` suite.

## Test Plan

1. `test_blocks_family_ndcg_drop`
   - Same aggregate can look acceptable, but one family NDCG drops.
   - Assert `status == "block"` and family appears in `blocking_families`.

2. `test_blocks_family_recall_drop`
   - NDCG unchanged or tolerable, recall drops for a family.
   - Assert recall reason blocks.

3. `test_passes_when_all_family_deltas_non_negative`
   - Candidate matches or improves every family.
   - Assert exit-equivalent status pass.

4. `test_query_family_id_grouping_uses_gold_metadata`
   - Multiple queries share one `metadata.query_family_id`.
   - Assert family aggregation groups them.

5. `test_conflicting_family_id_for_query_is_invalid`
   - Same query has two family IDs across gold rows.
   - Assert `status == "invalid"` and no normal deltas.

6. `test_missing_family_id_falls_back_to_query_family`
   - Gold rows have no family metadata.
   - Assert `family_mode` includes fallback and gate still works.

7. `test_prediction_artifact_requires_exact_gold_query_coverage`
   - Candidate missing a query, baseline has extra query, duplicate row case.
   - Assert validation errors and invalid status.

8. `test_cli_exit_codes`
   - No regression exits `0`.
   - Regression exits `1`.
   - Invalid artifact exits `2`.

9. `test_cli_writes_json_and_markdown_report`
   - Assert machine JSON and concise report both exist.

10. Regression safety: rerun existing metric tests.
   - Existing test file has four tests (`autorefine/tests/test_eval_search_metric_py.py:25`, `:52`, `:81`, `:124`).
   - This proves no behavior change to the current metric runner.

## Success Criteria

- A Phase 7 agent can call one CLI with explicit gold/baseline/candidate paths and receive a deterministic pass/block/invalid result.
- Per-family regressions are visible in `blocking_families[]`.
- Invalid or mismatched artifacts fail as tool errors, not as false regression decisions.
- Existing `eval-search-metric.py` behavior remains unchanged.
- No new dependencies.
- Full relevant test suite passes.

## Risks / Open Questions

- Unknown — verify before build: whether Phase 7 search evaluations currently persist prediction artifact refs. If not, do not add storage in this slice; require explicit CLI paths.
- Unknown — verify before build: whether production gold sets include `metadata.query_family_id`. Fallback mode covers missing metadata, but true family-level value depends on upstream family IDs.
- Threshold policy may need user tuning. Defaults are strict (`0.0` drop tolerance) because the goal is regression detection, not improvement scoring.
- The library will import a hyphenated script via `importlib` in v1. This is locally precedented in tests (`autorefine/tests/test_eval_search_metric_py.py:7-14`) but not ideal long term. Moving metric code into `autorefine/lib` is a later refactor.

## Decision Log

- **Use deterministic metric comparison, not LLM judges.** Existing search scoring is already deterministic and primary for this adapter (`autorefine/references/gulf3-generalization.md:144-147`).
- **Library plus thin CLI.** Keeps the tool usable by agents now and future Python runners later.
- **Do not integrate into `run-campaign.py`.** It explicitly reports handoff work before phase commands execute (`autorefine/scripts/run-campaign.py:3-8`).
- **Align by query for this adapter.** Existing score code keys by query (`autorefine/scripts/eval-search-metric.py:135-147`); generic `input_id` alignment remains separate version-comparison infrastructure (`autorefine/references.md:622-685`).
- **Gate NDCG and recall.** User problem names both aggregate NDCG and recall masking family regressions.
- **Ignore `judge_diagnostic`.** It is optional prediction input handled by the metric runner (`autorefine/scripts/eval-search-metric.py:107-151`) and is not populated by this gate.

## Concerns Addressed

1. **Phase 7 hook undefined**
   - Resolution: no Python runner is assumed. The hook is the documented Phase 7 step 2c regression-check contract (`autorefine/references/gulf3-generalization.md:165`). The agent or any future consumer calls this tool there.

2. **Alignment uses query, not input_id**
   - Resolution: query alignment is explicit and adapter-specific. `eval-search-metric.py` scores by query (`autorefine/scripts/eval-search-metric.py:135-147`); `input_id` remains the generic version-comparison key (`autorefine/references.md:622-685`).

3. **Metadata rejoin needs invariant**
   - Resolution: build `query -> query_family_id` from preserved gold rows before scoring; hard-fail if one query has conflicting family IDs. Silver rows already put `query_family_id` under `metadata` (`autorefine/scripts/build-search-silver.py:223-231`).

4. **Integration gap relocated, not closed**
   - Resolution: integration is closed as a caller contract, not a fake code integration. The new API and CLI are callable from Phase 7 step 2c, and the doc note tells the agent when to call it. No nonexistent runner is invented.

5. **CLI brittle for agents**
   - Resolution: CLI has explicit required inputs, strict artifact validation, structured JSON diagnostics, optional markdown report, and stable exit codes `0/1/2`.

6. **Missing canonical prediction-artifact contract**
   - Resolution: this plan defines exact JSONL prediction row shapes, exact query coverage requirements, duplicate/extra/missing-query behavior, and how empty retrieval results must be represented.

## References

- `autorefine/scripts/eval-search-metric.py:5-10` — existing gold and prediction row shapes.
- `autorefine/scripts/eval-search-metric.py:23-34` — JSONL loader with path/line errors.
- `autorefine/scripts/eval-search-metric.py:37-50` — gold validation and query-keyed relevance map.
- `autorefine/scripts/eval-search-metric.py:107-151` — optional judge diagnostic normalization and per-query passthrough.
- `autorefine/scripts/eval-search-metric.py:128-205` — `score_predictions` API and aggregate/per-query output.
- `autorefine/scripts/eval-search-metric.py:239-267` — existing CLI pattern.
- `autorefine/scripts/build-search-silver.py:210-267` — silver relevance rows and `metadata.query_family_id`.
- `autorefine/tests/test_eval_search_metric_py.py:7-14` — local import pattern for hyphenated scripts.
- `autorefine/tests/test_eval_search_metric_py.py:25` — existing metric unit test 1.
- `autorefine/tests/test_eval_search_metric_py.py:52` — existing metric unit test 2.
- `autorefine/tests/test_eval_search_metric_py.py:81` — existing metric CLI test.
- `autorefine/tests/test_eval_search_metric_py.py:124` — existing silver-builder integration test.
- `autorefine/scripts/run-campaign.py:3-8` — campaign runner is plan/handoff before execution.
- `autorefine/scripts/prepare-gulf-gate-pack.py:3-7` — gate pack helper does not execute Phase 7.
- `autorefine/references/gulf3-generalization.md:132-147` — domain metric and search adapter primary/secondary semantics.
- `autorefine/references/gulf3-generalization.md:165` — Phase 7 regression-check step.
- `autorefine/references.md:443-483` — mutation-stage split access policy.
- `autorefine/references.md:622-685` — generic version comparison aligns by stable `input_id`.
- `autorefine/references.md:4283-4301` — regression-check schema and skip rule.
