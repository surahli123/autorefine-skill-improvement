# AutoRefine References

Templates, schemas, methodology rationale, and detailed rubrics. SKILL.md references specific sections — read on demand, not upfront.

---

## Workspace Schemas

Read when: Initialize Workspace or resuming a session.

### state.json
```json
{"schema_version":4,"skill_name":"<name>","skill_path":"<path>","original_skill_path":"<path>","workspace_path":"<path>","started":"<today>","current_phase":1,"current_gulf":1,"phases":{},"gates":{"gulf_1":"pending","gulf_2":"pending"},"hamel_available":false,"loop_iteration":0,"locked_judges":[],"memory_path":null,"checkpoint":null,"consecutive_discards":0,"circuit_breaker":null,"current_run_path":null,"completion_cadence":null,"skill_pattern":null,"phase1_context":null,"mutation_stage_split_access_policy":null,"quick_start":null}
```
- `schema_version`: 4 for v2.3 workspaces. Legacy: 2 = Standard/Deep (v2.1), 3 = Quick Start (v2.2). New fields default to null when reading v2/v3 workspaces.
- `loop_iteration`: tracks Phase 7→5 loop-backs (0 = first run)
- `locked_judges`: judge IDs approved in prior loops — don't re-validate
- `checkpoint`: resume state — see `Checkpoint Schema` section. null when no checkpoint active.
- `original_skill_path`: full path to the user's original skill directory (set in Preflight Step 0.6). Used by Session Close Apply Back gate and ambient learning on resume.
- `workspace_path`: full path to the AutoRefine workspace (set in Preflight Step 0.6).
- `consecutive_discards`: integer (0). Circuit breaker counter — incremented on discard, reset on keep. See SKILL.md Phase 7.
- `circuit_breaker`: null, or `{triggered_count: N, last_experiment: N, diagnosis: "..."}`. Set when circuit breaker fires.
- `current_run_path`: null, or relative path to the current Phase 7 run directory (e.g., `runs/run_2026-04-03T14-30-00/`). Set at Phase 7 start, updated on loop-back. Used by resume to identify which run directory to read `decision.md` files from.
- `completion_cadence`: null, or `{"scope_type":"experiment_series|skill","scope_id":"<stable-scope-id>","completed_experiments":N,"last_finalized_experiment_id":N,"last_finalized_status":"baseline|keep|discard","incremented_at":"<ISO-timestamp>"}`. Default scope is the active Phase 7 run directory (`experiment_series` via `state.json.current_run_path`); use `skill` only when one cadence counter should span multiple Phase 7 runs for the same skill.
- Increment `completion_cadence.completed_experiments` exactly once when an experiment reaches its finalized state. Finalized means: baseline after `iteration_000/` artifacts are written, keep after the user-confirmed keep verdict and iteration write, discard after discard autopsy plus iteration write. Do not increment for provisional scores, regression checks, or pre-autopsy discard proposals.
- `phase1_context`: null, or `{"selected_skill_pattern":"<pattern_id>","selected_eval_strategy_id":"<strategy_id>","selection_scope":"current_run","source_skill_path":"skill-under-test/SKILL.md"}`. Run-scoped Phase 1 context persisted immediately after pattern classification + strategy selection and overwritten whenever Phase 1 reruns for the active workspace copy.
- When serializing `state.json` for phase boundaries, checkpoint writes, or any other state rewrite, preserve the full `phase1_context` object unchanged so the chosen pattern and resolved evaluation strategy survive persistence.
- When deserializing or loading `state.json` on startup/resume, restore `phase1_context` into the loaded run context before routing or resuming later phases. Later phases must read the chosen pattern and resolved evaluation strategy from the loaded context rather than recomputing classification ad hoc.
- `mutation_stage_split_access_policy`: null, or the exact machine-readable object from `Mutation-Stage Split Access Policy`. Phase 4 writes it into `state.json` as the active Phase 7 dataset-read gate for this workspace/run.
- When serializing `state.json` for phase boundaries, checkpoint writes, or any other state rewrite, preserve `mutation_stage_split_access_policy` unchanged so the active dataset-read policy survives persistence.
- When deserializing or loading `state.json` on startup/resume, restore `mutation_stage_split_access_policy` into the loaded run context before routing into Phase 7 or Session Close. If split-scoped Phase 7 work is active and the field is missing, read the same policy from `fixtures-manifest.md` or a stored Phase 4 `evaluation_metadata.config.mutation_stage_split_access_policy` snapshot, hydrate the run context, and stop if those sources disagree.
- When initializing any downstream phase or stage after Phase 1, read the canonical pattern and resolved strategy from the loaded run context first (`state.json.phase1_context.selected_skill_pattern` + `state.json.phase1_context.selected_eval_strategy_id`). If only the persisted Phase 1 output is available in the current context, read the same canonical IDs from the top-level `selected_skill_pattern` and `selected_eval_strategy_id` fields in `design-audit.md` and hydrate the loaded run context from that artifact before continuing. If the artifact has only the pattern, resolve the missing strategy deterministically through `Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector` before any downstream phase work.
- When initializing any downstream phase or stage after Phase 1, read the canonical pattern from the loaded run context first (`state.json.phase1_context.selected_skill_pattern`).
- If only the persisted Phase 1 output is available in the current context, read the same canonical ID from the top-level `selected_skill_pattern` field in `design-audit.md` and hydrate the loaded run context from that artifact before continuing.
- Once `selected_eval_strategy_id` is restored, route downstream eval orchestration through the matching entry in `Skill Pattern Eval Strategy > Strategy Definitions`.
- The selected strategy is a routing decision, not a soft preference or tie-breaker.
- The generic downstream path is a fallback only when Phase 1 failed to produce a valid strategy, which is a blocking state error rather than a normal branch.
- Downstream phase/stage initialization must reuse the persisted pattern from Phase 1 output/run context rather than triggering pattern classification again. Only rerun Phase 1 Step 0 when the persisted pattern is missing or mismatched with `state.json.skill_pattern`.
- The current run's Phase 1 source of truth is `state.json.phase1_context.selected_skill_pattern`.
- The current run's downstream evaluation-strategy source of truth is `state.json.phase1_context.selected_eval_strategy_id`.
- Mirror the same canonical ID into `state.json.skill_pattern` for compatibility; if they differ, treat it as a state corruption bug.
- Gate all downstream Phase 1 processing on `phase1_context.selected_skill_pattern` and `phase1_context.selected_eval_strategy_id` being captured for the active run.
- If `phase1_context.selected_skill_pattern` is null, missing, empty, or mismatched with `state.json.skill_pattern`, stop Phase 1 immediately and rerun Step 0 before scoring any dimension.
- If `phase1_context.selected_eval_strategy_id` is null, missing, empty, or does not resolve back to the current `selected_skill_pattern` through `Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector`, stop Phase 1 immediately and rerun strategy selection before scoring any dimension.

### results.json
```json
{"skill_name":"<name>","status":"running","current_experiment":0,"baseline_score":null,"best_score":null,"completion_cadence":null,"experiments":[],"eval_breakdown":[]}
```
Result retrieval consumers must preserve experiment-level `decision_breakdown` when they serialize or return this payload. Do not strip the stored aggregation breakdown field from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `decision_breakdown` directly from that stored record and return it unchanged. Never recompute `decision_breakdown` on the retrieval path from `eval_results[]` or via the scoring module.
Result retrieval consumers must also preserve experiment-level `evaluation_metadata` when they serialize or return this payload. Do not strip the stored dataset/config payload from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `evaluation_metadata` directly from that stored record and return the stored dataset/config payload unchanged. Keep the `adversarial_holdout` split metadata attached to its dataset/config record so load/resume consumers can verify the split boundary without reopening other files.
The `adversarial_holdout` split metadata stays attached to its dataset/config record.
If the stored metadata includes `config.mutation_refinement_split_datasets[]` (`mutation_refinement_split_datasets[]`), retrieval consumers should derive `evaluation_metadata_validation` from that snapshot while keeping the stored `evaluation_metadata` payload unchanged. Flag invalid metadata whenever `adversarial_holdout` shares any `input_id` with a mutation/refinement split or omits one of those split IDs from `split_metadata.separate_from`.
If the stored metadata includes `config.mutation_stage_split_access_policy`, load/resume consumers should hydrate that exact object into the active Phase 7 dataset-read gate instead of rebuilding a looser policy from prose or defaults.
Result retrieval consumers must also preserve experiment-level `eval_results` when they serialize or return this payload. Do not strip `pass_fail`, `evidence`, or `supporting_items` from the returned verdicts.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `eval_results` directly from that stored record and return the stored verdict objects unchanged so each `pass_fail` decision stays attached to its own `evidence[]` and `supporting_items[]` for downstream rendering.
Result retrieval consumers may additionally derive `judge_verdict_report_entries` for dashboards or review UIs, but that field is a report-facing view, not authoritative storage.
Each `judge_verdict_report_entries[]` item must expose the same verdict through reviewer-readable fields: `verdict_label`, `reasoning_trace`, and `evidence_attachments[]` with a stable `reference` plus a human-readable `snippet`.
Each `judge_verdict_report_entries[]` item should also expose an `evidence_block` object so every verdict carries a structured inspection payload. `evidence_block.items[]` must preserve the stable evidence `reference` plus either `inline_content` (for excerpts/metrics rendered directly in the payload) or `artifact_reference` (for direct artifact pointers that let a human inspect the supporting basis at the source).
Dashboard and report renderers should render `reasoning_trace` inline in the report body for the same verdict item so reviewers can inspect the rationale without opening raw logs.
Result retrieval consumers may also derive `review_handoff` for downstream review flows. This handoff payload is additive, not authoritative storage.
`review_handoff` should package the finalized review inputs in one object: `experiment_id`, `final_decision`, the stored `judge_verdict_report_entries[]`, the stored `decision_breakdown`, the stored `decision_explanation`, the stored `completion_cadence`, the stored `requires_human_spot_check`, and a derived `human_spot_check_task` when the cadence gate is active.
Carry `review_handoff.requires_human_spot_check` through from the finalized experiment record unchanged so downstream review flows can detect and enforce the required human spot-check without replaying cadence history.
When `review_handoff.requires_human_spot_check = true`, derive `review_handoff.human_spot_check_task` from the stored `completion_cadence` plus the resolved calibration config. Copy the resolved `sample_count` onto the task payload instead of forcing downstream queues to recompute it from cadence state or config defaults. In other words, `review_handoff.human_spot_check_task.sample_count` is the authoritative queue-time value for `N`.
Result retrieval consumers must also preserve experiment-level `decision_explanation` when they serialize or return this payload. Do not strip the stored explanation field from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `decision_explanation` directly from that stored record and return the stored `decision_explanation` field unchanged. Never recompute `decision_explanation` on the retrieval path from `decision_breakdown`, `eval_results[]`, or via the scoring module.
Result retrieval consumers must also preserve experiment-level `requires_human_spot_check` when they serialize or return this payload. Do not strip the stored trust-checkpoint flag from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `requires_human_spot_check` directly from that stored record and return it unchanged. Never recompute `requires_human_spot_check` on the retrieval path from `completion_cadence` or experiment order.
Result retrieval consumers must also preserve the persisted `completion_cadence` counter at both the root payload and experiment level. Do not rebuild cadence position from array order or recompute it from filtered experiment lists on the retrieval path.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `completion_cadence` directly from that stored record and return it unchanged.

Each experiment in `experiments[]`:
```json
{"id":N,"input_set_id":"phase4-dev-7f3c91ad","input_set_ref":"input-sets.json#phase4-dev-7f3c91ad","input_ids":["phase4-dev-7f3c91ad-I03","phase4-dev-7f3c91ad-I05","phase4-dev-7f3c91ad-I08"],"score":X,"max_score":Y,"pass_rate":Z,"status":"keep|discard|baseline","description":"...","changes":[{"type":"added|modified|removed","location":"section","snippet":"1-3 lines"}],"evaluation_metadata":{"dataset":{"input_set_id":"phase4-adversarial_holdout-91ab77ce","input_set_ref":"input-sets.json#phase4-adversarial_holdout-91ab77ce","input_ids":["phase4-adversarial_holdout-91ab77ce-I01"],"split_metadata":{"split_id":"adversarial_holdout","display_label":"Adversarial Holdout","evaluation_only":true,"hidden_until":"session_close","used_for":["session_close_holdout_validation"],"blocked_from":["phase5_judge_examples","phase6_judge_refinement","phase7_mutation_scoring","phase7_mutation_analysis"],"separate_from":["train","dev","test"]}},"config":{"scoring_scope":"session_close_holdout_validation","freeze_split_boundaries":true,"require_same_split_metadata_on_resume":true,"human_spot_check_calibration":{"sample_count":2},"mutation_refinement_split_datasets":[{"split_id":"train","input_set_id":"phase4-train-42be3101","input_ids":["phase4-train-42be3101-I01"]},{"split_id":"dev","input_set_id":"phase4-dev-7f3c91ad","input_ids":["phase4-dev-7f3c91ad-I03","phase4-dev-7f3c91ad-I05"]},{"split_id":"test","input_set_id":"phase4-test-6ca1b7d2","input_ids":["phase4-test-6ca1b7d2-I02"]}]}},"evaluation_metadata_validation":{"status":"valid","checked_split_ids":["train","dev","test"],"overlap_count":0,"issues":[]},"eval_results":[{"eval":"E1","pass_fail":"pass","reasoning_trace":"1. Criterion check: the required gotchas section is present. 2. Evidence: the output contains a gotchas heading and 3 specific warnings. 3. Verdict link: because the rubric requires a gotchas section with concrete warnings, this passes.","evidence":[{"kind":"output_excerpt","source":"skill_output","locator":"input_id:phase4-dev-7f3c91ad-I03 output lines 12-18","excerpt":"## Gotchas\\n- Never run rm -rf without checking the target path.","metric":null,"artifact_ref":null},{"kind":"metric","source":"scoring_metric","locator":"warnings_found","excerpt":"3 concrete warnings found in the gotchas section.","metric":{"name":"warnings_found","value":3,"unit":"count"},"artifact_ref":null}],"supporting_items":[{"stage":"criterion_check","decision":"required gotchas section is present","outcome":"met","evidence_refs":[0]},{"stage":"evidence_check","decision":"gotchas section includes 3 concrete warnings","outcome":"met","evidence_refs":[1]},{"stage":"verdict_link","decision":"the rubric passes when the gotchas section and concrete warnings are both present","outcome":"supports_pass","evidence_refs":[0,1]}],"weight":1.0,"weight_source":"code_eval_fixed","weighted_points":1.0,"normalized_contribution":0.25},{"eval":"E2","pass_fail":"fail","reasoning_trace":"1. Criterion check: the disclosure instruction is missing. 2. Evidence: no 'Read when:' pointer appears and the disclosure section is absent. 3. Verdict link: because the rubric requires explicit disclosure guidance, this fails.","evidence":[{"kind":"output_excerpt","source":"skill_output","locator":"input_id:phase4-dev-7f3c91ad-I03 output lines 1-9","excerpt":"No 'Read when:' pointer or disclosure section appears in the output.","metric":null,"artifact_ref":null},{"kind":"artifact_ref","source":"workspace_artifact","locator":"runs/run_2026-04-10T10-00-00/iteration_000/eval_results.json","excerpt":"Stored verdict artifact for replay and dashboard inspection.","metric":null,"artifact_ref":{"path":"runs/run_2026-04-10T10-00-00/iteration_000/eval_results.json","label":"baseline eval results"}}],"supporting_items":[{"stage":"criterion_check","decision":"disclosure guidance is missing","outcome":"not_met","evidence_refs":[0]},{"stage":"verdict_link","decision":"the rubric fails when disclosure guidance is absent","outcome":"supports_fail","evidence_refs":[0,1]}],"weight":0.9,"weight_source":"phase_6_validation_average","weighted_points":0.0,"normalized_contribution":0.0}],"decision_breakdown":{"components":[{"eval":"E1","pass_fail":"pass","weight":1.0,"weight_source":"code_eval_fixed","weighted_points":1.0,"normalized_contribution":0.213},{"eval":"E2","pass_fail":"fail","weight":0.9,"weight_source":"phase_6_validation_average","weighted_points":0.0,"normalized_contribution":0.0}],"formula":"combined_score = weighted_points / total_weight","weighted_points":3.7,"total_weight":4.7,"combined_score":0.787,"combined_score_pct":78.7,"threshold":0.8,"proposed_decision":"discard"},"decision_explanation":{"final_decision":"discard","summary":"E2 withheld 19.1% of the available score, while E1 added 21.3%; the mutation still finished below threshold.","strongest_outcomes":[{"eval":"E2","pass_fail":"fail","impact":"supports_discard","impact_magnitude":0.191,"impact_basis":"missed_weight_share","summary":"The failed high-weight eval withheld 19.1% of the available score."},{"eval":"E1","pass_fail":"pass","impact":"supports_keep","impact_magnitude":0.213,"impact_basis":"normalized_contribution","summary":"The strongest pass added 21.3% toward keep, but the experiment still missed threshold."}]},"regression_check":null,"discard_autopsy":null,"requires_human_spot_check":false}
```
- `evaluation_metadata`: stored dataset/config payload for this experiment's evaluation run. Preserve it unchanged on write and retrieval so split-aware consumers can inspect the scoring corpus and any split-boundary rules without reopening workspace files. When this payload records `adversarial_holdout`, keep the split metadata attached to the same record.
- `human_spot_check_calibration.sample_count`: configurable calibration sample-count setting `N` stored inside `evaluation_metadata.config.human_spot_check_calibration.sample_count`. Default to `2` when the config is missing. Validation: `sample_count` must be a positive integer (`>= 1`). Every 3rd experiment surfaces `sample_count` random `(eval, fixture)` pairs from the most recent finalized experiment. Session Close uses `max(sample_count, 5)` so the independent closeout calibration never drops below the 5-sample minimum.
- `evaluation_metadata_validation`: derived retrieval-time validation summary for `adversarial_holdout` metadata. Surface `status`, `checked_split_ids`, `overlap_count`, and `issues[]` without mutating the stored `evaluation_metadata`. Any shared `input_id` between holdout and `config.mutation_refinement_split_datasets[]` is invalid metadata and must be flagged here.
- `eval_results`: per-eval verdicts for this experiment. Each decision must include `eval`, `pass_fail`, `category` (from eval-suite.md: `structural`, `task-completion`, or `quality`), `reasoning_trace`, `evidence`, `supporting_items`, `weight`, `weight_source`, `weighted_points`, and `normalized_contribution`. `reasoning_trace` is always a concise ordered explanation: criterion check, evidence, then verdict link. `evidence` is an array of structured evidence objects, not free-form strings; use it to preserve cited inputs, output excerpts, metrics, and artifact references in a replayable form. `supporting_items` captures the concrete intermediate judgment calls and maps each one back to the exact `evidence[]` entries it used. Used by regression checks to compare across experiments.
- `judge_verdict_report_entries`: derived report-facing view of `eval_results`. Each entry repeats the stored verdict data and adds `verdict_label`, an `evidence_block`, and `evidence_attachments[]`. `evidence_block.items[]` is the structured inspection surface for that verdict: every item keeps a stable evidence `reference` plus either `inline_content` or an `artifact_reference` that points directly to the supporting artifact. `evidence_attachments[]` remains the reviewer-friendly attachment list with stable `reference` plus readable `snippet`. Render the same entry's `reasoning_trace` inline in the report body so the verdict rationale stays inspectable without opening raw logs. Use this for dashboard cards, external reports, or production review surfaces; do not write it back as the source of truth.
- `review_handoff`: derived downstream-review payload. Package `experiment_id`, `final_decision`, `judge_verdict_report_entries`, `decision_breakdown`, `decision_explanation`, `completion_cadence`, the stored trust gate in `review_handoff.requires_human_spot_check`, and `review_handoff.human_spot_check_task` when a cadence-triggered calibration pause is pending. Use the task payload to queue the human spot-check without recomputing `sample_count` from config.
- `weight_source`: where the eval's weight came from. Use `code_eval_fixed`, `phase_6_validation_average`, `mini_mode_code_default`, or `mini_mode_agent_discount`.
- `decision_breakdown`: aggregate scoring record used for keep/discard. `components[]` is the structured aggregation breakdown field: an ordered, self-contained copy of the exact eval inputs that rolled into the keep/discard math. `score` mirrors `weighted_points` and `max_score` mirrors `total_weight` for dashboard compatibility.
- `decision_explanation`: structured explanation mapping derived from `decision_breakdown` plus the final keep/discard. Store `final_decision`, a short `summary`, and ordered `strongest_outcomes[]` entries that identify the strongest contributing eval outcomes and their impact on the final keep/discard.
- `requires_human_spot_check`: boolean finalized-only trust checkpoint flag. Set to `true` when the post-increment `completion_cadence.completed_experiments` value for this finalized experiment is divisible by 3 (3, 6, 9, ...); otherwise `false`.
- `regression_check`: null (no check run), or `{"passed":true,"details":"..."}`, or `{"passed":false,"regressions":[{"experiment":1,"eval":"E2","was":"pass","now":"fail","detail":"..."}]}`
- `discard_autopsy`: null (experiment kept or baseline), or `{"classification":"wrong_target|wrong_params|wrong_type","reasoning":"1-sentence explanation"}`. Set after discard in Phase 7 step 2f. See `Discard Autopsy Heuristics` section.
- `input_set_id`: stable scoring set ID for this experiment.
- `input_set_ref`: exact registry pointer for the scoring set. Format: `input-sets.json#<set_id>`.
- `input_ids`: stable input IDs actually scored for this experiment, stored in finalized set order. Version comparisons are only valid when both `input_set_id` and the full `input_ids` list match across experiments.
- `completion_cadence`: finalized snapshot of the cadence counter for this experiment. Copy the active root counter into the experiment record only after the experiment reaches its final state so production systems can tell which completed-experiment slot this version occupied without replaying the run.

### Human Spot-Check Calibration Config Schema

Persist this config in `evaluation_metadata.config.human_spot_check_calibration` whenever Phase 7 or Session Close queues human spot-check calibration.

```json
{"sample_count":2}
```

- `sample_count`: configurable calibration sample-count setting `N`.
- Default to `2` when the config is missing.
- Validation: `sample_count` must be a positive integer (`>= 1`).
- Every 3rd completed experiment surfaces `sample_count` random `(eval, fixture)` pairs from the most recent finalized experiment.
- Session Close uses `max(sample_count, 5)` so the independent closeout calibration never drops below the 5-sample minimum.
- When a cadence-triggered or Session Close calibration task is constructed, copy the resolved `sample_count` into that task payload immediately. Do not require downstream queues to recompute `N` from the config later.

### Human Spot-Check Task Schema

Construct this payload whenever completion cadence or Session Close queues human spot-check calibration.

```json
{"task_type":"human_spot_check_calibration","trigger":"completion_cadence","status":"pending","experiment_id":3,"completed_experiment_slot":3,"sample_count":2,"sample_count_source":"evaluation_metadata.config.human_spot_check_calibration.sample_count","minimum_sample_floor":null}
```

- `task_type`: stable queue identifier. Use `human_spot_check_calibration`.
- `trigger`: `completion_cadence` for every-3rd-experiment pauses, `session_close` for the mandatory closeout review.
- `status`: initialize as `pending` when the task is queued.
- `experiment_id`: finalized experiment that triggered the calibration pause. Null only for Session Close tasks that are not tied to a single mutation.
- `completed_experiment_slot`: copy from `completion_cadence.completed_experiments` when cadence triggered the task. This lets downstream systems know which finalized slot caused the queue event.
- `sample_count`: resolved calibration sample-count used for the task. For cadence-triggered tasks, use the validated config value or the default `2`. For Session Close, use `max(sample_count, 5)`.
- `sample_count_source`: `evaluation_metadata.config.human_spot_check_calibration.sample_count` when the config supplied `N`, otherwise `default_human_spot_check_calibration.sample_count`.
- `minimum_sample_floor`: null for cadence-triggered tasks. Set to `5` for Session Close tasks so the queue records the mandatory closeout floor explicitly.

### results.tsv
Header: `experiment\tscore\tmax_score\tpass_rate\tstatus\tdescription`

### input-sets.json
```json
{"sets":[{"set_id":"phase3-fixtures-7f3c91ad","kind":"phase3_fixtures","canonical_hash":"7f3c91adf2f0f96f...","created":"<ISO-timestamp>","split_metadata":null,"inputs":[{"input_id":"phase3-fixtures-7f3c91ad-I01","content_hash":"c55f6f5d8c7d...","source_path":"traces/trace-T01.md","summary":"long edge-case fixture with planted flaw"},{"input_id":"phase3-fixtures-7f3c91ad-I02","content_hash":"9410d0fd5a19...","source_path":"traces/trace-T02.md","summary":"short happy-path fixture"}]},{"set_id":"phase4-adversarial_holdout-91ab77ce","kind":"phase4_split","canonical_hash":"91ab77ce91ab77ce...","created":"<ISO-timestamp>","split_metadata":{"split_id":"adversarial_holdout","display_label":"Adversarial Holdout","evaluation_only":true,"hidden_until":"session_close","used_for":["session_close_holdout_validation"],"blocked_from":["phase5_judge_examples","phase6_judge_refinement","phase7_mutation_scoring","phase7_mutation_analysis"],"separate_from":["train","dev","test"]},"inputs":[{"input_id":"phase4-adversarial_holdout-91ab77ce-I01","content_hash":"7ad0d9f0e5c3...","source_path":"fixtures/holdout/H01.md","summary":"hidden counterexample reserved for post-loop validation"}]}]}
```
- `set_id`: stable identifier for an evaluation input set. Derived from the canonical set hash. Reused on reruns of the same set.
- `kind`: explicit set label such as `quick_start_observation`, `quick_start_scoring`, `phase3_fixtures`, or `phase4_fixtures`.
- `canonical_hash`: hash of the normalized set membership. Used to detect "this is the same set again."
- `split_metadata`: null for unsplit corpora, required for every Phase 4 split-scoped set entry. Use it to preserve whether a set is `train`, `dev`, `test`, or the dedicated `adversarial_holdout` evaluation split.
- `input_id`: stable identifier for a single input inside the set. Assigned once, then reused.
- `content_hash`: hash of the normalized input content. If the content changes, this is a new input and should get a new `input_id`.

### Evaluation Split Metadata Schema

Use this schema whenever Phase 4 or later writes split-scoped evaluation datasets or `fixtures-manifest.md` sections.

```json
{
  "split_id": "adversarial_holdout",
  "display_label": "Adversarial Holdout",
  "evaluation_only": true,
  "hidden_until": "session_close",
  "used_for": ["session_close_holdout_validation"],
  "blocked_from": ["phase5_judge_examples", "phase6_judge_refinement", "phase7_mutation_scoring", "phase7_mutation_analysis"],
  "separate_from": ["train", "dev", "test"]
}
```

When `evaluation_metadata.dataset.split_metadata.split_id = "adversarial_holdout"`, also snapshot every mutation/refinement split in `evaluation_metadata.config.mutation_refinement_split_datasets[]`:

```json
[
  {"split_id":"train","input_set_id":"phase4-train-42be3101","input_ids":["phase4-train-42be3101-I01"]},
  {"split_id":"dev","input_set_id":"phase4-dev-7f3c91ad","input_ids":["phase4-dev-7f3c91ad-I03","phase4-dev-7f3c91ad-I05"]},
  {"split_id":"test","input_set_id":"phase4-test-6ca1b7d2","input_ids":["phase4-test-6ca1b7d2-I02"]}
]
```

### Mutation-Stage Split Access Policy

Persist this policy in `evaluation_metadata.config.mutation_stage_split_access_policy` whenever Phase 4 locks split boundaries for a run.

```json
{
  "stage_id": "phase7_mutation_stage",
  "allowed_split_ids": ["dev"],
  "blocked_split_ids": ["train", "test", "adversarial_holdout"],
  "split_access": {
    "dev": "allowed",
    "train": "blocked",
    "test": "blocked",
    "adversarial_holdout": "inaccessible"
  },
  "allowed_operations": [
    "baseline_scoring",
    "mutation_scoring",
    "mutation_analysis",
    "regression_check",
    "same_run_version_comparison"
  ]
}
```

- `allowed_split_ids`: `dev` only. Mutation-time operations may read the dev scoring corpus and no other split.
- `blocked_split_ids`: enumerate every split that mutation-time operations must not read.
- `split_access.adversarial_holdout`: must be `inaccessible` so the post-loop holdout cannot leak into Phase 7.
- `allowed_operations`: use this policy for baseline scoring, mutation scoring, mutation analysis, regression checks, and same-run version comparison during Phase 7.
- Persist the same object in `state.json.mutation_stage_split_access_policy` once Phase 4 freezes split boundaries. That state field is the orchestration-layer source of truth for later Phase 7 dataset reads and checkpoint resume.
- On resume or Phase 7 re-entry, restore the exact persisted object into the loaded run context before any scoring, mutation analysis, regression check, same-run version comparison, or other step that may reopen split-scoped inputs.
- If a Phase 7 step requests a dataset read, verify both the requested operation and the requested split against this restored object before reading fixtures, per-input outputs, or joined experiment records.
- Session Close adversarial holdout validation is intentionally outside this mutation-stage policy. Switch to the evaluation-only `session_close_holdout_validation` scope before reading holdout fixtures.
- `train`: blocked at mutation time. It remains few-shot material for Phase 5 judge prompts only.
- `test`: blocked at mutation time. It remains the Phase 6 final judge-measurement split only.
- `adversarial_holdout`: inaccessible during mutation-time operations. Only Session Close holdout validation may read it.

- `split_id`: canonical split identifier. Valid Phase 4 split IDs are `train`, `dev`, `test`, and `adversarial_holdout`.
- `display_label`: human-readable label for the split as shown in manifests and reports.
- `evaluation_only`: `true` only for `adversarial_holdout`. This explicitly marks the split as measurement-only.
- `hidden_until`: use `session_close` for `adversarial_holdout` so weak agents do not leak the examples into mutation or judge-refinement flows.
- `used_for`: the only allowed consumer for `adversarial_holdout` is `session_close_holdout_validation`.
- `blocked_from`: stages that must never consume the split. `adversarial_holdout` is blocked from Phase 5 judge examples, Phase 6 judge refinement, Phase 7 mutation scoring, and Phase 7 mutation analysis.
- `separate_from`: splits this entry must remain disjoint from. `adversarial_holdout` is a dedicated evaluation-only split and must stay separate from mutation/refinement splits. Every split listed in `config.mutation_refinement_split_datasets[]` must appear here.
- `mutation_refinement_split_datasets`: evaluation-metadata snapshot of the split corpora referenced by the Phase 5-7 boundary rules. Compare their `input_ids` against the holdout `input_ids` and flag invalid metadata if any overlap exists. For actual Phase 7 mutation-time reads, obey `mutation_stage_split_access_policy`: only `dev` is allowed at runtime.
- Never alias `adversarial_holdout` to `dev`, `test`, or any mutation/refinement split for convenience. `test` remains the Phase 6 judge-validation measurement split; `adversarial_holdout` is the post-loop overfitting check.
- Any shared `input_id` between `adversarial_holdout` and a mutation/refinement snapshot is a blocking metadata error. Fail or flag that overlap instead of silently continuing.

### session-log.json
```json
{"skill":"<name>","session_start":"<ISO-timestamp>","entries":[]}
```
Entry types:
- Design audit: `{"phase":"1","type":"design_audit","detail":"Scored 6 dims: Gotchas=Present, Voice=Partial, Disclosure=Missing, Anti-Railroading=Partial, Description Quality=Partial, Scripts=N/A"}`
- Sampling: `{"phase":"3","type":"sampling","detail":"Selected 8/15 traces, stratified by 3 dimensions"}`
- Consistency flag: `{"phase":"3","type":"consistency_flag","detail":"T03 and T07 match C2, judged differently"}`
- Gate decision: `{"phase":"gate_1","type":"gate_decision","detail":"APPROVED"}`
- Override: `{"phase":"gate_1","type":"override","detail":"Removed E4","reason":"..."}`
- Judge gap: `{"phase":"7","type":"judge_gap","experiment":4,"agent_verdict":"keep","user_verdict":"discard","reason":"..."}`
- Mini observation (Quick Start): `{"phase":"quick_start","step":"observation","type":"mini_observation","detail":"Reviewed 5 traces: 3 pass, 2 fail"}`
- Checkpoint: `{"phase":"3","type":"checkpoint","detail":"Saved checkpoint at Phase 3 boundary. Resume prompt written."}`
- Regression: `{"phase":"7","type":"regression","experiment":3,"detail":"E2 regressed: was pass (exp 1), now fail. Gotcha section removed by mutation.","user_action":"discard"}`
- Circuit breaker: `{"phase":"7","type":"circuit_breaker","diagnosis":"content_ceiling|strategy_review","consecutive_discards":3,"experiments":[3,4,5]}`
- Circuit breaker override: `{"phase":"7","type":"circuit_breaker_override","reason":"user chose to continue"}`
- Discard autopsy: `{"phase":"7","type":"discard_autopsy","experiment":N,"classification":"wrong_target|wrong_params|wrong_type","reasoning":"1-sentence explanation"}`
- Canonical headings: `{"phase":"7","type":"canonical_headings","sections":["section1","section2","..."]}`
- Iteration write: `{"phase":"7","type":"iteration_write","experiment":N,"path":"runs/run_.../iteration_NNN/"}`
- Completion cadence increment: `{"phase":"7","type":"completion_cadence","experiment":N,"scope_type":"experiment_series","scope_id":"runs/run_.../","completed_experiments":N,"status":"baseline|keep|discard"}`
- Input set registration: `{"phase":"3","type":"input_set_registered","set_id":"phase3-fixtures-7f3c91ad","kind":"phase3_fixtures","input_count":18,"canonical_hash":"7f3c91adf2f0f96f..."}`
- Eval strategy resolution: `{"phase":"1","type":"eval_strategy_resolution","skill_pattern":"pipeline","strategy_id":"pipeline_eval_strategy","reasoning":"Pattern requires gate-aware, resume-safe downstream evaluation."}`
- Derived registry snapshot: `{"phase":"7","type":"derived_registry_snapshot","experiment":N,"sections_explored":{"section1":{"count":2,"best_delta":0.12,"last_tried":3,"autopsy_pattern":"wrong_target"},...},"mutation_types":{"add":3,"modify":2,"delete":1},"diversity_score":0.6}`
- Apply back: `{"type":"apply_back","applied":true,"source":"[workspace]/skill-under-test/SKILL.md","target":"[original-skill-path]/SKILL.md"}`
- Ambient learning: `{"type":"ambient_learning","rules_extracted":2,"diff_size":12}` or `{"type":"ambient_learning","skipped":true,"reason":"full_rewrite","diff_size":180}`

---

## Input Set Identity Schema

Read when: generating evaluation inputs (Quick Start QS Step 2/QS Step 4, Phase 3 fixture prep, Phase 4 split writing, or Phase 7 scoring).

AutoRefine compares skill versions on the **same** evaluation inputs. That only works if every input has a stable identity. Positional filenames like `trace-T03.md` are not enough because files can be regenerated, reordered, or moved between splits.

### Deterministic ID rules

1. **Normalize each input before hashing.**
   - Convert CRLF to LF
   - Strip trailing whitespace on every line
   - Trim blank lines at the start and end
2. **Compute `content_hash`.**
   - `content_hash = sha256(normalized_input)`
3. **Compute the set hash from membership, not filenames.**
   - Build the multiset of all `content_hash` values in the finalized set
   - Sort those hashes lexicographically, keeping duplicates
   - `canonical_hash = sha256(join(sorted_hashes, "\n"))`
4. **Assign `set_id`.**
   - `set_id = <kind>-<canonical_hash[0:8]>`
5. **Assign `input_id` once.**
   - For a brand-new set, assign IDs in the finalized set order: `<set_id>-I01`, `<set_id>-I02`, ...
   - Store the mapping in `input-sets.json`

### Rerun reuse rule

Before assigning new IDs, read `input-sets.json`.

- If a prior set has the same `kind` and `canonical_hash`, reuse that `set_id` and every stored `input_id` exactly as written.
- If no match exists, create a new set entry and assign new IDs.
- **Never renumber an existing set** because filenames changed, traces were regenerated, or inputs moved between train/dev/test/adversarial_holdout. If the content set is unchanged, the IDs stay unchanged.

### Where to surface IDs

- Quick Start observation traces: show `Input ID: ...`
- Phase 3 trace files: include `Input ID: ...` in the header
- `fixtures-manifest.md`: list split membership by `input_id` and emit the split's `split_metadata` block when the set is split-scoped
- `results.json` and iteration `eval_results.json`: record the active `input_set_id`, exact `input_set_ref` (`input-sets.json#<set_id>`), and finalized-order `input_ids` for each experiment

### Minimal fixtures-manifest.md format

```markdown
## Dev Split
Fixture count: 12
Input set: phase4-fixtures-7f3c91ad
IDs: phase4-fixtures-7f3c91ad-I03, phase4-fixtures-7f3c91ad-I05, phase4-fixtures-7f3c91ad-I08

## Adversarial Holdout Split
Fixture count: 6
Input set: phase4-adversarial_holdout-91ab77ce
Split metadata: split_id=adversarial_holdout | evaluation_only=true | hidden_until=session_close | blocked_from=phase5_judge_examples,phase6_judge_refinement,phase7_mutation_scoring,phase7_mutation_analysis
Mutation-stage access policy: allowed_split_ids=dev | blocked_split_ids=train,test,adversarial_holdout | adversarial_holdout=inaccessible
IDs: phase4-adversarial_holdout-91ab77ce-I01, phase4-adversarial_holdout-91ab77ce-I02, phase4-adversarial_holdout-91ab77ce-I03
[Content hidden until Session Close holdout validation]
```

This is intentionally simple so weak agents can follow it. The important invariant is stable identity, not a rich manifest format.

---

## Version Comparison Alignment

Read when: comparing Version N vs Version N+1, showing baseline vs kept-version deltas, or building any before/after per-input diff.

Version comparisons are only trustworthy when the two experiments were scored on the same registered corpus. Before computing a per-input delta, require the same `input_set_id` and the exact same set of stable `input_id`s proven by the stored `input_ids`.

### Comparison preflight

1. Load both experiment records and treat the stored `input_ids` arrays as the source of truth for membership.
   - normalize them into stable-ID sets before any comparison work
   - do not reconstruct membership from UI rows, verdict order, or partial evidence locators
2. Verify the experiments point to the same scoring corpus.
   - require the same `input_set_id`
3. Verify exact stable-ID-set equality before joining any rows.
   - `missing_from_left`: IDs present in the right experiment but absent from the left experiment
   - `missing_from_right`: IDs present in the left experiment but absent from the right experiment
   - `extra_in_left`: same IDs as `missing_from_right`, labeled from the left experiment's perspective
   - `extra_in_right`: same IDs as `missing_from_left`, labeled from the right experiment's perspective
4. Hard-fail the comparison if `input_set_id` differs or if any missing/extra list is non-empty.
   - the comparison preflight passes only when both runs contain the exact same set of stable input IDs
   - report the missing/extra IDs on either side instead of guessing or dropping rows
   - return a rejected comparison or a flagged `invalid-comparison` status instead of a normal diff result
   - if the preflight fails, you must not emit normal comparison results, per-input delta rows, pass-rate deltas, weighted-score deltas, or token deltas

Example failure payload:

```json
{
  "status": "invalid-comparison",
  "left_experiment_id": 1,
  "right_experiment_id": 3,
  "input_set_id_match": true,
  "left_input_ids": ["phase4-dev-7f3c91ad-I03", "phase4-dev-7f3c91ad-I05"],
  "right_input_ids": ["phase4-dev-7f3c91ad-I03", "phase4-dev-7f3c91ad-I05", "phase4-dev-7f3c91ad-I08"],
  "missing_from_left": ["phase4-dev-7f3c91ad-I08"],
  "missing_from_right": [],
  "extra_in_left": [],
  "extra_in_right": ["phase4-dev-7f3c91ad-I08"]
}
```

### Alignment rules

1. Run the comparison preflight first.
   - require the same `input_set_id`
   - require the exact same stable `input_ids` membership from that corpus
   - stop immediately if the preflight reports missing or extra IDs on either side
   - surface that stop as a rejected comparison or `invalid-comparison`, never as a partial comparison
2. Build lookup tables for both experiments keyed by stable input identity.
   - align Version N and Version N+1 by `input_id`
   - use the `input_id` carried in verdict evidence locators, fixture manifests, or other persisted per-input records
3. Only after both lookups cover the same IDs, compute the delta row for each shared input.
   - compute per-input diffs only after the `input_id` join succeeds
   - then compare verdicts, scores, regressions, and evidence for that specific input

### Hard stops

- Do NOT align by list position, array order, or run order.
- If either version is missing a required `input_id`, stop the comparison, mark it `invalid-comparison`, and report the exact missing/extra IDs on both sides instead of guessing.
- If the corpus changed, start a new run/version lineage rather than mixing results from different input sets.

### Presentation order

After the join succeeds, present rows in the canonical scoring-set order recorded in `input-sets.json` or, if that entry is unavailable, the finalized `input_ids` order persisted with the experiments. Stable order is for display only; it is never the matching key.

### Successful comparison payload

After the comparison preflight passes, emit a structured per-input comparison payload. Do not collapse the comparison down to only aggregate score deltas because the human needs to inspect what changed on each shared input.

```json
{
  "status": "ok",
  "left_experiment_id": 1,
  "right_experiment_id": 3,
  "input_set_id": "phase4-dev-7f3c91ad",
  "shared_input_summary": {
    "total_shared_inputs": 2,
    "improved": 1,
    "regressed": 0,
    "unchanged": 1
  },
  "per_input": [
    {
      "input_id": "phase4-dev-7f3c91ad-I03",
      "before_output": {
        "locator": "runs/run_2026-04-10T10-00-00/iteration_001/outputs/phase4-dev-7f3c91ad-I03.md",
        "excerpt": "## Gotchas\n- Quote every shell path before running commands.",
        "artifact_ref": {
          "path": "runs/run_2026-04-10T10-00-00/iteration_001/outputs/phase4-dev-7f3c91ad-I03.md",
          "label": "v1 output for phase4-dev-7f3c91ad-I03"
        }
      },
      "after_output": {
        "locator": "runs/run_2026-04-10T10-00-00/iteration_003/outputs/phase4-dev-7f3c91ad-I03.md",
        "excerpt": "## Gotchas\n- Quote every shell path before running commands.\n- Confirm destructive targets before execution.",
        "artifact_ref": {
          "path": "runs/run_2026-04-10T10-00-00/iteration_003/outputs/phase4-dev-7f3c91ad-I03.md",
          "label": "v3 output for phase4-dev-7f3c91ad-I03"
        }
      },
      "score_changes": [
        {
          "eval": "E2",
          "field": "pass_fail",
          "before": "fail",
          "after": "pass"
        },
        {
          "eval": "E2",
          "field": "weighted_points",
          "before": 0.0,
          "after": 0.9
        }
      ],
      "metadata_changes": [
        {
          "field": "reasoning_trace",
          "before": "1. Criterion check: disclosure guidance is missing.",
          "after": "1. Criterion check: disclosure guidance is present."
        }
      ]
    },
    {
      "input_id": "phase4-dev-7f3c91ad-I05",
      "before_output": {
        "locator": "runs/run_2026-04-10T10-00-00/iteration_001/outputs/phase4-dev-7f3c91ad-I05.md",
        "excerpt": "## Plan\n1. Review the repo.\n2. Apply the fix.",
        "artifact_ref": {
          "path": "runs/run_2026-04-10T10-00-00/iteration_001/outputs/phase4-dev-7f3c91ad-I05.md",
          "label": "v1 output for phase4-dev-7f3c91ad-I05"
        }
      },
      "after_output": {
        "locator": "runs/run_2026-04-10T10-00-00/iteration_003/outputs/phase4-dev-7f3c91ad-I05.md",
        "excerpt": "## Plan\n1. Review the repo.\n2. Apply the fix.",
        "artifact_ref": {
          "path": "runs/run_2026-04-10T10-00-00/iteration_003/outputs/phase4-dev-7f3c91ad-I05.md",
          "label": "v3 output for phase4-dev-7f3c91ad-I05"
        }
      },
      "score_changes": [],
      "metadata_changes": []
    }
  ]
}
```

Rules:
- `shared_input_summary` aggregates the exact joined rows from `per_input[]`; never count rows from a rejected or mismatched comparison.
- `shared_input_summary.total_shared_inputs` must equal the `per_input[]` length and must also equal `improved + regressed + unchanged`.
- Classify each shared input by score outcome, not metadata-only edits. Prefer the `weighted_points` delta when present; otherwise derive the bucket from `pass_fail` transitions. Metadata-only changes stay in `unchanged`.
- `per_input[]` contains exactly one row per shared stable `input_id`, joined only after the comparison preflight passes.
- `before_output` and `after_output` are output objects, not raw strings. Each object must carry a stable `locator`, a human-readable `excerpt`, and an `artifact_ref` back to the persisted output artifact used for comparison.
- `score_changes[]` records only the score fields that changed for that input, for example `pass_fail`, `weight`, `weighted_points`, or `normalized_contribution`.
- `metadata_changes[]` records only metadata that changed for that input, for example `reasoning_trace`, evidence locators, regression annotations, or token estimates.
- Leave `score_changes` and `metadata_changes` empty when nothing changed for that input.

---

## Quick Start > Mini Phase 3 Template

Read when: Quick Start QS Step 2 active.

### Input Generation
Map Phase 1 gaps to inputs (one input per gap, max 5). If fewer than 5 gaps, fill remaining slots from the diversity spread — pick to maximize diversity (prioritize different length categories first):
- 1 short+simple, 1 short+complex, 1 medium+complex, 1 long+simple, 1 long+complex
- Example: 3 gaps → 2 remaining → pick 1 short+simple and 1 long+complex (maximizes length spread)

Length thresholds (same as Smart Sampling): short (<500 chars), medium (500-2000), long (>2000).

For interactive/session-spanning skills: create synthetic output fixtures instead of running the skill live. Same fallback as Standard Phase 3 Step 1.

### Trace Presentation Format
```
--- Trace N/5 ---
Input: [1-2 sentence summary of the input]
Output: [full skill output]

Pass or Fail? (one-line note if Fail)
```

---

## Quick Start > Bootstrap Eval Generator

Read when: Quick Start QS Step 3 active.

### Conversion Rules
**Phase 1 gap → structural eval:**
- "Missing gotchas section" → "Does the output include a gotchas/warnings section? Pass/Fail."
- "No progressive disclosure" → "Does the output use headers/sections to organize content? Pass/Fail."
- "Weak instructional voice" → "Does the output use 'Do X because Y' format for directives? Pass/Fail."

**Mini Phase 3 failure → behavioral eval:**
- User note "missed the main entity" → "Does the output reference the primary entity from the input? Pass/Fail."
- User note "too vague" → "Does the output include specific, concrete examples? Pass/Fail."
- User note "wrong format" → "Does the output follow the expected structure? Pass/Fail."

**Rule:** Prefer code-based (grep, regex, field presence) over agent-as-judge. Only use judge for subjective criteria.

### Bootstrap Judge Template (Zero-Shot)
Bootstrap judges use a simplified template — NO few-shot examples, NO train split (5 traces is too few).

```
You are an evaluator. Assess whether the skill output meets this criterion:

CRITERION: [specific criterion from failure taxonomy or Phase 1 gap]

PASS: [concrete, observable success — one sentence]
FAIL: [concrete failure — one sentence, with example from Mini Phase 3 if available]

Read the input and output below, then respond with:
Critique: 1. Criterion check: [state whether the criterion is met] 2. Evidence: [cite the concrete evidence] 3. Verdict link: [explain why that evidence leads to Pass or Fail]
Result: Pass or Fail
```

### Per-Eval Metadata
Tag EACH bootstrap eval individually in eval-suite.md (not as a suite-level header):
```
EVAL 1: Missing Gotchas Check
Question: Does the output include a gotchas/warnings section?
Pass: Gotchas section present with ≥1 specific warning
Fail: No gotchas section or only generic warnings
Why: Phase 1 found "Missing gotchas section"
Source: quick_start | Validated: false | Confidence: directional
```

When Standard Phase 6 validates a specific bootstrap eval with TPR/TNR > 90%, update THAT eval's tag: `Validated: true | Confidence: calibrated`. Do not mark other evals as validated.

---

## Quick Start > Directional Results Template

Read when: Quick Start QS Step 5 active.

```
## Quick Start Results — DIRECTIONAL (not validated)

### Before
[Phase 1 audit score summary]

### After (2-3 mutations applied)
[Updated score, which evals flipped, mutation descriptions]

### What Changed
- Experiment 1: [description] — [keep/discard] (directional score: X%)
- Experiment 2: [description] — [keep/discard] (directional score: X%)

### Confidence Note
These results use bootstrap evals (not validated with TPR/TNR).
Improvements are directional — run Standard for calibrated measurement.

### Next Steps
- Run Standard to validate evals and get calibrated scores
- Or run Quick again for more mutations with current bootstrap evals
```

---

## Quick Start > State Schema

Read when: Quick Start QS Step 5 (state update) or Initialize Workspace.

### state.json after Quick Start
```json
{
  "schema_version": 4,
  "skill_name": "<name>",
  "skill_path": "<path>",
  "original_skill_path": "<path>",
  "workspace_path": "<path>",
  "started": "<today>",
  "current_phase": 0,
  "current_gulf": 1,
  "phases": {"design_audit": "complete"},
  "gates": {"gulf_1": "pending", "gulf_2": "pending"},
  "hamel_available": false,
  "loop_iteration": 0,
  "locked_judges": [],
  "memory_path": null,
  "checkpoint": null,
  "consecutive_discards": 0,
  "circuit_breaker": null,
  "quick_start": {
    "completed": true,
    "mini_phase_3_traces": 5,
    "bootstrap_evals": 4,
    "mutations_run": 3,
    "scoring_inputs": 8,
    "timestamp": "<ISO-timestamp>"
  }
}
```

**Schema migration:** When reading state.json with `schema_version: 2`, treat as legacy — Quick Start not available, proceed with Standard/Deep routing only. When reading `schema_version: 3`, treat as legacy Quick Start (v2.2) — read-compatible with v2.3, checkpoint fields default to null. New workspaces and Quick Start completions both write schema_version 4.

---

## The Three Gulfs

Read when: user asks "why this order" or "why can't I skip to autoresearch."

### Gulf 1: Comprehension
**Gap:** What you think your skill does vs. what it actually does.
**How to close:** Manual error analysis. Read every output. No automation can close this.

### Gulf 2: Specification
**Gap:** What you want your skill to do vs. what your judges actually measure.
**Depends on Gulf 1.** You can't write good judges without seeing real failures.

### Gulf 3: Generalization
**Gap:** Test performance vs. real-world performance on unseen inputs.
**This is AutoResearch.** But only works if Gulfs 1-2 are closed.

### Why You Can't Skip
| Approach | Result |
|----------|--------|
| AutoResearch without manual reading | Scores up, skill worse. Optimized wrong things. |
| Structured inputs but no manual reading | Better inputs, judges still measuring imagined targets. |
| Manual reading → taxonomy → judges → AutoResearch | Actually improved the skill. |

> "If you are not willing to look at some data manually on a regular cadence you are wasting your time with evals." — Hamel Husain

---

## Phase 1 Design Audit Dimension Schema

Read when: Phase 1 active, formatting `design-audit.md`, or serializing/comparing design-audit results between versions.

Use this canonical ordering whenever a Phase 1 audit is represented structurally. Do not reorder dimensions ad hoc. `scripts` stays last because it is conditional; `description_quality` is part of the core audit set and must appear before any conditional script assessment.

| Order | Canonical key | Label | Score type | Allowed values | Applicability |
|-------|---------------|-------|------------|----------------|---------------|
| 1 | `gotchas` | Gotchas | `ordinal_presence_with_na` | `present`, `partial`, `missing`, `n/a` | `n/a` only when no gotcha category applies |
| 2 | `voice` | Instructional Voice | `ordinal_presence` | `present`, `partial`, `missing` | always scored |
| 3 | `progressive_disclosure` | Progressive Disclosure | `ordinal_presence` | `present`, `partial`, `missing` | always scored |
| 4 | `anti_railroading` | Anti-Railroading / Flexibility | `ordinal_presence` | `present`, `partial`, `missing` | always scored |
| 5 | `description_quality` | Description Quality / Trigger Precision | `ordinal_presence` | `present`, `partial`, `missing` | always scored; missing/weak frontmatter descriptions score `missing` or `partial`, never `n/a` |
| 6 | `scripts` | Composable Scripts | `ordinal_presence_with_na` | `present`, `partial`, `missing`, `n/a` | `n/a` when the skill ships no scripts/helpers |

### Canonical structured payload

When Phase 1 emits a structured audit payload, include the chosen primary pattern as a top-level `selected_skill_pattern` field and the resolved downstream selector as a top-level `selected_eval_strategy_id` field. Source both from the active run's `state.json.phase1_context` values rather than inferring them from prose or requiring downstream consumers to reopen state.
If Phase 1 replays the production routing fixtures, aggregate the full ordered batch under top-level `phase1_routing_fixture_result_collection` so downstream comparisons can read one comparable collection keyed by `input_id`. That wrapper must also expose `per_skill_trigger_precision` so humans can inspect grouped trigger precision and every incorrect route decision by expected routed skill.
`description_quality` should also expose per-skill trigger-precision reports with `score`, `evidence`, and `mismatches` when routing fixtures are replayed.

```json
{
  "selected_skill_pattern": "pipeline",
  "selected_eval_strategy_id": "pipeline_eval_strategy",
  "dimension_order": [
    "gotchas",
    "voice",
    "progressive_disclosure",
    "anti_railroading",
    "description_quality",
    "scripts"
  ],
  "dimensions": {
    "gotchas": {"score": "present", "score_type": "ordinal_presence_with_na"},
    "voice": {"score": "partial", "score_type": "ordinal_presence"},
    "progressive_disclosure": {"score": "missing", "score_type": "ordinal_presence"},
    "anti_railroading": {"score": "partial", "score_type": "ordinal_presence"},
    "description_quality": {"score": "present", "score_type": "ordinal_presence"},
    "scripts": {"score": "n/a", "score_type": "ordinal_presence_with_na"}
  },
  "description_quality": {
    "fixture_set_id": "production-routing-phase1",
    "comparison_key": "input_id",
    "evaluated_skills": [
      {
        "fixture_skill": {
          "skill_id": "vercel_deploy_precise",
          "label": "vercel-deploy-precise",
          "relative_path": "vercel-deploy-precise/SKILL.md",
          "absolute_path": "/abs/path/dev/tests/fixtures/production-routing-phase1/vercel-deploy-precise/SKILL.md"
        },
        "score": "present",
        "evidence": {
          "total_matches": 4,
          "total_evaluated_routes": 4,
          "overall_precision": 1.0
        },
        "mismatches": []
      }
    ]
  },
  "phase1_routing_fixture_result_collection": {
    "fixture_set_id": "production-routing-phase1",
    "comparison_key": "input_id",
    "total_results": 6,
    "aggregate_trigger_precision": {
      "total_matches": 6,
      "total_evaluated_routes": 6,
      "overall_precision": 1.0
    },
    "per_skill_trigger_precision": [
      {
        "fixture_skill": {
          "skill_id": "vercel_deploy_precise",
          "label": "vercel-deploy-precise",
          "relative_path": "vercel-deploy-precise/SKILL.md",
          "absolute_path": "/abs/path/dev/tests/fixtures/production-routing-phase1/vercel-deploy-precise/SKILL.md"
        },
        "total_matches": 4,
        "total_evaluated_routes": 4,
        "overall_precision": 1.0,
        "mismatch_details": []
      }
    ],
    "phase1_routing_fixture_results": []
  }
}
```

If only prose output is emitted, keep the same order in the summary line so diffs remain comparable.

## V2.0 Design Audit Rubric

Read when: Phase 1 active.

### Dimension 1: Gotchas Section
- Target 5-9 per skill. Each names a specific failure, explains WHY, states consequence.
- Good: "**Dashboard needs HTTP serving.** fetch() fails on file:// due to CORS."
- Bad: "Be careful with large files."

### Dimension 2: Instructional Voice
- Sample 5-10 directives. Count "Do X because Y" vs "X is Y."
- At Standard: >80% instructional. Partial: 40-80%. Missing: <40%.
- Before: "Causal forests estimate heterogeneous treatment effects"
- After: "Use causal forests when you need CATE estimates across segments because they handle high-dimensional covariates without pre-specifying interactions"

### Dimension 3: Progressive Disclosure
- Is the skill a folder or single file? Do references have `Read when:` tags?
- Flat reference lists waste context budget.

### Dimension 4: Anti-Railroading / Flexibility
- Sample the 3-5 strongest constraints (`must`, `always`, `exactly`, fixed tool/path/order/format requirements).
- Present: Instructions explain the invariant or success condition, then let the agent adapt the path. Exact sequencing appears only when correctness truly depends on it, and acceptable fallbacks are named when relevant.
- Partial: Mixed mode. Some instructions are outcome-based, but at least one hardcodes tool choice, path, ordering, or format without explaining why the exact path matters.
- Missing: The dominant interaction is railroading. Success depends on following an exact route, exact output structure, or exact tool choice with no room to adapt when the environment differs from the happy path.
- Flag an overspecific instruction when it is likely to fail edge cases such as already-complete work, missing prerequisites, partial state, unexpected errors, or alternate valid structures.
- Quote the rigid instruction and name the blocked adaptation in the audit output. Example: "Instruction says to always run ripgrep first, but the task may begin from a known file path where direct inspection is the correct faster path."
- Pipeline exception: pipeline-pattern skills may enforce stage order. Do not penalize stage sequencing by itself; only score Partial/Missing when the stage hardcodes implementation details that should remain adaptable inside the stage.
- Calibrate Present/Partial/Missing with the selected profile from `Anti-Railroading Calibration Profile Schema`; the shared rubric stays constant, but each pattern gets its own rigidity budget and heuristic emphasis.

### Dimension 5: Description Quality / Trigger Precision
- Score the frontmatter `description:` field using the canonical key `description_quality`.
- Apply the production-routing lens while scoring: if a production agent only saw this description during skill discovery, could it decide when to invoke the skill with acceptable precision?
- Present: Description is written as invocation logic, not a label. It names concrete user intents, task states, or environment cues and gives enough boundary to distinguish the skill from nearby alternatives.
- Treat `present` as the `precise` anchor: the description should tell an evaluator exactly why this skill matches now and why a nearby skill does not. Example: "Use when the user asks to deploy to Vercel, inspect build logs, or verify deployment health after a release."
- Production routing consequence for `present`: Production router can auto-select the skill with high precision and explain the match from description alone.
- Partial: Description contains some trigger hints, but they are broad, incomplete, or mixed with summary language, so the invocation boundary is still fuzzy.
- Treat `partial` as the `ambiguous` anchor: the domain is visible, but the routing boundary is not. Example: "Helps with Vercel deployments and debugging." This suggests a topic area without making clear when this skill should win over neighboring deployment, logging, or general debugging skills.
- Production routing consequence for `partial`: Production router may shortlist the skill, but should require secondary evidence or human review before auto-selection.
- Missing: Description is absent, generic, tautological, or only a capability summary.
- Treat `missing` as the `over-broad` anchor when the description turns into a catch-all. Example: "Use for web apps, deployment, debugging, and infrastructure tasks." Even though it names activities, the scope is so wide that a router cannot tell what should be excluded.
- Production routing consequence for `missing`: Production router cannot rely on it; the skill will be over-selected, under-selected, or silently missed.
- Never score `n/a`. If the frontmatter description is absent, that absence is the failure.
- Prefer trigger wording like "Use when the user asks to deploy to Vercel or inspect deployment health," not summary wording like "Vercel deployment helper."
- When replaying or calibrating this dimension against the production routing fixtures, treat `manifest.json` as source material only. Normalize it into `expected_routing_fixtures[]` first, then build one Phase 1 routing evaluation input per canonical `prompt_cases[]` entry.
- Downstream Phase 1 routing evaluation must consume the canonical payload shape: `description_quality.score`, `routing_rationale`, `source.relative_path|absolute_path|skill_text`, and `prompt_case.case_id|prompt|expected_routing_outcome|rationale`. Do not read manifest-era keys like `description_quality_score`, `path`, or `prompts` once normalization is complete.
- When Phase 1 persists the replay, surface the grouped trigger-precision evidence under top-level `description_quality` as one report per evaluated skill. Each `description_quality.evaluated_skills[]` item should preserve the expected `score` anchor (`present`, `partial`, `missing`), an `evidence` block (`total_matches`, `total_evaluated_routes`, `overall_precision`), and the exact `mismatches` copied from the canonical grouped routing results.

### Phase 1 Routing Fixture Run Result Schema

Emit one canonical Phase 1 routing result per `input_id`.
Preserve fixture identity separately from evaluator outcome and routing-decision normalization so later version-to-version comparisons can join identical prompt cases across runs without rereading raw manifests.
`routing_decision.actual_rank` and `routing_decision.expected_rank` use the shared scale `do_not_route=0`, `shortlist_only=1`, `auto_select=2`.
`fixture_identity.fixture_skill` captures the normalized fixture-skill identity for the routed SKILL.md under test.
`fixture_identity.trigger_metadata.expected_routing_outcome` preserves the canonical expected fixture route for the prompt case.
`evaluator_outcome.fixture_route_match_status` records `matched_fixture_route` or `mismatched_fixture_route` from the normalized comparison.
`routing_decision.selected_skill` captures the evaluator's actual selected skill when present.
`routing_decision.routing_metadata.shortlist_count` preserves how many skills the evaluator shortlisted.
When Phase 1 persists the routing replay into its structured output, aggregate the ordered per-input rows under top-level `phase1_routing_fixture_result_collection`.
`phase1_routing_fixture_result_collection` must preserve `fixture_set_id`, `comparison_key`, `total_results`, `aggregate_trigger_precision`, `per_skill_trigger_precision`, and the ordered `phase1_routing_fixture_results[]` array unchanged.
`aggregate_trigger_precision` summarizes the full fixture replay with `total_matches`, `total_evaluated_routes`, and `overall_precision`.
`per_skill_trigger_precision` groups the same comparison results by `fixture_identity.fixture_skill` and recomputes `total_matches`, `total_evaluated_routes`, and `overall_precision` for each expected routed skill.
Each `per_skill_trigger_precision[].mismatch_details[]` entry must preserve the incorrect route's `input_id`, `case_id`, `prompt`, expected vs actual routing outcomes, miss direction (`decision_delta_label`), and normalized selection context (`selected_skill`, `routing_metadata`).

Canonical single-run payload:

```json
{
  "input_id": "vercel_deploy_precise__vercel_deploy_precise_case_01",
  "fixture_identity": {
    "fixture_id": "vercel_deploy_precise",
    "case_id": "vercel_deploy_precise_case_01",
    "summary": "Precise invocation description for a Vercel deployment and health skill.",
    "description_quality": {"score": "present"},
    "source": {
      "relative_path": "vercel-deploy-precise/SKILL.md",
      "absolute_path": "/abs/path/dev/tests/fixtures/production-routing-phase1/vercel-deploy-precise/SKILL.md"
    },
    "prompt": "Deploy this Next.js app to Vercel and explain why the preview build is failing after the latest commit.",
    "fixture_skill": {
      "skill_id": "vercel_deploy_precise",
      "label": "vercel-deploy-precise",
      "relative_path": "vercel-deploy-precise/SKILL.md",
      "absolute_path": "/abs/path/dev/tests/fixtures/production-routing-phase1/vercel-deploy-precise/SKILL.md"
    },
    "trigger_metadata": {
      "routing_rationale": "Description names concrete user intents and excludes nearby non-Vercel work, so matched prompts can auto-route from description alone.",
      "case_rationale": "The prompt explicitly asks for a Vercel deployment and preview build diagnosis, which the description names directly.",
      "expected_routing_outcome": "auto_select"
    }
  },
  "evaluator_outcome": {
    "pass_fail": "pass",
    "matched_expected_outcome": true,
    "fixture_route_match_status": "matched_fixture_route"
  },
  "routing_decision": {
    "expected_routing_outcome": "auto_select",
    "expected_rank": 2,
    "actual_routing_outcome": "auto_select",
    "actual_rank": 2,
    "decision_delta": 0,
    "decision_delta_label": "matched_expected",
    "selected_skill": {
      "skill_id": "vercel_deploy",
      "label": "Vercel Deploy",
      "relative_path": "vercel-deploy-precise/SKILL.md",
      "absolute_path": "/abs/path/dev/tests/fixtures/production-routing-phase1/vercel-deploy-precise/SKILL.md"
    },
    "routing_metadata": {
      "selection_mode": "description_only",
      "selection_reasoning": "The prompt explicitly asks for a Vercel deployment.",
      "confidence": 0.97,
      "shortlist_count": 2,
      "shortlist": [
        {
          "skill_id": "vercel_deploy",
          "label": "vercel_deploy",
          "relative_path": "vercel-deploy-precise/SKILL.md",
          "absolute_path": ""
        },
        {
          "skill_id": "vercel_observability",
          "label": "vercel_observability",
          "relative_path": "",
          "absolute_path": ""
        }
      ]
    }
  }
}
```

Field intent:
- `input_id` is the stable join key for cross-run comparison of the same routing prompt case.
- `fixture_identity` preserves the canonical fixture case metadata needed for explanation and audit without embedding the full raw manifest row.
- `fixture_identity.fixture_skill` makes the expected routed SKILL.md inspectable without reconstructing an identity from the fixture path later.
- `fixture_identity.trigger_metadata` preserves the fixture-side trigger context that justified the expected route for this case.
- `evaluator_outcome.pass_fail` is derived from the normalized routing comparison, not from presentation order or freeform prose.
- `evaluator_outcome.fixture_route_match_status` gives the same comparison a stable human-readable label for match/mismatch reporting.
- `per_skill_trigger_precision` turns the flat comparison batch into a grouped trigger-precision report so humans can inspect route quality per expected skill instead of only at the aggregate fixture-set level.
- `mismatch_details` ensures every incorrect route decision stays explainable without rereading the entire `phase1_routing_fixture_results[]` array.
- `routing_decision` stores the canonical expected/actual outcomes plus shared integer ranks so comparison code can detect a tighter or broader decision numerically.
- `decision_delta_label` uses `matched_expected`, `under_triggered`, or `over_triggered` so humans and downstream diffing code can classify the miss direction without re-deriving it.
- `selected_skill` preserves the evaluator's chosen skill identity when the router actually selected something, rather than flattening that detail into prose only.
- `routing_metadata` preserves evaluator-side routing context like confidence, selection reasoning, and shortlist size so later comparison can distinguish the same outcome reached with different evidence.

### Dimension 6: Composable Scripts (if applicable)
- `__all__`, type hints, `Use when:` docstrings, `if __name__` demos.

### Anti-Railroading Calibration Profile Schema

Read when: Phase 1 Step 1 is scoring `anti_railroading` after `skill_pattern` classification is complete.

Use the current skill-under-test's profile keyed by `state.json.skill_pattern` before scoring `anti_railroading`.
That `skill_pattern` must come from the active workspace copy at `[workspace]/skill-under-test/SKILL.md`; do not substitute a generic default or calibration data resolved for another skill or version.
For the active run, read the same canonical ID from `state.json.phase1_context.selected_skill_pattern`; `state.json.skill_pattern` remains only the compatibility mirror.

Canonical configuration shape:

```yaml
profile_id: `<skill_pattern>_anti_railroading`
applies_to_pattern: `<pattern_id>`
thresholds:
  strongest_constraints_sample: <integer, normally 3-5>
  partial_floor: <pattern-defined threshold>
  missing_floor: <pattern-defined threshold>
heuristic_settings:
  <pattern_specific_toggle>: <value>
required_evidence:
  - <minimum audit proof required before partial/missing>
```

Field intent:
- `profile_id` is the stable configuration identifier for the anti-railroading profile selected in Phase 1.
- `applies_to_pattern` binds the profile to exactly one canonical `skill_pattern`.
- `thresholds` define the Present/Partial/Missing budgets for that pattern.
- `heuristic_settings` define pattern-aware interpretation knobs that change how rigid instructions are judged.
- `required_evidence` defines the minimum audit evidence that must be present before assigning `partial` or `missing`.

Scoring rules:
- Start from the shared anti-railroading rubric above, then interpret it through the selected profile's `thresholds` and `heuristic_settings`.
- Profiles can protect legitimate invariants without excusing unrelated rigidity. Calibration changes the threshold, not the requirement to cite evidence.
- If a profile threshold and the shared rubric appear to disagree, prefer the stricter interpretation and log the ambiguity in the audit output.

### Skill-Pattern-to-Calibration-Profile Resolution

Read when: Phase 1 Step 1 has already classified the current workspace copy's `state.json.skill_pattern` and Phase 1 Step 2 needs a concrete anti-railroading profile for that skill before scoring.

Resolve exactly one anti-railroading profile from `state.json.skill_pattern` before scoring `anti_railroading`.
Use the current skill-under-test's resolved `skill_pattern`; never fall back to a generic profile or a profile resolved for a different skill/version.
Resolve against `state.json.phase1_context.selected_skill_pattern` for the active run, then verify the mirrored top-level `state.json.skill_pattern` matches before continuing.

Resolution table:
- `tool_wrapper` -> `tool_wrapper_anti_railroading`
- `generator` -> `generator_anti_railroading`
- `reviewer` -> `reviewer_anti_railroading`
- `inversion` -> `inversion_anti_railroading`
- `pipeline` -> `pipeline_anti_railroading` (exempt/no-penalty for stage-order invariants)

Resolution contract:
- The mapping is one-to-one. Do not score `anti_railroading` until one `profile_id` is selected from this table.
- The `skill_pattern` source of truth is the active run's classification of `[workspace]/skill-under-test/SKILL.md`. Do not reuse cached resolution data from another skill, earlier version, or prior run.
- `profile_id` is the explainable artifact selected by the classifier; the profile body loaded afterward must still match the same `applies_to_pattern`.
- The loaded profile body must match both `profile_id` and `applies_to_pattern` for the current skill-under-test. If either key points to generic fallback data or another skill/version's resolution context, treat the resolution as invalid and rerun selection against the current workspace skill.
- `pipeline` resolves to the stage-order exemption path by default because ordered phases are part of the pipeline invariant, not evidence of railroading on their own.
- Emit the resolution mode alongside the selected profile so humans can verify why the profile was chosen.
- Carry the resolved `profile_id` and `resolution_mode` into runtime anti-railroading scoring; profile selection is not documentation-only.
- When `resolution_mode` is `exempt_no_penalty_stage_order`, suppress penalty application if the only rigidity evidence is stage ordering itself.
- When the active skill is classified as `pipeline`, skip the anti-railroading penalty branch entirely instead of entering a suppress-after-the-fact penalty path.
- Treat pipeline stage-order invariants and stage-local rigidity observations as explanatory audit notes only, not penalty inputs.
- Do not count exempt stage-order invariants toward `partial_floor`, `missing_floor`, or overspecific-instruction totals.

Canonical resolution payload:

```yaml
skill_pattern: `<pattern_id>`
profile_id: `<resolved_profile_id>`
resolution_mode: `<standard_resolution | exempt_no_penalty_stage_order>`
```

For `pipeline`, use:
- `profile_id: pipeline_anti_railroading`
- `resolution_mode: exempt_no_penalty_stage_order`

#### Tool Wrapper Profile

Pattern ID: `tool_wrapper`
profile_id: `tool_wrapper_anti_railroading`
applies_to_pattern: `tool_wrapper`

thresholds:
- strongest_constraints_sample: 3
- partial_floor: 1 overspecific instruction in the sampled set
- missing_floor: 2 or more overspecific instructions, or one instruction that blocks reference verification entirely
- reference_lookup_mandate_budget: 1

heuristic_settings:
- Treat "consult official docs first" as legitimate until the skill hardcodes more than one exact lookup route with no allowed fallback.
- Penalize rigidity fastest when the skill forces one vendor command, one site path, or one reference source even though equivalent authoritative sources exist.
- Stable response-card formatting is not railroading by itself unless the format suppresses the actual answer or blocks alternate evidence.

required_evidence:
- Quote the exact reference-loading instruction being evaluated.
- Name the blocked adaptation, such as using a bundled note, direct file read, or another authoritative doc source.
- Explain whether the rigidity threatens freshness, factual verification, or tool availability.

#### Generator Profile

Pattern ID: `generator`
profile_id: `generator_anti_railroading`
applies_to_pattern: `generator`

thresholds:
- strongest_constraints_sample: 4
- partial_floor: 1 overspecific instruction that exceeds the output contract
- missing_floor: 2 or more overspecific instructions that dictate route instead of just output quality
- required_output_slots_before_partial: 2

heuristic_settings:
- Protect true schema requirements and reusable templates; do not penalize output slots that are intrinsic to the artifact contract.
- Penalize rigidity when the skill prescribes the drafting path, intermediary tools, or section-writing order without tying them to output quality.
- Treat filler instructions as overspecific when they require exact wording or section order beyond what the declared template needs.

required_evidence:
- Quote both the rigid instruction and the underlying output contract it claims to serve.
- Name the alternate valid structure or drafting path that would still satisfy the contract.
- State whether the instruction is guarding required fields or merely imposing a happy-path composition order.

#### Reviewer Profile

Pattern ID: `reviewer`
profile_id: `reviewer_anti_railroading`
applies_to_pattern: `reviewer`

thresholds:
- strongest_constraints_sample: 4
- partial_floor: 1 rubric step that is over-locked without severity justification
- missing_floor: 2 or more over-locked rubric steps, or one lock that prevents a justified finding shape
- rubric_step_lock_budget: 1

heuristic_settings:
- Checklist order is acceptable when it protects evidence collection or severity calibration, but not when it dictates a single narrative shape for findings.
- Penalize exact remediation wording, forced issue counts, or mandatory finding order when the rubric's real invariant is calibrated judgment.
- A reviewer may demand evidence-backed findings; that is not railroading unless the evidence route is singular without reason.

required_evidence:
- Quote the locked review step, checklist rule, or report-format instruction.
- Name the blocked judgment adaptation, such as reordering findings by severity or merging duplicate issues.
- Explain whether the rule protects review quality or merely enforces one presentation path.

#### Inversion Profile

Pattern ID: `inversion`
profile_id: `inversion_anti_railroading`
applies_to_pattern: `inversion`

thresholds:
- strongest_constraints_sample: 4
- partial_floor: 1 question gate that remains rigid after ambiguity is materially reduced
- missing_floor: 2 or more rigid gates, or one gate that blocks safe execution after readiness is clear
- question_gate_rigidity_budget: 1

heuristic_settings:
- Protect true requirement-gathering gates; a stop condition is expected for inversion skills.
- Penalize repeated boilerplate question rounds, mandatory question counts, or exact interview order once the missing uncertainty is already resolved.
- Treat adaptive clarification as healthy flexibility even when the skill insists on gathering requirements before action.

required_evidence:
- Quote the gate, threshold, or mandatory question instruction.
- Name the blocked adaptation, such as moving to execution once sufficient answers exist or skipping already-answered questions.
- Explain why the gate is no longer reducing ambiguity in the specific edge case.

#### Pipeline Profile

Pattern ID: `pipeline`
profile_id: `pipeline_anti_railroading`
applies_to_pattern: `pipeline`

thresholds:
- strongest_constraints_sample: 5
- partial_floor: 1 stage-level implementation lock that is not justified by the stage invariant
- missing_floor: 2 or more unjustified stage-level locks, or one lock that blocks safe resume/continue behavior
- stage_order_is_not_a_penalty: true

heuristic_settings:
- Preserve explicit phase order, gate checks, and state transitions. Those are invariants for pipeline skills.
- Skip the anti-railroading penalty branch entirely once the active skill resolves to the pipeline profile.
- Surface stage-local implementation locks as explanatory audit notes so humans can inspect resume/fallback risk without converting those notes into Partial/Missing penalties.
- Escalate quickly when a stage assumes a happy-path filesystem state, one exact command, or one artifact layout and offers no resume-safe fallback.

required_evidence:
- Quote the stage instruction and name the stage invariant it is trying to protect.
- Name the blocked adaptation inside the stage, such as resume from partial state, alternate artifact location, or equivalent verification command.
- Explain why the stage order is still valid while the implementation detail is overspecified.

---

## Eval Audit Categories

Read when: Phase 2 active.

1. **Error analysis grounding** — Were evals built from observed failures, or brainstormed?
2. **Evaluator design** — Binary pass/fail? Or vague Likert scales? Holistic evals bundling multiple failure modes?
3. **Judge validation** — Any TPR/TNR measurements? Golden dataset? Or untested judges?
4. **Train/test split** — Same fixtures for iteration AND measurement? (= data leakage)
5. **Labeled data** — How many labeled examples? Target: >50. Under 25 is critical gap.
6. **Maintenance** — Process for re-auditing after skill changes? Or "set and forget"?

---

## Smart Sampling Methodology

Read when: Phase 3 active, or user asks about sampling strategy.

### Why 8-10 traces, not all 20+
Full review provides maximum coverage but creates HITL friction that blocks adoption. 8-10 traces with stratified sampling captures dimension coverage while keeping review under 30 minutes.

### Lightweight dimensions (pre-Phase 4)
- **Input length:** short (<500 chars), medium (500-2000), long (>2000)
- **Fixture source:** generated / real / synthetic
- **Planted flaw:** yes / no

On re-runs, Phase 4 dimensions automatically take over.

### Consistency detection algorithm
After each judgment (starting at review #5): scan prior traces with same cluster ID. Flag if different verdicts. Purpose: prompt reflection, not enforce consistency.

---

## Eval Suite Template

Read when: Phase 3 Step 7 or writing evals.

```
EVAL 1: [Name]
Question: [specific yes/no question]
Pass: [what success looks like]
Fail: [what failure looks like]
Why: [which observed failure mode this catches]
```

---

## Dimension Template

Read when: Phase 4 Step 2.

```
Dimension 1: [Name] — [What it captures]
  Values: [value_a, value_b, value_c, ...]
```
Example: Session Length × Domain Type × Error Density.

### Train/Dev/Test Split
| Split | Size | Purpose | Rules |
|-------|------|---------|-------|
| **Train** | ~15% (5-6) | Few-shot examples for judge prompts | Clear-cut Pass/Fail only |
| **Dev** | ~42% (13-17) | Iterative judge refinement | Never in judge prompts |
| **Test** | ~43% (13-17) | Final unbiased measurement | Do NOT look at during dev |

---

## Judge Prompt Template

Read when: Phase 5 Step 3 (building agent-as-judge prompts).

The coding agent itself IS the judge — no external API needed. Agent reads judge prompt + fixture, outputs verdict inline.

### 4 Required Components

**Component 1 — Task and criterion:**
```
You are an evaluator assessing whether [specific criterion from failure taxonomy].
```
One failure mode per judge. Never bundle multiple criteria.

**Component 2 — Pass/Fail definitions:**
```
PASS: [concrete, observable success]
FAIL: [concrete failure, with examples from Phase 3 traces]
```

**Component 3 — Few-shot examples (TRAIN split only):**
3 examples: clear Pass, clear Fail, borderline. Each must include critique BEFORE verdict.
```
### Example 1: PASS
Input: [fixture excerpt]
Critique: 1. Criterion check: [state whether the criterion is met] 2. Evidence: [reference specific evidence] 3. Verdict link: [explain why the evidence leads to Pass]
Result: Pass
```
**NEVER use dev or test examples.** This is data leakage.

**Component 4 — Output format:**
```
Critique: 1. Criterion check: [state whether the criterion is met] 2. Evidence: [reference specific evidence] 3. Verdict link: [explain why the evidence leads to Pass or Fail]
Result: Pass or Fail
```

---

## TPR/TNR Reference

Read when: Phase 6 active.

### Formulas
```
TPR = (judge says Pass AND human says Pass) / (human says Pass)
TNR = (judge says Fail AND human says Fail) / (human says Fail)
```
Target: >90% both. With 30-40 fixtures (~15 dev), treat as directional signal.

### Phase 6 Dev Fold Assignment
- Phase 6 cross-validation uses deterministic 3-fold assignment derived from stable input data.
- `stable_fold_key = <input_id>|<content_hash>`
- Sort the frozen dev split by `stable_fold_key`, then assign `fold_1`, `fold_2`, `fold_3` in repeating order down that sorted list.
- This keeps fold sizes within one item of each other while staying fully deterministic for a frozen dev set.
- Never derive fold membership from runtime iteration order, filesystem order, presentation order, or RNG state.
- Persist the finalized fold map in `judge-validation-report.md` under `phase6_dev_fold_assignments`.

Example payload:
```json
"phase6_dev_fold_assignments":[
  {"input_id":"phase4-dev-7f3c91ad-I01","content_hash":"91ab77ce...","stable_fold_key":"phase4-dev-7f3c91ad-I01|91ab77ce...","fold_id":"fold_1"},
  {"input_id":"phase4-dev-7f3c91ad-I02","content_hash":"42be3101...","stable_fold_key":"phase4-dev-7f3c91ad-I02|42be3101...","fold_id":"fold_2"},
  {"input_id":"phase4-dev-7f3c91ad-I03","content_hash":"6ca1b7d2...","stable_fold_key":"phase4-dev-7f3c91ad-I03|6ca1b7d2...","fold_id":"fold_3"}
]
```

### Phase 6 Dev Record Grouping
- Every persisted Phase 6 dev record must include `source_sample_group_id`.
- Derive `source_sample_group_id` from the frozen source sample, not from judge/run metadata: `source_sample_group_id = stable_fold_key = <input_id>|<content_hash>`.
- Reuse the same `source_sample_group_id` for every dev record emitted from the same underlying sample across judges, disagreement logs, and reruns.
- Never derive `source_sample_group_id` from batch order, row number, judge ID, retry count, or timestamps.

Example payload:
```json
"phase6_dev_records":[
  {"eval":"E2","input_id":"phase4-dev-7f3c91ad-I01","content_hash":"91ab77ce...","stable_fold_key":"phase4-dev-7f3c91ad-I01|91ab77ce...","source_sample_group_id":"phase4-dev-7f3c91ad-I01|91ab77ce...","fold_id":"fold_1","human_label":"pass","judge_label":"pass"},
  {"eval":"E5","input_id":"phase4-dev-7f3c91ad-I01","content_hash":"91ab77ce...","stable_fold_key":"phase4-dev-7f3c91ad-I01|91ab77ce...","source_sample_group_id":"phase4-dev-7f3c91ad-I01|91ab77ce...","fold_id":"fold_1","human_label":"pass","judge_label":"fail"}
]
```

### Disagreement Actions
| Type | Judge | Human | Fix |
|------|-------|-------|-----|
| False Pass | Pass | Fail | Strengthen Fail definitions or add edge-case examples |
| False Fail | Fail | Pass | Clarify Pass definitions or adjust examples |

### If alignment stalls
- Both low → sharper definitions + more specific examples
- One low → inspect disagreements for that metric
- Both <80% → decompose criterion into smaller atomic checks

---

## Results & Changelog Schemas

Read when: Phase 7 active.

### Changelog Format
```markdown
## Experiment N — [keep/discard]
**Score:** X/Y (Z%)
**Change:** [what was mutated]
**Reasoning:** [why this should help]
**Result:** [which evals flipped]
**Failing outputs:** [remaining failures, or "None"]
```

### Results.json experiment record
```json
{"id":N,"input_set_id":"phase4-dev-7f3c91ad","input_set_ref":"input-sets.json#phase4-dev-7f3c91ad","input_ids":["phase4-dev-7f3c91ad-I03","phase4-dev-7f3c91ad-I05","phase4-dev-7f3c91ad-I08"],"score":X,"max_score":Y,"pass_rate":Z,"status":"keep|discard|baseline","description":"...","changes":[{"type":"added|modified|removed","location":"section","snippet":"1-3 lines"}],"eval_results":[{"eval":"E1","pass_fail":"pass","reasoning_trace":"1. Criterion check: the rubric requires concrete gotcha warnings and the output includes them. 2. Evidence: the output contains a gotchas heading and 3 specific warnings. 3. Verdict link: because both the section and concrete warnings are present, this passes.","evidence":[{"kind":"output_excerpt","source":"skill_output","locator":"input_id:phase4-dev-7f3c91ad-I03 output lines 12-18","excerpt":"## Gotchas\\n- Never run rm -rf without checking the target path.","metric":null,"artifact_ref":null},{"kind":"metric","source":"scoring_metric","locator":"warnings_found","excerpt":"3 concrete warnings found in the gotchas section.","metric":{"name":"warnings_found","value":3,"unit":"count"},"artifact_ref":null}],"supporting_items":[{"stage":"criterion_check","decision":"gotchas heading is present","outcome":"met","evidence_refs":[0]},{"stage":"evidence_check","decision":"three concrete warnings were found","outcome":"met","evidence_refs":[1]},{"stage":"verdict_link","decision":"the rubric passes when both the heading and warning count are present","outcome":"supports_pass","evidence_refs":[0,1]}],"weight":1.0,"weight_source":"code_eval_fixed","weighted_points":1.0,"normalized_contribution":0.25}],"decision_breakdown":{"components":[{"eval":"E1","pass_fail":"pass","weight":1.0,"weight_source":"code_eval_fixed","weighted_points":1.0,"normalized_contribution":0.213}],"formula":"combined_score = weighted_points / total_weight","weighted_points":3.7,"total_weight":4.7,"combined_score":0.787,"combined_score_pct":78.7,"threshold":0.8,"proposed_decision":"discard"},"regression_check":null,"discard_autopsy":null}
```
Any result retrieval response schema or serializer that returns experiment records must include the stored `decision_breakdown` field unchanged so downstream dashboards and version-comparison views can explain the aggregation math.

- `input_set_id`: the scoring corpus used for this experiment.
- `input_set_ref`: exact pointer back to the registered set entry in `input-sets.json`.
- `input_ids`: exact stable inputs scored for this experiment, listed in finalized set order. Version comparisons are only valid when this matches across experiments.

## Judge Verdict Evidence Schema

Read when: Phase 7 records `eval_results[]` or iterates on judge verdict storage.

`evidence` is an array of objects, not strings. Use the smallest set of evidence objects that makes the verdict replayable by a human:

```json
{"kind":"output_excerpt","source":"skill_output","locator":"input_id:phase4-dev-7f3c91ad-I03 output lines 12-18","excerpt":"## Gotchas\\n- Never run rm -rf without checking the target path.","metric":null,"artifact_ref":null}
{"kind":"input_excerpt","source":"fixture_input","locator":"input_id:phase4-dev-7f3c91ad-I03 input lines 1-4","excerpt":"Please review this shell script and call out any dangerous commands.","metric":null,"artifact_ref":null}
{"kind":"metric","source":"scoring_metric","locator":"warnings_found","excerpt":"3 concrete warnings found in the gotchas section.","metric":{"name":"warnings_found","value":3,"unit":"count"},"artifact_ref":null}
{"kind":"artifact_ref","source":"workspace_artifact","locator":"runs/run_2026-04-10T10-00-00/iteration_002/eval_results.json","excerpt":"Stored verdict artifact for replay and dashboard inspection.","metric":null,"artifact_ref":{"path":"runs/run_2026-04-10T10-00-00/iteration_002/eval_results.json","label":"iteration eval results"}}
```

Required core fields:
- `kind`: one of `input_excerpt`, `output_excerpt`, `metric`, `artifact_ref`
- `source`: one of `fixture_input`, `skill_output`, `scoring_metric`, `workspace_artifact`
- `locator`: stable pointer to the cited thing (`input_id`, output line span, metric name, or artifact path)

Optional payload fields:
- `excerpt`: required for `input_excerpt` and `output_excerpt`; concise factual summary for `metric` or `artifact_ref` when useful
- `metric`: required when `kind = "metric"`; object shape: `{"name":"<metric>","value":<number|string>,"unit":"<unit|null>"}`
- `artifact_ref`: required when `kind = "artifact_ref"`; object shape: `{"path":"<workspace-relative-or-absolute-path>","label":"<human-readable label>"}`

Usage rules:
- `reasoning_trace` should only summarize facts that are grounded in `evidence[]`.
- A stored `pass_fail` verdict is invalid unless `evidence[]` contains at least one object.
- Prefer stable locators (`input_id:...`, `output lines 12-18`, `decision_breakdown.total_weight`, `runs/.../eval_results.json`) over vague prose.
- Store quoted inputs and outputs as `input_excerpt` or `output_excerpt`, numeric checks as `metric`, and replay/debug links as `artifact_ref`.
- Do not store opaque strings like `"looks good"` or `"seems wrong"` inside `evidence[]`.

## Judge Decision Support Schema

Read when: Phase 7 needs to preserve the concrete supporting items behind each verdict.

`supporting_items` is an array of structured sub-decisions. It sits next to `evidence[]`, not inside it, so the verdict can say which evidence objects supported each material judgment call:

```json
{"stage":"criterion_check","decision":"required gotchas section is present","outcome":"met","evidence_refs":[0]}
{"stage":"evidence_check","decision":"gotchas section includes 3 concrete warnings","outcome":"met","evidence_refs":[1]}
{"stage":"verdict_link","decision":"the rubric passes when the gotchas section and concrete warnings are both present","outcome":"supports_pass","evidence_refs":[0,1]}
```

Required fields:
- `stage`: one of `criterion_check`, `evidence_check`, `verdict_link`
- `decision`: concise factual statement of the sub-decision the judge made
- `outcome`: local result for that sub-decision. Use `met`, `not_met`, `supports_pass`, or `supports_fail`
- `evidence_refs`: array of zero-based indexes into `evidence[]`

Usage rules:
- Create one `supporting_items[]` entry for every material judgment call, not just the final verdict.
- Every `evidence_refs[]` entry must point to an existing object in `evidence[]`; do not invent citations that are not stored there.
- Keep the order aligned to `reasoning_trace`: criterion check first, then evidence check, then verdict link.
- If multiple supporting items rely on the same evidence object, reuse the same `evidence_refs` index instead of duplicating the evidence payload.
- Attach `supporting_items[]` to the same verdict record that produced the cited `evidence[]`; never reassign supporting items by array position, aggregation order, or a later rendering pass.
- Preserve `supporting_items[]` unchanged in the final judge output for that verdict so replay, dashboards, and version comparison all read the same sub-decision record.
- `reasoning_trace` must be reconstructible from `supporting_items[]` plus `evidence[]` without additional hidden context.

### decision_breakdown fields

The aggregation engine emits `decision_breakdown` for baseline and every mutation:

```json
{
  "components": [
    {
      "eval": "E1",
      "pass_fail": "pass",
      "weight": 1.0,
      "weight_source": "code_eval_fixed",
      "weighted_points": 1.0,
      "normalized_contribution": 0.213
    },
    {
      "eval": "E2",
      "pass_fail": "fail",
      "weight": 0.9,
      "weight_source": "phase_6_validation_average",
      "weighted_points": 0.0,
      "normalized_contribution": 0.0
    }
  ],
  "formula": "combined_score = weighted_points / total_weight",
  "weighted_points": 3.7,
  "total_weight": 4.7,
  "combined_score": 0.787,
  "combined_score_pct": 78.7,
  "threshold": 0.8,
  "proposed_decision": "discard"
}
```

- `components`: ordered aggregation inputs used in the keep/discard calculation. Persist the exact eval rows shown in the Aggregation Explainer so the decision record is self-contained and human-auditable even if `eval_results[]` rendering changes later. This field is populated as soon as scoring completes, not deferred until after user confirmation.
- `weighted_points`: numerator after applying pass/fail to each eval weight.
- `total_weight`: denominator used to normalize the score.
- `combined_score`: canonical keep/discard score in 0-1 form.
- `combined_score_pct`: same score in percent for user presentation.
- `threshold`: keep/discard threshold used for the recommendation.
- `proposed_decision`: `baseline`, `keep`, or `discard`.

### decision_explanation fields

The aggregation engine also emits `decision_explanation` for baseline and every mutation:

```json
{
  "final_decision": "discard",
  "summary": "E2 withheld 19.1% of the available score, while E1 added 21.3%; the mutation still finished below threshold.",
  "strongest_outcomes": [
    {
      "eval": "E2",
      "pass_fail": "fail",
      "impact": "supports_discard",
      "impact_magnitude": 0.191,
      "impact_basis": "missed_weight_share",
      "summary": "The failed high-weight eval withheld 19.1% of the available score."
    },
    {
      "eval": "E1",
      "pass_fail": "pass",
      "impact": "supports_keep",
      "impact_magnitude": 0.213,
      "impact_basis": "normalized_contribution",
      "summary": "The strongest pass added 21.3% toward keep, but the experiment still missed threshold."
    }
  ]
}
```

- `final_decision`: final keep/discard/baseline outcome that the explanation is describing.
- `summary`: concise sentence describing why the final decision happened. When both keep-supporting and discard-supporting signals exist, synthesize both in one balanced explanation and end by naming why the result was still kept or discarded.
- `strongest_outcomes`: ordered strongest-first list of the eval outcomes that mattered most to the final keep/discard. When mixed signals exist, include at least the strongest `supports_keep` outcome and the strongest `supports_discard` outcome before any additional outcomes of the same polarity.
- `impact`: whether that outcome supports `keep` or `discard`.
- `impact_magnitude`: normalized size of that outcome's effect. Use `normalized_contribution` for successful positive contributions and the withheld weight share when a failed eval supports discard.
- `impact_basis`: how the magnitude was computed, such as `normalized_contribution` or `missed_weight_share`.
- `summary` on each strongest outcome: one sentence connecting that outcome to the final decision.
- Mixed-signal synthesis rule: for `keep`, combine the strongest keep signal with the strongest discard signal as "positive pressure vs. drag," then explain why the keep signal still cleared threshold. For `discard`, combine the strongest discard signal with the strongest keep signal, then explain why the keep signal still missed threshold.
- Populate `decision_explanation` immediately after `decision_breakdown` is finalized so both records describe the same scoring event.
- Return the stored `decision_explanation` field unchanged anywhere experiment payloads are serialized, fetched, or shown. Never recompute `decision_explanation` on the retrieval path.

---

## Discard Autopsy Heuristics

Read when: Phase 7 step 2f, after a discard decision.

After each discard, classify WHY the mutation failed. This directs the next hypothesis instead of blindly trying again. Source: AutoKaggle's U4 rule ("Was this truly exhausted or just tried with wrong params?").

### 3-Way Classification

| Classification | When to use | Signal for next iteration |
|---|---|---|
| `wrong_target` | This section was tried 2+ times with negative or flat deltas. Evidence: multiple experiments targeting the same `changes[].location` with no improvement. | Explore a different, untried section. Check derived mutation registry for unexplored sections. |
| `wrong_params` | The section responded positively before (in a prior experiment) but this specific mutation regressed or was flat. The section is viable, the approach was wrong. | Retry the same section with a fundamentally different approach (e.g., rewrite vs. tweak, different examples, different framing). |
| `wrong_type` | The mutation was additive on an already-long section, or subtractive on a short/critical section, or modified when a full replacement was needed. The mutation direction (add/modify/delete) was the mismatch. | Try the opposite mutation type on the same section. If you added, try deleting. If you modified, try replacing entirely. |

### Decision Process

1. Read the discarded experiment's `changes[].location` and `changes[].type`
2. Check experiment history: was this section targeted before? What were the results?
3. If targeted 2+ times with negative/flat deltas → `wrong_target`
4. If targeted before with positive delta but this attempt failed → `wrong_params`
5. If first attempt on this section, check mutation type vs. section characteristics → `wrong_type` if mismatch is clear, `wrong_params` as default
6. When uncertain between `wrong_params` and `wrong_type`, prefer `wrong_params` (it's more actionable)

### Output Format

Record in `experiments[].discard_autopsy`:
```json
{"classification": "wrong_target", "reasoning": "gotchas section targeted 3 times, all negative deltas — section is not responsive to mutations"}
```

### Mini Mode

Discard autopsy runs in Mini mode. With only 2-3 experiments the history-based heuristics (rule 3-4) may not apply, but the type-based heuristic (rule 5) still helps direct the tiny budget.

---

## Derived Mutation Registry

Read when: Circuit breaker diagnosis, before hypothesizing mutations (step 2a), or when computing search diversity.

The mutation registry is a **derived view** computed on demand from `results.json experiments[]`. It is NOT stored as authoritative state. After each computation, log a snapshot to session-log for forensic purposes.

### Computation Steps

1. **Read canonical headings** from the session-log entry `type: "canonical_headings"` (logged at Experiment 0). This is the denominator — the full list of sections in the target skill.

2. **Traverse experiments[]** in results.json. For each experiment with `status != "baseline"`:
   - Extract `changes[].location` values
   - Map each location to the nearest canonical heading (fuzzy match to the heading list)
   - Record the experiment's score delta vs. baseline: `experiment.pass_rate - baseline.pass_rate`

3. **Compute sections_explored:**
   ```
   For each canonical heading:
     count: number of experiments that targeted this section
     best_delta: highest score delta among experiments targeting this section
     last_tried: most recent experiment ID targeting this section
     autopsy_pattern: most common discard_autopsy classification (if any discards)
   ```

4. **Compute mutation_types:**
   ```
   Count of changes[].type across all experiments: {"add": N, "modify": N, "delete": N}
   ```

5. **Compute diversity_score:**
   ```
   diversity_score = (sections with count >= 1) / (total canonical headings)
   ```
   Range: 0.0 (all mutations on one section) to 1.0 (every section explored at least once).

### Session-Log Snapshot

After computing, write to session-log:
```json
{"phase":"7","type":"derived_registry_snapshot","experiment":N,
 "sections_explored":{"gotchas":{"count":2,"best_delta":0.12,"last_tried":3},
   "voice":{"count":1,"best_delta":-0.03,"last_tried":2}},
 "mutation_types":{"add":3,"modify":2,"delete":1},
 "diversity_score":0.6}
```

This snapshot is forensic only — nothing reads it as authoritative state. It captures what the agent computed at decision time for debugging.

### Consumers

- **Circuit breaker diagnosis** (SKILL.md): compute before presenting the `⚠ Circuit breaker` report. Shows `diversity_score` and `sections_explored` to help the user understand search coverage.
- **Step 2a hypothesis** (SKILL.md): when diversity_score is low (<0.5), prioritize unexplored sections. When a section has `autopsy_pattern: "wrong_target"`, deprioritize it.
- **Mutation Reviewer** (P2, future): fires on `diversity_score < 0.5 AND experiments >= 3`.

### Mini Mode

Derived registry computes in Mini mode. With 2-3 experiments, diversity_score will typically be low (1-2 sections out of many). The score is still useful as a diagnostic in the session-log snapshot but does not trigger the Mutation Reviewer (P2, not yet implemented) or the circuit breaker (disabled in Mini).

### Heading Granularity

Canonical headings are parsed at `##` level only. Skills with meaningful structure at `###` level will report higher `diversity_score` than warranted (e.g., a skill with 3 `##` headings each containing 5 `###` sub-sections shows diversity based on 3 sections, not 15). This is acceptable for v1 — `##` headings correspond to the sections the agent targets in mutations. If mutation granularity moves to `###` level, update the heading parse to match.

### Multi-Section Mutations

When a single experiment targets multiple sections (`changes[]` has 2+ entries with different `location` values), count the experiment toward ALL targeted sections. The `best_delta` for each section is the same (the experiment's overall delta), since per-section attribution is not possible with the current scoring model.

---

## Gotchas

Read when: something goes wrong, or starting a session.

1. **Don't skip Gulf 1.** A 100% score on narrow evals is an artifact, not evidence of quality.
2. **Error analysis cannot be automated.** Phase 3 requires the human to read outputs. An LLM doing it is comprehension theater.
3. **Let categories emerge.** In Phase 3, don't start with existing eval categories. Fresh eyes.
4. **Keep rate > final score.** 60%→85% through 4 keeps teaches more than 95%→100% in 1.
5. **High Phase 3 fail rates are healthy.** 60-100% fail = diverse fixtures + rigorous reviewer. <30% = too easy.
6. **Dashboard needs HTTP serving.** `python3 -m http.server 8080`. Direct `file://` fails (CORS). Needs internet for Chart.js CDN.
7. **Never run two sessions on same skill.** state.json has no locking.
8. **"Invoke" means "read and follow."** Not all agents support direct skill invocation.
9. **session-log.json is best-effort.** If corrupted, recreate and continue. Never blocks.

## When AutoRefine Doesn't Help

1. **Phase 1 passes but skill is bad.** Design audit checks structure, not logic. Skip to Phase 3.
2. **Phase 3 fail rate <20%.** Fixtures too easy or reviewer too generous. Add harder inputs.
3. **AutoResearch plateaus after 3+ experiments.** Evals may not discriminate, or failure needs architectural change.
4. **Fixtures don't represent real usage.** Include 3-5 "ugly" real-world inputs.

---

## Failure Taxonomy Template

Read when: Phase 3 Step 6.

```
## Failure Taxonomy: <skill>
1. [Category Name] — [description] — observed in N/M traces
2. [Category Name] — [description] — observed in N/M traces
```

---

## Judge Execution Procedure

Read when: Phase 6 (running judges) or Phase 7 (scoring experiments).

To run an agent-as-judge eval:
1. Read `judges/judge-E{N}-{name}.md` (the judge prompt)
2. Read the fixture file being evaluated
3. Output: `Critique: 1. Criterion check: ... 2. Evidence: ... 3. Verdict link: ...` then `Result: Pass or Fail`

Dispatch as a subagent or evaluate in main context. Run judges sequentially (not parallel) to avoid context contamination. Normalize the critique into `reasoning_trace` exactly as written so every stored verdict preserves the same ordered explanation shape, extract `evidence[]` using `Judge Verdict Evidence Schema` so the stored verdict has machine-readable citations instead of free-form notes, and extract `supporting_items[]` using `Judge Decision Support Schema` so each material judgment call is tied to the exact evidence objects that supported it. During verdict assembly, create or update one verdict object per eval and attach the extracted `supporting_items[]` to that same verdict object before reading the next judge result. If a judge emits `Result: Pass` or `Result: Fail` without extractable evidence, log `invalid_verdict_missing_evidence`, do not write that verdict into `eval_results[]`, and re-run or fail the eval instead of silently accepting it. Preserve that assembled verdict unchanged in the final judge output (`eval_results[]`, iteration `eval_results.json`, and any stored verdict artifact).

### Eval-Task File Format (Phase 7 Tier 1 Verification Isolation)

Read when: Phase 7 step 2b, Tier 1 subagent dispatch.

Write to `[workspace]/eval-tasks/exp{N}-E{M}.md`:
```markdown
# Eval Task: E{M} — {eval name}

## Judge Prompt
{contents of judges/judge-E{M}-{name}.md}

## Fixture Input
{fixture content}

## Skill Output to Evaluate
{the mutated skill's output for this fixture}

## Instructions
Evaluate the Skill Output above against the Judge Prompt criteria.
Output: Critique: 1. Criterion check: ... 2. Evidence: ... 3. Verdict link: ... then Result: Pass or Fail
```

Do NOT include: baseline output, mutation hypothesis, Phase 1-3 findings, or any reasoning about why changes were made. The subagent receiving this file should have zero context about the mutation intent.

### Preferences File Format (Ambient Learning)

Read when: Ambient learning check on resume, or Phase 7 step 2a.

`[workspace]/preferences.md`:
```markdown
# User Preferences (ambient learning)

## Preference 1 (captured: YYYY-MM-DD)
RULE: [one-sentence preference]
EVIDENCE: [removed text] → [added text]
CONFIDENCE: high | medium

## Preference 2 (captured: YYYY-MM-DD)
...
```

Phase 7 reads this file before hypothesizing mutations — do NOT propose changes that contradict learned preferences.

---

## Judge Validation Report Format

Read when: Phase 6 Step 5.

```
| Judge | Dev TPR | Dev TNR | Test TPR | Test TNR | Status |
|-------|---------|---------|----------|----------|--------|
| E1: Name | 92% | 88% | 89% | 85% | APPROVED |
```

---

## Per-Phase State Fields

Read when: updating state.json after a phase.

| Phase | Fields to record |
|-------|-----------------|
| 1 | `design_audit: "complete"`, `skill_pattern`, `phase1_context.selected_skill_pattern`, `phase1_context.selected_eval_strategy_id` |
| 2 | `eval_audit: "complete"` |
| 3 | `traces_reviewed, sampled_trace_ids, sampling_strategy, taxonomy_summary` |
| 4 | `fixture_count, pass_count, fail_count, split_sizes, mutation_stage_split_access_policy` |
| 5 | `code_eval_count, judge_eval_count` |
| 6 | `validation_results` (TPR/TNR per judge) |
| 7 | `current_experiment, best_score, consecutive_discards, circuit_breaker, completion_cadence` |

---

## Confidence-Weighted Scoring

Read when: Phase 7 active.

Formula: `score = sum(weight_i * pass_i) / sum(weight_i)` where `pass_i` is 1 (pass) or 0 (fail).

Weights:
- Code-based evals: `weight = 1.0`
- Agent-as-judge evals: `weight = (TPR + TNR) / 2` from Phase 6 validation

Example: 5 evals, 3 code (weight 1.0 each) + 2 agent (weights 0.92, 0.70). Mutation passes all code evals + fails both agent evals. Score = (1+1+1+0+0) / (1+1+1+0.92+0.70) = 3/4.62 = 64.9%. Without weighting: 3/5 = 60%. The weighting gives less influence to the noisy agent judge (0.70).

Every scored experiment must emit:
- per eval: `weight`, `weight_source`, `weighted_points`, `normalized_contribution`
- aggregate: `decision_breakdown.weighted_points`, `decision_breakdown.total_weight`, `decision_breakdown.combined_score`, `decision_breakdown.threshold`
- timing: populate `decision_breakdown` immediately when scoring completes, before regression checks, explainer rendering, or user override. The field must contain both the intermediate per-eval math copied into `components[]` and the final aggregate used for the keep/discard recommendation.

Mini mode uses the same structure, but `weight_source` is `mini_mode_code_default` or `mini_mode_agent_discount`.

## Aggregation Explainer Template

Read when: Phase 7 active (after scoring, before presenting to user).

Show the same structure for baseline and mutations. Every eval appears, even failures.

```text
Experiment 3: 78.7% (▲ +11.5pp vs baseline)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  E1  Pass  ✓
    weight: 1.00
    weight_source: code_eval_fixed
    weighted_points: 1.00
    normalized_contribution: 1.00 / 4.70 = 21.3%
  E2  Pass  ✓
    weight: 0.90
    weight_source: phase_6_validation_average
    weighted_points: 0.90
    normalized_contribution: 0.90 / 4.70 = 19.1%
  E3  Fail  ✗
    weight: 0.90
    weight_source: phase_6_validation_average
    weighted_points: 0.00
    normalized_contribution: 0.00 / 4.70 = 0.0%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  normalization: combined_score = weighted_points / total_weight
  weighted_points: 3.70
  total_weight: 4.70
  combined_score: 78.7%
  keep/discard threshold: 80.0%
  proposed_decision: discard
```

Rules:
- Do not skip failed evals. Zero contribution is still part of the explanation.
- Persist the explainer rows as `decision_breakdown.components[]` in the same order they are shown to the user.
- `normalized_contribution` always uses the shared denominator `total_weight`.
- `combined_score` is the score used for keep/discard. Do not switch to raw pass count in the presentation.
- In Mini mode, keep the same layout and swap in the simplified weight sources.

---

## Loop-Back Protocol

Read when: Loop-Back Prompt fires (≥2 judge_gap entries).

**When `locked_judges` gets populated:** At Gulf 2 gate approval, record all approved judge IDs in `state.json.locked_judges`.

**Append mode for Phase 5:**
- Step 1: Skip classification of existing evals. Only classify NEW evals derived from judge gap reasons.
- Step 2-3: Write only NEW judges. Do NOT modify locked judges.
- Step 4: Append new judge files to `judges/`. Do not overwrite existing ones.

**Phase 6 on loop-back:** Validate only judges NOT in `locked_judges`. Locked judges keep their prior TPR/TNR.

**Phase 7 on loop-back:** Re-run with the expanded eval suite (old + new judges). Score may drop — this is more accurate measurement, not regression. Explain this to the user.

---

## Hamel Integration Details

Read when: `hamel_available` is true in state.json.

### Phase 2: eval-audit
Invoke for deeper analysis — flags class imbalance, stale analyses, recommends next skills.

### Phase 3: error-analysis
Adaptations: use 20-25 fixture outputs (not 100 production traces), manual clustering (smaller trace count), fixture diversity instead of random sampling.

### Phase 3/4: generate-synthetic-data
Dimension-based tuple generation: define 3 dimensions → draft 20 tuples → LLM generates more → convert to test inputs. Target 30-40 for skills (not 100).

### Phase 5: write-judge-prompt
Use for richer prompt engineering. Adapt: agent-as-judge instead of external API calls.

### Phase 6: validate-evaluator
Deeper calibration. Skip Rogan-Gladen correction and bootstrap CI (insufficient data for skills). Core protocol applies: dev iteration → test once → report TPR/TNR.

### Phase 7: skill-creator subagents
- **Grader** — structured pass/fail verdicts with evidence + eval critique
- **Comparator** — blinded A/B testing between baseline and mutation
- **Analyzer** — explains WHY winner won + prioritized improvement suggestions

---

## Gotcha Taxonomy

Read when: Phase 1 active (Gotcha Detection).

### 6 Categories

Check the target skill against each category. For each match, cite specific lines creating the risk.

| Category | What to look for | Example patterns |
|----------|-----------------|-----------------|
| **Shell execution** | Commands, subshells, exec, `$B`, `Bash` tool calls | `$B goto $URL`, `bash -c "$CMD"`, `` `command` `` |
| **Path handling** | File reads/writes, directory creation, deletion, traversal | `rm -rf $DIR`, `cat $FILE`, `mkdir -p $PATH` |
| **State mutation** | Files written to disk, config changes, git operations | `git commit`, `Write` tool, `state.json` updates |
| **Concurrent access** | Shared files without locking, race conditions | Two sessions on same workspace, no file locks |
| **Authentication / secrets** | API keys, tokens, credentials in instructions or output | `$API_KEY`, `Authorization: Bearer`, `.env` references |
| **External API calls** | Network requests, third-party services, webhooks | `WebSearch`, `WebFetch`, `curl`, API endpoints |

### Scoring Scale

- **N/A** — Skill touches NONE of the 6 categories. No gotcha-prone patterns detected. This is the correct score for simple skills (e.g., a formatting skill that only reads and reformats text).
- **Present** — Applicable categories found AND the skill documents corresponding gotchas with specific warnings.
- **Missing** — Applicable categories found BUT the skill has NO documented gotchas for those categories. This is the failure case.

### Smoke Probe Instructions

For the top 2 highest-risk findings from the static evidence step:

1. **Narrate before probing:** "I found [risk] on line [N]. I'm going to test this with a probe input to confirm the risk."
2. **Construct ONE minimal input** designed to trigger the risk. Keep it safe — the goal is to observe the skill's handling, not to cause damage. Example: for an unsanitized URL, use `javascript:alert(1)` not an actual exploit.
3. **Run the target skill** with the probe input (same execution model as Phase 3 — read the skill and provide the input as if you were a user).
4. **Record the result:**
   - `confirmed` — probe demonstrated the risk. Include the probe input and relevant output excerpt.
   - `not_confirmed` — skill handled the probe safely. Note this in the audit but still report the static evidence.
5. **For session-spanning or interactive skills:** Skip the smoke probe. Record as `suspected` (static evidence only). Same fallback as Phase 3 Step 1 for these skill types.

Cap at 2 probes per audit to keep Phase 1 under 10 minutes.

---

## Judge Confidence Card Template

Read when: Phase 6 Step 5 (after validation complete).

Generate `judge-confidence-card.md` in the workspace. One card per agent-as-judge eval (skip code-based evals — they are deterministic).

```markdown
# Judge Confidence Card: E{N} — {eval name}

## Metrics
- **TPR:** {X}% — catches {X} out of 100 real failures
- **TNR:** {Y}% — correctly accepts {Y} out of 100 passing outputs
- **Confidence:** {High|Medium|Low}

{If |TPR - TNR| > 20: "**ASYMMETRY WARNING:** This judge is much better at {catching failures|accepting good outputs} ({higher}%) than {the other} ({lower}%). Interpret results with this bias in mind."}

## Evidence: What the judge got right
| # | Fixture | Human | Judge | Critique excerpt |
|---|---------|-------|-------|-----------------|
| 1 | {fixture name} | Pass | Pass | "{first sentence of judge critique}" |
| 2 | ... | Fail | Fail | "..." |
| 3 | ... | ... | ... | "..." |

## Evidence: What the judge got wrong
| # | Fixture | Human | Judge | Why it disagreed |
|---|---------|-------|-------|-----------------|
| 1 | {fixture name} | Fail | Pass | {analysis of why judge missed this} |

## Known blind spots
{Patterns derived from False Pass and False Fail analysis. 1-3 bullets.}
- "{pattern 1}"
- "{pattern 2}"
```

### Confidence Level Thresholds
- **High:** TPR + TNR > 180 (both metrics strong)
- **Medium:** 150 < TPR + TNR ≤ 180 (adequate but watch for weaknesses)
- **Low:** TPR + TNR ≤ 150 (judge needs refinement before trusting results)

These are percentage points summed (range 0-200). Example: TPR=92%, TNR=85% → sum=177 → Medium.

### Narration Template
After generating the card, walk the human through it:
"Here's your judge for E{N}. It catches failures well ({TPR}% TPR) but {occasionally marks passing outputs as failures | misses some real failures} ({TNR}% TNR). Its main weakness is {blind spot pattern}. Here are the examples it got right and wrong — check whether its reasoning makes sense to you."

---

## Batch Review Format

Read when: Phase 3 Step 5 (trace review) or Phase 6 Steps 1-4 (dev split judge validation).

**Important:** Batch review applies to Phase 6 dev split ONLY. Phase 6 Step 5 (test split) runs WITHOUT human review — it is automated measurement. Never show test-split examples to the human.

### Worksheet Presentation

Present traces/judge results in batches of 5. Show a summary table first, then full details for each item.

```
=== Batch Review: {context} ({start}-{end} of {total}) ===

| # | Input Summary | Output Summary | Cluster | Your Verdict |
|---|--------------|----------------|---------|-------------|
| T01 | {1-line input summary} | {1-line output summary} | {cluster} | ___ |
| T02 | ... | ... | ... | ___ |
| T03 | ... | ... | ... | ___ |
| T04 | ... | ... | ... | ___ |
| T05 | ... | ... | ... | ___ |

Review each item below, then give your verdicts in one message.
Format: T01:Pass T02:Fail(reason) T03:Pass ...
```

Then show each item in full detail below the table.

### Narration Before Batch
"Here are 5 {traces|judge results} to review. I've grouped them by similarity — {cluster narrative}. When you're ready, give me your verdicts in one go: `T01:Pass T02:Fail(reason) ...`"

### Verdict Parsing
Expected format: `T01:Pass T02:Fail(missed entity) T03:Pass T04:Fail(flaw not caught) T05:Pass`

Parsing rules:
- Split on whitespace to get per-trace tokens
- Each token: `{ID}:{verdict}` or `{ID}:{verdict}({note})`
- Verdict is case-insensitive: Pass, pass, PASS all valid
- Notes in parentheses are optional — record if present
- If fewer verdicts received than traces in the batch: accept the ones provided, then ask for the missing ones: "Missing verdicts for {IDs}. Pass or Fail?"
- If parsing fails (freeform text, missing IDs, unrecognized format): fall back to asking one at a time (current Phase 3 behavior). Say: "I couldn't parse that format. Let me ask one at a time instead."

### Batch Size
Default: 5 items per batch. On the first batch, offer: "Want a different batch size? Default is 5." If user requests a different size, use that for remaining batches.

---

## Checkpoint Schema

Read when: Initialize Workspace (resume detection) or Session Close (checkpoint writing).

### Checkpoint fields in state.json

The `checkpoint` field in state.json stores resume state. Set to null when no checkpoint is active (fresh start or after successful resume).

```json
{
  "checkpoint": {
    "next_action": "Begin Phase 4: Expand Inputs",
    "files_to_read_on_resume": ["state.json", "error-analysis-traces.md", "failure-taxonomy.md", "eval-suite.md", "session-log.json"],
    "files_modified": ["error-analysis-traces.md", "failure-taxonomy.md", "eval-suite.md"],
    "resume_prompt": "Continue autorefine on [skill]. Workspace at [path]. Last completed: Phase 3 error analysis (8 traces reviewed, 3 failure categories, 5 evals drafted). Gulf 1 gate pending. Next: Phase 4.",
    "timestamp": "2026-03-23T20:46:00Z"
  }
}
```

**Phase 7 mid-experiment checkpoint:**
```json
{
  "checkpoint": {
    "next_action": "Continue Phase 7: AutoResearch Loop — resume from experiment 4",
    "files_to_read_on_resume": ["state.json", "fixtures-manifest.md", "input-sets.json", "results.json", "eval-suite.md", "changelog.md"],
    "iteration_decisions_on_resume": "Read all decision.md files from state.json.current_run_path (e.g., runs/run_.../iteration_*/decision.md)",
    "files_modified": ["results.json", "results.tsv", "changelog.md"],
    "resume_prompt": "Continue autorefine on [skill]. Workspace at [path]. Phase 7 in progress: 3 experiments complete (kept 1,3; discarded 2). Best score: 0.82. Consecutive discards: 1. Budget remaining: 2. Resume from experiment 4.",
    "timestamp": "2026-03-23T21:15:00Z"
  }
}
```

### resume-prompt.txt

Written alongside state.json checkpoint. Standalone human-readable file — the user can `cat` it directly.

Format:
```
Continue autorefine on {skill_name}.
Workspace: {workspace_path}
Last completed: {phase description with key metrics}
Next: {next_action}

To resume, paste this prompt into a new autorefine session.
```

### Resume Detection (Initialize Workspace)

When reading state.json on startup:
1. If `checkpoint` is not null and `checkpoint.next_action` exists → resume mode
2. Read all files listed in `checkpoint.files_to_read_on_resume`. If any file is missing, skip it and note: "Missing file: {filename} — may have been deleted between sessions."
3. Deserialize `state.json.phase1_context` and `state.json.mutation_stage_split_access_policy` into the loaded run context before routing or resuming later phases. If `phase1_context.selected_skill_pattern` and/or `phase1_context.selected_eval_strategy_id` exist, restore them unchanged so later phases can read the chosen pattern + resolved strategy from the loaded context. If the restored pattern and `state.json.skill_pattern` differ, treat it as state corruption and rerun Phase 1 Step 0 instead of continuing. If the restored strategy is missing or no longer maps back to the restored pattern through `Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector`, treat it as state corruption and rerun strategy selection before continuing. If split-scoped Phase 7 work is active and `mutation_stage_split_access_policy` is missing, read the same policy from `fixtures-manifest.md` or a stored Phase 4 `evaluation_metadata.config.mutation_stage_split_access_policy` snapshot, restore it into the loaded run context, and stop if the sources disagree.
4. Print resume context: "Resuming from checkpoint: {next_action}"
5. Set `checkpoint` to null (clear the checkpoint — it's been consumed). Preserve all non-checkpoint state, including `phase1_context` and `mutation_stage_split_access_policy`, when writing the updated `state.json`.
6. Proceed from `checkpoint.next_action`

### Checkpoint Writing (Phase Boundaries + Pause)

At every phase boundary (phase completes) and on user-initiated pause:
1. Update `state.json.checkpoint` with current state
2. Write `resume-prompt.txt` to workspace root
3. Append to session-log: `{"type":"checkpoint",...}`

On user-initiated pause, also offer: "Want to save key learnings to memory before pausing?"

---

## Regression Check Schema

Read when: Phase 7 active (after scoring, before presenting to user).

### When to Run

After scoring a mutation against the eval suite, BEFORE presenting results to the user. This ensures the user sees score + regression status together in one decision point.

**Skip on experiments 0 and 1** — experiment 0 is the baseline (no mutation), experiment 1 is the first mutation (no prior kept experiments to compare against).

### How It Works

1. Score the current mutation against all evals (this already happens in Phase 7). Record per-eval results in `eval_results`.
2. Load `eval_results` from prior kept experiments in `results.json` (cap at 5 most recent for Deep tier).
3. For each eval: compare the current `pass_fail` verdict against the BEST prior `pass_fail` verdict for that eval across kept experiments.
   - If an eval was `pass` in ANY prior kept experiment and is now `fail` → regression detected.
4. Record `regression_check` in the current experiment record.

### Presenting Results

**No regressions:**
Use the `Aggregation Explainer Template` first, then summarize:
"combined_score: {X}%. Regression check: all prior improvements stable. {Recommend keep/discard based on score}."

**Regressions found:**
"combined_score: {X}%. **Regression warning:** {N} eval(s) that previously passed now fail:
- E{N}: was pass (experiment {M}), now fail. {detail}
Recommend discard — this mutation breaks previous improvements."

The user can override (keep anyway). Log as: `{"phase":"7","type":"regression","experiment":N,...,"user_action":"keep_override","reason":"..."}`

### Backup and Revert

- **Before each mutation:** save `<skill>-optimized-prev.md` as backup. Overwritten before each new mutation (single-level undo).
- **On discard (regression or user choice):** restore backup as the current baseline. Do NOT record the discarded mutation as "keep" in results.json.
- **On keep:** backup is no longer needed (next mutation will create a new one).

---

## Iteration Directory Schema

Read when: Phase 7 active (after each experiment).

The iteration directory provides filesystem-as-memory for Phase 7. Each experiment's full state is written to disk as individual files, making experiments independently inspectable and surviving context compaction.

### Directory Structure

```
[workspace]/runs/
  run_YYYY-MM-DDTHH-MM-SS/         # One Phase 7 execution
    iteration_000/                   # Experiment 0 (baseline)
      mutation.md
      skill_before.md
      skill_after.md
      eval_results.json
      decision.md
    iteration_001/                   # Experiment 1
      ...
  run_YYYY-MM-DDTHH-MM-SS/         # After loop-back → new run
    ...
```

A new `run_*` directory is created each time Phase 7 starts (including after loop-backs). The timestamp uses the format `YYYY-MM-DDTHH-MM-SS` (colons replaced with dashes for filesystem safety).

### File Formats

**mutation.md** — What was changed and why.
```markdown
# Experiment N — [mutation description]

## Hypothesis
[Why this change should improve the skill]

## Changes
- [type: added|modified|removed] [location/section]: [1-3 line snippet]

## Mutation Type
[add | modify | delete]
```
For baseline (iteration_000):
~~~markdown
# Experiment 0 — Baseline

No mutation applied. This is the initial scoring run.
~~~

**skill_before.md** — Full skill content before mutation was applied.
For baseline: content is `N/A — this is the baseline scoring run.`

**skill_after.md** — Full skill content after mutation (or current skill for baseline).

**eval_results.json** — Per-eval results for this experiment.
```json
{
  "experiment_id": 0,
  "input_set_id": "phase4-dev-7f3c91ad",
  "input_set_ref": "input-sets.json#phase4-dev-7f3c91ad",
  "input_ids": [
    "phase4-dev-7f3c91ad-I03",
    "phase4-dev-7f3c91ad-I05",
    "phase4-dev-7f3c91ad-I08"
  ],
  "pass_rate": 0.75,
  "score": 6,
  "max_score": 8,
  "eval_results": [
    {
      "eval": "E1",
      "pass_fail": "pass",
      "reasoning_trace": "1. Criterion check: the required gotchas section is present. 2. Evidence: line 12 contains '## Gotchas' and 3 concrete warnings follow. 3. Verdict link: because the rubric requires a gotchas section with concrete warnings, this passes.",
      "evidence": [
        {
          "kind": "output_excerpt",
          "source": "skill_output",
          "locator": "input_id:phase4-dev-7f3c91ad-I03 output lines 12-18",
          "excerpt": "## Gotchas\n- Never run rm -rf without checking the target path.",
          "metric": null,
          "artifact_ref": null
        },
        {
          "kind": "metric",
          "source": "scoring_metric",
          "locator": "warnings_found",
          "excerpt": "3 concrete warnings found in the gotchas section.",
          "metric": {
            "name": "warnings_found",
            "value": 3,
            "unit": "count"
          },
          "artifact_ref": null
        }
      ],
      "supporting_items": [
        {
          "stage": "criterion_check",
          "decision": "required gotchas section is present",
          "outcome": "met",
          "evidence_refs": [0]
        },
        {
          "stage": "evidence_check",
          "decision": "gotchas section includes 3 concrete warnings",
          "outcome": "met",
          "evidence_refs": [1]
        },
        {
          "stage": "verdict_link",
          "decision": "the rubric passes when the gotchas section and concrete warnings are both present",
          "outcome": "supports_pass",
          "evidence_refs": [0, 1]
        }
      ],
      "weight": 1.0,
      "weight_source": "code_eval_fixed",
      "weighted_points": 1.0,
      "normalized_contribution": 0.25
    },
    {
      "eval": "E2",
      "pass_fail": "fail",
      "reasoning_trace": "1. Criterion check: the disclosure guidance is missing. 2. Evidence: no 'Read when:' pointer is present and the disclosure section is absent. 3. Verdict link: because the rubric requires explicit disclosure guidance, this fails.",
      "evidence": [
        {
          "kind": "output_excerpt",
          "source": "skill_output",
          "locator": "input_id:phase4-dev-7f3c91ad-I03 output lines 1-9",
          "excerpt": "No 'Read when:' pointer or disclosure section appears in the output.",
          "metric": null,
          "artifact_ref": null
        },
        {
          "kind": "artifact_ref",
          "source": "workspace_artifact",
          "locator": "runs/run_2026-04-10T10-00-00/iteration_000/eval_results.json",
          "excerpt": "Stored verdict artifact for replay and dashboard inspection.",
          "metric": null,
          "artifact_ref": {
            "path": "runs/run_2026-04-10T10-00-00/iteration_000/eval_results.json",
            "label": "baseline eval results"
          }
        }
      ],
      "supporting_items": [
        {
          "stage": "criterion_check",
          "decision": "disclosure guidance is missing",
          "outcome": "not_met",
          "evidence_refs": [0]
        },
        {
          "stage": "verdict_link",
          "decision": "the rubric fails when disclosure guidance is absent",
          "outcome": "supports_fail",
          "evidence_refs": [0, 1]
        }
      ],
      "weight": 0.9,
      "weight_source": "phase_6_validation_average",
      "weighted_points": 0.0,
      "normalized_contribution": 0.0
    }
  ],
  "decision_breakdown": {
    "components": [
      {
        "eval": "E1",
        "pass_fail": "pass",
        "weight": 1.0,
        "weight_source": "code_eval_fixed",
        "weighted_points": 1.0,
        "normalized_contribution": 0.213
      },
      {
        "eval": "E2",
        "pass_fail": "fail",
        "weight": 0.9,
        "weight_source": "phase_6_validation_average",
        "weighted_points": 0.0,
        "normalized_contribution": 0.0
      }
    ],
    "formula": "combined_score = weighted_points / total_weight",
    "weighted_points": 3.7,
    "total_weight": 4.7,
    "combined_score": 0.787,
    "combined_score_pct": 78.7,
    "threshold": 0.8,
    "proposed_decision": "discard"
  },
  "regression_check": null,
  "discard_autopsy": null
}
```
Fields mirror the experiment record in results.json. `experiment_id` matches the iteration directory number (0 for baseline, 1+ for mutations). `input_set_id` records which stable scoring set this experiment used. `input_set_ref` points directly to the registered set entry, and `input_ids` preserve the exact stable inputs scored in finalized set order. Persist `completion_cadence` here too, using the finalized snapshot copied from the root cadence counter at the moment the experiment becomes final. Persist `requires_human_spot_check` here too, copying the finalized boolean written on the experiment record after the cadence increment instead of recomputing it on load. Every `eval_results[]` entry must preserve `pass_fail`, `reasoning_trace`, `evidence`, `supporting_items`, `weight`, `weight_source`, `weighted_points`, and `normalized_contribution`. `evidence[]` uses `Judge Verdict Evidence Schema` so each verdict can store output/input excerpts, metrics, and artifact references in a uniform shape. `supporting_items[]` uses `Judge Decision Support Schema` so each verdict also records which concrete evidence objects backed each individual sub-decision. Include `decision_breakdown`, `decision_explanation` (with `strongest_outcomes[]`), `regression_check`, and `discard_autopsy` when applicable (null otherwise).

**decision.md** — Keep/discard verdict with full reasoning.
```markdown
# Experiment N — [KEEP | DISCARD | BASELINE]

## Score
[X]/[Y] ([Z]%)  |  Delta: [+/-N]pp vs baseline

## Aggregation Breakdown
weighted_points: [X]
total_weight: [Y]
combined_score: [Z]%  |  threshold: [T]%

## Verdict
[KEEP | DISCARD | BASELINE]

## Reasoning
[Why this was kept or discarded — score delta, regression status, user override if any]

## Discard Autopsy
[Only for discards: wrong_target | wrong_params | wrong_type — with 1-sentence reasoning]
[For keeps/baseline: N/A]
```

### When to Write

- **Experiment 0 (baseline):** Write to `iteration_000/` immediately after baseline scoring (Phase 7 step 1).
- **Kept experiments:** Write to `iteration_NNN/` at Phase 7 step 2e (verdict is final, no autopsy needed).
- **Discarded experiments:** Write to `iteration_NNN/` at end of Phase 7 step 2f (after discard autopsy is recorded). This ensures `eval_results.json` and `decision.md` include the autopsy classification.

### When to Read

- **Step 2a (hypothesis):** Before proposing a new mutation, read `decision.md` files from all prior iterations in the current run. This provides full reasoning context (not just scores) for what was tried, why it was kept or discarded, and what autopsy classification was assigned. Especially valuable after context compaction or session resume.

### Relationship to Other Artifacts

| Artifact | Purpose | Iteration directory replaces it? |
|---|---|---|
| results.json | Machine-readable experiment scores for dashboard | No — iteration dir complements it |
| session-log.json | Audit trail of all pipeline events | No — iteration dir logs a write event |
| changelog.md | Human-readable experiment summaries | No — iteration dir has full detail |
| `<skill>-optimized-prev.md` | Single-level undo backup | No — iteration dir archives all versions |

The iteration directory is the **forensic record** — it has everything. The other artifacts remain the **operational interfaces** for the dashboard, session resume, and undo.

---

## Skill Pattern Eval Strategy

Read when: Phase 1 Step 0 (pattern classification complete). Use the classified pattern to shape downstream evaluation strategy.

### 5 Patterns

| Pattern | Description | Distinguishing trait |
|---------|-------------|---------------------|
| **Tool Wrapper** | On-demand context for a library/API | Answers are verifiable against external source |
| **Generator** | Consistent structured output from templates | Output has a predictable format/schema |
| **Reviewer** | Score against a checklist by severity | Produces verdicts, ratings, or prioritized findings |
| **Inversion** | Interview/gather requirements before acting | Asks questions before producing output |
| **Pipeline** | Strict multi-step workflow with checkpoints | Has ordered phases, gates, and state transitions |

Skills can exhibit secondary signals from other patterns, but Phase 1 must still assign exactly one primary pattern. Use that primary pattern's eval strategy. Capture any secondary signals in the classification reasoning only; do not encode them in `state.json.skill_pattern`.

### Pattern-to-Evaluation-Strategy Selector

Read when: Phase 1 Step 0 has already written `state.json.phase1_context.selected_skill_pattern` and needs one concrete downstream evaluation strategy before any Phase 1 scoring or later-phase planning continues.

Resolve exactly one downstream evaluation strategy from the active run's primary pattern. This selector is the bridge between classification and the later-phase tactics; downstream phases must consume the resolved selector, not improvise from pattern prose.

Resolution table:
- `tool_wrapper` -> `tool_wrapper_eval_strategy`
- `generator` -> `generator_eval_strategy`
- `reviewer` -> `reviewer_eval_strategy`
- `inversion` -> `inversion_eval_strategy`
- `pipeline` -> `pipeline_eval_strategy`

Resolution contract:
- The mapping is one-to-one. Do not continue Phase 1 Step 1-6, Phase 4-6, or Phase 7 until exactly one `selected_eval_strategy_id` is resolved for the current run.
- Resolve from `state.json.phase1_context.selected_skill_pattern` first, then confirm the mirrored `state.json.skill_pattern` still matches before persisting `selected_eval_strategy_id`.
- Persist the selected strategy in `state.json.phase1_context.selected_eval_strategy_id`. This is the active run's downstream evaluation-strategy source of truth.
- Do not infer strategy from prose summaries, ad hoc pattern recollection, or a prior skill/version's state. If the strategy is missing, rerun this selector against the current workspace copy's persisted pattern.
- If the selected strategy does not map back to the same pattern through this table, treat that as a blocking state error instead of defaulting.
- If only the Phase 1 artifact is available downstream, read the same selector from the top-level `selected_eval_strategy_id` field when present. If that field is absent in an older artifact, resolve it deterministically from the top-level `selected_skill_pattern` using this table before continuing.

Canonical resolution payload:

```json
{
  "skill_pattern": "pipeline",
  "selected_eval_strategy_id": "pipeline_eval_strategy",
  "resolved_from": "state.json.phase1_context.selected_skill_pattern",
  "reasoning": "Pipeline patterns require gate-aware, resume-safe evaluation tactics."
}
```

Downstream routing contract:
- After Phase 1 has resolved `selected_eval_strategy_id`, later phases must read the matching strategy row in `Strategy Definitions` before doing any eval-oriented work.
- Use that row as the active tactic bundle for Quick Start bootstrap eval generation, Phase 2 eval audit framing, Phase 3/4 failure clustering and fixture expansion, Phase 5/6 judge design and validation, and Phase 7 mutation analysis.
- Do not continue on the generic downstream path when a valid `selected_eval_strategy_id` is present; missing strategy state is a blocking error, not a normal fallback branch.

### Pattern Identification Section

Read when: Phase 1 Step 0 is deciding the primary pattern for a skill. This is the classifier-facing surface. Use it to identify what is directly observable in the skill, what must be present before a pattern can be primary, and what signals disqualify that pattern even if some wording overlaps.

Classification rules:
- `Observable classification signals` are the concrete cues a classifier can see in `SKILL.md`, companion references, templates, or state instructions.
- `Required indicators` are the minimum conditions that must be true for primary classification. Missing any one means the pattern can still be secondary, but not primary.
- `Exclusion criteria` are the counter-signals that override superficial matches and force a different primary pattern.
- Secondary signals do not rescue a failed primary classification. Phase 1 must emit exactly one primary `skill_pattern` value.

### Pattern Classification Procedure

Read when: Phase 1 Step 0 needs a deterministic primary pattern assignment. This procedure evaluates the pattern signals in a fixed order and always resolves to exactly one of the 5 pattern IDs.

1. Build the evidence set.
   - Read the workspace copy at `[workspace]/skill-under-test/SKILL.md`.
   - Read only the companion references, templates, or state instructions that the skill explicitly depends on for execution.
   - Write one sentence for the skill's dominant job and one sentence for its success condition. These two sentences anchor every later check.
2. Evaluate patterns in this fixed order: `pipeline` -> `inversion` -> `reviewer` -> `generator` -> `tool_wrapper`.
3. For each pattern in that order, run the same three checks:
   - `Purpose alignment`: does the dominant job and success condition match the pattern's purpose?
   - `Required indicators`: are all required indicators present in the observable evidence?
   - `Exclusion check`: are all exclusion criteria absent?
4. The first pattern that passes all three checks becomes the primary classification. Stop immediately once one pattern passes.
5. If no pattern passes all three checks, use the same order as a deterministic fallback:
   - Keep only patterns whose purpose still matches the dominant job at least partially.
   - Among those, choose the pattern with the most required indicators satisfied.
   - Break any tie by the same fixed order: `pipeline` before `inversion` before `reviewer` before `generator` before `tool_wrapper`.
   - Record the missing required indicators or conflicting exclusions in the reasoning as classification debt to fix later.
6. Never write a composite `skill_pattern` value. Secondary behavior can be mentioned in the reasoning sentence, but `state.json.skill_pattern` must contain exactly one of the five canonical IDs.

Why this order:
- `pipeline` comes first because durable stage ordering, gates, and state transitions dominate any embedded review, generation, or reference steps.
- `inversion` comes second because a hard "gather first, do not act yet" gate dominates later generation or review behavior.
- `reviewer` comes third because evaluating an existing artifact dominates incidental formatting or reference lookups.
- `generator` comes fourth because producing a repeatable artifact dominates supporting reference context.
- `tool_wrapper` comes last because it is the best fit only after the orchestration, gating, review, and generation patterns have been ruled out.

### Boundary-Case Resolution Examples

Read when: more than one pattern looks plausible, a skill mixes behaviors from multiple patterns, or the fallback tie-breaker is needed.

Boundary-case rules:
- Always resolve overlap by the dominant job plus the fixed procedure. Surface cues like numbered steps, markdown sections, or a final QA pass do not outrank `purpose`, `required indicators`, and `exclusion criteria`.
- An exclusion signal defeats a pattern even when that pattern has more visible cues than its competitor.
- The fixed order matters only after `purpose` alignment is established. Do not award a pattern just because it appears earlier if its purpose is clearly not the skill's dominant job.
- Fallback tie-breaking compares only partially plausible patterns, counts satisfied `required indicators`, then uses the fixed order to resolve exact ties. Log the unresolved gap as classification debt.

| Boundary case | Observable overlap | Why the conflict resolves this way | Final pattern |
| --- | --- | --- | --- |
| Stateful interview system with later execution phases | The skill opens with adaptive questioning like an inversion skill, but it also has named phases, resume state, gate reports, and explicit handoffs into planning and execution. | `pipeline` wins because the dominant job is moving work across durable stages with stored state and advancement gates. The interview is one stage inside the broader orchestration, not the terminal job. | `pipeline` |
| Multi-stage audit workflow with a final severity checklist | The skill contains a strong review rubric and pass/fail outputs, but those only happen after earlier phases create artifacts, collect evidence, and pass gates tracked in state files. | `pipeline` wins because stage progression and handoff artifacts are the success condition. The review logic is important, but it is embedded inside a stateful workflow rather than being the primary deliverable. | `pipeline` |
| Requirements interview that ends by filling a PRD template | The skill asks adaptive clarification questions, blocks execution until ambiguity is reduced, then generates a structured PRD or plan. | `inversion` wins because the hard "do not execute yet" gate is the dominant behavior. The template output is downstream follow-through after readiness is established. | `inversion` |
| Review skill with a fixed markdown output format | The skill inspects an existing artifact, assigns severity, and emits findings in sections like `Summary`, `Findings`, and `Risks`. | `reviewer` wins because the template only structures the judgment. The primary deliverable is evaluative output about an existing artifact, not generation of a new artifact for its own sake. | `reviewer` |
| Structured artifact generator that reads external docs first | The skill loads API docs or reference notes, then fills a repeatable artifact such as a migration memo, rollout plan, or checklist-driven report. | `generator` wins because the dominant job is producing a reusable structured artifact. External references supply facts, but they do not turn the skill into a reference helper. | `generator` |
| Reference helper with a consistent response card | The skill answers dependency or API questions, loads official docs, and returns the answer in a standard card like `Answer`, `Gotchas`, and `Links`. | `tool_wrapper` wins because the dominant job is delivering externally grounded guidance. A stable response card is formatting support, not evidence that artifact generation is the primary job. | `tool_wrapper` |
| Reviewer vs generator fallback tie | The skill inspects an existing artifact, emits pass/fail plus a suggested rewrite block, but it lacks calibrated severity rules and also lacks a strict reusable output schema. Reviewer and generator each satisfy the same number of required indicators, so neither clears all checks. | The fallback keeps both patterns as partially plausible, counts satisfied indicators, finds an exact tie, then applies the fixed order. `reviewer` outranks `generator`, so choose `reviewer` and log the missing severity calibration plus missing schema contract as classification debt. | `reviewer` |

#### Tool Wrapper

Observable classification signals:
- Trigger-oriented language that activates on library, platform, API, or tool-specific requests.
- Instructions to load references, docs, examples, gotchas, or setup notes before giving guidance.
- The main payload is domain guidance, usage constraints, or reference context rather than a durable artifact or workflow state.
- Little or no persistent step state, checkpointing, or handoff artifact management.

Required indicators:
- The skill's primary job is to deliver externally grounded guidance about a dependency, platform, API, or tool.
- Success depends on factual correctness, freshness, or alignment with an external source of truth.
- Reference retrieval or tool-specific context is central to the output, not an incidental support step.

Exclusion criteria:
- Exclude if the main job is filling a repeatable output template or schema.
- Exclude if the main job is scoring, reviewing, or prioritizing an existing artifact.
- Exclude if the main job is interviewing for missing requirements before action.
- Exclude if ordered phases, explicit gates, or persistent state transitions are the dominant behavior.

#### Generator

Observable classification signals:
- Explicit output templates, schemas, section lists, placeholders, or formatting contracts.
- Directions to produce, transform, or rewrite an artifact into a known target shape.
- Repeated emphasis on completeness, field coverage, formatting consistency, or style conformance.
- Supporting references or questions exist mainly to help fill the output correctly.

Required indicators:
- The skill's dominant output is a newly produced or transformed artifact.
- A reusable format, schema, or structural contract defines success.
- Output completeness and consistency are first-order concerns, not just a side effect of another pattern.

Exclusion criteria:
- Exclude if the main job is evaluating an existing artifact against a rubric or severity model.
- Exclude if the main job is serving as a reference library or tool-usage guide.
- Exclude if the main job is requirement gathering with a hard "do not proceed yet" gate.
- Exclude if the skill primarily coordinates a durable staged workflow with explicit advancement logic.

#### Reviewer

Observable classification signals:
- Rubrics, checklists, scorecards, severity levels, pass/fail thresholds, or prioritized findings.
- Instructions to inspect an existing artifact, output, diff, trace, or behavior before writing judgments.
- Output formats centered on findings, verdicts, ratings, risk calls, or remediation priorities.
- Evidence gathering is tied to judgments rather than to building the artifact under review.

Required indicators:
- The skill evaluates something that already exists or has already been produced.
- Review criteria drive the output, whether via rubric, checklist, scoring model, or severity rules.
- The primary deliverable is evaluative judgment with calibrated importance, not artifact generation.

Exclusion criteria:
- Exclude if the dominant job is drafting or transforming the artifact itself.
- Exclude if the dominant job is delivering external dependency or platform guidance.
- Exclude if the dominant job is interviewing to clarify requirements before any substantive review can occur.
- Exclude if workflow orchestration, state progression, or checkpoint control matters more than judgment quality.

#### Inversion

Observable classification signals:
- Question-first flow, ambiguity checks, readiness thresholds, or explicit "do not execute yet" language.
- Instructions to keep gathering requirements, constraints, or clarifications until a gate is satisfied.
- Adaptive follow-up questions based on uncertainty, contradictions, or missing information.
- Any later generation or execution steps are clearly blocked behind the discovery phase.

Required indicators:
- Requirement gathering or ambiguity reduction happens before the main deliverable.
- The skill defines a gate, threshold, or stop condition that determines when execution may begin.
- The questioning adapts to the task's unknowns instead of being a fixed boilerplate preamble.

Exclusion criteria:
- Exclude if the skill normally produces the final artifact immediately and questions are optional setup only.
- Exclude if the dominant job is scoring or reviewing an existing artifact.
- Exclude if the dominant job is delivering reference guidance about a dependency, platform, or API.
- Exclude if the dominant behavior is a staged execution pipeline after the inputs are already known.

#### Pipeline

Observable classification signals:
- Named phases, stages, gates, checkpoints, or ordered steps with explicit dependency flow.
- State files, progress markers, run directories, handoff artifacts, or resume instructions.
- Advancement rules that block later work until earlier artifacts, approvals, or checks exist.
- Sequencing discipline is visible in the instructions, not just implied by numbering.

Required indicators:
- Later work depends on outputs, approvals, or state transitions from earlier stages.
- Persistent state, handoff artifacts, or progress markers are necessary to resume, verify, or advance the workflow.
- Correctness depends on enforcing stage order and gates, not just on producing one good isolated artifact.

Exclusion criteria:
- Exclude if the skill is only a single checklist pass with no durable state progression.
- Exclude if the skill is only a single template-fill artifact generator written as numbered steps.
- Exclude if the skill is primarily a reference helper with optional sequencing.
- Exclude if the dominant job is requirement gathering before action and any later steps are contingent follow-through rather than persistent orchestration.

### Skill Pattern Specification Schema

Read when: defining a pattern section, classifying a skill in Phase 1 Step 0, or comparing how a pattern spec changed between versions.

Every pattern section in this document must use the same canonical shape:

```markdown
### <Pattern Name>
Pattern ID: `<snake_case_id>`
Purpose:
- ...
Required characteristics:
- ...
Exclusion boundaries:
- ...
```

Field requirements:
- `Pattern ID`: stable identifier used in `state.json.skill_pattern`, comparison payloads, and downstream eval mapping. Do not change it for wording-only edits.
- `Purpose`: the core job this pattern is meant to perform and the main success condition. Write this as intent, not as examples or implementation steps.
- `Required characteristics`: the minimum signals that must be present for the pattern to be a valid primary classification.
- `Exclusion boundaries`: the counter-signals that disqualify the pattern as the primary classification even if some wording overlaps on the surface.

### Canonical Pattern Sections

#### Tool Wrapper

Pattern ID: `tool_wrapper`

Purpose:
- Canonical purpose statement: supply on-demand, externally grounded reference context about a dependency, platform, API, or tool so the agent can make a correct downstream decision.
- Success condition: the skill reduces factual mistakes, stale advice, and mis-triggered guidance about that external system.

Required characteristics:
- The core output is reference guidance, not a first-draft artifact, scoring verdict, or workflow state transition.
- The advice is expected to be checked against an external source of truth, official documentation, or concrete tool behavior.
- The skill is invoked because the agent needs situational context about a dependency or platform before taking another action.
- Reference freshness and correctness matter more than stylistic polish of the response format.

Exclusion boundaries:
- Do not classify as primary if the dominant job is generating a repeatable artifact from a template, schema, or house style.
- Do not classify as primary if the dominant job is reviewing, scoring, ranking, or prioritizing findings about existing work.
- Do not classify as primary if the dominant job is gathering requirements through questioning before action.
- Do not classify as primary if ordered phases, checkpoints, or state transitions are the dominant behavior.

#### Generator

Pattern ID: `generator`

Purpose:
- Canonical purpose statement: produce a repeatable output artifact that conforms to an explicit template, schema, or constrained format.
- Success condition: outputs are complete, internally consistent, and reliably match the expected shape across repeated runs.

Required characteristics:
- The skill defines an explicit output structure, template, schema, or formatting contract to fill.
- The core job is artifact creation or transformation, not evaluation of an existing artifact.
- Output completeness and consistency matter at least as much as factual lookup or process orchestration.
- The result can be judged directly against the target format without needing a separate external reference lookup to define success.

Exclusion boundaries:
- Do not classify as primary if the dominant job is inspecting existing work and emitting findings, severity calls, or pass/fail judgments.
- Do not classify as primary if the dominant job is supplying external dependency or API context before another skill acts.
- Do not classify as primary if the dominant job is requirement gathering, clarification, or gated questioning before action.
- Do not classify as primary if the skill primarily coordinates a multi-step workflow with checkpoints, state transitions, or enforced ordering.

#### Reviewer

Pattern ID: `reviewer`

Purpose:
- Canonical purpose statement: inspect an existing artifact, behavior trace, or candidate output and emit a calibrated judgment with findings, verdicts, severity calls, or prioritized recommendations.
- Success condition: the skill catches materially important issues, suppresses low-signal noise, and explains each judgment clearly enough for a human to verify it.

Required characteristics:
- The skill evaluates something that already exists or has already been produced; it is not primarily generating the artifact under review.
- The skill uses a checklist, rubric, scoring model, or explicit review criteria to decide pass/fail, severity, or priority.
- The primary output is evaluative rather than generative: findings, verdicts, scores, rankings, or remediation priorities tied to the inspected input.
- The skill calibrates issue importance by severity, confidence, priority, or threshold instead of treating all observations as equally important.

Exclusion boundaries:
- Do not classify as primary if the dominant job is drafting or transforming the artifact itself from a template, schema, or house style.
- Do not classify as primary if the dominant job is supplying external dependency, platform, or API context for another step to use.
- Do not classify as primary if the dominant job is eliciting missing requirements before any substantive review can happen.
- Do not classify as primary if ordered phases, checkpoints, or workflow state transitions are more central than review judgment quality.

#### Inversion

Pattern ID: `inversion`

Purpose:
- Canonical purpose statement: invert the default "act immediately" behavior by forcing requirement gathering, ambiguity reduction, or scope clarification before the agent is allowed to execute.
- Success condition: the skill asks the highest-value clarifying questions, establishes a clear go/no-go threshold, and only proceeds once the task is sufficiently specified.

Required characteristics:
- The skill explicitly gathers missing requirements, assumptions, or constraints before attempting the main deliverable.
- It defines a gating rule, ambiguity threshold, stop condition, or interview completion check that determines when execution may begin.
- The questioning adapts to uncovered uncertainty rather than acting as a fixed boilerplate preamble.
- Requirement coverage and decision-readiness matter more than immediate artifact generation on the first pass.

Exclusion boundaries:
- Do not classify as primary if the skill normally produces the final artifact immediately and any questions are optional, perfunctory, or purely stylistic.
- Do not classify as primary if the dominant job is scoring, reviewing, or prioritizing an existing artifact against a rubric.
- Do not classify as primary if the dominant job is supplying reference material about a dependency, platform, or API.
- Do not classify as primary if the dominant behavior is an ordered execution workflow after inputs are already known and accepted.

#### Pipeline

Pattern ID: `pipeline`

Purpose:
- Canonical purpose statement: orchestrate a multi-step workflow where progress depends on explicit phase ordering, checkpoint enforcement, state transitions, and handoff artifacts.
- Success condition: the skill moves work through the correct stages in order, preserves the required intermediate state, and blocks unsafe or premature progression.

Required characteristics:
- The skill defines explicit ordered stages, phases, or checkpoints where later work depends on outputs or approvals from earlier stages.
- Persistent state, handoff artifacts, or progress markers are used to resume, verify, or advance work across steps.
- The skill enforces gate conditions, stop/resume rules, or advancement checks rather than treating every step as optional guidance.
- Correctness depends more on sequencing and gate discipline than on the quality of any single isolated output.

Exclusion boundaries:
- Do not classify as primary if the dominant job is reviewing, scoring, or prioritizing an existing artifact and any numbered steps are only an internal checklist rather than meaningful workflow state transitions.
- Do not classify as primary if the dominant job is producing a single artifact from a template or schema, even when the instructions are written as numbered steps.
- Do not classify as primary if the dominant job is supplying on-demand reference context, API guidance, or tool usage notes without enforced stage transitions.
- Do not classify as primary if the dominant job is requirement gathering before action and any later steps are contingent follow-through rather than persistent pipeline orchestration.

### Pattern Spec Comparison Rules

Use these rules when comparing version N vs N+1 of the same skill's pattern specification:

1. Compare only within the same `pattern_id`.
   - If the primary `pattern_id` changes, flag the change as a `reclassification` rather than a normal field-level improvement/regression.
2. Compare `purpose` semantically.
   - Treat changes to the job-to-be-done, success condition, or "act now vs gather first" timing as material changes even when wording is similar.
3. Compare `required_characteristics` as explicit structural deltas.
   - Surface each item as `added`, `removed`, `tightened`, or `relaxed`.
   - Do not collapse those changes into a prose-only summary.
4. Compare `exclusion_boundaries` as boundary deltas.
   - Any addition or removal widens or narrows the classification boundary and must be surfaced separately from required-characteristic changes.
   - Boundary changes are high-sensitivity because they change what the pattern is *not* allowed to cover.
5. Do not satisfy one pattern's `required_characteristics` with another pattern's `exclusion_boundaries`.
   - Comparison is field-to-field and pattern-to-pattern, not a free-form prose interpretation.

### Pattern-to-Eval Mapping (Legacy Alias)

Use `Strategy Definitions` as the canonical section name. Older docs may still point here.

### Strategy Definitions

All five patterns still use the same v4 foundation:
- The same 7-phase AutoRefine pipeline
- The same canonical Phase 1 dimensions: `gotchas`, `voice`, `progressive_disclosure`, `anti_railroading`, `description_quality`, `scripts`
- The same eval category family: `structural`, `task-completion`, `quality`

What changes by pattern is which dimensions carry the most signal, how failure analysis is clustered, which judge tactics dominate, and what mutation targets matter most.

Each strategy row below is a downstream execution route. Once `selected_eval_strategy_id` is restored for the active run, later phases should execute the matching row instead of improvising a generic eval path.

| Strategy ID | Pattern | Phase 1 dimensions that shift | Eval category emphasis | Phase 3: Failure focus | Phase 5/6: Judge and validation tactics | Phase 7: Mutation priority |
|-------------|---------|-------------------------------|------------------------|------------------------|-----------------------------------------|----------------------------|
| `tool_wrapper_eval_strategy` | Tool Wrapper | `gotchas`, `description_quality`, and `scripts` carry the most signal. `anti_railroading` should penalize hardcoded stale commands, forced tool paths, or one-true-way usage advice. `progressive_disclosure` checks that reference loading happens only when needed. | `task-completion` means factual correctness on the dependency/tool question. `quality` means trigger precision, caveats, and freshness. `structural` is supporting only. | Wrong API advice, stale flags, hallucinated capabilities, missing prerequisites, bad trigger boundaries. | Use fixtures with known-good source answers, unsupported/negative cases, and trigger-vs-no-trigger prompts. Judges must anchor verdicts in source-aligned evidence and separate factual accuracy from polished wording. Validation should include unseen examples so freshness/recall is not tuned only to the dev set. | Refresh references, sharpen trigger language, improve gotchas, remove stale commands/examples, clarify when to load docs. |
| `generator_eval_strategy` | Generator | `progressive_disclosure`, `voice`, and `scripts` focus on making the output contract easy to follow. `anti_railroading` may allow strict output schemas, but should still penalize unnecessary tool/path/order rigidity outside the schema contract. | `structural` and `quality` dominate. `task-completion` means all required fields/sections are produced, but the main risk is schema drift or inconsistent formatting. | Missing fields, schema drift, inconsistent formatting, style drift, weak examples, partial template fill. | Use repeated prompt variants, schema validators, completeness checks, and pairwise consistency judges across runs. Validation should test whether the skill preserves structure across equivalent prompts, not just whether a single sample looked good once. | Tighten templates, examples, field coverage, formatting instructions, style guardrails, section ordering. |
| `reviewer_eval_strategy` | Reviewer | `gotchas` and `description_quality` focus on review scope and when this reviewer should trigger. `anti_railroading` should penalize pre-baked conclusions, but explicit severity rubrics and evidence requirements are desirable rigidity. | `task-completion` means catching the right issues. `quality` means severity calibration, prioritization, and evidence quality. `structural` is secondary. | Missed critical issues, false positives, wrong severity, weak evidence chains, noisy/unprioritized findings. | Seed fixtures with known defects and gold severities. Judges should score issue recall/precision, severity agreement, and evidence-linked findings rather than mere formatting. Validation should track disagreement by severity band, not only aggregate pass rate. | Refine checklist coverage, severity anchors, evidence requirements, prioritization rules, and false-positive suppression guidance. |
| `inversion_eval_strategy` | Inversion | `progressive_disclosure`, `description_quality`, and `anti_railroading` dominate. Question-gating is required behavior and should not be treated as rigidity. `gotchas` focus on when not to proceed and which unknowns must be surfaced. | `task-completion` means making the correct ask-vs-act decision. `quality` means question prioritization, depth, and stop condition clarity. `structural` is minimal unless the skill has an interview artifact. | Premature action, skipped clarifications, shallow probing, missed contradictions, unclear readiness thresholds, endless questioning without convergence. | Use under-specified, contradictory, and edge-threshold prompts. Judges should score whether the skill asks the highest-value next question, pauses appropriately, and only proceeds once the readiness rule is met. Validation should track false-proceed vs false-block behavior on ambiguous cases. | Improve question tree quality, readiness thresholds, stop/go rules, ambiguity handling, and transition from interview mode to execution mode. |
| `pipeline_eval_strategy` | Pipeline | `scripts` and `progressive_disclosure` focus on stage-local loading and handoff clarity. `anti_railroading` bypasses penalties for stage order/checkpoints and should only flag avoidable within-stage rigidity. `description_quality` must make staged orchestration obvious to the router. | `task-completion` includes completing the workflow safely in order. `structural` matters more here than in other patterns because state files, handoff artifacts, and checkpoints are part of correctness. `quality` covers stage clarity and recovery guidance. | Skipped steps, bypassed gates, bad resume behavior, state corruption, broken handoffs, already-complete-work mishandling. | Use end-to-end traces plus partial-state resume cases, already-complete-work cases, and missing-artifact cases. Judges should verify checkpoint enforcement, artifact creation, and safe stage transitions. Validation should measure rerun/resume stability, not just one clean from-scratch pass. | Clarify gates, resume/handoff rules, state writes, stage-local instructions, checkpoint artifacts, and safe recovery paths. |

Pattern-specific downstream rules:
- Tool Wrapper: prefer reference-grounded evals over format-heavy rubric checks. A well-formatted wrong answer is still a hard fail.
- Generator: prefer repeated-structure and completeness checks over open-ended judge prose. One lucky well-formed sample is not enough.
- Reviewer: prioritize seeded-issue recall, severity agreement, and evidence quality over template neatness.
- Inversion: score the decision to keep asking as part of task completion. A skill that acts too early should fail even if its eventual artifact is good.
- Pipeline: treat resume correctness, gate integrity, and handoff artifact presence as first-class eval targets. Stage ordering is invariant, not a flexibility defect.

### Classification in state.json

```json
{
  "skill_pattern": "pipeline",
  "phase1_context": {
    "selected_skill_pattern": "pipeline",
    "selected_eval_strategy_id": "pipeline_eval_strategy",
    "selection_scope": "current_run",
    "source_skill_path": "skill-under-test/SKILL.md"
  }
}
```

Valid values: `"tool_wrapper"`, `"generator"`, `"reviewer"`, `"inversion"`, or `"pipeline"`.
Persist exactly one canonical pattern ID in `phase1_context.selected_skill_pattern` and exactly one canonical strategy ID in `phase1_context.selected_eval_strategy_id` for the active run. Do not write candidate arrays, hybrid labels, or secondary-pattern lists into the run-scoped Phase 1 context.
Gate all downstream Phase 1 processing on `phase1_context.selected_skill_pattern` and `phase1_context.selected_eval_strategy_id` being captured for the active run.
If `phase1_context.selected_skill_pattern` is null, missing, empty, or mismatched with `state.json.skill_pattern`, stop Phase 1 immediately and rerun Step 0 before scoring any dimension.
If `phase1_context.selected_eval_strategy_id` is null, missing, empty, or does not map back to the same `selected_skill_pattern` through `Pattern-to-Evaluation-Strategy Selector`, stop Phase 1 immediately and rerun strategy selection before scoring any dimension.
When the classifier-orchestration boundary rejects a payload, emit a structured stop payload instead of silently repairing the result.
The structured stop payload must include `fallback_allowed: false` and enough detail for a human to inspect the failed boundary decision before rerunning classification.
Example boundary stop payload:

```json
{
  "status": "stopped",
  "blocking": true,
  "fallback_allowed": false,
  "stop_before": "downstream_routing",
  "error_code": "mismatched_selected_eval_strategy_id",
  "invalid_field": "selected_eval_strategy_id",
  "invalid_value": "reviewer_eval_strategy",
  "selected_skill_pattern": "generator",
  "expected_selected_eval_strategy_id": "generator_eval_strategy",
  "raw_classifier_result": {
    "selected_skill_pattern": "generator",
    "selected_eval_strategy_id": "reviewer_eval_strategy"
  },
  "message": "phase1 classifier result produced mismatched selected_eval_strategy_id 'reviewer_eval_strategy'; expected 'generator_eval_strategy' for pattern 'generator'"
}
```

### Session-log entry

```json
{"phase":"1","type":"pattern_classification","pattern":"pipeline","reasoning":"Skill has 7 ordered phases with human gates and state.json transitions"}
```

---

## Eval Category Tags Schema

Read when: Phase 5 Step 1b (assigning category tags to evals).

### Categories

| Category | What it measures | When to use |
|----------|-----------------|-------------|
| `structural` | Presence of required sections, artifacts, or format elements | "Gotchas section exists", "Output has 3+ examples", "Headers follow template" |
| `task-completion` | Whether the skill achieves its core intended task | "Output addresses primary entity", "All pipeline steps executed", "Query answered" |
| `quality` | Output quality, style, rubric adherence beyond task completion | "Voice is instructional not descriptive", "Disclosure is progressive", "Examples are diverse" |

### Format in eval-suite.md

Each eval gets a `Category:` field in its metadata block:

```markdown
EVAL 1: [Gotchas Section Present]
Type: code-based | Category: structural
Source: standard | Validated: true
PASS: Skill output contains a ## Gotchas section with at least one specific warning
FAIL: No gotchas section or only generic warnings

EVAL 2: [Output Addresses Primary Entity]
Type: agent-as-judge | Category: task-completion
Source: standard | Validated: true
PASS: Output directly addresses the user's primary entity/question
FAIL: Output is generic or addresses a different entity

EVAL 3: [Voice Is Instructional Not Descriptive]
Type: agent-as-judge | Category: quality
Source: standard | Validated: true
PASS: Skill uses imperative/instructional voice ("Do X", "Run Y")
FAIL: Skill describes what could be done rather than instructing ("One could X")
```

### Per-Category Score Computation

At Session Close, compute separate pass rates per category:

```python
# Pseudocode
for category in ["structural", "task-completion", "quality"]:
    category_evals = [e for e in eval_results if e.category == category]
    passing = sum(1 for e in category_evals if e.pass_fail == "pass")
    total = len(category_evals)
    print(f"{category}: {passing}/{total} ({100*passing/total:.0f}%)")
```

### Session-log entry

```json
{"phase":"5","type":"eval_category_tags","detail":"Tagged 7 evals: 2 structural, 3 task-completion, 2 quality"}
```

---

## Version Registry Schema

Read when: Phase 7 (after kept mutation) or Session Close (version summary).

The version registry is a **derived view** — it is computed on demand from `results.json`, not stored as a separate file.

### Computation

```python
# Pseudocode — handles loop-backs where experiments span multiple run directories.
# Phase 7 may create multiple runs on loop-back, each with its own run_<timestamp>/.
experiments = results_json["experiments"]

# Build experiment_id -> run_path map from all iteration directories on disk
exp_to_run = {}
for run_dir in sorted(glob("runs/run_*/")):
    for iter_dir in sorted(glob(f"{run_dir}iteration_*/")):
        exp_id = int(iter_dir.split("iteration_")[1].rstrip("/"))
        exp_to_run[exp_id] = run_dir

versions = []
for exp in sorted(experiments, key=lambda e: e["id"]):
    if exp["status"] in ("baseline", "keep"):
        run_path = exp_to_run.get(exp["id"], current_run)
        version_label = f"v{len(versions)}"
        versions.append({
            "version": version_label,
            "experiment_id": exp["id"],
            "status": exp["status"],
            "score": exp.get("decision_breakdown", {}).get("combined_score_pct"),
            "description": exp["description"],
            "completion_cadence": exp.get("completion_cadence"),
            "requires_human_spot_check": exp.get("requires_human_spot_check"),
            "iteration_path": f"{run_path}iteration_{exp['id']:03d}/",
            "skill_snapshot": f"{run_path}iteration_{exp['id']:03d}/skill_after.md"
        })
```

Carry the stored `completion_cadence` snapshot through the derived view unchanged. This lets dashboards or production consumers read the finalized cadence position for each version without recomputing it from partial run history.
Carry the stored `requires_human_spot_check` flag through the derived view unchanged. Do not recompute it from version index, cadence order, or filtered experiment order.

### Version Labels

- `v0` = baseline (experiment 0, status "baseline")
- `v1` = 1st kept mutation
- `v2` = 2nd kept mutation
- `vN` = Nth kept mutation

Discarded experiments do NOT receive version labels. They remain in results.json with full forensic detail but are not part of the version lineage.

### Display Format

After a kept mutation in Phase 7:
```
Kept as v3 (78.5%, +16.2pp from v0)
```

At Session Close, show the version timeline:
```
Version History
  v0  baseline   62.3%  --
  v1  kept       70.1%  +7.8pp  "Added gotcha warnings for path handling"
  v2  kept       74.8%  +4.7pp  "Restructured progressive disclosure"
  v3  kept       78.5%  +3.7pp  "Improved example diversity"
```

---

## Version Comparison Template

Read when: Phase 7 (after kept mutation, compare vs previous version) or Session Close (compare v0 vs vN).

### Prerequisites

Before rendering a comparison, run the comparison preflight from `Version Comparison Alignment` section. Only proceed if the preflight passes (same `input_set_id`, exact same `input_ids`).

### Per-Input Layout

For each shared-input comparison entry, render two explicitly labeled output panels: `Before` and `After`. Use a consistent two-column side-by-side layout on wider screens, and collapse to a stacked layout on narrow screens while preserving the same `Before` then `After` order. Within those panels, visually highlight only the sections that changed and leave unchanged sections unaccented for quick scanning.

### Side-by-Side Format

```text
Version Comparison: v1 -> v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Eval              v1        v3        Delta
────────────────────────────────────────────────────
E1 (code)         Pass      Pass      --
E2 (agent)        Fail      Pass      improved
E3 (agent)        Pass      Pass      --
E4 (code)         Pass      Pass      --
E5 (agent)        Pass      Fail      REGRESSED
────────────────────────────────────────────────────
Pass rate         80.0%     80.0%     --
Weighted score    82.3%     85.1%     +2.8pp
Shared inputs     1 improved / 1 regressed / 3 unchanged
────────────────────────────────────────────────────

Skill diff (v1 -> v3):  [expandable]
```

### Delta Indicators

- `--` = no change
- `improved` = was Fail, now Pass
- `REGRESSED` = was Pass, now Fail

### Aggregate Metrics

| Metric | Computation |
|--------|------------|
| Pass rate | `passing_evals / total_evals` for each version |
| Weighted score | From `decision_breakdown.combined_score_pct` |
| Shared input outcomes | From `shared_input_summary.improved`, `shared_input_summary.regressed`, and `shared_input_summary.unchanged`; counts must sum to `shared_input_summary.total_shared_inputs` |

### Skill Diff

Show a markdown diff of the skill content between versions. Use the `skill_after.md` files from each version's iteration directory:
- Left: `runs/.../iteration_{left_exp}/skill_after.md`
- Right: `runs/.../iteration_{right_exp}/skill_after.md`

Collapse by default — show only on user expansion. Highlight additions, deletions, and modifications.

### When to Show

1. **Phase 7, after kept mutation:** Compare the just-kept version against the previous kept version (or baseline if this is v1). Append to the Aggregation Explainer output.
2. **Session Close:** Compare v0 (baseline) against vN (final kept version). Part of the Version Comparison Summary.
3. **On user request:** "Compare v2 and v4" — compute both versions from the registry and render the template.
