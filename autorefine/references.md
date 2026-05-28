# AutoRefine References

Templates, schemas, methodology rationale, and detailed rubrics. SKILL.md references specific sections — read on demand, not upfront.

---

## Workspace Schemas

Read when: Initialize Workspace or resuming a session.

Workspace directories for new runs are `traces/`, `judges/`, `runs/`, `skill-versions/`, `contract/`, and `domain-eval/`. `skill-versions/` stores immutable per-version `SKILL.md` snapshots for rollback, comparison, and external replay. `domain-eval/` is the shared on-disk surface for adapter-aware evaluation assets and remains the canonical location even when runtime state uses generic adapter field names.

### state.json
```json
{"schema_version":4,"skill_name":"<name>","skill_path":"<path>","original_skill_path":"<path>","workspace_path":"<path>","started":"<today>","current_phase":1,"current_gulf":1,"phases":{},"gates":{"gulf_1":"pending","gulf_2":"pending"},"hamel_available":false,"loop_iteration":0,"locked_judges":[],"memory_path":null,"checkpoint":null,"consecutive_discards":0,"circuit_breaker":null,"current_run_id":null,"current_run_path":null,"current_experiment":null,"iteration_state":null,"completion_cadence":null,"pending_user_override_scan":null,"mid_session_preference_signals":null,"mid_session_preference_signals_path":null,"skill_pattern":null,"phase1_context":null,"mutation_stage_split_access_policy":null,"meta_learnings_path":null,"research_intake":null,"research_intake_path":null,"final_only_evaluation":null,"quick_start":null,"contract_status":null,"contract_path":null,"effectiveness_floor":null,"edit_budget":null,"adapter_config_path":null,"selected_adapter_id":null,"active_experiment_contract_path":null,"domain_eval_config_path":null}
```
- `schema_version`: 4 for v2.3 workspaces. Legacy: 2 = Standard/Deep (v2.1), 3 = Quick Start (v2.2). New fields default to null when reading v2/v3 workspaces.
- `loop_iteration`: tracks Phase 7→5 loop-backs (0 = first run)
- `locked_judges`: judge IDs approved in prior loops — don't re-validate
- `checkpoint`: resume state — see `Checkpoint Schema` section. null when no checkpoint active.
- `original_skill_path`: full path to the user's original skill directory (set in Preflight Step 0.6). Used by Session Close Apply Back gate and ambient learning on resume.
- `workspace_path`: full path to the AutoRefine workspace (set in Preflight Step 0.6).
- `consecutive_discards`: integer (0). Circuit breaker counter — incremented on discard, reset on keep. See SKILL.md Phase 7.
- `circuit_breaker`: null, or `{triggered_count: N, last_experiment: N, diagnosis: "..."}`. Set when circuit breaker fires.
- `edit_budget`: null, or `{"schedule":"constant","max_edits":N,"current_budget":N}`. Bounds how many discrete changes (added/modified/removed sections — the `changes[]` unit) a single Phase 7 mutation experiment may make to the baseline: the textual learning-rate analogue. It is applied as a **generation-time constraint** (the proposer makes at most `current_budget` changes when writing `candidate_skill_revision.content`); there is no post-hoc clip, because the candidate is a full `content` rewrite, not an edit list. null means unbounded (legacy behavior). `schedule` is `constant` for v4.x (`current_budget` always equals `max_edits`); the object shape reserves room for decaying schedules (e.g. `cosine`) later without a migration. Phase 7 iteration-start initializes `edit_budget` to `{"schedule":"constant","max_edits":3,"current_budget":3}` when it is null, so the regularizer is active by default (surgical edits — keeps one mutation from rewriting large regions and overfitting to a single failure); set a different `max_edits`, or set `edit_budget = null` before Phase 7 start to disable. On every load/resume, for a `constant` schedule recompute `current_budget = max_edits` so a stale or hand-edited `current_budget` cannot silently cap mutations differently from the configured `max_edits`. The mutation step records `mutation.md > edit_budget_applied = {current_budget, change_count}`; the circuit breaker reads `edit_budget` plus those records before diagnosing a content ceiling so a too-tight budget is not mistaken for exhausted content.
- When serializing `state.json` for checkpoint writes, phase boundaries, or any other persistence path, preserve `edit_budget` unchanged. When loading or resuming a workspace, restore `edit_budget` into the active run context before Phase 7 routing, applying the `constant`-schedule `current_budget = max_edits` recompute above.
- `current_run_id`: null, or the unique iteration-run identifier for the active Phase 7 execution (for example `run_2026-04-03T14-30-00`). Set exactly once by the single iteration-start trigger at Phase 7 start. Resume/load should use this ID to reopen the matching run record in `results.json.iteration_runs[]` before reading iteration artifacts.
- `current_run_path`: null, or relative path to the current Phase 7 run directory (e.g., `runs/run_2026-04-03T14-30-00/`). Set at Phase 7 start, updated on loop-back. Used by resume to identify which run directory to read `decision.md` files from.
- `current_experiment`: null, or the active Phase 7 experiment slot. Set `current_experiment = 0` for the baseline-in-progress slot when a new iteration run starts, before any `iteration_000/` artifacts exist. Resume/checkpoint flows should use this field together with `current_run_path` to reopen the active baseline or mutation slot instead of guessing from directory scans.
- `iteration_state`: null, or `{"run_id":"run_...","run_path":"runs/run_.../","experiment_id":0,"active_phase":"eval|mutate|test|session_close","phase_status":"running|ready|completed|blocked","last_eval_status":"completed|invalid|blocked|null","last_eval_results_ref":"runs/.../iteration_000/eval_results.json|null","last_mutation_status":"completed|skipped|invalid|blocked|null","last_mutation_results_ref":"runs/.../iteration_001/mutation.md|null","next_action":"phase7_baseline_eval|phase7_mutation_analysis|phase7_test_phase|phase7_session_close|null"}`. This is the canonical runner handoff record for the active Phase 7 run.
- On the iteration-start write, initialize `iteration_state` with the new `run_id`, `run_path`, `experiment_id = 0`, `active_phase = "eval"`, `phase_status = "running"`, `last_eval_status = null`, `last_eval_results_ref = null`, and `next_action = "phase7_baseline_eval"`.
- When the baseline eval finishes and `iteration_000/eval_results.json` exists, update the same `iteration_state` object to `active_phase = "mutate"`, `phase_status = "ready"`, `last_eval_status = "completed"`, `last_eval_results_ref = "runs/.../iteration_000/eval_results.json"`, and `next_action = "phase7_mutation_analysis"`. This is the explicit eval-to-mutate handoff for the same run; do not create a new `run_id`, `run_path`, or run record.
- When later mutation evals finish, overwrite `iteration_state.experiment_id`, `last_eval_status`, and `last_eval_results_ref` for the current `iteration_<NNN>/eval_results.json` while keeping the same run identifiers. Resume/load should reopen the latest eval artifact from this object instead of rescanning directories.
- When the mutate phase finishes for an experiment with a real candidate, record the mutation output/status on the same `iteration_state` object (`last_mutation_status = "completed"`, `last_mutation_results_ref = "runs/.../iteration_<NNN>/mutation.md"`), then automatically advance the same run into test by setting `active_phase = "test"`, `phase_status = "ready"`, and `next_action = "phase7_test_phase"`. Do not open a second run.
- When the mutate phase resolves to a no-op / skip result, record `last_mutation_status = "skipped"` and `last_mutation_results_ref = "runs/.../iteration_<NNN>/mutation.md"` on the same `iteration_state` object, keep `active_phase = "mutate"`, keep the current baseline active, and keep `next_action = "phase7_mutation_analysis"` so the run can re-target, continue, or stop without fabricating a scored candidate.
- When the test phase finishes for an experiment, automatically advance the same run into Session Close by setting `active_phase = "session_close"`, `phase_status = "ready"`, and `next_action = "phase7_session_close"` on the same `iteration_state` object.
- Session Close resolves the run to a terminal state on that same object: success writes `active_phase = "session_close"`, `phase_status = "completed"`, `next_action = null`; unrecoverable failure writes `active_phase = "session_close"`, `phase_status = "blocked"`, `next_action = null`.
- When serializing `state.json` for checkpoint writes, phase boundaries, or any other persistence path, preserve `iteration_state` unchanged so the active eval->mutate->test->session_close handoff survives resume.
- When loading or resuming a workspace, deserialize `iteration_state` into the active run context before Phase 7 routing. Treat it as authoritative over directory scans when deciding whether the current run is in eval, mutate, test, session_close-ready, or a terminal completed/blocked state.
- `completion_cadence`: null, or `{"scope_type":"experiment_series|skill","scope_id":"<stable-scope-id>","completed_experiments":N,"last_finalized_experiment_id":N,"last_finalized_status":"baseline|keep|discard","incremented_at":"<ISO-timestamp>"}`. Default scope is the active Phase 7 run directory (`experiment_series` via `state.json.current_run_path`); use `skill` only when one cadence counter should span multiple Phase 7 runs for the same skill.
- Increment `completion_cadence.completed_experiments` exactly once when an experiment reaches its finalized state. Finalized means: baseline after `iteration_000/` artifacts are written, keep after the user-confirmed keep verdict and iteration write, discard after discard autopsy plus iteration write. Do not increment for provisional scores, regression checks, or pre-autopsy discard proposals.
- `pending_user_override_scan`: null, or the active-loop cadence task from `User Override Scan Task Schema`. Queue or update it whenever the post-finalization `completion_cadence.completed_experiments` value is divisible by 3 and `iteration_state.phase_status` remains `running` or `ready`. The scan window is the last 3 finalized experiments in the current active refinement loop.
- `mid_session_preference_signals`: null, or `{"status":"not_detected|pending_confirmation|confirmed|applied|skipped","source_task_ref":"checkpoint-tasks/exp6-user-override-scan.json|null","source_window_experiment_ids":[4,5,6],"signals":[{"preference_key":"verbosity","preference_value":"concise", "...":"preference_signal payload"}],"detected_signal_count":N,"confirmed_signal_count":N,"last_detected_at":"<ISO-timestamp>|null","last_confirmed_experiment_id":N|null}`. Session-level ledger for style-preference signals detected from the cadence-triggered override scan. `signals[]` stores normalized `preference_signal` payloads so later mutation steps and exports can reuse the same explainable records without reparsing markdown.
- `mid_session_preference_signals_path`: null, or `[workspace]/preferences.md`. Refresh this mirrored path whenever the override scan runs so the session keeps one stable human-facing preference ledger location, even while the latest scan is still `not_detected`, `pending_confirmation`, or `skipped`. Confirmed detections append rules to that file and keep mirroring the same resolved path here so resume-time mutation steps can reopen the same artifact without guessing.
- Whenever the cadence-triggered override scan runs, write or refresh `mid_session_preference_signals` and `mid_session_preference_signals_path` in both `state.json` and `results.json` from that scan's latest window. Overwrite stale `source_task_ref`, `source_window_experiment_ids`, counts, and `last_detected_at` with the current scan result. If no reusable rule is found, persist `status:"not_detected"` with `signals: []` instead of carrying older confirmed signals forward as if they were freshly detected.
- When serializing `state.json` for checkpoint writes, phase boundaries, or any other state rewrite, preserve `mid_session_preference_signals` and `mid_session_preference_signals_path` unchanged so detected style-preference signals survive resume.
- When deserializing or loading `state.json` on startup/resume, restore `mid_session_preference_signals` and `mid_session_preference_signals_path` into the loaded run context before Phase 7 mutation analysis. If `mid_session_preference_signals.status` is `confirmed` or `applied`, treat its `signals[]` entries as the current run's machine-readable mid-session preference ledger and use the mirrored path to reopen `[workspace]/preferences.md` only when the human-readable file is needed.
- After restoring `mid_session_preference_signals` and `mid_session_preference_signals_path`, immediately rebuild the normalized active-loop `style_preferences` payload using `Style Preferences Payload` and keep that envelope in the loaded run context across eval, mutate, test, and session_close. Mid-loop stages should read `style_preferences.active_signals` and `style_preferences.resolved_preferences_path` instead of reparsing raw state or rescanning override sources ad hoc.
- When serializing `state.json` for phase boundaries, checkpoint writes, or any other state rewrite, preserve the full `phase1_context` object unchanged so the chosen pattern survives persistence.
- When deserializing or loading `state.json` on startup/resume, restore `phase1_context` into the loaded run context before routing or resuming later phases.
- `phase1_context`: null, or `{"selected_skill_pattern":"<pattern_id>","selection_scope":"current_run","source_skill_path":"skill-under-test/SKILL.md"}`. Minimal run-scoped Phase 1 context shape used by downstream pattern-state checks.
- `phase1_context`: null, or `{"selected_skill_pattern":"<pattern_id>","selected_eval_strategy_id":"<strategy_id>","selection_scope":"current_run","source_skill_path":"skill-under-test/SKILL.md"}`. Run-scoped Phase 1 context persisted immediately after pattern classification + strategy selection and overwritten whenever Phase 1 reruns for the active workspace copy.
- When serializing `state.json` for phase boundaries, checkpoint writes, or any other state rewrite, preserve the full `phase1_context` object unchanged so the chosen pattern and resolved evaluation strategy survive persistence.
- When deserializing or loading `state.json` on startup/resume, restore `phase1_context` into the loaded run context before routing or resuming later phases. Later phases must read the chosen pattern and resolved evaluation strategy from the loaded context rather than recomputing classification ad hoc.
- `mutation_stage_split_access_policy`: null, or the exact machine-readable object from `Mutation-Stage Split Access Policy`. Phase 4 writes it into `state.json` as the active Phase 7 dataset-read gate for this workspace/run.
- When serializing `state.json` for phase boundaries, checkpoint writes, or any other state rewrite, preserve `mutation_stage_split_access_policy` unchanged so the active dataset-read policy survives persistence.
- When deserializing or loading `state.json` on startup/resume, restore `mutation_stage_split_access_policy` into the loaded run context before routing into Phase 7 or Session Close. If split-scoped Phase 7 work is active and the field is missing, read the same policy from `fixtures-manifest.md` or a stored Phase 4 `evaluation_metadata.config.mutation_stage_split_access_policy` snapshot, hydrate the run context, and stop if those sources disagree.
- `meta_learnings_path`: null, or an absolute path to the curated `meta-learnings.md` file for this run. When null, default to the AutoRefine skill directory copy. This field only points to the source document; do not persist parsed bundle contents here.
- When a session may enter Phase 7 or Session Close, campaign bootstrap must resolve `meta_learnings_path`, normalize the current target context (`skill_pattern`, `agent_target`, `scenario_target`, `scope_type`, `scope_ref`), and hydrate the loaded run context with the `Campaign Bootstrap Meta-Learnings Context`. Rebuild that object on every start/resume instead of caching parsed entries in `state.json`.
- `research_intake`: null, or `{"status":"not_requested|skipped|in_progress|completed|partial|failed","target_skill_path":"skill-under-test/SKILL.md","target_domain":"<one-sentence target job>","requested_sources":0,"accepted_sources":0,"rejected_sources":0,"completed_at":"<ISO-timestamp>|null","error_code":"none|target_skill_missing|target_domain_missing|missing_phase1_context|no_valid_sources|artifact_write_failed|invalid_research_intake_config"}`. Phase 6.5 stage ledger. `completed` and `partial` mean Phase 7 may read `research-intake.md`; `failed` is blocking and `skipped` means continue with internal-only mutation analysis.
- `research_intake_path`: null, or `[workspace]/research-intake.md`. Set only when the current run wrote a readable research intake artifact for the current target skill/domain.
- `final_only_evaluation`: null, or `{"run_path":"runs/run_2026-04-03T14-30-00/","stage_id":"session_close_holdout_validation","status":"completed|skipped|failed|aborted","triggered_after_loop":true,"triggered_from":"session_close_step_0c","evaluated_experiment_id":N|null,"evaluated_experiment_ids":[0,2,4],"variant_results_ref":"runs/run_2026-04-03T14-30-00/session_close_holdout/variant_results.json","reason":"<resolved-exit-reason|null>"}`. This is the idempotence guard for the post-loop final-only evaluation stage.
- When a new Phase 7 run starts and the stored `final_only_evaluation.run_path` is absent or differs from the new `state.json.current_run_path`, clear it back to null as part of the same run-start write. Only the active run's holdout marker should remain live in top-level state.
- Write `final_only_evaluation` exactly once after the mutation loop exits for the active `current_run_path`. Intermediate mutation iterations must never write or modify this field.
- If Session Close resumes and `final_only_evaluation.run_path` already matches `state.json.current_run_path` with `status = completed` or `status = skipped`, reuse the stored outcome instead of rerunning the final-only evaluation stage.
- `evaluated_experiment_id` is the selected final candidate. Reopen `state.json.final_only_evaluation.variant_results_ref` and read `selected_candidate_summary` for the authoritative holdout score. If you need dev-side tuning diagnostics such as the dev score or holdout gap, read the sibling `optimization_metrics` section from the same artifact. Do not mirror those numeric outputs into top-level state.
- `evaluated_experiment_ids` records the completed variant lineage that the final evaluation runner actually scored on the holdout split.
- `variant_results_ref` points at the ordered per-variant holdout results artifact written by `Final Holdout Variant Runner`.
- All machine-readable Session Close holdout outputs live only in that dedicated artifact. Top-level state keeps the idempotence guard plus reopen/ref metadata, not a second copy of holdout scores or per-variant rows.
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
- `contract_status`: null, or `"not_started" | "collecting" | "inferred" | "confirmed" | "skipped"`. Tracks Phase 0.5 progress. Null and `"not_started"` both trigger Phase 0.5 entry; `"collecting"` means Phase 0.5 is mid-wizard gathering examples; `"inferred"` means examples collected but author correction not yet applied; `"confirmed"` means contract is ready for downstream consumption; `"skipped"` bypasses Phase 0.5 entirely. On resume, `"collecting"` and `"inferred"` states route back into Phase 0.5 to continue from where the wizard stopped.
- `contract_path`: null, or `[workspace]/contract/`. Set when Phase 0.5 creates the contract directory. Contains `success-examples.jsonl`, `failure-examples.jsonl`, `do-not-trigger-examples.jsonl`, and `inferred-contract.md` per `Contract Example Schema` and `Inferred Contract Template`.
- `effectiveness_floor`: null, or the floor result object from Phase 1b (see `Effectiveness Floor Schema > Floor Result`). Persisted for dashboard and Session Close delta reporting.
- `adapter_config_path`: null, or `[workspace]/domain-eval/config.json`. Canonical runtime pointer for adapter-aware evaluation config. This is the generic state field later phases should prefer.
- `selected_adapter_id`: null, or the confirmed adapter identifier for the active workspace copy (for example `search_retrieval_v1` or `code_verification_v1`). Suggestions from pattern classification do not populate this field until the author confirms activation.
- `active_experiment_contract_path`: null, or `[workspace]/runs/<run-id>/experiment-contract.json`. Canonical run-scoped contract artifact for adapter-aware mutation/evaluation loops. This file is written before a bounded run, then read by both the mutation actor and the evaluator.
- `domain_eval_config_path`: null, or `[workspace]/domain-eval/config.json`. Set when author provides domain eval assets in Phase 0.5 Step 7. See `Domain Eval Config Schema`.
- `domain_eval_config_path` is a legacy alias for `adapter_config_path`. New writes should keep both fields aligned when the config lives at `[workspace]/domain-eval/config.json`, but downstream logic should prefer `adapter_config_path` when both are present.

### results.json
```json
{"skill_name":"<name>","status":"running","current_experiment":0,"iteration_state":null,"baseline_score":null,"noise_floor":null,"best_score":null,"completion_cadence":null,"pending_user_override_scan":null,"mid_session_preference_signals":null,"mid_session_preference_signals_path":null,"iteration_runs":[],"meta_learning_outcomes":[],"meta_learning_audit_records":[],"experiments":[],"eval_breakdown":[]}
```
Result retrieval consumers must also preserve the root-level `noise_floor` when they serialize or return this payload. Do not strip the derived session baseline-variance summary from the returned payload.
If the payload already stores `noise_floor`, return the stored object unchanged. Otherwise derive it from the Experiment 0 `baseline_trials[]` collection and publish it alongside `baseline_score` as the baseline-run summary for the session output.
`noise_floor` is a derived summary over Experiment 0 `baseline_trials[]`, not a second authoritative baseline artifact. Preserve the stored summary when present, but treat `baseline_trials[]` as the source record that produced it.
Result retrieval consumers must also preserve the root-level `iteration_state` object unchanged. Do not rebuild the eval-vs-mutate runner state from `current_experiment`, directory scans, or dashboard timers when the persisted handoff record is already present.
Result retrieval consumers must also preserve the root-level `pending_user_override_scan` cadence hook when it is present. If the writer has not materialized it yet, retrieval consumers may derive the same hook from the persisted `completion_cadence`, the active `iteration_state`, and the last 3 finalized experiments while the refinement loop is still active.
`pending_user_override_scan` is a session-level checkpoint task, not an experiment-level verdict field. Its job is to surface the last-3-experiment override window at every third completed experiment without reopening session-log history.
Result retrieval consumers must also preserve the root-level `mid_session_preference_signals` ledger unchanged when it is present. Do not collapse confirmed signals into prose-only summaries, rebuild them heuristically from `preferences.md`, or drop the typed `signals[]` payload that explains what the scan detected.
Result retrieval consumers must also preserve the root-level `mid_session_preference_signals_path` unchanged when it is present. That mirrored path is the authoritative human-readable persistence location for the current session's detected style preferences.
Serialized reporting payloads should also expose the normalized root-level `style_preferences` envelope from `Style Preferences Payload`. If the stored payload only has `mid_session_preference_signals` and `mid_session_preference_signals_path`, rebuild `style_preferences` on retrieval so downstream stage handoffs, dashboards, and production consumers all read one stable active-loop preference context.
Result retrieval consumers must also preserve the root-level `iteration_runs[]` ledger unchanged. Do not collapse it into `current_run_path`, derive it from directory scans, or drop the run-start metadata needed by production systems.
`iteration_runs[]` is the append-only run-start ledger written by the single iteration-start trigger at Phase 7 start. Each row uses `Iteration Run Record Schema` and links one unique `run_id` to the target skill/version snapshot that baseline scoring will evaluate.
Result retrieval consumers must also preserve the root-level `meta_learning_bootstrap_context` when it is present in the stored run output. Do not strip `curator_source`, `curator_version`, `transfer_parameters`, or `transfer_traceability` from the returned payload.
If an older run output only stores `meta_learnings_path`, `target_context`, and `parsed_meta_learnings` at the root, synthesize `meta_learning_bootstrap_context` on retrieval so exports and report renderers can read one stable envelope.
Result retrieval consumers may additionally derive `meta_learning_filter_index` for export/filter flows. This additive index should expose deduplicated `curator_sources[]`, `curator_versions[]`, `transfer_signatures[]`, and `filter_refs[]` copied from `meta_learning_bootstrap_context.transfer_traceability` without mutating the stored run payload.
Result retrieval consumers must also preserve the root-level `meta_learning_outcomes[]` ledger unchanged when present. Do not drop per-run meta-learning effectiveness rows or rebuild them heuristically from version deltas.
Each `meta_learning_outcomes[]` row must follow `Meta-Learning Outcome Record Schema` and stay keyed to the original `run_id` plus `meta_learning_id`.

### Style Preferences Payload

Use this normalized payload as the active refinement-loop context for mid-session style steering. Build or rebuild it from `state.json.mid_session_preference_signals` plus `state.json.mid_session_preference_signals_path` on every start/resume and after any loop-iteration state refresh; then keep the same envelope available to all mid-loop stages instead of recomputing active signals ad hoc.

```json
{"schema_version":1,"payload_type":"style_preferences","status":"not_detected|pending_confirmation|confirmed|applied|skipped|null","source_task_ref":"checkpoint-tasks/exp6-user-override-scan.json|null","source_window_experiment_ids":[4,5,6],"signals":[{"preference_key":"verbosity","preference_value":"concise","...":"preference_signal payload"}],"active_signals":[{"preference_key":"verbosity","preference_value":"concise","...":"preference_signal payload"}],"detected_signal_count":1,"confirmed_signal_count":1,"last_detected_at":"<ISO-timestamp>|null","last_confirmed_experiment_id":6,"mid_session_preference_signals_path":"[workspace]/preferences.md|null","resolved_preferences_path":"/abs/path/to/preferences.md|null"}
```

- `schema_version`: currently `1`.
- `payload_type`: always `style_preferences`.
- `signals[]`: the full normalized ledger restored from `mid_session_preference_signals`.
- `active_signals[]`: identical to `signals[]` only when `status` is `confirmed` or `applied`; otherwise `[]`.
- `mid_session_preference_signals_path`: the stable human-facing path reference, usually `[workspace]/preferences.md`.
- `resolved_preferences_path`: absolute reopen path for the same ledger when the workspace root is known.
- Keep this payload in the loaded run context as `style_preferences` across eval, mutate, test, and session_close so all mid-loop stages read the same explainable preference envelope.
- Mid-loop refinement must consume `style_preferences.active_signals` directly and must not rescan raw override tasks, raw `mid_session_preference_signals`, or `[workspace]/preferences.md` once the hydrated payload is present.
- Serialized reporting payloads should expose the same root-level `style_preferences` envelope unchanged when it is already present, or synthesize it deterministically from the persisted ledger fields when it is not.
Result retrieval consumers must also preserve the root-level `meta_learning_audit_records[]` ledger unchanged when present. Do not collapse skipped rows away, rebuild applied/skip status heuristically from prose, or strip the evidence/helpfulness fields that explain why a curated rule did or did not steer the run.
Each `meta_learning_audit_records[]` row must follow `Meta-Learning Audit Record Schema` and stay keyed to the original `run_id` plus `meta_learning_id`.
Dashboard and human-readable campaign report renderers should render a dedicated `Curated Meta-Learnings` section from `meta_learning_audit.entries[]`, listing each rule's applied/skip status, evidence metrics, and helpfulness verdict so reviewers can audit transfer decisions without reopening raw markdown or artifacts.
Result retrieval consumers must preserve experiment-level `decision_breakdown` when they serialize or return this payload. Do not strip the stored aggregation breakdown field from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `decision_breakdown` directly from that stored record and return it unchanged. Never recompute `decision_breakdown` on the retrieval path from `eval_results[]` or via the scoring module.
Result retrieval consumers must also preserve experiment-level `final_score` when they serialize or return this payload. Do not strip the published experiment-level score output from the returned payload.
Publish `final_score` only from the adversarial holdout result. If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `final_score` directly from that stored holdout record and return the stored `final_score` field unchanged. When the reporting payload also includes `session_close_holdout.selected_candidate_summary` and it matches the experiment being serialized, use `selected_candidate_summary.holdout_score` as the published `final_score` percentage without reopening scoring internals. For mutation-time-only experiments with no matching holdout result, leave `final_score` null instead of backfilling it from `decision_breakdown.combined_score_pct`, `pass_rate`, or any other non-holdout score field.
Result retrieval consumers must also preserve experiment-level `evaluation_metadata` when they serialize or return this payload. Do not strip the stored dataset/config payload from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `evaluation_metadata` directly from that stored record and return the stored dataset/config payload unchanged. Keep the `adversarial_holdout` split metadata attached to its dataset/config record so load/resume consumers can verify the split boundary without reopening other files.
The `adversarial_holdout` split metadata stays attached to its dataset/config record.
If the stored metadata includes `config.mutation_refinement_split_datasets[]` (`mutation_refinement_split_datasets[]`), retrieval consumers should derive `evaluation_metadata_validation` from that snapshot while keeping the stored `evaluation_metadata` payload unchanged. Flag invalid metadata whenever `adversarial_holdout` shares any `input_id` with a mutation/refinement split or omits one of those split IDs from `split_metadata.separate_from`.
If the stored metadata includes `config.mutation_stage_split_access_policy`, load/resume consumers should hydrate that exact object into the active Phase 7 dataset-read gate instead of rebuilding a looser policy from prose or defaults.
Result retrieval consumers must also preserve experiment-level `eval_results` when they serialize or return this payload. Do not strip `pass_fail`, `evidence`, `supporting_items`, or `multi_judge` from the returned verdicts.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `eval_results` directly from that stored record and return the stored verdict objects unchanged so each `pass_fail` decision stays attached to its own `evidence[]`, `supporting_items[]`, and optional `multi_judge` consensus block for downstream rendering.
Result retrieval consumers must also preserve experiment-level `validation_results` when they serialize or return this payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `validation_results` directly from that stored record and return the stored `validation_results` field unchanged.
Keep fold-level TPR/TNR outputs in `phase6_dev_fold_metrics` instead of flattening them into the aggregate mean/range fields.
At the root of the serialized payload, keep `final_only_evaluation` as the idempotence/ref object only, and expose the dedicated `session_close_holdout` artifact whenever final-only holdout validation resolves, including failed or aborted runs with empty `variant_results[]`. `session_close_holdout.variant_results[]` carries one final-only adversarial holdout evaluation record per completed variant plus the ordered lineage ids and `selected_candidate_summary`. Emit intermediate dev-side tuning numbers in the sibling `session_close_holdout.optimization_metrics` section instead of mixing them into the authoritative final-candidate summary. If an older completion/reporting payload still stores those holdout rows via top-level `evaluated_experiment_ids`, `selected_variant_version`, `selected_experiment_id`, `selected_candidate_summary`, `variant_results`, or a failure-only `final_only_evaluation.reason` field, synthesize the same `session_close_holdout` object on retrieval instead of dropping the per-variant holdout lineage or its failure artifact. Do not mirror that machine-readable holdout detail back into `final_only_evaluation`; keep that object as the ref/idempotence surface only.
Completion and report UIs should render a dedicated `Final Holdout Results` section from `session_close_holdout`, including selected-candidate summary cards plus one visible row/card per `variant_results[]` entry so every completed variant's holdout outcome is inspectable without reopening raw artifacts.
Result retrieval consumers may additionally derive `judge_verdict_report_entries` for dashboards or review UIs, but that field is a report-facing view, not authoritative storage.
Each `judge_verdict_report_entries[]` item must expose the same verdict through reviewer-readable fields: `verdict_label`, `reasoning_trace`, and `evidence_attachments[]` with a stable `reference` plus a human-readable `snippet`.
Each `judge_verdict_report_entries[]` item should also expose an `evidence_block` object so every verdict carries a structured inspection payload. `evidence_block.items[]` must preserve the stable evidence `reference` plus either `inline_content` (for excerpts/metrics rendered directly in the payload) or `artifact_reference` (for direct artifact pointers that let a human inspect the supporting basis at the source).
If a verdict was produced by multiple independent judges, preserve the stored `multi_judge` block on the report entry too. Do not collapse the panel into one opaque verdict string on the retrieval path.
Dashboard and report renderers should render `reasoning_trace` inline in the report body for the same verdict item so reviewers can inspect the rationale without opening raw logs.
Result retrieval consumers may also derive `review_handoff` for downstream review flows. This handoff payload is additive, not authoritative storage.
When `requires_human_spot_check = true`, result retrieval consumers should also derive `pending_human_spot_check_task` on the serialized experiment payload. This is the linked pending calibration task for the flagged experiment and must carry the resolved queue-time `sample_count`.
Result retrieval consumers must also preserve experiment-level `human_review_judgments` when they serialize or return this payload. Do not strip completed human review records from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `human_review_judgments` directly from that stored record and return the stored judgments unchanged. Never recompute `agreement`, `decision_type`, reviewer identity, or review timestamps from session-log fragments on the retrieval path.
`review_handoff` should package the finalized review inputs in one object: `experiment_id`, `final_decision`, the stored `judge_verdict_report_entries[]`, the stored `decision_breakdown`, the stored `decision_explanation`, the stored `completion_cadence`, the stored `requires_human_spot_check`, and a derived `human_spot_check_task` when the cadence gate is active.
Carry `review_handoff.requires_human_spot_check` through from the finalized experiment record unchanged so downstream review flows can detect and enforce the required human spot-check without replaying cadence history.
When `review_handoff.requires_human_spot_check = true`, derive `review_handoff.human_spot_check_task` from the stored `completion_cadence` plus the resolved calibration config. Copy the resolved `sample_count` onto the task payload instead of forcing downstream queues to recompute it from cadence state or config defaults. In other words, `review_handoff.human_spot_check_task.sample_count` is the authoritative queue-time value for `N`.
Carry the same selected samples and eligibility snapshot onto `review_handoff.human_spot_check_task` that you expose on `pending_human_spot_check_task`. In particular, `review_handoff.human_spot_check_task.evaluation_samples` and `review_handoff.human_spot_check_task.evaluation_sample_eligibility` must mirror the experiment-level pending task so reviewer-facing queues can inspect the exact chosen `(eval, fixture)` set without reopening the experiment payload.
Copy the same derived task into `pending_human_spot_check_task` on the serialized experiment payload. `review_handoff.human_spot_check_task` should mirror that linked experiment-level task instead of resolving a second copy with potentially different queue-time metadata.
Result retrieval consumers must also preserve experiment-level `decision_explanation` when they serialize or return this payload. Do not strip the stored explanation field from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `decision_explanation` directly from that stored record and return the stored `decision_explanation` field unchanged. Never recompute `decision_explanation` on the retrieval path from `decision_breakdown`, `eval_results[]`, or via the scoring module.
Result retrieval consumers must also preserve experiment-level `mutation_handoff` when they serialize or return this payload. Do not strip the stored eval-to-mutate handoff block from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `mutation_handoff` directly from that stored record and return the stored `mutation_handoff` field unchanged. Never recompute `mutation_handoff` on the retrieval path from `decision_breakdown`, `decision_explanation`, `eval_results[]`, or mutation-registry helpers.
Result retrieval consumers must also preserve experiment-level `requires_human_spot_check` when they serialize or return this payload. Do not strip the stored trust-checkpoint flag from the returned payload.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `requires_human_spot_check` directly from that stored record and return it unchanged. Never recompute `requires_human_spot_check` on the retrieval path from `completion_cadence` or experiment order.
Result retrieval consumers must also preserve the persisted `completion_cadence` counter at both the root payload and experiment level. Do not rebuild cadence position from array order or recompute it from filtered experiment lists on the retrieval path.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `completion_cadence` directly from that stored record and return it unchanged.
Result retrieval consumers must also preserve experiment-level `baseline_trials` when they serialize or return this payload. Do not collapse the three unchanged-skill baseline executions into one summarized blob on the retrieval path.
Treat `baseline_trials[]` as the baseline phase output collection for Experiment 0. Derived statistics such as mean baseline score, standard deviation, and noise floor are summaries computed from that collection, not replacements for it.
If the retrieval layer reads a nested stored evaluation result (for example iteration `eval_results.json` copied into an experiment payload), lift `baseline_trials` directly from that stored record and return those rows unchanged apart from filling any missing `trial_index` / `trial_id` / `run_index` fallback identifiers.

Each experiment in `experiments[]`:
```json
{"id":N,"input_set_id":"phase4-dev-7f3c91ad","input_set_ref":"input-sets.json#phase4-dev-7f3c91ad","input_ids":["phase4-dev-7f3c91ad-I03","phase4-dev-7f3c91ad-I05","phase4-dev-7f3c91ad-I08"],"score":X,"max_score":Y,"pass_rate":Z,"status":"keep|discard|baseline","final_score":78.7,"description":"...","changes":[{"type":"added|modified|removed","location":"section","snippet":"1-3 lines"}],"baseline_trials":[],"version_artifact":{"version_id":"skill_version__run_2026-04-11T09-00-00__exp_003","artifact_path":"skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/","snapshot_path":"skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/SKILL.md","snapshot_sha256":"sha256:4b2859d8c0f1f1a9...","parent_version_id":"skill_version__run_2026-04-11T09-00-00__exp_002","created_at":"2026-04-11T09:05:00Z"},"evaluation_metadata":{"dataset":{"input_set_id":"phase4-adversarial_holdout-91ab77ce","input_set_ref":"input-sets.json#phase4-adversarial_holdout-91ab77ce","input_ids":["phase4-adversarial_holdout-91ab77ce-I01"],"split_metadata":{"split_id":"adversarial_holdout","display_label":"Adversarial Holdout","evaluation_only":true,"hidden_until":"session_close","used_for":["session_close_holdout_validation"],"blocked_from":["phase5_judge_examples","phase6_judge_refinement","phase7_mutation_scoring","phase7_mutation_analysis"],"separate_from":["train","dev","test"]}},"config":{"scoring_scope":"session_close_holdout_validation","freeze_split_boundaries":true,"require_same_split_metadata_on_resume":true,"human_spot_check_calibration":{"sample_count":2},"mutation_refinement_split_datasets":[{"split_id":"train","input_set_id":"phase4-train-42be3101","input_ids":["phase4-train-42be3101-I01"]},{"split_id":"dev","input_set_id":"phase4-dev-7f3c91ad","input_ids":["phase4-dev-7f3c91ad-I03","phase4-dev-7f3c91ad-I05"]},{"split_id":"test","input_set_id":"phase4-test-6ca1b7d2","input_ids":["phase4-test-6ca1b7d2-I02"]}]}},"evaluation_metadata_validation":{"status":"valid","checked_split_ids":["train","dev","test"],"overlap_count":0,"issues":[]},"eval_results":[{"eval":"E1","pass_fail":"pass","reasoning_trace":"1. Criterion check: the required gotchas section is present. 2. Evidence: the output contains a gotchas heading and 3 specific warnings. 3. Verdict link: because the rubric requires a gotchas section with concrete warnings, this passes.","evidence":[{"kind":"output_excerpt","source":"skill_output","locator":"input_id:phase4-dev-7f3c91ad-I03 output lines 12-18","excerpt":"## Gotchas\\n- Never run rm -rf without checking the target path.","metric":null,"artifact_ref":null},{"kind":"metric","source":"scoring_metric","locator":"warnings_found","excerpt":"3 concrete warnings found in the gotchas section.","metric":{"name":"warnings_found","value":3,"unit":"count"},"artifact_ref":null}],"supporting_items":[{"stage":"criterion_check","decision":"required gotchas section is present","outcome":"met","evidence_refs":[0]},{"stage":"evidence_check","decision":"gotchas section includes 3 concrete warnings","outcome":"met","evidence_refs":[1]},{"stage":"verdict_link","decision":"the rubric passes when the gotchas section and concrete warnings are both present","outcome":"supports_pass","evidence_refs":[0,1]}],"weight":1.0,"weight_source":"code_eval_fixed","weighted_points":1.0,"normalized_contribution":0.25},{"eval":"E2","pass_fail":"fail","reasoning_trace":"1. Criterion check: the disclosure instruction is missing. 2. Evidence: no 'Read when:' pointer appears and the disclosure section is absent. 3. Verdict link: because the rubric requires explicit disclosure guidance, this fails.","evidence":[{"kind":"output_excerpt","source":"skill_output","locator":"input_id:phase4-dev-7f3c91ad-I03 output lines 1-9","excerpt":"No 'Read when:' pointer or disclosure section appears in the output.","metric":null,"artifact_ref":null},{"kind":"artifact_ref","source":"workspace_artifact","locator":"runs/run_2026-04-10T10-00-00/iteration_000/eval_results.json","excerpt":"Stored verdict artifact for replay and dashboard inspection.","metric":null,"artifact_ref":{"path":"runs/run_2026-04-10T10-00-00/iteration_000/eval_results.json","label":"baseline eval results"}}],"supporting_items":[{"stage":"criterion_check","decision":"disclosure guidance is missing","outcome":"not_met","evidence_refs":[0]},{"stage":"verdict_link","decision":"the rubric fails when disclosure guidance is absent","outcome":"supports_fail","evidence_refs":[0,1]}],"weight":0.9,"weight_source":"phase_6_validation_average","weighted_points":0.0,"normalized_contribution":0.0}],"decision_breakdown":{"components":[{"eval":"E1","pass_fail":"pass","weight":1.0,"weight_source":"code_eval_fixed","weighted_points":1.0,"normalized_contribution":0.213},{"eval":"E2","pass_fail":"fail","weight":0.9,"weight_source":"phase_6_validation_average","weighted_points":0.0,"normalized_contribution":0.0}],"formula":"combined_score = weighted_points / total_weight","weighted_points":3.7,"total_weight":4.7,"combined_score":0.787,"combined_score_pct":78.7,"threshold":0.8,"proposed_decision":"discard"},"decision_explanation":{"final_decision":"discard","summary":"E2 withheld 19.1% of the available score, while E1 added 21.3%; the mutation still finished below threshold.","strongest_outcomes":[{"eval":"E2","pass_fail":"fail","impact":"supports_discard","impact_magnitude":0.191,"impact_basis":"missed_weight_share","summary":"The failed high-weight eval withheld 19.1% of the available score."},{"eval":"E1","pass_fail":"pass","impact":"supports_keep","impact_magnitude":0.213,"impact_basis":"normalized_contribution","summary":"The strongest pass added 21.3% toward keep, but the experiment still missed threshold."}]},"regression_check":null,"discard_autopsy":null,"requires_human_spot_check":false,"pending_human_spot_check_task":null}
```
- For baseline noise measurement, persist the three unchanged-skill executions inside `baseline_trials[]` on Experiment 0 instead of overwriting one shared baseline slot.
- Baseline trial row example: `{"trial_index":1,"trial_id":"baseline-trial-001","run_index":1,"score":72.3,"pass_rate":72.3,"timestamps":{"started_at":"2026-04-11T09:00:00Z","completed_at":"2026-04-11T09:00:08Z"},"raw_outputs":[{"input_id":"phase4-dev-7f3c91ad-I03","output_text":"Trial 1 output for fixture I03"}],"trial_metadata":{"requested_operation":"baseline_scoring","requested_split_id":"dev","input_set_id":"phase4-dev-7f3c91ad","input_set_ref":"input-sets.json#phase4-dev-7f3c91ad","input_ids":["phase4-dev-7f3c91ad-I03"]}}`.
- When Phase 7 output is surfaced to a human or downstream consumer, expose `baseline_trials[]` as the primary baseline artifact and compute mean/noise-floor summaries from those rows instead of replacing them with one aggregated baseline record.
- Session Close holdout outputs do not belong in `results.json.experiments[]` or duplicated top-level state score fields. That array stays mutation-time only (`baseline`, `keep`, `discard` on the dev-scored run corpus). Persist final holdout outputs separately in `session_close_holdout/variant_results.json` and reopen them through `state.json.final_only_evaluation.variant_results_ref`.
- Serialized reporting payloads should expose those per-variant holdout results through root-level `session_close_holdout.variant_results[]`, not by copying them into `experiments[]` or re-expanding `final_only_evaluation`.
- Mutation-time score cards, running-best selection, and same-run version comparisons must derive from the mutation-time `results.json.experiments[]` corpus only. Never compute those mutation-time summaries by reopening `session_close_holdout/variant_results.json`, `selected_candidate_summary`, or any other holdout-only result structure.
- `evaluation_metadata`: stored dataset/config payload for this experiment's evaluation run. Preserve it unchanged on write and retrieval so split-aware consumers can inspect the scoring corpus and any split-boundary rules without reopening workspace files. When this payload records `adversarial_holdout`, keep the split metadata attached to the same record.
- `human_spot_check_calibration.sample_count`: configurable calibration sample-count setting `N` stored inside `evaluation_metadata.config.human_spot_check_calibration.sample_count`. Default to `2` when the config is missing. Validation: `sample_count` must be a positive integer (`>= 1`). Every 3rd experiment surfaces up to `sample_count` reviewable `(eval, fixture)` pairs from the most recent finalized experiment. When the eligible pool is larger than `sample_count`, select deterministically by stable sample identity unless `evaluation_metadata.config.human_spot_check_calibration.selection_mode = randomized` explicitly opts into backend randomization without replacement. Session Close uses `max(sample_count, 5)` so the independent closeout calibration never drops below the 5-sample minimum.
- `evaluation_metadata_validation`: derived retrieval-time validation summary for `adversarial_holdout` metadata. Surface `status`, `checked_split_ids`, `overlap_count`, and `issues[]` without mutating the stored `evaluation_metadata`. Any shared `input_id` between holdout and `config.mutation_refinement_split_datasets[]` is invalid metadata and must be flagged here.
- `eval_results`: per-eval verdicts for this experiment. Each decision must include `eval`, `pass_fail`, `category` (from eval-suite.md: `structural`, `task-completion`, or `quality`), `reasoning_trace`, `evidence`, `supporting_items`, `weight`, `weight_source`, `weighted_points`, and `normalized_contribution`. `reasoning_trace` is always a concise ordered explanation: criterion check, evidence, then verdict link. `evidence` is an array of structured evidence objects, not free-form strings; use it to preserve cited inputs, output excerpts, metrics, and artifact references in a replayable form. `supporting_items` captures the concrete intermediate judgment calls and maps each one back to the exact `evidence[]` entries it used. Used by regression checks to compare across experiments.
- `judge_verdict_report_entries`: derived report-facing view of `eval_results`. Each entry repeats the stored verdict data and adds `verdict_label`, an `evidence_block`, and `evidence_attachments[]`. `evidence_block.items[]` is the structured inspection surface for that verdict: every item keeps a stable evidence `reference` plus either `inline_content` or an `artifact_reference` that points directly to the supporting artifact. `evidence_attachments[]` remains the reviewer-friendly attachment list with stable `reference` plus readable `snippet`. Render the same entry's `reasoning_trace` inline in the report body so the verdict rationale stays inspectable without opening raw logs. Use this for dashboard cards, external reports, or production review surfaces; do not write it back as the source of truth.
- `pending_human_spot_check_task`: derived experiment-level pending calibration task. Populate it when `requires_human_spot_check = true` using the Human Spot-Check Task Schema and the resolved queue-time `sample_count`; otherwise return `null`. This is the linked task object that downstream queueing or audit consumers can inspect without opening `review_handoff`.
- `pending_human_spot_check_task.evaluation_samples`: selected pending calibration samples. Start from the filtered reviewable pool, then choose up to `sample_count` backend-selected samples for the queued task. By default the backend selection is deterministic over stable sample identity; when `evaluation_metadata.config.human_spot_check_calibration.selection_mode = randomized`, select without replacement from the eligible pool instead. Exclude verdicts that fail the reviewability checks instead of surfacing them for calibration.
- `pending_human_spot_check_task.evaluation_sample_eligibility`: backend eligibility snapshot for the pending calibration pool. Record `status` (`ready`, `underfilled`, or `empty`), the requested vs eligible sample counts, and `excluded_samples[]` with reason codes so downstream review flows can explain why a queue is short or empty without re-running eligibility logic.
- `human_review_judgments`: completed human reviews for surfaced calibration samples tied to this experiment. Each item uses `Human Review Judgment Schema`. Preserve the stored decision, reviewer identity, timestamps, and audit metadata unchanged on retrieval.
- `human_judgment_comparison_dataset`: aligned system-vs-human judgment dataset keyed by stable judgment target. Preserve the matched `system_judgment`, `human_judgment`, and `comparison` summary per target so downstream trust consumers do not re-match review rows from scratch.
- `human_judgment_calibration_result`: derived calibration summary for the aligned review set. Compute `human_judgment_calibration_result` from `human_judgment_comparison_dataset`.
- `counted_reviews`: calibration denominator inside `human_judgment_calibration_result`. Count only paired targets whose `human_judgment.decision_type` is `confirm` or `override`.
- `excluded_from_agreement_rate[]`: audit trail inside `human_judgment_calibration_result` for aligned targets that stayed out of the denominator. Preserve the target descriptor plus the exclusion reason instead of silently dropping `skip`, `not_reviewable`, or missing-system rows.
- `review_handoff`: derived downstream-review payload. Package `experiment_id`, `final_decision`, `judge_verdict_report_entries`, `decision_breakdown`, `decision_explanation`, `completion_cadence`, the stored trust gate in `review_handoff.requires_human_spot_check`, and `review_handoff.human_spot_check_task` when a cadence-triggered calibration pause is pending. Use the task payload to queue the human spot-check without recomputing `sample_count` from config.
- `review_handoff.human_spot_check_task.evaluation_samples`: selected pending calibration samples mirrored from `pending_human_spot_check_task`. Reviewer-facing queues should read this exact backend-selected list instead of deriving a second sample set.
- `review_handoff.human_spot_check_task.evaluation_sample_eligibility`: mirrored eligibility snapshot for the reviewer-facing task payload. Preserve `status`, requested vs eligible sample counts, and `excluded_samples[]` unchanged so review consumers can explain underfilled or empty queues without replaying selection.
- `final_score`: published experiment-level score output sourced only from the adversarial holdout result. Preserve the stored holdout `final_score` when present. If the selected candidate summary in `session_close_holdout` matches this experiment, publish `selected_candidate_summary.holdout_score` as a percentage. For mutation-time-only rows with no holdout match, leave `final_score` null instead of backfilling it from `decision_breakdown.combined_score_pct`, `pass_rate`, or any other non-holdout score.
- `weight_source`: where the eval's weight came from. Use `code_eval_fixed`, `phase_6_validation_average`, `mini_mode_code_default`, or `mini_mode_agent_discount`.
- `decision_breakdown`: aggregate scoring record used for keep/discard. `components[]` is the structured aggregation breakdown field: an ordered, self-contained copy of the exact eval inputs that rolled into the keep/discard math. `score` mirrors `weighted_points` and `max_score` mirrors `total_weight` for dashboard compatibility.
- `decision_explanation`: structured explanation mapping derived from `decision_breakdown` plus the final keep/discard. Store `final_decision`, a short `summary`, and ordered `strongest_outcomes[]` entries that identify the strongest contributing eval outcomes and their impact on the final keep/discard.
- `mutation_handoff`: canonical eval-to-mutate handoff block. Store `normalized_evaluation_scores`, `failure_reasons[]`, and ordered `mutation_targets[]` in the exact structure Phase 7 step 2a reads, so the mutate phase does not have to reverse-engineer target priorities from prose.
- `requires_human_spot_check`: boolean finalized-only trust checkpoint flag. Set to `true` when the post-increment `completion_cadence.completed_experiments` value for this finalized experiment is divisible by 3 (3, 6, 9, ...); otherwise `false`.
- `regression_check`: null (no check run), or `{"passed":true,"details":"..."}`, or `{"passed":false,"regressions":[{"experiment":1,"eval":"E2","was":"pass","now":"fail","detail":"..."}]}`
- `discard_autopsy`: null (experiment kept or baseline), or `{"classification":"wrong_target|wrong_params|wrong_type","reasoning":"1-sentence explanation"}`. Set after discard in Phase 7 step 2f. See `Discard Autopsy Heuristics` section.
- `input_set_id`: stable scoring set ID for this experiment.
- `input_set_ref`: exact registry pointer for the scoring set. Format: `input-sets.json#<set_id>`.
- `input_ids`: stable input IDs actually scored for this experiment, stored in finalized set order. Version comparisons are only valid when both `input_set_id` and the full `input_ids` list match across experiments.
- `completion_cadence`: finalized snapshot of the cadence counter for this experiment. Copy the active root counter into the experiment record only after the experiment reaches its final state so production systems can tell which completed-experiment slot this version occupied without replaying the run.
- `baseline_trials`: baseline-only array of unchanged-skill execution records. Preserve one row per baseline invocation with stable `trial_index` / `trial_id` / `run_index` identifiers so repeated baseline evaluations do not overwrite each other. Each row should also preserve `timestamps`, `raw_outputs[]`, and `trial_metadata` so later comparisons can inspect what the unchanged skill produced, when it ran, and which dev input set backed the sample.
- `version_artifact`: immutable version snapshot metadata for this experiment. Use `Skill Version Artifact Schema`. Preserve `version_id`, `artifact_path`, `snapshot_path`, `snapshot_sha256`, `parent_version_id`, and `created_at` unchanged on retrieval. Do not rebuild this object from `iteration_path`, `skill_after.md`, or derived version labels when the stored artifact is already present.
- `test_launch_payload`: mutate-to-test handoff payload emitted from the finalized mutation output. Use `Mutation Test Launch Payload`. Preserve `candidate_version`, `source_artifact_refs`, `eval_artifact_refs`, and `test_bootstrap_metadata` unchanged whenever the mutation artifact already stored them.

### Meta-Learning Outcome Record Schema

Persist run-level meta-learning effectiveness rows in `results.json.meta_learning_outcomes[]` for same-skill version comparisons. This ledger is append-only per evaluated meta-learning event and is designed for both individual replay and production aggregation.

```json
{"schema_version":1,"outcome_id":"mlo-run_2026-04-11T09-00-00-ML-2026-04-11-001","run_id":"run_2026-04-11T09-00-00","meta_learning_id":"ML-2026-04-11-001","quality_signals":{"before":{"version_label":"v2","experiment_id":2,"signal_score":78.2,"signal_label":"directional_improvement"},"after":{"version_label":"v3","experiment_id":3,"signal_score":84.9,"signal_label":"validated_improvement"},"delta":6.7},"helpful":{"score":0.82,"label":"helpful"},"evaluation_criteria_snapshot":{"schema_version":1,"criteria_id":"meta_learning_effectiveness_v1","criteria_labels":["task_completion","quality","regression_safety"],"aggregation_formula":"weighted_delta_plus_regression_guard","weights":{"task_completion":0.4,"quality":0.4,"regression_safety":0.2}},"timestamps":{"evaluated_at":"2026-04-11T19:22:03Z","recorded_at":"2026-04-11T19:22:04Z"}}
```

- `schema_version`: starts at `1` for the canonical persisted outcome row contract. Future changes must be additive or version-bumped.
- `outcome_id`: stable unique row ID. Recommended format: `mlo-<run_id>-<meta_learning_id>`.
- `run_id`: Phase 7 iteration-run identifier that produced this outcome.
- `meta_learning_id`: canonical curated rule ID from `meta-learnings.md` (`ML-YYYY-MM-DD-NNN`).
- `quality_signals.before` and `quality_signals.after`: same-skill version quality snapshots used for this outcome judgment.
- `quality_signals.delta`: scalar `after.signal_score - before.signal_score` in the same units as `signal_score`.
- `quality_signals.*.version_label`: human-facing version tag (`v0`, `v1`, ... ) from the same lineage.
- `quality_signals.*.experiment_id`: numeric experiment ID backing the version snapshot in this run.
- `quality_signals.*.signal_score`: normalized quality signal used by this outcome evaluation (for example holdout final score or selected canonical quality metric).
- `quality_signals.*.signal_label`: one of `validated_improvement`, `directional_improvement`, `flat`, `directional_regression`, or `validated_regression`.
- `helpful.score`: normalized helpfulness score in `[0, 1]`.
- `helpful.label`: one of `helpful`, `neutral`, or `not_helpful`.
- `evaluation_criteria_snapshot`: frozen scoring criteria payload used to produce this row so historical rows remain replayable after later criteria changes.
- `evaluation_criteria_snapshot.schema_version`: criteria snapshot contract version (starts at `1`).
- `evaluation_criteria_snapshot.criteria_id`: stable criteria bundle identifier (for example `meta_learning_effectiveness_v1`).
- `evaluation_criteria_snapshot.criteria_labels[]`: ordered criterion labels evaluated for this row.
- `evaluation_criteria_snapshot.aggregation_formula`: deterministic aggregation formula identifier or expression.
- `evaluation_criteria_snapshot.weights`: optional criterion weights keyed by `criteria_labels[]`.
- `evaluation_criteria_snapshot.helpfulness_mode`: `binary` or `graded`; controls how captured signal deltas map onto helpfulness.
- `evaluation_criteria_snapshot.helpfulness_thresholds`: delta thresholds (`helpful_min_delta`, `not_helpful_max_delta`, optional `noise_floor_threshold`) used by the helpfulness evaluator.
- `evaluation_criteria_snapshot.label_score_bands`: score cutoffs (`helpful_min_score`, `not_helpful_max_score`) used to map graded scores to helpfulness labels.
- `timestamps.evaluated_at`: when before/after comparison and helpfulness were computed.
- `timestamps.recorded_at`: when this row was persisted to `results.json.meta_learning_outcomes[]`.
- Capture timing: after an experiment is scored, if that experiment applied one or more actionable meta-learning IDs, append one row per applied ID for the active `run_id`.
- Before/after attachment rule: for each appended row, set `quality_signals.before` from the previous experiment snapshot in the same run and `quality_signals.after` from the current experiment snapshot so every applied meta-learning carries an explicit within-run before/after trace.
- Configured-criteria evaluator: convert `quality_signals.delta` into `helpful.score` + `helpful.label` using the frozen `evaluation_criteria_snapshot` so each meta-learning application is replayable under the exact binary/graded thresholds used at write time.

### Meta-Learning Audit Record Schema

Persist run-level curation audit rows in `results.json.meta_learning_audit_records[]` so dashboards, humans, and production systems can inspect every curated meta-learning considered in the current run, including rules that were skipped instead of applied. This ledger is one row per `(run_id, meta_learning_id)` and complements the per-application `meta_learning_outcomes[]` ledger instead of replacing it.

```json
{"schema_version":1,"audit_record_id":"mla-run_2026-04-11T09-00-00-ML-2026-04-11-001","run_id":"run_2026-04-11T09-00-00","meta_learning_id":"ML-2026-04-11-001","title":"Subtractive cleanup after additive streaks","consideration_status":"applied","consideration_bucket":"actionable","skip_reason":null,"evidence_metrics":{"supporting_evidence_count":2,"supporting_case_count":1,"source_kinds":["prior_campaign","reference_skill"],"confidence":"medium","precedence":"high"},"application_summary":{"application_count":2,"applied_experiment_ids":[2,3],"latest_outcome_id":"mlo-run_2026-04-11T09-00-00-ML-2026-04-11-001-exp3"},"helpfulness_verdict":{"status":"evaluated","score":0.82,"label":"helpful"}}
```

- `schema_version`: starts at `1` for the canonical persisted audit-row contract.
- `audit_record_id`: stable unique row ID. Recommended format: `mla-<run_id>-<meta_learning_id>`.
- `run_id`: Phase 7 iteration-run identifier whose curation pass considered this meta-learning.
- `meta_learning_id`: canonical curated rule ID from `meta-learnings.md` (`ML-YYYY-MM-DD-NNN`).
- `title`: human-facing rule title copied from the parsed curated entry when available.
- `consideration_status`: `applied` when the run emitted one or more `meta_learning_outcomes[]` rows for this rule, otherwise `skipped`.
- `consideration_bucket`: the parsed-bundle partition that exposed this rule to the run. Use `actionable`, `historical`, or `blocked`.
- `skip_reason`: null when `consideration_status = applied`. Otherwise copy the parsed entry's `block_reason` when present, or use `not_selected_for_mutation` when an actionable rule stayed available but the run never applied it.
- `evidence_metrics`: compact audit summary of the curated rule's evidence strength.
- `evidence_metrics.supporting_evidence_count`: count of `supporting_evidence[]` rows on the parsed entry.
- `evidence_metrics.supporting_case_count`: count of `supporting_case_ids[]` on the parsed entry.
- `evidence_metrics.source_kinds[]`: unique sorted `supporting_evidence[].source_kind` values so humans can see whether the rule rests on prior campaigns, reference skills, or other sources.
- `evidence_metrics.confidence`: curated confidence label copied from the parsed entry.
- `evidence_metrics.precedence`: curated precedence label copied from the parsed entry.
- `application_summary.application_count`: number of applied outcome rows for this `(run_id, meta_learning_id)` pair.
- `application_summary.applied_experiment_ids[]`: unique sorted experiment IDs whose scored mutation applied this rule in the current run.
- `application_summary.latest_outcome_id`: outcome row ID for the latest applied event in the current run, or null when skipped.
- `helpfulness_verdict`: run-level helpfulness readout for this rule.
- `helpfulness_verdict.status`: `evaluated` when at least one applied outcome row exists for this run/rule pair, otherwise `not_evaluated`.
- `helpfulness_verdict.score`: latest applied outcome `helpful.score` when evaluated, otherwise null.
- `helpfulness_verdict.label`: latest applied outcome `helpful.label` when evaluated, otherwise null.
- Capture timing: after serializing `meta_learning_bootstrap_context` and `meta_learning_outcomes[]`, emit one audit row for every curated entry in the bootstrapped `parsed_meta_learnings.entries[]` list. Use the parsed bundle partition lists to determine `consideration_bucket`, then join against same-run `meta_learning_outcomes[]` rows to determine applied-vs-skipped status and helpfulness.
- Brownfield fallback: if a stored run output preserves `meta_learning_outcomes[]` but not the parsed entry bundle, retrieval may emit minimal audit rows keyed from those stored outcomes so applied rules remain visible. When the parsed bundle is available, prefer it as the authoritative source for title, evidence metrics, and skip reasoning.

### Human Spot-Check Calibration Config Schema

Persist this config in `evaluation_metadata.config.human_spot_check_calibration` whenever Phase 7 or Session Close queues human spot-check calibration.

```json
{"sample_count":2}
```

- `sample_count`: configurable calibration sample-count setting `N`.
- Default to `2` when the config is missing.
- Validation: `sample_count` must be a positive integer (`>= 1`).
- Every 3rd completed experiment surfaces up to `sample_count` reviewable `(eval, fixture)` pairs from the most recent finalized experiment.
- Session Close uses `max(sample_count, 5)` so the independent closeout calibration never drops below the 5-sample minimum.
- When a cadence-triggered or Session Close calibration task is constructed, copy the resolved `sample_count` into that task payload immediately. Do not require downstream queues to recompute `N` from the config later.

### Human Spot-Check Task Schema

Construct this payload whenever completion cadence or Session Close queues human spot-check calibration.

```json
{"task_type":"human_spot_check_calibration","trigger":"completion_cadence","status":"pending","experiment_id":3,"completed_experiment_slot":3,"sample_count":2,"sample_count_source":"evaluation_metadata.config.human_spot_check_calibration.sample_count","minimum_sample_floor":null,"selection_strategy":"priority_order","selection_priority":["multi_judge_disagreement","quality_eval","near_threshold","deterministic_fallback"],"evaluation_sample_eligibility":{"status":"ready","requested_sample_count":2,"eligible_sample_count":2,"excluded_samples":[{"eval":"E3","reason_codes":["missing_reasoning_trace"]}]},"evaluation_samples":[{"eval":"E1","pass_fail":"pass","verdict_label":"PASS","reasoning_trace":"1. Criterion check: the output includes the required gotchas section. 2. Evidence: the output has a gotchas heading and 3 concrete warnings. 3. Verdict link: because the rubric requires that section and those warnings, this passes.","fixture_reference":"phase4-dev-7f3c91ad-I03","selection_reason":"multi_judge_disagreement","selection_rank":1,"evidence_reference":"input_id:phase4-dev-7f3c91ad-I03 output lines 12-18","evidence_preview":"## Gotchas\n- Never run rm -rf without checking the target path.","artifact_reference":null}]}
```

- `task_type`: stable queue identifier. Use `human_spot_check_calibration`.
- `trigger`: `completion_cadence` for every-3rd-experiment pauses, `session_close` for the mandatory closeout review.
- `status`: initialize as `pending` when the task is queued.
- `experiment_id`: finalized experiment that triggered the calibration pause. Null only for Session Close tasks that are not tied to a single mutation.
- `completed_experiment_slot`: copy from `completion_cadence.completed_experiments` when cadence triggered the task. This lets downstream systems know which finalized slot caused the queue event.
- `sample_count`: resolved calibration sample-count used for the task. For cadence-triggered tasks, use the validated config value or the default `2`. For Session Close, use `max(sample_count, 5)`.
- `sample_count_source`: `evaluation_metadata.config.human_spot_check_calibration.sample_count` when the config supplied `N`, otherwise `default_human_spot_check_calibration.sample_count`.
- `minimum_sample_floor`: null for cadence-triggered tasks. Set to `5` for Session Close tasks so the queue records the mandatory closeout floor explicitly.
- `selection_strategy`: deterministic review-sample routing policy for the queued task. Use `priority_order` for the v4.1 trust contract.
- `selection_priority[]`: ordered sampling reasons applied under `selection_strategy = priority_order`. Keep this order: `multi_judge_disagreement`, `quality_eval`, `near_threshold`, `deterministic_fallback`.
- `evaluation_sample_eligibility`: backend eligibility snapshot for the pending calibration pool. `status = ready` when eligible samples meet or exceed `sample_count`, `underfilled` when at least one reviewable sample exists but the pool is smaller than `sample_count`, and `empty` when no reviewable samples survived filtering.
- `evaluation_sample_eligibility.excluded_samples[]`: verdicts that were excluded from the pending calibration pool. Use `reason_codes` from this set: `missing_eval`, `missing_pass_fail`, `missing_reasoning_trace`, `missing_reviewable_evidence`.
- `evaluation_samples[]`: backend-selected reviewable `(eval, fixture)` samples for human calibration. Choose up to `sample_count` from the eligible pool. When `selection_strategy = priority_order`, select from the eligible pool in this order: unresolved `multi_judge_disagreement`, then `quality_eval`, then `near_threshold`, then a deterministic fallback over the remaining reviewable pool. Default fallback ordering stays deterministic over stable sample identity (`fixture_reference`, then `eval`, then evidence locator); when `evaluation_metadata.config.human_spot_check_calibration.selection_mode = randomized`, randomize only inside the final eligible bucket and still sample without replacement.
- `evaluation_samples[].fixture_reference`: fixture identifier for sampling and audit views. Derive it from the `input_id:` embedded in `evidence_reference` when present; otherwise fall back to the artifact path used for review.
- `evaluation_samples[].selection_reason`: the specific priority bucket that caused this sample to be surfaced. Use one of `multi_judge_disagreement`, `quality_eval`, `near_threshold`, or `deterministic_fallback`.
- `evaluation_samples[].selection_rank`: 1-based order position after the task-level selection strategy is applied.
- `evaluation_samples[].evidence_reference`: stable reviewer-facing reference to the cited evidence. This must survive serialization unchanged.
- `evaluation_samples[].evidence_preview`: inline preview snippet for the cited evidence when one exists. Leave null only when the human reviewer should inspect `artifact_reference` instead.
- `evaluation_samples[].artifact_reference`: optional artifact pointer copied from the verdict evidence when the reviewable sample is backed by a stored artifact rather than inline content.
- `evaluation_samples[].sample_identity`: stable join key for the surfaced sample. Use `exp<id>:<eval>:<fixture_reference>` when the sample is tied to one experiment; otherwise use the task-scoped equivalent.
- `evaluation_samples[].source_results_ref`: authoritative pointer back to the stored machine verdict the human is reviewing. Preserve the stored reference unchanged instead of regenerating it from session logs.
- `evaluation_samples[].source_task_sample_index`: zero-based position of this sample inside the queued calibration task artifact. Preserve it so replay tooling can reconstruct the exact reviewed row.
- `evaluation_samples[].sample_payload_hash`: hash of the exact surfaced sample payload. If the payload changes, write a new human-review judgment instead of mutating the existing review record.
- `evaluation_samples[].sample_surfaced_at`: when this sample entered the human-review queue. Preserve the stored timestamp unchanged on retrieval.
- `evaluation_samples[].human_review_judgment`: optional linked completed review payload for this sample. When a matching entry exists in `human_review_judgments[]`, attach the exact stored `Human Review Judgment Schema` object here for reviewer-facing surfaces instead of rebuilding a second shape. Once this linked object is present, downstream sample renderers and submission/update consumers should read it directly instead of re-matching against `human_review_judgments[]`; otherwise stale experiment-level copies can overwrite the surfaced reviewer judgment.

### Human Review Judgment Schema

Use this schema once a surfaced calibration sample is actually reviewed by a human. Write one object per reviewed sample. If the review is tied to a specific experiment, append it to that experiment's `human_review_judgments[]` array. If the completed review is also stored in a task artifact, mirror the exact same object there instead of inventing a second review shape.

```json
{"judgment_id":"human-review-exp3-E1-phase4-dev-7f3c91ad-I03-2026-04-11T18:22:03Z","schema_version":1,"task_context":{"task_type":"human_spot_check_calibration","task_trigger":"completion_cadence","task_ref":"checkpoint-tasks/exp3-human-spot-check.json","task_status_before_review":"pending","task_status_after_review":"completed"},"sample_reference":{"experiment_id":3,"completed_experiment_slot":3,"eval":"E1","fixture_reference":"phase4-dev-7f3c91ad-I03","evidence_reference":"input_id:phase4-dev-7f3c91ad-I03 output lines 12-18","sample_identity":"exp3:E1:phase4-dev-7f3c91ad-I03"},"judge_decision":{"pass_fail":"pass","verdict_label":"PASS","reasoning_trace":"1. Criterion check: the output includes the required gotchas section. 2. Evidence: the output has a gotchas heading and 3 concrete warnings. 3. Verdict link: because the rubric requires that section and those warnings, this passes."},"human_decision":{"pass_fail":"fail","decision_type":"override","agreement":false,"rationale":"The section exists, but the rubric requires three concrete warnings and only one is present.","reviewer_notes":"Judge over-weighted section presence over rubric completeness."},"reviewer_identity":{"reviewer_id":"human:sarahli","display_name":"Sarah Li","reviewer_role":"skill_author"},"timestamps":{"sample_surfaced_at":"2026-04-11T18:20:00Z","review_started_at":"2026-04-11T18:21:10Z","review_completed_at":"2026-04-11T18:22:03Z"},"audit_metadata":{"source_results_ref":"results.json#experiments[3].eval_results[E1]","source_task_sample_index":0,"sample_payload_hash":"sha256:2d57d74eb7f1...","artifact_reference":null,"session_log_ref":"session-log-2026-04-11T18-20-00.json#spot_check-exp3-E1","supersedes_judgment_id":null}}
```

- `judgment_id`: stable unique ID for this completed human review. If the same sample is reviewed again, write a new judgment object and link the older one through `audit_metadata.supersedes_judgment_id`.
- `schema_version`: starts at `1` for the canonical human-review storage contract.
- `task_context.task_type`: use `human_spot_check_calibration`.
- `task_context.task_trigger`: `completion_cadence` or `session_close`.
- `task_context.task_ref`: exact task artifact or queue record that surfaced the sample.
- `task_context.task_status_before_review` / `task_context.task_status_after_review`: preserve the queue state transition around the review so audit tooling can prove the human action closed a pending task.
- `sample_reference.experiment_id`: triggering experiment ID when the review is tied to one experiment. Null only for Session Close reviews that intentionally span multiple experiment sources.
- `sample_reference.completed_experiment_slot`: copy the finalized cadence slot when the source task came from completion cadence. Null is allowed for Session Close bundles without one slot anchor.
- `sample_reference.eval`: eval ID for the surfaced verdict (`E1`, `E2`, ...).
- `sample_reference.fixture_reference`: stable fixture or input ID surfaced for review.
- `sample_reference.evidence_reference`: stable pointer to the exact cited evidence shown to the human reviewer.
- `sample_reference.sample_identity`: stable join key for this surfaced sample. Format: `exp<id>:<eval>:<fixture_reference>` when `experiment_id` exists; otherwise use the task-scoped equivalent.
- `judge_decision`: immutable snapshot of the machine verdict as surfaced to the human reviewer. Preserve the original `pass_fail`, `verdict_label`, and `reasoning_trace` exactly as presented.
- `human_decision.pass_fail`: required when `decision_type` is `confirm` or `override`; null only when the human marked the sample `skip` or `not_reviewable`.
- `human_decision.decision_type`: one of `confirm`, `override`, `skip`, or `not_reviewable`.
- `human_decision.agreement`: required boolean when `decision_type` is `confirm` or `override`; null for `skip` and `not_reviewable`.
- `human_decision.rationale`: required when `decision_type` is `override`, `skip`, or `not_reviewable`; recommended for `confirm`.
- `human_decision.reviewer_notes`: optional free-form notes that add context without replacing the canonical rationale field.
- `reviewer_identity.reviewer_id`: stable reviewer identifier (`human:<handle>` or another locally meaningful principal ID).
- `reviewer_identity.display_name`: human-readable reviewer label shown in audit views.
- `reviewer_identity.reviewer_role`: reviewer context such as `skill_author`, `operator`, or `qa_reviewer`.
- `timestamps.sample_surfaced_at`: when the sample entered the human-review queue.
- `timestamps.review_started_at`: when the human began evaluating the surfaced sample.
- `timestamps.review_completed_at`: when the human finalized the review. Required for any stored completed judgment.
- `audit_metadata.source_results_ref`: authoritative pointer back to the stored machine verdict being reviewed.
- `audit_metadata.source_task_sample_index`: zero-based sample index inside the queued task artifact so replay tooling can reconstruct which surfaced row was reviewed.
- `audit_metadata.sample_payload_hash`: hash of the exact surfaced sample payload. If the payload changes, write a new judgment instead of mutating the old one.
- `audit_metadata.artifact_reference`: optional artifact pointer when the human review depended on a stored artifact rather than inline evidence alone.
- `audit_metadata.session_log_ref`: optional pointer to the additive session-log event written for this review.
- `audit_metadata.supersedes_judgment_id`: link to the prior judgment when a rereview replaces it; otherwise null.

Usage rules:
- `human_review_judgments[]` is the authoritative completed-review record. Session-log `spot_check` events are additive, not authoritative.
- Compute calibration agreement rates from stored judgments where `human_decision.decision_type` is `confirm` or `override`. Exclude `skip` and `not_reviewable` from the denominator, but keep them in the audit trail.
- Derive `human_judgment_calibration_result` from the aligned `human_judgment_comparison_dataset` so the agreement math reuses the same stable judgment-target matching as reviewer-facing payloads.
- Do not rewrite `judge_decision` after the fact. It is the frozen snapshot of what the human reviewer actually saw.
- Preserve `human_review_judgments[]` unchanged on retrieval. Do not backfill or infer missing rationale, agreement, reviewer identity, or timestamps from other files.

### User Override Scan Task Schema

Use this schema for the session-level cadence hook that batches the last 3 finalized experiments into a mid-loop user-override scan. Queue or update it whenever the post-finalization `completion_cadence.completed_experiments` value is divisible by 3 and the refinement loop remains active (`iteration_state.phase_status = running|ready`).

```json
{"task_type":"user_override_scan","trigger":"completion_cadence","status":"pending","completed_experiment_slot":6,"trigger_experiment_id":6,"scan_window_size":3,"scan_window_status":"ready","scan_scope":"last_3_finalized_experiments","override_count":2,"override_detected":true,"scan_window_experiment_ids":[4,5,6],"experiment_window":[{"experiment_id":4,"agent_verdict":"keep","user_verdict":"discard","final_status":"discard","override_detected":true,"override_direction":"keep_to_discard","changed_locations":["## Gotchas"],"mutation_types":["added"],"description":"Expanded gotchas section.","completion_cadence":{"scope_type":"experiment_series","scope_id":"runs/run_2026-04-11T09-00-00/","completed_experiments":4}},{"experiment_id":5,"agent_verdict":"keep","user_verdict":"discard","final_status":"discard","override_detected":true,"override_direction":"keep_to_discard","changed_locations":["## Gotchas"],"mutation_types":["added"],"description":"Added more gotchas reminders.","completion_cadence":{"scope_type":"experiment_series","scope_id":"runs/run_2026-04-11T09-00-00/","completed_experiments":5}},{"experiment_id":6,"agent_verdict":"keep","user_verdict":"keep","final_status":"keep","override_detected":false,"override_direction":null,"changed_locations":["## Examples"],"mutation_types":["modified"],"description":"Tightened example wording.","completion_cadence":{"scope_type":"experiment_series","scope_id":"runs/run_2026-04-11T09-00-00/","completed_experiments":6}}],"completion_cadence":{"scope_type":"experiment_series","scope_id":"runs/run_2026-04-11T09-00-00/","completed_experiments":6,"last_finalized_experiment_id":6,"last_finalized_status":"keep","incremented_at":"2026-04-11T18:25:00Z"}}
```

- `task_type`: always `user_override_scan`.
- `trigger`: `completion_cadence` for the every-third-experiment checkpoint hook.
- `status`: `pending`, `completed`, or `skipped`.
- `completed_experiment_slot`: the post-increment cadence slot that triggered the scan.
- `trigger_experiment_id`: finalized experiment ID that closed the cadence window.
- `scan_window_size`: required integer window size. v4.2 default is `3`.
- `scan_window_status`: `ready`, `underfilled`, or `empty` depending on how many finalized experiments were available to scan.
- `scan_scope`: required string; use `last_3_finalized_experiments`.
- `override_count`: number of experiments in `experiment_window[]` whose `agent_verdict` and `user_verdict` differ.
- `override_detected`: boolean shortcut for whether `override_count > 0`.
- `scan_window_experiment_ids`: stable ordered experiment IDs in the scan window.
- `experiment_window[]`: compact, replayable scan inputs copied from the last finalized experiments. `agent_verdict` comes from `decision_breakdown.proposed_decision`; `user_verdict` comes from the finalized experiment status; `override_detected` is true only when both are `keep|discard` and they differ.
- `experiment_window[].changed_locations`: unique `changes[].location` values for the experiment. Preserve these so later preference extraction can detect section-level patterns without reopening diffs.
- `experiment_window[].mutation_types`: unique `changes[].type` values for the experiment (`added`, `modified`, `removed`).
- `completion_cadence`: root cadence snapshot at the moment the scan task was queued or updated.
- Session-level only: store this object at the root of `state.json` / `results.json` as `pending_user_override_scan`. Do not copy it onto every experiment row.
- Active-loop guardrail: do not queue or keep this task active once `iteration_state.phase_status` becomes `completed` or `blocked`. Session Close and terminal states clear or leave the hook null instead of surfacing a stale checkpoint.

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
- Canonical split IDs only: `allowed_split_ids`, `blocked_split_ids`, and `split_access` keys must use `train`, `dev`, `test`, or `adversarial_holdout`. Do not store convenience aliases such as `holdout`, `adversarial-holdout`, or `adversarial holdout` inside the mutation-stage policy.
- Terminal split decisions only: `split_access` values must be `allowed`, `blocked`, or `inaccessible`. Do not encode delegated resolution like `delegate:adversarial_holdout` or `{ "delegate_split_id": "adversarial_holdout" }` inside the mutation-stage policy.
- `allowed_operations`: use this policy for baseline scoring, mutation scoring, mutation analysis, regression checks, and same-run version comparison during Phase 7.
- Intermediate mutation scoring is dev-only. If `requested_operation = mutation_scoring` resolves to `adversarial_holdout`, explicitly deny the request and fail closed before reopening any stored dev corpus.
- Persist the same object in `state.json.mutation_stage_split_access_policy` once Phase 4 freezes split boundaries. That state field is the orchestration-layer source of truth for later Phase 7 dataset reads and checkpoint resume.
- On resume or Phase 7 re-entry, restore the exact persisted object into the loaded run context before any scoring, mutation analysis, regression check, same-run version comparison, or other step that may reopen split-scoped inputs.
- If a Phase 7 step requests a dataset read, verify both the requested operation and the requested split against this restored object before reading fixtures, per-input outputs, or joined experiment records.
- Session Close adversarial holdout validation is intentionally outside this mutation-stage policy. Switch to the evaluation-only `session_close_holdout_validation` scope before reading holdout fixtures.
- The final-only evaluation stage is a single post-loop step. Trigger it exactly once after the mutation loop exits for the active `current_run_path`; never call it from Experiment 0 or any intermediate mutation iteration.
- `train`: blocked at mutation time. It remains few-shot material for Phase 5 judge prompts only.
- `test`: blocked at mutation time. It remains the Phase 6 final judge-measurement split only.
- `adversarial_holdout`: inaccessible during mutation-time operations. Only Session Close holdout validation may read it.

### Restricted Mutation-Stage Dataset Access Path

Use this access path for every split-scoped Phase 7 read after `mutation_stage_split_access_policy` has been restored into the loaded run context. Replace direct fixture/result reads inside the mutation loop with this path; the loop must not reopen `fixtures-manifest.md`, `input-sets.json`, per-input outputs, or joined comparison payloads on an ad hoc basis once Phase 7 is active.
Candidate generation and mutation hypothesis generation must obtain split-scoped inputs exclusively through this access path.
Do not load split membership, `fixtures-manifest.md`, or `input-sets.json` directly from the candidate-generation path.

Inputs:
- `policy`: the threaded `mutation_stage_split_access_policy` restored into the active run context.
- `requested_operation`: one of `baseline_scoring`, `mutation_analysis`, `mutation_scoring`, `regression_check`, or `same_run_version_comparison`.
- `requested_split_id`: raw split token supplied by the caller. Canonicalize it before the policy check; every mutation-stage read must still resolve to `dev`.
- `input_set_id`, `input_set_ref`, and `input_ids`: required whenever the read reopens an already-scored dev corpus instead of the initial baseline manifest.

Procedure:
1. Load the active `policy` from the run context. If it is missing, stop and restore it before reading any split-scoped data.
2. Verify `requested_operation` is present in `policy.allowed_operations`.
3. Canonicalize `requested_split_id` before checking the policy. If the raw token, a supported alias, or a delegated resolution path resolves to `adversarial_holdout`, reject the read as a blocked holdout access attempt. If `requested_operation = mutation_scoring` resolves to `adversarial_holdout`, explicitly deny the request and fail closed before reopening any stored dev corpus.
4. Verify the canonical requested split is present in `policy.allowed_split_ids` and not blocked by `policy.split_access`.
5. Resolve the dev-scoped corpus through persisted refs only:
   - `baseline_scoring`: open the dev split recorded in `fixtures-manifest.md` / `input-sets.json`.
   - `mutation_analysis`, `mutation_scoring`, `regression_check`, and `same_run_version_comparison`: reopen only the stored dev-scoped `input_set_id`, exact `input_set_ref`, and finalized-order `input_ids` for that run/experiment.
   - Intermediate mutation scoring must resolve its split through this policy-aware accessor. Do not branch on raw split IDs, reopen split manifests, or bypass the accessor to recover the dev corpus.
6. Return only the dev-scoped fixture content, scored inputs, per-input outputs, or joined comparison payload needed for the requested operation. Never materialize `train`, `test`, or `adversarial_holdout` while servicing this path.
7. If the request would cross into a blocked split, uses a mismatched `input_set_id`, omits required persisted refs for a reopen, or tries to satisfy a `dev` request by delegating to another split, reject the read and surface a blocking error instead of silently falling back to a direct file read.

Call-site mapping:
- Experiment 0 baseline scoring -> `requested_operation = baseline_scoring`
- Failure analysis or hypothesis generation that reopens scored inputs / fixture text -> `requested_operation = mutation_analysis`
- Experiment scoring -> `requested_operation = mutation_scoring`
- Regression checks -> `requested_operation = regression_check`
- Same-run version comparison preflight or joined per-input comparison -> `requested_operation = same_run_version_comparison`

Session Close holdout validation is intentionally outside this path. Once the run switches to `session_close_holdout_validation`, stop using the mutation-stage accessor and use the evaluation-only holdout scope instead. That final-only evaluation stage runs exactly once after mutation completes for the active run; it is never part of Experiment 0 or any intermediate mutation iteration.

- `split_id`: canonical split identifier. Valid Phase 4 split IDs are `train`, `dev`, `test`, and `adversarial_holdout`.
- `display_label`: human-readable label for the split as shown in manifests and reports.
- `evaluation_only`: `true` only for `adversarial_holdout`. This explicitly marks the split as measurement-only.
- `hidden_until`: use `session_close` for `adversarial_holdout` so weak agents do not leak the examples into mutation or judge-refinement flows.
- `used_for`: the only allowed consumer for `adversarial_holdout` is `session_close_holdout_validation`.
- `blocked_from`: stages that must never consume the split. `adversarial_holdout` is blocked from Phase 5 judge examples, Phase 6 judge refinement, Phase 7 mutation scoring, and Phase 7 mutation analysis.
- `separate_from`: splits this entry must remain disjoint from. `adversarial_holdout` is a dedicated evaluation-only split and must stay separate from mutation/refinement splits. Every split listed in `config.mutation_refinement_split_datasets[]` must appear here.
- `mutation_refinement_split_datasets`: evaluation-metadata snapshot of the split corpora referenced by the Phase 5-7 boundary rules. Compare their `input_ids` against the holdout `input_ids` and flag invalid metadata if any overlap exists. For actual Phase 7 mutation-time reads, obey `mutation_stage_split_access_policy`: only `dev` is allowed at runtime.
- Never alias `adversarial_holdout` to `dev`, `test`, or any mutation/refinement split for convenience. `test` remains the Phase 6 judge-validation measurement split; `adversarial_holdout` is the post-loop overfitting check.
- Never satisfy a mutation-stage `dev` request by delegating it to `adversarial_holdout`, even indirectly through alias tables, helper indirection, or resolved split targets.
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
- Iteration run started: `{"phase":"7","type":"iteration_run_started","run_id":"run_2026-04-03T14-30-00","path":"runs/run_2026-04-03T14-30-00/","target_version_label":"baseline_candidate|vN"}`
- Iteration phase transition: `{"phase":"7","type":"iteration_phase_transition","run_id":"run_2026-04-03T14-30-00","experiment":0,"from":"eval","to":"mutate","last_eval_status":"completed","last_eval_results_ref":"runs/run_.../iteration_000/eval_results.json","next_action":"phase7_mutation_analysis"}`
- Completion cadence increment: `{"phase":"7","type":"completion_cadence","experiment":N,"scope_type":"experiment_series","scope_id":"runs/run_.../","completed_experiments":N,"status":"baseline|keep|discard"}`
- User override scan queued: `{"phase":"7","type":"user_override_scan_queued","experiment":N,"completed_experiment_slot":N,"window":[N-2,N-1,N],"override_count":M}`
- Input set registration: `{"phase":"3","type":"input_set_registered","set_id":"phase3-fixtures-7f3c91ad","kind":"phase3_fixtures","input_count":18,"canonical_hash":"7f3c91adf2f0f96f..."}`
- Eval strategy resolution: `{"phase":"1","type":"eval_strategy_resolution","skill_pattern":"pipeline","strategy_id":"pipeline_eval_strategy","reasoning":"Pattern requires gate-aware, resume-safe downstream evaluation."}`
- Research intake started: `{"phase":"6.5","type":"research_intake_started","target_skill_path":"skill-under-test/SKILL.md","target_domain":"<one-sentence target job>","requested_sources":3}`
- Research intake completed: `{"phase":"6.5","type":"research_intake_completed","status":"completed|partial|skipped|failed","accepted_sources":2,"rejected_sources":1,"artifact":"research-intake.md","error_code":"none|target_skill_missing|target_domain_missing|missing_phase1_context|no_valid_sources|artifact_write_failed|invalid_research_intake_config"}`
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
  "left_experiment_id": 0,
  "right_experiment_id": 3,
  "input_set_id": "phase4-dev-7f3c91ad",
  "left_baseline_trials": [
    {
      "trial_index": 1,
      "trial_id": "baseline-trial-001",
      "run_index": 1,
      "score": 72.3,
      "pass_rate": 72.3,
      "timestamps": {
        "started_at": "2026-04-11T09:00:00Z",
        "completed_at": "2026-04-11T09:00:08Z"
      },
      "raw_outputs": [
        {
          "input_id": "phase4-dev-7f3c91ad-I03",
          "output_text": "Trial 1 output for fixture I03"
        }
      ],
      "trial_metadata": {
        "requested_operation": "baseline_scoring",
        "requested_split_id": "dev",
        "input_set_id": "phase4-dev-7f3c91ad"
      }
    }
  ],
  "right_baseline_trials": null,
  "shared_input_summary": {
    "total_shared_inputs": 2,
    "improved": 1,
    "regressed": 0,
    "unreliable": 0,
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
- `shared_input_summary.total_shared_inputs` must equal the `per_input[]` length and must also equal `improved + regressed + unreliable + unchanged`.
- Classify each shared input by score outcome, not metadata-only edits. Prefer the `weighted_points` delta when present; otherwise derive the bucket from `pass_fail` transitions. When a baseline reliability threshold is available, `improved` and `regressed` become the trusted buckets and any within-noise-floor delta must move to `unreliable`. Metadata-only changes stay in `unchanged`.
- When either comparison side is the Experiment 0 baseline, also expose `left_baseline_trials[]` or `right_baseline_trials[]` and reuse the same serialized `baseline_trials[]` rows on that comparison side so later comparison flows can inspect the three saved pre-mutation runs without reopening the standalone experiment card first.
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

### Quick Start state snapshot
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

When Phase 1 emits a structured audit payload, include the chosen primary pattern as a top-level `selected_skill_pattern` field.
Include the resolved downstream selector as a top-level `selected_eval_strategy_id` field.
Source it from `state.json.phase1_context.selected_skill_pattern` for the active run rather than inferring it from prose or rereading state later.
Source both fields from the active run's `state.json.phase1_context` values rather than inferring them from prose or requiring downstream consumers to reopen state.
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
- **`description_quality.not_for_clause_hint` — diagnostic sub-signal (informational only).** After assigning the Present/Partial/Missing anchor, compute this hint. It does NOT change the anchor score. Purpose: inform the skill author that adding an explicit exclusion clause ("NOT for: …" or "Do not use for: …") to the description may improve routing precision when no behavioral DNT examples exist. Trigger condition: fires only when BOTH of the following are true: (1) `[workspace]/contract/do-not-trigger-examples.jsonl` is absent OR contains zero rows, AND (2) the lowercased `description:` field contains no `"not for:"` or `"do not use for:"` substring (normalize the description to lowercase, then match against the two lowercased canonical strings). **Emission rule: emit `description_quality.not_for_clause_hint` ONLY when both trigger conditions hold. When either silencing condition is met — DNT has ≥1 row, OR the description already contains a `"not for:"` / `"do not use for:"` clause — OMIT the key entirely from the output payload.** This guarantees zero findings on any skill that already has DNT examples or prose exclusion clauses, aligning with the W2 exit criterion. Output payload when emitted: `{"suggested": true, "reason": "no_dnt_examples_and_no_not_for_clause"}`. Severity: `info` — never a warning, never a gate.

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
- Sort the unique `source_sample_group_id` values for the frozen dev split, then assign `fold_1`, `fold_2`, `fold_3` in repeating order down that sorted group list.
- Every `source_sample_group_id` must appear in exactly one persisted fold-assignment entry, and every Phase 6 dev record in that group inherits the same `fold_id`.
- This keeps fold sizes within one group of each other while staying fully deterministic for a frozen dev set.
- Never derive fold membership from runtime iteration order, filesystem order, presentation order, or RNG state.
- Persist the finalized fold map in `judge-validation-report.md` under `phase6_dev_fold_assignments`.

Example payload:
```json
"phase6_dev_fold_assignments":[
  {"source_sample_group_id":"phase4-dev-7f3c91ad-I01|91ab77ce...","input_id":"phase4-dev-7f3c91ad-I01","content_hash":"91ab77ce...","stable_fold_key":"phase4-dev-7f3c91ad-I01|91ab77ce...","fold_id":"fold_1"},
  {"source_sample_group_id":"phase4-dev-7f3c91ad-I02|42be3101...","input_id":"phase4-dev-7f3c91ad-I02","content_hash":"42be3101...","stable_fold_key":"phase4-dev-7f3c91ad-I02|42be3101...","fold_id":"fold_2"},
  {"source_sample_group_id":"phase4-dev-7f3c91ad-I03|6ca1b7d2...","input_id":"phase4-dev-7f3c91ad-I03","content_hash":"6ca1b7d2...","stable_fold_key":"phase4-dev-7f3c91ad-I03|6ca1b7d2...","fold_id":"fold_3"}
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

### Phase 6 Validation Result Payload
- Store aggregate Phase 6 mean/range outputs on each `validation_results[]` row.
- Mirror the aggregate dev/test TPR/TNR outputs inside `aggregated_tpr_tnr_summary` so the final evaluation result has a dedicated summary section for downstream consumers.
- Within `aggregated_tpr_tnr_summary.dev`, keep the flat compatibility fields and also persist structured `tpr_confidence_range` / `tnr_confidence_range` objects with `lower_bound`, `upper_bound`, and `half_width`, bounding the interval to the valid 0-1 metric domain.
- Persist one aggregate confusion matrix per judge on the same `validation_results[]` row. This is the primary Phase 6 trust surface for false-pass / false-fail review.
- Persist replayable exemplar rows for the aggregate confusion matrix instead of asking report consumers to reopen every fold artifact by hand.
- Keep fold-level TPR/TNR outputs in `phase6_dev_fold_metrics` instead of flattening them into the aggregate mean/range fields.

Example payload:
```json
"validation_results":[
  {
    "eval":"E2",
    "dev_tpr_mean":0.92,
    "dev_tnr_mean":0.86,
    "dev_tpr_range":0.07,
    "dev_tnr_range":0.08,
    "test_tpr":0.89,
    "test_tnr":0.84,
    "aggregated_tpr_tnr_summary":{
      "dev":{
        "tpr_mean":0.92,
        "tpr_range":0.07,
        "tpr_confidence_range":{"lower_bound":0.85,"upper_bound":0.99,"half_width":0.07},
        "tnr_mean":0.86,
        "tnr_range":0.08,
        "tnr_confidence_range":{"lower_bound":0.78,"upper_bound":0.94,"half_width":0.08}
      },
      "test":{"tpr":0.89,"tnr":0.84}
    },
    "confusion_matrix":{"tp":12,"tn":5,"fp":1,"fn":2},
    "confusion_examples":{
      "false_positives":[{"fixture_reference":"phase4-dev-7f3c91ad-I09","judge_reason":"The judge treated tone as sufficient evidence of correctness."}],
      "false_negatives":[{"fixture_reference":"phase4-dev-7f3c91ad-I12","judge_reason":"The judge missed that the required gotchas section was present and specific."}]
    },
    "status":"APPROVED",
    "phase6_dev_fold_metrics":[
      {"fold_id":"fold_1","metric_object":{"sample_count":5,"human_pass_count":3,"human_fail_count":2,"true_positive_count":3,"true_negative_count":2,"tpr":1.0,"tnr":1.0}},
      {"fold_id":"fold_2","metric_object":{"sample_count":5,"human_pass_count":3,"human_fail_count":2,"true_positive_count":2,"true_negative_count":2,"tpr":0.667,"tnr":1.0}},
      {"fold_id":"fold_3","metric_object":{"sample_count":5,"human_pass_count":2,"human_fail_count":3,"true_positive_count":2,"true_negative_count":2,"tpr":1.0,"tnr":0.667}}
    ]
  }
]
```

- `validation_results[].confusion_matrix`: aggregate per-judge confusion counts across the stored Phase 6 dev folds. Persist `tp`, `tn`, `fp`, and `fn` explicitly instead of asking report consumers to rebuild them from fold tables.
- `validation_results[].confusion_examples`: primary replayable false-pass / false-fail exemplars for the aggregate confusion matrix. Store reviewer-readable `false_positives[]` and `false_negatives[]` rows so trust review can inspect how the judge failed without reopening every fold artifact.

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
{"id":N,"input_set_id":"phase4-dev-7f3c91ad","input_set_ref":"input-sets.json#phase4-dev-7f3c91ad","input_ids":["phase4-dev-7f3c91ad-I03","phase4-dev-7f3c91ad-I05","phase4-dev-7f3c91ad-I08"],"score":X,"max_score":Y,"pass_rate":Z,"status":"keep|discard|baseline","description":"...","changes":[{"type":"added|modified|removed","location":"section","snippet":"1-3 lines"}],"validation_results":[{"eval":"E2","dev_tpr_mean":0.92,"dev_tnr_mean":0.86,"dev_tpr_range":0.07,"dev_tnr_range":0.08,"test_tpr":0.89,"test_tnr":0.84,"aggregated_tpr_tnr_summary":{"dev":{"tpr_mean":0.92,"tpr_range":0.07,"tpr_confidence_range":{"lower_bound":0.85,"upper_bound":0.99,"half_width":0.07},"tnr_mean":0.86,"tnr_range":0.08,"tnr_confidence_range":{"lower_bound":0.78,"upper_bound":0.94,"half_width":0.08}},"test":{"tpr":0.89,"tnr":0.84}},"confusion_matrix":{"tp":12,"tn":5,"fp":1,"fn":2},"confusion_examples":{"false_positives":[{"fixture_reference":"phase4-dev-7f3c91ad-I09","judge_reason":"The judge treated tone as sufficient evidence of correctness."}],"false_negatives":[{"fixture_reference":"phase4-dev-7f3c91ad-I12","judge_reason":"The judge missed that the required gotchas section was present and specific."}]},"status":"APPROVED","phase6_dev_fold_metrics":[{"fold_id":"fold_1","metric_object":{"sample_count":5,"human_pass_count":3,"human_fail_count":2,"true_positive_count":3,"true_negative_count":2,"tpr":1.0,"tnr":1.0}},{"fold_id":"fold_2","metric_object":{"sample_count":5,"human_pass_count":3,"human_fail_count":2,"true_positive_count":2,"true_negative_count":2,"tpr":0.667,"tnr":1.0}},{"fold_id":"fold_3","metric_object":{"sample_count":5,"human_pass_count":2,"human_fail_count":3,"true_positive_count":2,"true_negative_count":2,"tpr":1.0,"tnr":0.667}}]}],"eval_results":[{"eval":"E1","pass_fail":"pass","reasoning_trace":"1. Criterion check: the rubric requires concrete gotcha warnings and the output includes them. 2. Evidence: the output contains a gotchas heading and 3 specific warnings. 3. Verdict link: because both the section and concrete warnings are present, this passes.","evidence":[{"kind":"output_excerpt","source":"skill_output","locator":"input_id:phase4-dev-7f3c91ad-I03 output lines 12-18","excerpt":"## Gotchas\\n- Never run rm -rf without checking the target path.","metric":null,"artifact_ref":null},{"kind":"metric","source":"scoring_metric","locator":"warnings_found","excerpt":"3 concrete warnings found in the gotchas section.","metric":{"name":"warnings_found","value":3,"unit":"count"},"artifact_ref":null}],"supporting_items":[{"stage":"criterion_check","decision":"gotchas heading is present","outcome":"met","evidence_refs":[0]},{"stage":"evidence_check","decision":"three concrete warnings were found","outcome":"met","evidence_refs":[1]},{"stage":"verdict_link","decision":"the rubric passes when both the heading and warning count are present","outcome":"supports_pass","evidence_refs":[0,1]}],"weight":1.0,"weight_source":"code_eval_fixed","weighted_points":1.0,"normalized_contribution":0.25}],"decision_breakdown":{"components":[{"eval":"E1","pass_fail":"pass","weight":1.0,"weight_source":"code_eval_fixed","weighted_points":1.0,"normalized_contribution":0.213}],"formula":"combined_score = weighted_points / total_weight","weighted_points":3.7,"total_weight":4.7,"combined_score":0.787,"combined_score_pct":78.7,"threshold":0.8,"proposed_decision":"discard"},"regression_check":null,"discard_autopsy":null}
```
Any result retrieval response schema or serializer that returns experiment records must include the stored `decision_breakdown` field unchanged so downstream dashboards and version-comparison views can explain the aggregation math.

- `input_set_id`: the scoring corpus used for this experiment.
- `input_set_ref`: exact pointer back to the registered set entry in `input-sets.json`.
- `input_ids`: exact stable inputs scored for this experiment, listed in finalized set order. Version comparisons are only valid when this matches across experiments.
- `validation_results`: Phase 6 judge validation summaries. Store aggregate dev/test TPR/TNR mean/range fields on each row, mirror them inside `aggregated_tpr_tnr_summary`, include structured `tpr_confidence_range` / `tnr_confidence_range` interval objects in the dev summary, persist the aggregate `confusion_matrix` plus reviewer-readable `confusion_examples`, and keep fold-level TPR/TNR outputs in `phase6_dev_fold_metrics` instead of flattening them into the aggregate mean/range fields.
- Return the stored verdict objects unchanged so each `pass_fail` decision stays attached to its own `evidence[]` and `supporting_items[]`.
- return the stored verdict objects unchanged so each `pass_fail` decision stays attached to its own `evidence[]` and `supporting_items[]`

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
- A Pass/Fail verdict without at least one concrete evidence item is invalid judge output.
- If a verdict is missing evidence, it must be flagged and rejected from scoring/storage until the judge is rerun or fixed.

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

## Multi-Judge Verdict Schema

Read when: an eval is marked multi-judge in Phase 5 or a stored verdict was produced by 2+ independent judges.

`multi_judge` is an optional structured consensus block attached to one verdict. It preserves the independent panel outputs, the unanimity rule, and whether the verdict is still blocked on human review:

```json
{
  "required_judge_count": 2,
  "agreement_rule": "unanimous",
  "consensus_status": "disagreement",
  "requires_human_review": true,
  "disagreement_event": {
    "event_type": "multi_judge_disagreement",
    "session_log_ref": "session-log.json#multi_judge_disagreement-exp4-E2"
  },
  "judges": [
    {
      "judge_id": "judge_a",
      "judge_label": "Judge A",
      "pass_fail": "pass",
      "reasoning_trace": "Presence-framed judge accepted the examples because two examples were provided."
    },
    {
      "judge_id": "judge_b",
      "judge_label": "Judge B",
      "pass_fail": "fail",
      "reasoning_trace": "Failure-framed judge rejected the examples because they are generic and not concrete enough."
    }
  ]
}
```

Required fields:
- `required_judge_count`: positive integer. Number of independent judges that must weigh in before the verdict can resolve automatically.
- `agreement_rule`: use `unanimous` in v4. A single judge cannot decide a multi-judge eval alone.
- `consensus_status`: one of `agreed`, `disagreement`, `single_judge`, or `unknown`.
- `requires_human_review`: boolean. Set `true` whenever the panel disagrees and the verdict must be resolved outside the automated judge loop.
- `judges[]`: one object per independent judge with `judge_id`, `judge_label`, `pass_fail`, and `reasoning_trace`.

Usage rules:
- Only agreed multi-judge verdicts may contribute to `decision_breakdown.components[]`.
- Only unanimous multi-judge verdicts should contribute weighted points to the final score.
- When `consensus_status = disagreement`, persist `pass_fail = disagreement` on the parent verdict, do not let one judge silently choose the score, and surface the verdict for human review.
- Log disagreements through `disagreement_event` so the human-review queue and calibration audit trail can reopen the exact split verdict later.
- Preserve the `multi_judge` object unchanged in `eval_results[]`, `judge_verdict_report_entries[]`, and any surfaced human-review sample derived from that verdict.

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

### mutation_handoff fields

The scoring pass also emits `mutation_handoff` for baseline and every mutation. This is the stable structured handoff from eval to mutate:

```json
{
  "mutation_handoff": {
    "schema_version": 1,
    "artifact_role": "phase7_eval_to_mutate_handoff",
    "normalized_evaluation_scores": {
      "combined_score": 0.787,
      "combined_score_pct": 78.7,
      "threshold": 0.8,
      "gap_to_threshold": -0.013,
      "per_eval": [
        {
          "eval": "E1",
          "category": "structural",
          "pass_fail": "pass",
          "normalized_score": 0.213,
          "missed_weight_share": 0.0,
          "weight": 1.0,
          "weight_source": "code_eval_fixed"
        },
        {
          "eval": "E2",
          "category": "quality",
          "pass_fail": "fail",
          "normalized_score": 0.0,
          "missed_weight_share": 0.191,
          "weight": 0.9,
          "weight_source": "phase_6_validation_average"
        }
      ]
    },
    "failure_reasons": [
      {
        "reason_id": "exp3-E2-missing-disclosure-guidance",
        "eval": "E2",
        "category": "quality",
        "reason_code": "missing_required_instruction",
        "summary": "Disclosure guidance is missing.",
        "source_eval_ref": "eval_results[E2]",
        "evidence_refs": [
          "eval_results[E2].evidence[0]"
        ],
        "supporting_item_refs": [
          "eval_results[E2].supporting_items[0]",
          "eval_results[E2].supporting_items[1]"
        ],
        "missed_weight_share": 0.191,
        "mapped_target_ids": [
          "target-progressive-disclosure-read-when"
        ]
      }
    ],
    "mutation_targets": [
      {
        "target_id": "target-progressive-disclosure-read-when",
        "target_location": "Progressive Disclosure",
        "recommended_mutation_type": "modify",
        "priority": 1,
        "source_eval_ids": [
          "E2"
        ],
        "source_reason_ids": [
          "exp3-E2-missing-disclosure-guidance"
        ],
        "strategy_alignment": "pipeline_eval_strategy",
        "rationale": "Restore explicit stage-local disclosure guidance for pipeline readers.",
        "expected_effect": "Recover the missed disclosure requirement without destabilizing passing gotcha behavior.",
        "evidence_admission": {
          "status": "admitted",
          "reason_code": "skill_deficiency",
          "evidence_refs": [
            "eval_results[E2].evidence[0]"
          ],
          "summary": "The failure was caused by missing disclosure guidance in the skill itself."
        }
      }
    ]
  }
}
```

- `schema_version`: currently `1` for the canonical eval-to-mutate handoff contract.
- `artifact_role`: always `phase7_eval_to_mutate_handoff`.
- `normalized_evaluation_scores`: normalized score surface that the mutate phase reads directly instead of reverse-engineering weight math from `decision_breakdown`.
- `normalized_evaluation_scores.gap_to_threshold`: signed `combined_score - threshold`; negative means the experiment is still below keep threshold, positive means it cleared threshold with headroom.
- `normalized_evaluation_scores.per_eval[]`: ordered per-eval score rows. `normalized_score` is the eval's realized share of the final score. `missed_weight_share` is the withheld share for a failed eval and should be `0.0` for passing evals.
- `failure_reasons[]`: canonical blocking reasons extracted from failing or unresolved evals. One eval may emit multiple failure reasons when the mutate phase must track distinct blockers separately.
- `failure_reasons[].source_eval_ref`: stable pointer back to the owning `eval_results[]` row.
- `failure_reasons[].evidence_refs` and `failure_reasons[].supporting_item_refs`: stable pointers back to the exact stored evidence and sub-decisions that justified the failure reason.
- `failure_reasons[].mapped_target_ids`: ordered link(s) to the mutation target entries this failure reason should feed.
- `mutation_targets[]`: ordered candidate mutation list for Phase 7 step 2a. Each row is the machine-readable target contract the mutate phase acts on directly, so it must carry `target_id`, `target_location`, `recommended_mutation_type`, `priority`, `source_eval_ids`, `source_reason_ids`, `strategy_alignment`, `rationale`, and `expected_effect` without requiring prose reconstruction.
- `mutation_targets[].target_id`: stable identifier for the target row. `failure_reasons[].mapped_target_ids` should point here so mutate can join reasons to targets without fuzzy matching.
- `mutation_targets[].target_location`: use the same section/instruction naming convention as `changes[].location` so keeps, discards, and future autopsies can compare target history without fuzzy matching.
- `mutation_targets[].recommended_mutation_type`: canonical mutation action for this target. Use the same mutation-type vocabulary the loop already understands (`add`, `modify`, `delete`) so the mutate phase can seed a one-change hypothesis directly from the row.
- `mutation_targets[].priority`: ordered execution rank where lower numbers mean earlier mutation candidates. Phase 7 step 2a should start from the smallest priority value before consulting later targets.
- `mutation_targets[].source_eval_ids`: ordered eval rows whose outcomes created this target. Preserve the exact eval IDs so mutate can reopen the right judge verdicts or evidence bundles without re-clustering failures.
- `mutation_targets[].source_reason_ids`: ordered failure-reason rows that map into this target. Carry these forward unchanged into the one-change hypothesis so later autopsies can trace the mutation back to the exact blocker IDs.
- `mutation_targets[].strategy_alignment`: the active `selected_eval_strategy_id` or compatible strategy tag that justified choosing this target. Mutate should treat this as the canonical pattern-aware route instead of falling back to a generic edit path.
- `mutation_targets[].rationale`: concise target-local explanation for why this target is the next mutation candidate. This is the machine-readable summary mutate can display or copy into the hypothesis scaffold without mining free-form critique prose.
- `mutation_targets[].expected_effect`: concise statement of the intended improvement if this target is mutated successfully. Mutate should propagate this unchanged into the candidate hypothesis and later compare the observed outcome against it.
- `mutation_targets[].evidence_admission`: mutation-stage evidence-admission decision for this target. Required fields are `status` (`admitted|rejected`), `reason_code`, `evidence_refs[]`, and `summary`.
- Only `mutation_targets[]` rows with `evidence_admission.status = admitted` may feed step 2a candidate generation.
- Use `reason_code = skill_deficiency` when the evidence shows the skill content is actually wrong, missing, or misleading.
- Use `reason_code = agent_misuse_not_skill_deficiency` when the skill already contained correct guidance and the failure came from agent misuse, runtime behavior, or missed tool use. Rejected rows remain audit-visible but may not be promoted into candidate revisions.
- Populate `mutation_handoff` immediately after `decision_explanation` is finalized so scoring, explanation, and mutation-target extraction all describe the same evaluation event.
- Return the stored `mutation_handoff` field unchanged anywhere experiment payloads are serialized, fetched, or shown. Never recompute `mutation_handoff` on the retrieval path.

### Mutation Candidate Evaluation Schema

Before AutoRefine promotes a research-derived donor into a one-change hypothesis, emit a `mutation_candidate_evaluation` artifact that captures the extracted donor pattern, the exact source evidence, target-skill similarity, a transparent relevance rubric, and trust/overfitting signals. This keeps the research-to-mutation bridge explainable before any candidate revision is materialized.

```json
{
  "schema_version": 1,
  "artifact_role": "phase7_mutation_candidate_evaluation",
  "candidate_source": {
    "entry_id": "rc-pattern-read-when-001",
    "entry_type": "pattern_observation",
    "source_kind": "reference_skill",
    "source_ref": {
      "source_id": "source-ship-skill-001",
      "canonical_location": "~/.claude/skills/ship/SKILL.md",
      "content_hash": "sha256:source-ship-skill-001"
    },
    "source_pattern": {
      "pattern_label": "progressive_disclosure_read_when",
      "pattern_statement": "Use explicit Read when guards before optional reference expansion.",
      "transfer_type": "positive_pattern",
      "applicability_reason": "The target skill already has a Progressive Disclosure section that is missing a clear gate.",
      "mutation_leverage": "Restore a short Read when guard ahead of deep reference sections."
    },
    "source_evidence_reference": {
      "schema_version": 1,
      "source_hash": "sha256:source-ship-skill-001",
      "source_location": {
        "locator": "## Progressive Disclosure",
        "section_id": "progressive_disclosure",
        "heading_path": [
          "Progressive Disclosure"
        ]
      },
      "quote": "Read when: before expanding the answer, inspect the linked reference section.",
      "span": {
        "line_start": 12,
        "line_end": 12,
        "char_start": 422,
        "char_end": 491,
        "byte_start": 422,
        "byte_end": 491,
        "offset_basis": "normalized_text_utf8"
      },
      "retrieval_fingerprint": "ri-2026-04-11-source-ship-001:progressive_disclosure"
    },
    "traceability": {
      "research_artifact_ref": "research-intake.md#accepted-source-source-ship-skill-001",
      "raw_artifact_refs": [
        "research-sources/source-ship-skill-001/SKILL.md"
      ],
      "evidence_refs": [
        "research-intake.md#pattern-progressive-disclosure"
      ]
    }
  },
  "target_skill_context": {
    "skill_path": "skill-under-test/SKILL.md",
    "skill_pattern": "pipeline",
    "selected_eval_strategy_id": "pipeline_eval_strategy",
    "target_section": "Progressive Disclosure",
    "agent_target": "any_skill_md",
    "scenario_target": "production"
  },
  "similarity_assessment": {
    "overall_similarity": 0.82,
    "similarity_label": "high",
    "matched_dimensions": [
      {
        "dimension": "skill_pattern",
        "source_value": "pipeline",
        "target_value": "pipeline",
        "match_status": "match",
        "score": 1.0
      },
      {
        "dimension": "target_section",
        "source_value": "Progressive Disclosure",
        "target_value": "Progressive Disclosure",
        "match_status": "match",
        "score": 0.9
      }
    ],
    "rationale": "The donor pattern and target skill share the same structure, section focus, and delivery scenario."
  },
  "relevance_rubric": {
    "schema_version": 1,
    "aggregation_formula": "weighted_sum(dimension.score * dimension.weight)",
    "dimensions": [
      {
        "dimension": "goal_alignment",
        "weight": 0.45,
        "criterion_description": "Does the donor pattern directly improve the same target job, failure mode, or mutation objective that the current skill version is trying to improve?",
        "score": 0.9,
        "score_label": "strong_match",
        "evidence_summary": "Both the donor and target are trying to restore an explicit read-when disclosure gate in the same section."
      },
      {
        "dimension": "structural_fit",
        "weight": 0.35,
        "criterion_description": "Can the donor pattern be transplanted into the target skill's pattern, section boundaries, and workflow shape without importing incompatible stage logic or hidden assumptions?",
        "score": 0.85,
        "score_label": "strong_match",
        "evidence_summary": "Both source and target are pipeline-pattern skills and the change lands in the same Progressive Disclosure section."
      },
      {
        "dimension": "domain_context_match",
        "weight": 0.20,
        "criterion_description": "Do the donor and target operate in a similar agent, domain, and scenario context so the terminology, constraints, and reference expectations still transfer cleanly?",
        "score": 0.75,
        "score_label": "usable_match",
        "evidence_summary": "Both are SKILL.md-based agents for production-oriented workflows, even though they solve different concrete tasks."
      }
    ],
    "weighted_score": 0.853,
    "weighted_score_pct": 85.3
  },
  "trust_signals": {
    "confidence": "high",
    "status": "active",
    "evidence_count": 1,
    "provenance_complete": true,
    "has_structured_evidence_reference": true,
    "source_snapshot_pinned": true,
    "retrieval_span_seconds": 2
  },
  "overfitting_signals": {
    "same_skill_lineage": false,
    "same_input_set_verified": null,
    "evaluation_corpus_overlap_status": "disjoint",
    "holdout_exposure_status": "not_exposed",
    "noise_floor_dependency": "indirect_only",
    "risk_flags": []
  },
  "recommendation": {
    "status": "promote_to_mutation_hypothesis",
    "target_section": "Progressive Disclosure",
    "reason": "High structural similarity plus complete provenance make this donor pattern safe to try before scoring.",
    "expected_effect": "Recover the missing disclosure gate without importing unrelated workflow steps."
  }
}
```

- `artifact_role`: always `phase7_mutation_candidate_evaluation`.
- `candidate_source`: frozen donor-pattern payload copied from the normalized research corpus entry. Keep `source_pattern` separate from `source_evidence_reference` so humans can inspect the extracted claim independently from its supporting proof.
- `target_skill_context`: the exact skill/version/pattern context that the donor is being compared against.
- `similarity_assessment`: why the donor is structurally compatible with the target skill before mutation.
- `relevance_rubric`: transparent donor-to-target relevance surface used before recommendation. Preserve the weighted dimensions, human-readable criterion descriptions, per-dimension evidence summaries, and the computed weighted score so humans can audit why a donor looked relevant.
- `trust_signals`: provenance completeness checks derived from the corpus entry itself. This is the minimum trust surface before the donor can influence a mutation.
- `overfitting_signals`: defense-in-depth checks that ensure a donor pattern is not being promoted from the same lineage, same scoring corpus, or exposed holdout material.
- `recommendation`: the explicit promote / hold / reject decision that bridges research intake into mutation hypothesis generation.
- `recommendation` must not bypass `relevance_rubric.weighted_score`; trust and overfitting signals may veto promotion, but the relevance score is the default explanatory surface for why a donor is considered on-target or off-target before mutation.

### Mutation Candidate Relevance Rubric Schema

Use this default rubric whenever `mutation_candidate_evaluation` compares a donor pattern against the current skill-under-test. The rubric is transparent by default: the weights are fixed, every dimension carries a human-readable criterion description, and the final relevance score is just the weighted sum of the visible dimension scores.

```json
{
  "schema_version": 1,
  "aggregation_formula": "weighted_sum(dimension.score * dimension.weight)",
  "dimensions": [
    {
      "dimension": "goal_alignment",
      "weight": 0.45,
      "criterion_description": "Does the donor pattern directly improve the same target job, failure mode, or mutation objective that the current skill version is trying to improve?",
      "score": 0.0,
      "score_label": "weak_match|partial_match|strong_match",
      "evidence_summary": "<why this donor does or does not help the target objective>"
    },
    {
      "dimension": "structural_fit",
      "weight": 0.35,
      "criterion_description": "Can the donor pattern be transplanted into the target skill's pattern, section boundaries, and workflow shape without importing incompatible stage logic or hidden assumptions?",
      "score": 0.0,
      "score_label": "weak_match|partial_match|strong_match",
      "evidence_summary": "<why the donor does or does not fit the target structure>"
    },
    {
      "dimension": "domain_context_match",
      "weight": 0.20,
      "criterion_description": "Do the donor and target operate in a similar agent, domain, and scenario context so the terminology, constraints, and reference expectations still transfer cleanly?",
      "score": 0.0,
      "score_label": "weak_match|partial_match|strong_match",
      "evidence_summary": "<why the donor does or does not transfer across context>"
    }
  ],
  "weighted_score": 0.0,
  "weighted_score_pct": 0.0
}
```

- `goal_alignment` has default weight `0.45` because same-skill version improvement should privilege donor patterns that attack the target job-to-be-done or observed failure mode directly, not just generic writing overlap.
- `structural_fit` has default weight `0.35` because a useful donor still has to fit the target skill's pattern, section boundaries, and workflow shape without importing brittle or incompatible mechanics.
- `domain_context_match` has default weight `0.20` because transfer still depends on the donor living close enough to the target agent/domain/scenario context, but a strong target-objective match can still justify reuse across adjacent domains.
- The three weights must sum to `1.0`. Do not add hidden bonus factors or opaque post-hoc multipliers on the recommendation path.
- Score each dimension on a normalized `0.0-1.0` scale and keep the written `criterion_description` visible to human reviewers. If a later phase wants to tune thresholds, tune the downstream recommendation policy, not the rubric dimensions or their meaning.

### Mutation Candidate Revision Artifact

Once mutate selects the highest-priority target row, convert that structured eval-to-mutate handoff into exactly one candidate `SKILL.md` revision artifact. This is the stable machine-readable record of the candidate the mutation engine produced before scoring or user presentation.

```json
{
  "schema_version": 1,
  "artifact_role": "phase7_mutation_candidate_revision",
  "source_artifact_role": "phase7_eval_to_mutate_handoff",
  "source_artifact_schema_version": 1,
  "lineage_metadata": {
    "experiment_id": 3,
    "version_label": "v3",
    "experiment_status": "discard",
    "input_set_id": "phase4-dev-7f3c91ad",
    "input_set_ref": "input-sets.json#phase4-dev-7f3c91ad",
    "input_ids": [
      "phase4-dev-7f3c91ad-I03",
      "phase4-dev-7f3c91ad-I05"
    ],
    "dataset_split_id": "dev",
    "selected_eval_strategy_id": "pipeline_eval_strategy"
  },
  "selected_mutation_target": {
    "target_id": "target-progressive-disclosure-read-when",
    "target_location": "Progressive Disclosure",
    "recommended_mutation_type": "modify",
    "priority": 1,
    "source_eval_ids": [
      "E2"
    ],
    "source_reason_ids": [
      "exp3-E2-missing-disclosure-guidance"
    ],
    "strategy_alignment": "pipeline_eval_strategy",
    "rationale": "Restore explicit read-when guidance before later expansion.",
    "expected_effect": "Recover the missed disclosure requirement without disturbing stage order."
  },
  "mutation_outcome": {
    "status": "candidate_generated",
    "skip_reason_code": null,
    "skip_summary": null,
    "next_recommended_action": "phase7_test_phase"
  },
  "candidate_skill_revision": {
    "format": "SKILL.md",
    "content_type": "text/markdown",
    "content": "# AutoRefine\n\nRead when: before expanding the answer, inspect the linked reference section.\n\n## Progressive Disclosure\n- Load references.md before writing the final response."
  },
  "reviewer_confirmation_gate": {
    "required": false,
    "trigger_kinds": [],
    "status": "not_required",
    "reviewer_id": null,
    "confirmed_at": null,
    "notes": null
  },
  "version_artifact": {
    "schema_version": 1,
    "artifact_type": "skill_version_artifact",
    "version_id": "skill_version__run_2026-04-11T09-00-00__exp_003",
    "run_id": "run_2026-04-11T09-00-00",
    "experiment_id": 3,
    "lineage_label": null,
    "parent_version_id": "skill_version__run_2026-04-11T09-00-00__exp_000",
    "root_version_id": "skill_version__run_2026-04-11T09-00-00__exp_000",
    "lineage_depth": 1,
    "lineage_store_path": "skill-versions/lineage.json",
    "artifact_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/",
    "snapshot_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/SKILL.md",
    "snapshot_sha256": "sha256:4b2859d8c0f1f1a9...",
    "source_iteration_path": "runs/run_2026-04-11T09-00-00/iteration_003/",
    "source_mutation_artifact_ref": "runs/run_2026-04-11T09-00-00/iteration_003/mutation.md#version_artifact",
    "created_at": "2026-04-11T09:05:00Z"
  }
}
```

- `schema_version`: currently `1` for the mutation candidate revision artifact contract.
- `artifact_role`: always `phase7_mutation_candidate_revision`.
- `source_artifact_role`: always `phase7_eval_to_mutate_handoff`; this candidate artifact is produced from the structured eval-to-mutate input, not from free-form critique text.
- `source_artifact_schema_version`: copy the `mutation_handoff.schema_version` that powered this candidate revision.
- `lineage_metadata`: copy the same experiment/input-set/strategy lineage used to build the direct mutate input so downstream consumers can trace which scoring corpus and pattern-aware route produced the candidate.
- `selected_mutation_target`: copy the selected `mutation_targets[]` row unchanged from `mutation_handoff`. Do not paraphrase or rebuild the target from prose.
- `mutation_outcome`: canonical mutate-phase result for this attempt. Use `status = candidate_generated` when mutate produced a real candidate revision. Use `status = skipped` when mutate intentionally makes no change and persists only the skip result.
- `mutation_outcome.skip_reason_code`: null for `candidate_generated`; required for `skipped`.
- `mutation_outcome.skip_summary`: concise explanation of why no candidate was generated.
- `mutation_outcome.next_recommended_action`: canonical next step after this mutate attempt. Use `phase7_test_phase` only when a real candidate exists. Skip outcomes should point back to mutate / retarget / stop handling instead of test.
- `candidate_skill_revision`: the full candidate revision produced for this experiment.
- `candidate_skill_revision.format`: always `SKILL.md`.
- `candidate_skill_revision.content_type`: always `text/markdown`.
- `candidate_skill_revision.content`: the full revised `SKILL.md` body. This field is required so the mutation artifact carries the candidate revision directly instead of forcing downstream readers to reopen sibling files.
- `reviewer_confirmation_gate`: machine-readable confirmation gate for env-fact mutations such as API endpoints, schemas, and filenames.
- `reviewer_confirmation_gate.required`: true when the candidate edits an externally constrained environment fact; otherwise false.
- `reviewer_confirmation_gate.trigger_kinds[]`: ordered trigger categories such as `api_endpoint`, `schema`, or `filename`.
- `reviewer_confirmation_gate.status`: one of `not_required`, `pending`, `confirmed`, or `rejected`.
- A candidate may not be kept while `reviewer_confirmation_gate.status` is `pending` or `rejected`.
- `version_artifact`: immutable persisted version snapshot for this candidate revision. Use `Skill Version Artifact Schema`.
- `skill_after.md` must exactly mirror `candidate_skill_revision.content` for the same experiment.
- Persist this artifact in the `mutation.md` iteration artifact under `## Mutation Artifact` before scoring or user presentation.
- When `mutation_outcome.status = skipped`, do not write `candidate_skill_revision`, do not write `version_artifact`, do not advance into test, and do not finalize a new experiment record.
- A skip result is still persisted in `mutation.md` as the canonical mutate-phase outcome for that attempt so resume/reporting can distinguish `skipped` from `missing` or `failed`.

### Mutation Test Launch Payload

When mutate finishes persisting the candidate revision, emit a dedicated test-launch payload from that finalized mutate output. This is the canonical mutate-to-test handoff that the test phase consumes before it advances `iteration_state` to `test/ready`.

Persist the payload in `mutation.md` under `## Test Launch Payload`. Resume-time readers should reopen that stored payload through `last_mutation_results_ref`; do not reconstruct test launch inputs from directory scans, free-form prose, or split loaders.

```json
{
  "schema_version": 1,
  "artifact_role": "phase7_mutation_to_test_launch",
  "source_artifact_role": "phase7_mutation_candidate_revision",
  "source_artifact_schema_version": 1,
  "candidate_version": {
    "schema_version": 1,
    "artifact_type": "skill_version_artifact",
    "version_id": "skill_version__run_2026-04-11T09-00-00__exp_003",
    "run_id": "run_2026-04-11T09-00-00",
    "experiment_id": 3,
    "lineage_label": null,
    "parent_version_id": "skill_version__run_2026-04-11T09-00-00__exp_000",
    "root_version_id": "skill_version__run_2026-04-11T09-00-00__exp_000",
    "lineage_depth": 1,
    "lineage_store_path": "skill-versions/lineage.json",
    "artifact_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/",
    "snapshot_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/SKILL.md",
    "snapshot_sha256": "sha256:4b2859d8c0f1f1a9...",
    "source_iteration_path": "runs/run_2026-04-11T09-00-00/iteration_003/",
    "source_mutation_artifact_ref": "runs/run_2026-04-11T09-00-00/iteration_003/mutation.md#version_artifact",
    "created_at": "2026-04-11T09:05:00Z"
  },
  "source_artifact_refs": {
    "source_iteration_path": "runs/run_2026-04-11T09-00-00/iteration_003/",
    "mutation_artifact_ref": "runs/run_2026-04-11T09-00-00/iteration_003/mutation.md#mutation_artifact",
    "candidate_revision_artifact_ref": "runs/run_2026-04-11T09-00-00/iteration_003/mutation.md#candidate_skill_revision",
    "version_artifact_ref": "runs/run_2026-04-11T09-00-00/iteration_003/mutation.md#version_artifact",
    "skill_after_ref": "runs/run_2026-04-11T09-00-00/iteration_003/skill_after.md"
  },
  "eval_artifact_refs": {
    "eval_results_ref": "runs/run_2026-04-11T09-00-00/iteration_003/eval_results.json",
    "mutation_handoff_ref": "runs/run_2026-04-11T09-00-00/iteration_003/eval_results.json#mutation_handoff",
    "decision_breakdown_ref": "runs/run_2026-04-11T09-00-00/iteration_003/eval_results.json#decision_breakdown",
    "input_set_id": "phase4-dev-7f3c91ad",
    "input_set_ref": "input-sets.json#phase4-dev-7f3c91ad",
    "input_ids": [
      "phase4-dev-7f3c91ad-I03",
      "phase4-dev-7f3c91ad-I05"
    ]
  },
  "test_bootstrap_metadata": {
    "run_id": "run_2026-04-11T09-00-00",
    "run_path": "runs/run_2026-04-11T09-00-00/",
    "experiment_id": 3,
    "dataset_split_id": "dev",
    "selected_eval_strategy_id": "pipeline_eval_strategy",
    "active_phase": "test",
    "phase_status": "ready",
    "next_action": "phase7_test_phase",
    "bootstrap_generated_at": "2026-04-11T09:05:00Z"
  }
}
```

- `schema_version`: currently `1` for the mutate-to-test launch contract.
- `artifact_role`: always `phase7_mutation_to_test_launch`.
- `source_artifact_role`: always `phase7_mutation_candidate_revision`.
- `source_artifact_schema_version`: copy the mutation candidate artifact schema version that produced this launch payload.
- `candidate_version`: copy the immutable `version_artifact` object unchanged. Test must execute against this stored snapshot, not against the mutable working copy.
- `source_artifact_refs`: stable references back to the mutate output artifacts that produced the candidate version. Preserve `source_iteration_path`, `mutation_artifact_ref`, `candidate_revision_artifact_ref`, `version_artifact_ref`, and `skill_after_ref`.
- `eval_artifact_refs`: stable references back to the eval-phase artifact that selected the target and froze the replay corpus. Preserve `eval_results_ref`, `mutation_handoff_ref`, `decision_breakdown_ref`, `input_set_id`, `input_set_ref`, and the ordered `input_ids[]`.
- `test_bootstrap_metadata`: explicit bootstrap state for the next phase. Preserve `run_id`, `run_path`, `experiment_id`, `dataset_split_id`, `selected_eval_strategy_id`, `active_phase = test`, `phase_status = ready`, `next_action = phase7_test_phase`, and `bootstrap_generated_at`.
- Do not rebuild `input_ids[]`, `input_set_ref`, or the candidate snapshot path from split manifests, filesystem scans, or free-form mutation notes once this payload has been written.
- Do not emit `## Test Launch Payload` when `mutation_outcome.status = skipped`; skip/no-op outcomes stay in the mutate lane and do not bootstrap test.

---

## Skill Version Artifact Schema

Read when: Phase 7 baseline finalization, Phase 7 step 2a candidate generation, version registry computation, rollback, version comparison, or evaluation-result-store retrieval.

Persist every finalized baseline and every generated mutation candidate as an immutable version artifact under `[workspace]/skill-versions/<version_id>/`. This is the canonical stored `SKILL.md` snapshot for replayable version lineage. The iteration directory remains the forensic run log; `skill-versions/` is the stable per-version archive.

### Storage Rules

- `version_id` is the immutable identifier for one stored skill snapshot. Recommended format: `skill_version__<run_id>__exp_<NNN>`.
- `artifact_path` is always `skill-versions/<version_id>/`.
- `snapshot_path` is always `skill-versions/<version_id>/SKILL.md`.
- `parent_version_id` is null for the Experiment 0 baseline artifact and otherwise points to the active carried-forward baseline artifact that the new candidate mutated from.
- `root_version_id` is the stable lineage root for this snapshot. Experiment 0 points to itself; descendants inherit the root from the source version they mutated from.
- `lineage_depth` is the distance from `root_version_id` in parent-child hops (`0` for the baseline root, `1` for its direct child, and so on).
- `lineage_store_path` is always `skill-versions/lineage.json`. This store records `child_version_ids[]` on parent nodes so lineage history can be queried and traversed without mutating older version directories.
- `snapshot_sha256` is computed from the exact bytes written to `snapshot_path`.
- `created_at` is the write timestamp for the version artifact. Once written, do not mutate or overwrite the artifact directory.
- If `artifact_path` already exists, stop with a collision error instead of rewriting the artifact.
- For mutation experiments, `snapshot_path` must exactly mirror both `mutation.md > Mutation Artifact > candidate_skill_revision.content` and the sibling `skill_after.md` file for that experiment.
- For mutation experiments, `mutation.md` must also persist `## Test Launch Payload` using `Mutation Test Launch Payload` so the test phase can reopen the same candidate version and eval corpus without reconstructing them from scans.
- Carry the stored `version_artifact` object unchanged into `mutation.md`, iteration `eval_results.json`, and the finalized experiment record in `results.json.experiments[]`.
- Update `skill-versions/lineage.json` in the same successful write as `version.json` so the new candidate is recorded as a child of `parent_version_id` and later retrieval can reopen the stored lineage graph directly.
- Derived human-facing labels such as `v0`, `v1`, and `vN` are layered on top of this artifact. Do not use the derived label as the immutable storage key.

### version.json

```json
{
  "schema_version": 1,
  "artifact_type": "skill_version_artifact",
  "version_id": "skill_version__run_2026-04-11T09-00-00__exp_003",
  "run_id": "run_2026-04-11T09-00-00",
  "experiment_id": 3,
  "lineage_label": null,
  "parent_version_id": "skill_version__run_2026-04-11T09-00-00__exp_002",
  "root_version_id": "skill_version__run_2026-04-11T09-00-00__exp_000",
  "lineage_depth": 3,
  "lineage_store_path": "skill-versions/lineage.json",
  "artifact_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/",
  "snapshot_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/SKILL.md",
  "snapshot_sha256": "sha256:4b2859d8c0f1f1a9...",
  "source_iteration_path": "runs/run_2026-04-11T09-00-00/iteration_003/",
  "source_mutation_artifact_ref": "runs/run_2026-04-11T09-00-00/iteration_003/mutation.md#version_artifact",
  "created_at": "2026-04-11T09:05:00Z"
}
```

- `lineage_label`: optional human-facing label if the experiment is already finalized into the derived baseline/keep lineage (`v0`, `v1`, ...). Leave null for unresolved candidate snapshots.
- `source_iteration_path`: iteration directory that produced the artifact.
- `source_mutation_artifact_ref`: null for the Experiment 0 baseline artifact; otherwise points to the mutation artifact that first emitted the candidate revision.

### Retrieval Rule

Whenever a consumer can see both `version_artifact.snapshot_path` and a legacy `skill_snapshot` / `skill_after.md`, prefer `version_artifact.snapshot_path` as the canonical replay target and use the legacy path only as a backward-compatibility fallback for older runs.

## Skill Version Lineage Store Schema

Read when: skill-version persistence, version-history traversal, rollback ancestry checks, or version-to-version comparison tooling.

`skill-versions/lineage.json` is the queryable parent-child index for immutable version artifacts. `version.json` remains immutable per snapshot; the lineage store is the only place that should accumulate `child_version_ids[]` over time.

### lineage.json

```json
{
  "schema_version": 1,
  "artifact_type": "skill_version_lineage_store",
  "artifact_path": "skill-versions/lineage.json",
  "nodes": {
    "skill_version__run_2026-04-11T09-00-00__exp_000": {
      "version_id": "skill_version__run_2026-04-11T09-00-00__exp_000",
      "run_id": "run_2026-04-11T09-00-00",
      "experiment_id": 0,
      "lineage_label": null,
      "parent_version_id": null,
      "child_version_ids": [
        "skill_version__run_2026-04-11T09-00-00__exp_003"
      ],
      "root_version_id": "skill_version__run_2026-04-11T09-00-00__exp_000",
      "lineage_depth": 0,
      "artifact_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_000/",
      "snapshot_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_000/SKILL.md",
      "version_manifest_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_000/version.json",
      "created_at": "2026-04-11T09:00:00Z"
    },
    "skill_version__run_2026-04-11T09-00-00__exp_003": {
      "version_id": "skill_version__run_2026-04-11T09-00-00__exp_003",
      "run_id": "run_2026-04-11T09-00-00",
      "experiment_id": 3,
      "lineage_label": null,
      "parent_version_id": "skill_version__run_2026-04-11T09-00-00__exp_000",
      "child_version_ids": [],
      "root_version_id": "skill_version__run_2026-04-11T09-00-00__exp_000",
      "lineage_depth": 1,
      "artifact_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/",
      "snapshot_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/SKILL.md",
      "version_manifest_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/version.json",
      "created_at": "2026-04-11T09:05:00Z"
    }
  }
}
```

- Every node is keyed by `version_id`.
- `child_version_ids[]` is the canonical traversal surface for descending the lineage tree.
- `parent_version_id` remains the canonical upward pointer.
- Consumers may compute `lineage_path`, `ancestor_version_ids`, and `descendant_version_ids` from this store instead of mutating older `version.json` files.
- If `lineage.json` is missing, recover the current node from `version.json` and rebuild the missing traversal state before returning results to the user.

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

## Contract Example Schema

Read when: Phase 0.5 (Contract Collection) or any phase consuming contract examples.

Each contract example is a JSONL row. Three files in `[workspace]/contract/`:
- `success-examples.jsonl` — 3 rows minimum
- `failure-examples.jsonl` — 3 rows minimum
- `do-not-trigger-examples.jsonl` — 3 rows minimum

### Success Example Row
```json
{
  "id": "success-1",
  "input": "The prompt or context given to the skill",
  "output_shape": {
    "description": "Natural language description of correct output. Required. Used by Phase 5 judges for Pass/Fail criteria.",
    "schema": null
  },
  "actual_output": "A concrete example output written by the author or captured from a real run. Required for success and failure examples."
}
```

### Failure Example Row
```json
{
  "id": "failure-1",
  "input": "The prompt or context given to the skill",
  "output_shape": {
    "description": "What correct output would have looked like",
    "schema": null
  },
  "actual_output": "What the skill actually produced (the bad output)",
  "failure_reason": "What went wrong and why it is unacceptable. Required for failure examples."
}
```

### Do-Not-Trigger Example Row
```json
{
  "id": "dnt-1",
  "input": "An input that looks similar to the skill's domain but should NOT activate it",
  "expected_behavior": "decline | route_elsewhere | ignore"
}
```

Field rules:
- `id`: stable identifier. Format: `success-N`, `failure-N`, `dnt-N`. Used for traceability across phases.
- `output_shape.description`: always required. Natural language. Consumed by Phase 5 agent-as-judge evals.
- `output_shape.schema`: null or JSON Schema object. Auto-generated by Phase 0.5 from description + actual_output. Author confirms or sets null. Consumed by Phase 5 code-based validators.
- `actual_output`: required for success and failure examples. Omitted for do-not-trigger examples.
- `failure_reason`: required for failure examples only.
- `expected_behavior`: required for do-not-trigger examples only.

## Effectiveness Floor Schema

Read when: Phase 1 effectiveness floor evaluation.

### Floor Result
```json
{
  "floor_version": "1.0",
  "evaluated_at": "<ISO-timestamp>",
  "skill_name": "<name>",
  "contract_available": true,
  "overall_status": "pass | concern | fail",
  "dimensions": [
    {
      "id": "activation_quality",
      "name": "Activation Quality",
      "status": "pass | concern | fail",
      "evidence": "One-sentence summary of test result",
      "test_inputs_used": ["success-1", "success-2", "dnt-1", "dnt-2"],
      "details": "Extended explanation if status is concern or fail"
    }
  ],
  "dimension_count": {"pass": 0, "concern": 0, "fail": 0}
}
```

### Dimension Definitions

| ID | Name | Test Method | Pass | Concern | Fail |
|----|------|-------------|------|---------|------|
| `activation_quality` | Activation Quality | Run 3 success examples (should fire) + 3 do-not-trigger examples (should not fire). Score precision + recall on activation. | All correct | 1 misfire or 1 miss | 2+ errors |
| `outcome_quality` | Outcome Quality | Run 3 success examples through skill. Judge output against `output_shape.description`. | All 3 produce acceptable output | 1 marginal output | 2+ failures |
| `robustness` | Robustness | Take 3 success examples, perturb inputs (paraphrase, omit context, add noise). Run perturbed versions. | Output quality holds on 2+ | Quality holds on 1 | All degrade |
| `recovery` | Recovery | Run 3 failure examples. Check if skill surfaces the problem instead of producing confident garbage. | Skill flags or recovers on 2+ | Flags or recovers on 1 | Blindly continues on all |
| `efficiency` | Efficiency | Measure token count and tool-call count on success examples. Compare to the pre-mutation baseline captured in Phase 7 Experiment 0 (`baseline_trials[].trial_metadata` in `results.json`). If no Phase 7 baseline yet, use the raw counts with absolute threshold: 20K tokens / 10 tool calls per success example. | Within 2x of baseline or under 20K tokens/10 calls | 2-3x of baseline or 20-40K tokens | >3x of baseline or >40K tokens |
| `boundary_discipline` | Boundary Discipline | Two-part check. Part A: Run 3 do-not-trigger examples — skill should decline/route/ignore. Part B: Run 3 success examples — skill should NOT produce out-of-scope side effects (e.g., modify files outside its stated scope, call unrelated tools). | Declines all DNT + no side effects | 1 partial activation or minor side effect | Activates on DNT or harmful side effects |

When no contract exists: skip `activation_quality` and `boundary_discipline` (no do-not-trigger examples), run remaining 4 dimensions using Phase 3 traces as proxy inputs. Mark skipped dimensions as `"status": "skipped"`.

### Floor Scoring Rules
- `overall_status = "fail"` if ANY dimension is `fail`
- `overall_status = "concern"` if ANY dimension is `concern` and none are `fail`
- `overall_status = "pass"` if ALL dimensions are `pass`
- Floor result is a **warning**, not a gate. Print result and continue to Phase 2 regardless.

## Domain Eval Config Schema

Read when: Phase 0.5 domain eval setup or Phase 5/7 domain metric scoring.

### config.json
```json
{
  "domain_eval_version": "1.0",
  "metric_name": "ndcg_at_5",
  "metric_display_name": "NDCG@5",
  "threshold_pass": 0.65,
  "threshold_concern": 0.50,
  "weight_multiplier": 2.0,
  "eval_script_path": "domain-eval/eval-metric.py",
  "golden_set_path": "domain-eval/golden-set.jsonl",
  "golden_set_count": 50,
  "suggested_by_autorefine": true,
  "author_confirmed": true,
  "pattern_source": "retrieval_search"
}
```

### golden-set.jsonl row
```json
{
  "id": "golden-1",
  "input": "The query or prompt",
  "expected_output": "The ground-truth output or label",
  "metadata": {}
}
```

Field rules:
- `weight_multiplier`: default 2.0. Applied as a multiplier on the eval's `weight` field in Phase 7 `decision_breakdown.components[]` before the `weighted_points = weight * pass_fail_score` computation. Default 2x chosen so domain ground-truth metrics outrank LLM judges in the weighted average — a domain metric scoring pass has twice the pull of a standard agent-as-judge passing. Authors can override (e.g., 3.0 to dominate, 1.0 to treat as equal-weight) in `config.json`.
- `suggested_by_autorefine`: true if metric was suggested by pattern classification, false if author provided.
- `author_confirmed`: must be true before domain eval runs. Phase 0.5 sets this after author confirmation.
- `eval_script_path`: relative to `[workspace]/`. Script takes input + skill_output + expected_output, returns score 0-1.
- When `golden_set_path` is null or empty: domain eval is disabled, falls back to LLM judges only.

## Domain Adapter Contract Schema

Read when: any phase needs a generic adapter-aware evaluation interface instead of a domain-specific special case.

Each adapter definition must provide one shared contract shape, even when the primary oracle differs by domain.

### adapter contract
```json
{
  "adapter_id": "search_retrieval_v1",
  "skill_family": "search_retrieval",
  "input_schema": {
    "description": "Canonical evaluation input shape for this adapter."
  },
  "output_schema": {
    "description": "Canonical normalized output shape consumed by the primary metric."
  },
  "runner": {
    "description": "How the skill is executed for adapter-aware evaluation."
  },
  "normalizer": {
    "description": "How raw skill output becomes metric-ready normalized output."
  },
  "primary_metric": {
    "metric_name": "ndcg_at_5",
    "description": "The task-truth metric that decides quality for this adapter."
  },
  "secondary_metrics": [
    {
      "metric_name": "explanation_quality",
      "description": "Behavioral or presentation checks that diagnose quality but do not replace the primary oracle."
    }
  ],
  "failure_taxonomy": {
    "description": "Adapter-specific failure buckets used for diagnostics and reporting."
  },
  "gold_source": {
    "type": "labeled_set | executable_checks | reference_outputs | human_review",
    "description": "The evidence source required by the primary oracle."
  },
  "trust_rule": {
    "description": "How dev, holdout, hard-fail conditions, and human review combine for this adapter."
  }
}
```

Field rules:
- `adapter_id`: stable versioned identifier. Use this as the runtime adapter handle.
- `skill_family`: broad adapter family label such as `search_retrieval`, `code_verification`, `structured_extraction`, or `prose_review`.
- `input_schema` and `output_schema`: canonicalize what the evaluator reads and scores. These are adapter contracts, not user-facing output templates.
- `runner`: defines how the skill is invoked for evaluation.
- `normalizer`: defines how raw output is transformed into the `output_schema`.
- `primary_metric`: the primary oracle. This decides task quality for the adapter.
- `secondary_metrics`: diagnostic checks such as explanation quality, formatting, or boundary discipline. These support diagnosis and regression detection but do not replace the primary oracle.
- `gold_source`: the evidence substrate the primary oracle depends on.
- `trust_rule`: the adapter-specific trust policy layered on top of AutoRefine's shared holdout and human-review model.

## Experiment Contract Schema

Read when: starting a bounded mutation/evaluation run or resuming one.

The experiment contract is the shared success definition for one run. The mutation actor and evaluator must both read the same artifact instead of improvising targets from chat history.

### experiment-contract.json
```json
{
  "run_id": "run_2026-04-17T14-30-00",
  "adapter_id": "search_retrieval_v1",
  "objective": "Improve NDCG@5 without regressing boundary or clarity checks.",
  "fixture_refs": ["fixtures-manifest.md#search-fixtures"],
  "primary_metric": {
    "metric_name": "ndcg_at_5",
    "threshold_pass": 0.65
  },
  "secondary_metrics": [
    {
      "metric_name": "explanation_quality",
      "threshold_pass": 0.8
    }
  ],
  "thresholds": {
    "combined_score": 0.8
  },
  "hard_fail_dimensions": [
    "primary_metric_below_threshold",
    "invalid_normalized_output",
    "holdout_leakage"
  ],
  "holdout_policy": {
    "split_id": "adversarial_holdout",
    "mode": "evaluation_only"
  },
  "mutation_scope": {
    "allowed_targets": ["skill-under-test/SKILL.md"]
  },
  "evaluator_inputs": {
    "normalized_output_ref": "runs/run_2026-04-17T14-30-00/iteration_001/eval_results.json"
  }
}
```

Field rules:
- `run_id`: must match `state.json.current_run_id`.
- `adapter_id`: the confirmed adapter for the run. Null means no adapter-aware contract should be written.
- `objective`: concise statement of what quality change the run is trying to achieve.
- `fixture_refs`: the exact fixture/artifact sources this run scores against.
- `primary_metric`: the task-truth metric and its pass threshold.
- `secondary_metrics`: evaluator-side diagnostics that may contribute to score or hard-fail logic.
- `thresholds`: aggregate thresholds used by Phase 7 scoring.
- `hard_fail_dimensions`: any listed failure condition can fail the candidate even when aggregate scores look acceptable.
- `holdout_policy`: run-scoped expression of the shared holdout rule. Mutation-stage callers must never target the holdout directly.
- `mutation_scope`: what the mutation actor may change.
- `evaluator_inputs`: artifact refs the evaluator needs to score the current run consistently.

## Adapter Resolution Rules

Read when: pattern classification suggests an adapter or resume logic restores one from state.

- Pattern classification may suggest an adapter, but suggestion alone is not activation.
- `selected_adapter_id` is null until the author explicitly confirms activation.
- When an adapter is confirmed, runtime state should write `selected_adapter_id` and `adapter_config_path`.
- If required adapter assets are missing, stop and ask the user to either provide the missing assets or explicitly downgrade to the LLM-judge-only path.
- Do not silently downgrade from an active adapter-aware path.

### Search adapter reference

Use this as the first concrete adapter implementation.

```json
{
  "adapter_id": "search_retrieval_v1",
  "skill_family": "search_retrieval",
  "primary_metric_defaults": ["ndcg_at_5", "recall_at_5"],
  "secondary_metric_defaults": [
    "explanation_quality",
    "clarifying_question_quality",
    "boundary_discipline"
  ],
  "normalized_output_shape": {
    "results": [
      {
        "doc_id": "doc_123",
        "rank": 1,
        "title": "Optional title",
        "url": "Optional URL",
        "rationale": "Optional explanation"
      }
    ]
  },
  "failure_taxonomy": [
    "missed_relevant_results",
    "poor_ranking",
    "irrelevant_top_results",
    "over_filtering",
    "explanation_mismatch"
  ]
}
```

Rules:
- `search_retrieval_v1` is the stable search adapter ID.
- The primary oracle scores the ordered `doc_id` sequence, not the prose explanation.
- `ndcg_at_5` is the default display metric. `recall_at_5` is the minimum companion diagnostic.
- Explanation/rationale quality stays secondary; it must not override a failing retrieval metric.

### Minimum viable search gold-set row
```json
{
  "query": "python web framework",
  "doc_id": "doc_123",
  "grade": 2,
  "metadata": {}
}
```

Required fields:
- `query`: the retrieval query being evaluated
- `doc_id`: stable identifier used for ranking metrics
- `grade`: relevance grade consumed by ranking metrics such as `NDCG@k`

Optional fields:
- `metadata`: any extra adapter-specific information needed for replay or diagnostics

## Inferred Contract Template

Read when: Phase 0.5 generates inferred-contract.md from author examples.

### inferred-contract.md format
```markdown
# Inferred Effectiveness Contract

Generated by AutoRefine from 9 author-provided examples. Author-corrected sections marked with [confirmed] or [corrected].

## Intent
[One-sentence skill purpose, inferred from success examples]

## Success Criteria
[Synthesized from success example output shapes — what "done right" looks like]

## Non-Goals
[Inferred from do-not-trigger examples — what the skill should NOT do]

## Must-Catch Failure Modes
[Extracted from failure examples — ranked by severity]

## Trigger Conditions
[Synthesized from success + do-not-trigger examples — when to fire vs stay quiet]

## Domain Metric (if applicable)
[Suggested metric, threshold, and reasoning. Null if not applicable.]

## Evaluation Dimensions
[Which Phase 5 evals map to which contract sections]

## Correction Log
[Author corrections to inferred content, with original vs corrected text]
```

Rules:
- Every section must cite which example IDs informed it (e.g., "Inferred from success-1, success-3").
- Author corrections are recorded in the Correction Log section with `ORIGINAL:` and `CORRECTED:` blocks.
- After author correction, re-derive any dependent sections (e.g., if author corrects Intent, re-check Non-Goals alignment).

## Contract Effectiveness Result Schema

Read when: Session Close generates the Contract Effectiveness Report; dashboard reads `results.json.contract_effectiveness` to render the Contract Coverage card.

Written by Session Close (see `references/gulf3-generalization.md > Contract Effectiveness Report`) at the end of each AutoRefine campaign. Persisted to `results.json.contract_effectiveness`. Consumed by `dashboard.html`.

### results.json.contract_effectiveness

```json
{
  "generated_at": "<ISO-timestamp>",
  "final_version_id": "skill_version__<run_id>__exp_<NNN>",

  "exact_match": {
    "success_examples_pass": 0,
    "success_examples_total": 3,
    "failure_examples_caught": 0,
    "failure_examples_total": 3,
    "trigger_correct_fires": 0,
    "trigger_total_fires": 3,
    "trigger_correct_declines": 0,
    "trigger_total_declines": 3
  },

  "paraphrased": {
    "success_examples_pass": 0,
    "success_examples_total": 6,
    "failure_examples_caught": 0,
    "failure_examples_total": 6,
    "trigger_correct_fires": 0,
    "trigger_total_fires": 6,
    "trigger_correct_declines": 0,
    "trigger_total_declines": 6
  },

  "overfit_analysis": {
    "overfit_ratio": 0.0,
    "overfit_threshold": 0.20,
    "status": "overfit_none | overfit_warning",
    "success_gap_pct": 0.0,
    "failure_gap_pct": 0.0,
    "trigger_gap_pct": 0.0
  },

  "domain_metric": null,

  "efficiency_trend": {
    "baseline_tokens": 0,
    "final_tokens": 0,
    "baseline_tool_calls": 0,
    "final_tool_calls": 0,
    "baseline_experiment_id": "exp_000",
    "final_experiment_id": "exp_NNN"
  },

  "floor_delta": null,

  "leakage_audit": {
    "test_split_matches": 0,
    "holdout_split_matches": 0,
    "longest_match_chars": 0,
    "status": "clean | warning | fail"
  }
}
```

### Field rules

- `generated_at`: ISO-8601 timestamp when the report was written
- `final_version_id`: the `version_id` of the kept winning skill version (from `skill-versions/`)
- **`exact_match`**: results from re-running the final skill on the 9 original contract examples. High scores here combined with low `paraphrased` scores indicate memorization. Diagnostic only.
- **`paraphrased`**: results from re-running on the 18 paraphrase variants (2 per original × 9). This is the honest effectiveness signal.
- **`overfit_analysis`**:
  - `overfit_ratio` = average of `(exact_match_rate - paraphrased_rate)` across success, failure, trigger categories. Range: -1.0 to 1.0. Positive values indicate exact-match outperforms paraphrased.
  - `overfit_threshold`: fixed at 0.20 (20 percentage points). Configurable only for research runs.
  - `status = "overfit_warning"` if `overfit_ratio > overfit_threshold`; else `"overfit_none"`.
  - Individual gap fields (`success_gap_pct`, `failure_gap_pct`, `trigger_gap_pct`) expose per-category gaps for diagnostic display.
- **`domain_metric`**: null when no domain eval configured. When configured, object: `{name: string, continuous_score: float, threshold_pass: float, status: "pass" | "concern" | "fail"}`.
- **`efficiency_trend`**: token/tool-call delta from baseline experiment (`iteration_000`) to final kept experiment. Used for efficiency summary in report and dashboard.
- **`floor_delta`**: null when no Phase 1b floor exists. When populated, array of `{dimension_id, before_status, after_status, changed: bool}` entries — one per dimension that existed at Phase 1b time.
- **`leakage_audit`**: results from scanning the final `SKILL.md` for verbatim matches against test and adversarial_holdout fixture inputs.
  - `test_split_matches`: count of test-fixture strings (>=20 contiguous chars) found in `SKILL.md`
  - `holdout_split_matches`: count of holdout-fixture strings (>=20 contiguous chars) found in `SKILL.md`
  - `longest_match_chars`: length of the longest verbatim match found (across both splits)
  - `status`:
    - `"clean"` if both match counts are 0
    - `"warning"` if 1-2 total matches and `longest_match_chars < 50`
    - `"fail"` if 3+ total matches OR `longest_match_chars >= 50`

### Dashboard consumption

`dashboard.html > renderContract` reads this object to populate the Contract Coverage card. Expected fields for the summary line: `exact_match.success_examples_pass`, `exact_match.failure_examples_caught`, `exact_match.trigger_correct_fires + trigger_correct_declines`, `paraphrased.success_examples_pass`, `overfit_analysis.status`, `domain_metric.name` (when non-null). The efficiency trend table reads `efficiency_trend.baseline_tokens → efficiency_trend.final_tokens` and the tool-call equivalents.

### Missing field handling

When Session Close writes the object but some fields aren't applicable (e.g., no domain eval, no Phase 1b floor), set the missing top-level field to `null` rather than omitting it. The dashboard is tolerant of `null` but not of missing keys — a missing key will cause the render path to crash.

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

Read when: Ambient learning check on resume, or Phase 7 step 2a when the already-hydrated `style_preferences.resolved_preferences_path` needs human-readable wording/evidence.

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

Phase 7 should steer mutation hypotheses from the hydrated `style_preferences` envelope first. Reopen this file only through `style_preferences.resolved_preferences_path` when the human-readable wording/evidence must be shown or cited, and do NOT propose changes that contradict learned preferences.
Whenever mid-session preference detection runs, refresh `state.json.mid_session_preference_signals_path` and `results.json.mid_session_preference_signals_path` to this ledger location so later scan passes, resumes, and exports reopen the same artifact without guessing. When a new rule is confirmed, append it here immediately and keep mirroring the same human-readable artifact path.

---

## Research Intake Stage Contract

Read when: Gulf 2 gate is approved and before Phase 7 starts, or when resuming a run whose `state.json.research_intake.status` is `in_progress`, `completed`, or `partial`.

Purpose: turn external references into mutation-ready, source-cited patterns for the current skill/domain without replacing the existing 7-phase foundation, leaking evaluation holdout data, or confusing reference skills with alternate routing targets.

### Inputs

- `target_skill_path`: workspace-relative path to the skill under test. It must point to a readable `SKILL.md`.
- `target_domain`: one-sentence description of the job this skill is being improved for.
- `selected_skill_pattern` + `selected_eval_strategy_id`: restored from `state.json.phase1_context` so research stays pattern-aware instead of generic.
- `reference_sources[]`: zero or more user-provided references. Each item must declare a stable `source_id`, `source_kind` (`reference_skill`, `design_doc`, `best_practice`, `article`, or `repo`), a readable `location`, and an `analysis_goal`.
- Optional `failure_focus[]`: Phase 1/3/6 findings that the extraction should emphasize.
- Optional `preferences_path`: `[workspace]/preferences.md`, used to reject mutation leads that obviously conflict with captured user preferences.
- Optional `research_intake_overrides`: per-run patch object applied to the default configuration below. Omitted fields inherit defaults; guardrail-breaking overrides fail before any source reads begin.

### Research Intake Configuration Schema

Resolve exactly one `research_intake_config` object before source validation or extraction. This resolved config is the explainable source-selection and retrieval-budget contract for the run.

```yaml
research_intake_config:
  targeting:
    target_skill_path: "[workspace]/skill-under-test/SKILL.md"
    target_domain: "<one-sentence target job>"
    improvement_scope: same_skill_only
    require_phase1_pattern_context: true
    pattern_context_source: state.json.phase1_context
  source_selection:
    selection_mode: explicit_user_curation
    enabled_source_kinds:
      - reference_skill
      - design_doc
      - best_practice
      - article
      - repo
    preferred_source_kinds_by_pattern:
      tool_wrapper: [best_practice, design_doc, article, reference_skill]
      generator: [reference_skill, design_doc, article, repo]
      reviewer: [reference_skill, best_practice, design_doc, article]
      inversion: [design_doc, best_practice, article, reference_skill]
      pipeline: [reference_skill, design_doc, repo, best_practice]
    max_total_sources: 4
    max_sources_per_kind: 2
    require_analysis_goal: true
    dedupe_strategy: normalized_location
    allow_remote_locations: true
    remote_locations_require_explicit_selection: true
  retrieval_limits:
    target_patterns_per_accepted_source: 3-5
    minimum_patterns_per_accepted_source: 1
    max_patterns_per_accepted_source: 5
    max_total_patterns: 12
    max_mutation_leads: 8
    max_failure_focus_items: 5
    require_evidence_locator_per_pattern: true
  overrides:
    merge_strategy: deep_merge_replace_arrays
    precedence:
      - base_defaults
      - pattern_defaults
      - research_intake_overrides
      - per_source_analysis_goal
    immutable_guardrails:
      - improvement_scope stays same_skill_only
      - require_phase1_pattern_context stays true
      - dedupe_strategy stays normalized_location
      - adversarial_holdout remains unreadable
```

Default behavior:
- `targeting` always anchors the run to the current workspace copy plus one explicit target domain. Research Intake improves one skill; reference skills are donors, not alternate routing candidates.
- `source_selection` defaults to explicit user curation with all 5 supported source kinds enabled, but caps the run at 4 total sources and 2 sources from any one kind so weak agents do not drown in reference material.
- `preferred_source_kinds_by_pattern` reorders which source kinds should be prioritized after Phase 1 classification. It is a ranking hint, not a license to skip validation or invent missing sources.
- `retrieval_limits` default to a mutation-ready artifact: aim for 3-5 extracted patterns per accepted source, never exceed 5 from one source, cap the run at 12 total extracted patterns and 8 mutation leads, and keep `failure_focus[]` to at most 5 items.
- Remote URLs are allowed only when they were explicitly selected as reference sources for the run; Research Intake does not auto-discover or crawl new remote sources beyond the user-provided list.

Override behavior:
- Resolve config in this order: base defaults -> pattern defaults -> `research_intake_overrides` -> per-source `analysis_goal`. The resolved object, not the raw override payload, is the contract Phase 6.5 executes.
- Scalar values replace earlier values. Object values merge key-by-key. Arrays replace the earlier array in full so humans can see the final source mix without mentally merging two lists.
- Overrides may narrow the source mix or lower retrieval caps freely. Widening is valid only within hard ceilings: `max_total_sources <= 6`, `max_sources_per_kind <= 3`, `max_patterns_per_accepted_source <= 5`, `max_total_patterns <= 15`, `max_mutation_leads <= 10`, and `max_failure_focus_items <= 5`.
- Any override that changes `improvement_scope`, disables `require_phase1_pattern_context`, weakens `dedupe_strategy`, or opens access to `adversarial_holdout` is invalid. Fail fast with `error_code = invalid_research_intake_config` instead of silently falling back.
- If no override is provided, treat the run as `default_only`. If the pattern-aware ranking changed the resolved source priorities, treat it as `pattern_default_only`. If user input changed the resolved config, treat it as `explicit_override`. Surface that resolution mode in `research-intake.md`.

### External Source Retrieval and Snapshot Requirements

Fetch remote `best_practice`, `article`, and `repo` sources before extraction. When a source `location` resolves to a URL, remote repository blob, or other non-local artifact, Phase 6.5 must first fetch the exact source content into `[workspace]/research-sources/<source_id>/` before extracting patterns. Persist at least one raw snapshot artifact plus one metadata sidecar per fetched source, then perform extraction from that stored snapshot instead of from transient browser state, streamed tool output, or memory.

Required fetched-source metadata:

- `citation_metadata`: preserve `title`, `author_or_org`, `published_at`, `publication_or_site`, `canonical_url`, and `accessed_at`. Unknown fields may be `null` or `unknown`, but the object itself must exist for fetched external sources.
- `retrieval_started_at` + `retrieval_completed_at`: record when the fetch began and when the raw snapshot finished writing. Keep `retrieved_at` as the accepted-source timestamp that downstream readers can treat as "the snapshot is now available."
- `raw_artifact_ref`: workspace-relative pointer to the stored raw artifact. Also preserve `raw_artifact_kind`, `raw_artifact_sha256`, and `raw_artifact_bytes` when those values are available from the fetch path.
- `source_last_modified_at`: copy from HTTP headers, page metadata, repo metadata, or commit metadata when available; otherwise record `null`.

Local `reference_skill` and `design_doc` sources may be read in place or copied into the same snapshot directory when the run needs a frozen copy. Remote retrieval failures are blocking for that source: reject the source explicitly instead of extracting from partial content, a stale browser buffer, or an unfetched placeholder.

### Responsibilities

1. Normalize the target first: confirm the stage is about improving one specific `SKILL.md` and one target domain, not comparing different skills or doing runtime routing.
2. Resolve `research_intake_config` before reading sources. Every later validation and extraction decision must use the resolved targeting, source-selection, and retrieval-limit values instead of ad hoc operator judgment.
3. Validate every reference before extraction. Unsupported or unreadable sources are rejected explicitly; they are never silently ignored.
4. For external `best_practice`, `article`, and `repo` sources, fetch the exact source content into `[workspace]/research-sources/<source_id>/` before extraction. Persist citation metadata, retrieval timestamps, and raw artifact refs so the run can be replayed later.
5. Extract only mutation-relevant patterns. Capture 3-5 evidence-backed patterns per accepted source, not generic summaries.
6. Normalize every persisted finding into the shared research corpus contract: assign a stable `entry_id`, keep `source_kind` as provenance, and choose exactly one canonical `entry_type`.
7. Record why each pattern matters to the current target: every extracted pattern must name its applicability, evidence locator, and expected mutation leverage.
8. Distinguish transferable patterns from local quirks. Reference skills are pattern donors, not gold-standard outputs that Phase 7 must mimic.
9. Preserve transparency for weak agents: the contract must be satisfiable with plain Read/Write/Bash workflows and a human-readable artifact, without requiring subagents or hidden state.
10. Stay off protected evaluation data. Research Intake must never read `adversarial_holdout`, mutation-only scoring outputs, or any other hidden evaluation corpus.

### Outputs

- `[workspace]/research-intake.md`: canonical human-readable artifact for the current run.
- `[workspace]/research-sources/`: per-source snapshot directory for fetched external content and copied frozen source artifacts when the run needs replayable provenance.
- `state.json.research_intake`: stage ledger with `{status, target_skill_path, target_domain, requested_sources, accepted_sources, rejected_sources, completed_at, error_code}`. Accepted-source records must preserve `citation_metadata`, `retrieval_started_at`, `retrieval_completed_at`, and `raw_artifact_ref` whenever a fetched or copied snapshot exists.
- `state.json.research_intake_path`: set to `[workspace]/research-intake.md` only when the artifact is written successfully for the current target.
- `session-log.json` entries for `research_intake_started`, optional per-source `research_source_fetched`, and `research_intake_completed`.

### Research Corpus Normalization Contract

AutoRefine v4.2 preserves the existing filesystem-as-memory foundation. The research corpus is not a new database; it is a read-time normalized view over the artifacts AutoRefine already writes:

- `research-intake.md` contributes external pattern observations and mutation hypotheses.
- `meta-learnings.md` contributes manually promoted cross-campaign rules.
- `preferences.md` contributes confirmed user preference signals.
- prior campaign `results.json` plus version-comparison artifacts contribute reusable case studies.

`source_kind` is an ingestion/provenance field, not the final storage type. Do not store `reference_skill`, `design_doc`, `best_practice`, `article`, or `repo` as the canonical `entry_type`. Normalize every reusable research record into exactly one of:

- `pattern_observation`
- `case_study`
- `meta_learning_rule`
- `preference_signal`
- `mutation_hypothesis`

Comparison guardrail: `case_study` entries may cite version-to-version improvement only when the stored evidence proves same-corpus comparison for that skill lineage. Cross-skill transfer happens through promoted patterns and rules, not by pretending two different skills were directly comparable.

### Corpus Provenance and Attribution Requirements

Every normalized research record must carry enough provenance to answer four human questions without reopening the source:

1. What exact source snapshot produced this entry?
2. Why was that source retrieved for this target skill and run?
3. When was the source observed and when was the normalized entry captured?
4. How do I trace the entry back to the human-readable artifact, session log, and evidence chain?

Required provenance dimensions for every entry:

- `source identity`: capture `source_ref.source_id`, `source_ref.display_name`, `source_ref.location`, `source_ref.canonical_location`, `source_ref.locator`, `source_ref.artifact_kind`, and `source_ref.content_hash`.
- `citation metadata`: capture `source_ref.citation_metadata.title`, `source_ref.citation_metadata.author_or_org`, `source_ref.citation_metadata.published_at`, `source_ref.citation_metadata.publication_or_site`, `source_ref.citation_metadata.canonical_url`, and `source_ref.citation_metadata.accessed_at`.
- `retrieval context`: capture `retrieval_context.retrieval_id`, `retrieval_context.stage`, `retrieval_context.run_path`, `retrieval_context.analysis_goal`, `retrieval_context.retrieved_via`, and `retrieval_context.selection_basis`.
- `timestamps`: preserve both source-observation time and normalization time. `captured_at` remains the normalized-entry timestamp; `source_timestamps.retrieval_started_at`, `source_timestamps.retrieval_completed_at`, `source_timestamps.retrieved_at`, and `source_timestamps.source_observed_at` are required; `source_timestamps.source_last_modified_at` must exist as a field but may be `null` when unavailable.
- `traceability`: capture `traceability.research_artifact_ref`, `traceability.raw_artifact_refs[]`, `traceability.session_log_refs[]`, `traceability.evidence_refs[]`, `traceability.lineage_parent_ids[]`, and `traceability.normalization_note`.

Normalization rule: unknown provenance must be explicit as `null` or `unknown`. Do not omit required attribution fields or silently invent metadata.

### Reference and Exemplar Canonicalization Rules

References and exemplars are upstream input shapes, not extra canonical `entry_type`s. After normalization, downstream phases should branch only on `entry_type` plus the shared metadata envelope, never on raw reference-source kinds or exemplar loader bundle kinds.

Stable identity rules:

- `source_id` is the stable identity for one accepted reference snapshot. Reuse it across every extracted row derived from that source. If `canonical_location` or the stored snapshot `content_hash` changes materially, mint a new `source_id` instead of mutating provenance in place.
- `record_id` from the canonical exemplar loader is the stable exemplar identity. Reuse it when a repository or evaluated-skill exemplar is cited by later research artifacts, case studies, or meta-learning promotion notes.
- `entry_id` is the stable identity for one normalized research finding. Never derive it from transient array position alone; mint a new `entry_id` only when the normalized claim, evidence chain, or applicability envelope materially changes.

Reference canonicalization rules:

- Canonicalize reference sources on `canonical_location` plus the stored snapshot `content_hash`. Keep the original operator-provided `location` for audit, but treat `canonical_location` as the de-duplication key and `content_hash` as the exact-source proof.
- Carry one `retrieval_id` per accepted source snapshot. All entries derived from that snapshot must reuse the same `source_ref` and `retrieval_context` envelope so humans can trace the full family of findings back to one fetch.
- Normalize fetched references from stored artifacts only. Do not compute `source_ref.content_hash`, `citation_metadata.accessed_at`, or `traceability.raw_artifact_refs[]` from live browser state, transient tool output, or memory.

Exemplar canonicalization rules:

- Canonical exemplar inputs come from the loader-native `candidate_skill_record_bundle` / `selected_exemplar_payload` surfaces. Preserve loader-native provenance: `record_id`, `record_kind`, `skill_id`, `version_label`, `source_id`, `source_kind`, `content_hash`, and `performance.source_results_ref` when present.
- Repository exemplars (`record_kind = repository_skill`) normalize into `pattern_observation` unless a human later promotes them into a curated rule. Do not invent a repository-only corpus type.
- Evaluated exemplars (`record_kind = evaluated_skill_version`) may normalize into `case_study` only when the stored evidence proves same-skill lineage and `same_input_set_verified = true`. Otherwise, extract reusable patterns and normalize them as `pattern_observation` instead of treating the exemplar as direct comparison proof.
- When exemplar selection deduplicates records, preserve the chosen `selection.dedupe_strategy` and `selection.dedupe_key` in traceability or index metadata so downstream consumers can replay why one exemplar survived.

### Downstream Normalized Research Corpus View

Downstream phases should consume one normalized bundle rather than reopening raw markdown tables, source snapshots, or exemplar payloads ad hoc:

```json
{
  "schema_version": 1,
  "bundle_type": "normalized_research_corpus",
  "generated_at": "2026-04-11T18:40:00Z",
  "target_context": {
    "skill_pattern": "pipeline",
    "agent_target": "any_skill_md",
    "scenario_target": "individual"
  },
  "entries": [],
  "entry_index": {
    "rc-pattern-autorefine-2026-04-11-001": 0
  },
  "reference_index": [
    {
      "source_id": "source-reference-skill-ship-001",
      "canonical_location": "~/.claude/skills/ship/SKILL.md",
      "entry_ids": ["rc-pattern-autorefine-2026-04-11-001"],
      "raw_artifact_refs": ["research-sources/source-reference-skill-ship-001/source.md"]
    }
  ],
  "exemplar_index": [
    {
      "record_id": "autorefine-v3-keep-004",
      "record_kind": "evaluated_skill_version",
      "normalization_mode": "case_study",
      "entry_ids": ["rc-case-autorefine-2026-04-11-001"]
    }
  ]
}
```

- `entries[]` is the authoritative normalized corpus payload.
- `entry_index` maps stable `entry_id` to array position for weak-agent lookup without reparsing.
- `reference_index[]` groups entries by normalized source snapshot (`source_id` + `canonical_location`).
- `exemplar_index[]` groups entries derived from exemplar records and declares whether the exemplar was reduced to `pattern_observation`, promoted to `case_study`, or mixed across both.
- Downstream consumers should read `entries[]`, `entry_index`, `reference_index[]`, and `exemplar_index[]` from the same normalized view. Do not branch on raw `research-intake.md` tables or the exemplar loader payload once this bundle exists.

### Shared Research Corpus Entry Schema

Every normalized research record must share the following required fields before any type-specific payload is read:

```json
{
  "entry_id": "rc-pattern-autorefine-2026-04-11-001",
  "schema_version": 1,
  "entry_type": "pattern_observation",
  "title": "Explicit exit conditions improve checkpoint fidelity",
  "summary": "A donor skill uses numbered exits at each step, which reduces weak-agent drift in pipeline skills.",
  "source_kind": "reference_skill",
  "source_ref": {
    "source_id": "source-reference-skill-ship-001",
    "location": "~/.claude/skills/ship/SKILL.md",
    "canonical_location": "~/.claude/skills/ship/SKILL.md",
    "locator": "## Phase 7",
    "artifact_kind": "markdown_section",
    "display_name": "ship/SKILL.md",
    "content_hash": "sha256:31d8f4f0c3...",
    "citation_metadata": {
      "title": "ship/SKILL.md",
      "author_or_org": "Surah Li",
      "published_at": null,
      "publication_or_site": "Local skill library",
      "canonical_url": null,
      "accessed_at": "2026-04-11T18:26:10Z"
    }
  },
  "retrieval_context": {
    "retrieval_id": "ri-2026-04-11-source-01",
    "stage": "phase_6_5_research_intake",
    "run_path": "runs/run_2026-04-11T18-25-00/",
    "analysis_goal": "extract pipeline checkpoint and exit-condition patterns",
    "retrieved_via": "read_and_extract",
    "selection_basis": "pattern_default_priority:pipeline"
  },
  "captured_at": "2026-04-11T18:30:00Z",
  "captured_by": {
    "stage": "phase_6_5_research_intake",
    "method": "agent_extracted"
  },
  "source_timestamps": {
    "retrieval_started_at": "2026-04-11T18:26:02Z",
    "retrieval_completed_at": "2026-04-11T18:26:10Z",
    "retrieved_at": "2026-04-11T18:26:10Z",
    "source_observed_at": "2026-04-11T18:26:10Z",
    "source_last_modified_at": null
  },
  "applicability": {
    "skill_patterns": ["pipeline"],
    "agent_targets": ["claude_code", "rovodev", "any_skill_md"],
    "scenario_targets": ["individual", "production"],
    "scope_type": "pattern_family",
    "scope_ref": "pipeline"
  },
  "evidence": [
    {
      "kind": "source_excerpt",
      "source": "research_source",
      "locator": "## Phase 7",
      "excerpt": "Step 3 ends with an explicit exit condition."
    }
  ],
  "confidence": "medium",
  "status": "active",
  "derived_from_entry_ids": [],
  "traceability": {
    "research_artifact_ref": "research-intake.md#accepted-source-source-reference-skill-ship-001",
    "raw_artifact_refs": ["research-sources/source-reference-skill-ship-001/source.md"],
    "session_log_refs": ["session-log.json#research_intake_started-2026-04-11T18:25:00Z"],
    "evidence_refs": [0],
    "lineage_parent_ids": [],
    "normalization_note": "Normalized from Accepted Sources row source-reference-skill-ship-001 and Extracted Pattern row 1."
  },
  "type_payload": {
    "pattern_label": "explicit_exit_conditions",
    "pattern_statement": "Use explicit exit conditions after numbered steps to keep weak agents on track.",
    "transfer_type": "positive_pattern",
    "applicability_reason": "Pipeline skills benefit from explicit stage exits.",
    "mutation_leverage": "Add completion gates to long multi-step instructions.",
    "evidence_reference": {
      "schema_version": 1,
      "source_hash": "sha256:31d8f4f0c3...",
      "source_location": {
        "locator": "## Phase 7",
        "section_id": "phase_7",
        "heading_path": ["Phase 7"]
      },
      "quote": "Step 3 ends with an explicit exit condition.",
      "span": {
        "line_start": 42,
        "line_end": 45,
        "char_start": 812,
        "char_end": 924,
        "byte_start": 812,
        "byte_end": 924,
        "offset_basis": "normalized_text_utf8"
      },
      "retrieval_fingerprint": null
    }
  }
}
```

- `entry_id`: stable corpus identifier. Do not recycle ids across materially different findings.
- `schema_version`: starts at `1` for the normalized research corpus contract.
- `entry_type`: exactly one canonical normalized type. Valid values: `pattern_observation`, `case_study`, `meta_learning_rule`, `preference_signal`, or `mutation_hypothesis`.
- `title` + `summary`: compact human-readable description. Weak agents should understand the record without reopening the source immediately.
- `source_kind`: original ingestion surface, such as `reference_skill`, `design_doc`, `best_practice`, `article`, `repo`, `meta_learning`, `preference_log`, or `prior_campaign`.
- `source_ref`: stable provenance pointer. Required fields: `source_id`, `location`, `canonical_location`, `locator`, `artifact_kind`, `display_name`, `content_hash`, and `citation_metadata`. `location` is the original operator-provided location; `canonical_location` is the normalized de-duplication target.
- `retrieval_context`: why and how this source entered the current run. Required fields: `retrieval_id`, `stage`, `run_path`, `analysis_goal`, `retrieved_via`, and `selection_basis`.
- `captured_at`: when this normalized entry was created.
- `captured_by`: stage + method that produced the entry, for example `phase_6_5_research_intake` + `agent_extracted` or `session_close` + `human_curated`.
- `source_timestamps`: required source-time metadata. `retrieval_started_at`, `retrieval_completed_at`, `retrieved_at`, and `source_observed_at` are required; `source_last_modified_at` may be `null` when the upstream source does not expose it.
- `applicability`: normalized targeting envelope. `skill_patterns[]`, `agent_targets[]`, and `scenario_targets[]` are required so the same corpus can serve both individual and production scenarios without runtime routing. `scope_type` + `scope_ref` describe whether the entry applies to one skill lineage, one pattern family, or the full SKILL.md ecosystem.
- `evidence[]`: structured support for the entry. Reuse the same evidence shape as judge verdicts whenever possible (`kind`, `source`, `locator`, plus optional `excerpt`, `metric`, and `artifact_ref`).
- `confidence`: `high`, `medium`, or `low`.
- `status`: lifecycle flag. Use `candidate`, `active`, `superseded`, or `rejected`.
- `derived_from_entry_ids[]`: upstream corpus entries that informed this one. Use an empty list for first-order observations.
- `traceability`: required back-pointers to the artifact/evidence chain. `research_artifact_ref`, `raw_artifact_refs[]`, and at least one `evidence_refs[]` item are required; `session_log_refs[]` and `lineage_parent_ids[]` preserve replayable lineage, and `normalization_note` explains how the normalized entry was produced from markdown-first artifacts.
- `type_payload`: entry-type-specific extension object. Required fields depend on `entry_type`. For `pattern_observation`, this payload must also preserve a structured `evidence_reference` so humans can trace the extracted pattern back to one precise source span without reopening the raw source first.

### Research Corpus Entry Types

#### `pattern_observation`

Use when one reusable pattern, anti-pattern, or heuristic is extracted from a source artifact.

Required `type_payload` fields:
- `pattern_label`
- `pattern_statement`
- `transfer_type`: `positive_pattern`, `anti_pattern`, or `heuristic`
- `applicability_reason`
- `mutation_leverage`
- `evidence_reference`
- `pattern_type_tactic`
- `pattern_type_structure`
- `pattern_type_heuristic`
- `evidence_reference`: canonical structured pointer to the pattern's primary supporting evidence with
  - `schema_version`
  - `source_hash`
  - `source_location.locator`
  - `source_location.section_id`
  - `source_location.heading_path[]`
  - `quote` or `span`
  - optional `retrieval_fingerprint`
- `span`: when present, preserve `line_start`, `line_end`, `char_start`, `char_end`, `byte_start`, `byte_end`, and `offset_basis`
- `pattern`: canonical nested object with
  - `schema_version`
  - `pattern_label`
  - `pattern_statement`
  - `transfer_type`
  - `applicability_reason`
  - `mutation_leverage`
  - `evidence_reference`
  - `pattern_type_tactic`
  - `pattern_type_structure`
  - `pattern_type_heuristic`

Typical `source_kind`: `reference_skill`, `design_doc`, `best_practice`, `article`, or `repo`.

#### `case_study`

Use when a prior campaign or version comparison contributes reusable evidence about what helped or hurt.

Required `type_payload` fields:
- `campaign_ref`
- `skill_id`
- `version_before`
- `version_after`
- `same_input_set_verified`
- `observed_delta`
- `takeaway`

Guardrail: if `same_input_set_verified = false`, the entry cannot be used as version-comparison proof. It may only be promoted into a looser `pattern_observation` after human review.

#### `meta_learning_rule`

Use when a human promotes a repeatable cross-campaign rule into `meta-learnings.md`.

Required `type_payload` fields:
- `rule_statement`
- `supporting_case_ids`
- `promotion_basis`
- `precedence`
- `review_status`

Use `precedence` to resolve conflicts with lower-trust preference signals. Meta-learning rules outrank ambient and mid-session preferences unless the current user explicitly overrides them in-session.

### meta-learnings.md required sections

`meta-learnings.md` is markdown-first and manually curated so weak agents can read it directly, but every entry must normalize into one `meta_learning_rule` record from the shared research corpus schema.

```markdown
# AutoRefine Meta-Learnings

## Curation Rules
- Manual promotion only.
- One entry per reusable rule.
- Every entry must name its applicability conditions and supporting evidence.

## Entry Template

### ML-<YYYY-MM-DD>-<NNN> | <short title>
- entry_type: meta_learning_rule
- status: candidate | active | superseded | rejected
- learning: <one-sentence reusable insight>
- applicability_conditions:
  - skill_patterns: [tool_wrapper|generator|reviewer|inversion|pipeline]
  - agent_targets: [claude_code|rovodev|any_skill_md]
  - scenario_targets: [individual|production]
  - scope_type: skill_lineage | pattern_family | ecosystem
  - scope_ref: <skill id, pattern id, or any_skill_md>
  - skill_metadata_keywords: [optional metadata phrases from skill id/title/summary/tags/path]
  - objective_keywords: [optional campaign-objective phrases]
  - when_to_apply: <observable conditions>
  - do_not_apply_when: <known exclusions>
- supporting_evidence:
  - case_id: <campaign/version-comparison id>
    source_kind: prior_campaign | reference_skill | meta_learning | best_practice
    source_ref: <path, artifact ref, or URL>
    evidence_locator: <section/lines/experiment/comparison artifact>
    excerpt_or_metric: <quote or numeric delta>
    why_it_supports: <causal link>
- confidence: high | medium | low
- promotion_basis: <why this was promoted>
- precedence: high | medium | low
- review_status: pending | approved | superseded
- supporting_case_ids: [<case-study ids>]
- derived_from_entry_ids: [<research corpus ids>]
- last_reviewed_at: <ISO timestamp>
```

- `learning` is the canonical reusable rule that Phase 7 may consider during mutation design.
- `applicability_conditions` is required. Do not treat a rule as universal unless the scope explicitly says so.
- `skill_metadata_keywords` and `objective_keywords` are optional relevance filters inside `applicability_conditions`. Use them when a rule should only steer campaigns whose target skill metadata or stated objective clearly matches the curated evidence.
- `supporting_evidence` is required. Cite concrete artifacts or metrics, not memory or intuition.
- Prefer at least 2 supporting cases before promoting an entry from `candidate` to `active`.
- `supporting_case_ids` maps directly to `type_payload.supporting_case_ids`.
- `promotion_basis`, `precedence`, and `review_status` map directly to the required `meta_learning_rule` payload.
- Keep superseded or rejected entries in the file with updated status so future runs can understand why a rule lost trust.

### Parsed Meta-Learnings Runtime Schema

Campaign setup does not consume `meta-learnings.md` as raw markdown bullets. After resolving `state.json.meta_learnings_path` (or defaulting to the AutoRefine skill directory copy), parse the document into one in-memory `parsed_meta_learnings` bundle and use that bundle for Phase 7 startup, resume-time context hydration, and mutation steering.

```json
{
  "schema_version": 1,
  "bundle_type": "parsed_meta_learnings",
  "meta_learnings_path": "~/.claude/skills/autorefine/meta-learnings.md",
  "curator_source": "~/.claude/skills/autorefine/meta-learnings.md",
  "curator_version": "sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
  "loaded_at": "2026-04-11T18:30:00Z",
  "load_status": "loaded",
  "target_context": {
    "skill_pattern": "pipeline",
    "agent_target": "claude_code",
    "scenario_target": "individual",
    "scope_type": "skill_lineage",
    "scope_ref": "autorefine",
    "skill_metadata": {
      "skill_id": "autorefine",
      "title": "AutoRefine",
      "summary": "Improve one SKILL.md through staged evaluation and mutation.",
      "tags": ["pipeline", "evaluation", "mutation"]
    },
    "campaign_objective": "Improve mutation-loop reliability without broadening scope."
  },
  "transfer_parameters": {
    "skill_pattern": "pipeline",
    "agent_target": "claude_code",
    "scenario_target": "individual",
    "scope_type": "skill_lineage",
    "scope_ref": "autorefine",
    "campaign_objective": "Improve mutation-loop reliability without broadening scope."
  },
  "entries": [],
  "actionable_entry_ids": ["ML-2026-04-11-001"],
  "historical_entry_ids": ["ML-2026-03-29-001"],
  "blocked_entry_ids": ["ML-2026-04-09-002"],
  "transfer_traceability": {
    "trace_id": "ml-transfer-3f9a2f8d1c4b",
    "transfer_signature": "sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
    "actionable_entry_refs": ["~/.claude/skills/autorefine/meta-learnings.md#ML-2026-04-11-001"],
    "historical_entry_refs": ["~/.claude/skills/autorefine/meta-learnings.md#ML-2026-03-29-001"],
    "blocked_entry_refs": ["~/.claude/skills/autorefine/meta-learnings.md#ML-2026-04-09-002"],
    "filter_refs": [
      "curator_source:~/.claude/skills/autorefine/meta-learnings.md",
      "curator_version:sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
      "transfer_signature:sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
      "skill_pattern:pipeline",
      "agent_target:claude_code",
      "scenario_target:individual",
      "scope_type:skill_lineage",
      "scope_ref:autorefine"
    ]
  }
}
```

- `bundle_type`: fixed discriminator for campaign setup consumers that expect parsed meta-learning input.
- `meta_learnings_path`: resolved source path used for this load.
- `curator_source`: exact curated source document used for this load. In v4.2 this is the resolved `meta-learnings.md` path.
- `curator_version`: deterministic content version for the curated source. Use a stable hash of the source contents so production exports can distinguish one curation snapshot from another.
- `load_status`: `loaded`, `missing`, `parse_failed`, or `empty`.
- `target_context`: the current campaign setup envelope. Match `skill_pattern`, `agent_target`, `scenario_target`, `scope_type`, and `scope_ref` against each entry before applying it. When present, also use `skill_metadata` and `campaign_objective` to enforce optional relevance filters.
- `transfer_parameters`: normalized transfer-target envelope used to decide whether curated learnings apply to this run. Default to the normalized `target_context` fields so filters and exports can reference the exact transfer settings without reparsing the source payload.
- `entries[]`: full parsed entry list. Keep the original curation record visible for humans and resume flows.
- `actionable_entry_ids[]`: precedence-aware ids that campaign setup may actually use as cross-campaign steering input.
- `historical_entry_ids[]`: ids whose entries are retained for transparency but should never steer the current run (`superseded` or `rejected`).
- `blocked_entry_ids[]`: ids that parsed successfully but are not actionable for the current run because of status, review, coarse applicability mismatch, or metadata/objective relevance mismatch.
- `transfer_traceability`: deterministic trace envelope for exports and filters. Preserve `trace_id`, `transfer_signature`, stable entry refs, and `filter_refs[]` so dashboards and production systems can reference the same transfer event without recomputing it differently.
- Only entries with `status = active` and `review_status = approved` may appear in `actionable_entry_ids`.
- When `skill_metadata_keywords` or `objective_keywords` are present, those entries must also pass the current run's normalized metadata/objective relevance filters before they remain actionable.
- `candidate` entries stay visible for humans but are excluded from the actionable list until approved.
- Do not persist this bundle back into `state.json`. Reconstruct it from `meta-learnings.md` whenever campaign setup or resume needs it so the markdown file stays the single source of truth.

### Campaign Bootstrap Meta-Learnings Context

Campaign bootstrap should provide the parsed meta-learnings surface as part of the initial campaign configuration/context. Resolve the source path once, normalize the current campaign target envelope once, then carry the parsed bundle forward in the loaded run context:

```json
{
  "meta_learnings_path": "~/.claude/skills/autorefine/meta-learnings.md",
  "curator_source": "~/.claude/skills/autorefine/meta-learnings.md",
  "curator_version": "sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
  "target_context": {
    "skill_pattern": "pipeline",
    "agent_target": "claude_code",
    "scenario_target": "individual",
    "scope_type": "skill_lineage",
    "scope_ref": "autorefine",
    "campaign_objective": "Improve mutation-loop reliability without broadening scope."
  },
  "transfer_parameters": {
    "skill_pattern": "pipeline",
    "agent_target": "claude_code",
    "scenario_target": "individual",
    "scope_type": "skill_lineage",
    "scope_ref": "autorefine",
    "campaign_objective": "Improve mutation-loop reliability without broadening scope."
  },
  "parsed_meta_learnings": {
    "bundle_type": "parsed_meta_learnings",
    "actionable_entry_ids": ["ML-2026-04-11-001"]
  },
  "transfer_traceability": {
    "trace_id": "ml-transfer-3f9a2f8d1c4b",
    "transfer_signature": "sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
    "actionable_entry_refs": ["~/.claude/skills/autorefine/meta-learnings.md#ML-2026-04-11-001"],
    "filter_refs": [
      "curator_source:~/.claude/skills/autorefine/meta-learnings.md",
      "curator_version:sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
      "transfer_signature:sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
      "skill_pattern:pipeline",
      "agent_target:claude_code",
      "scenario_target:individual",
      "scope_type:skill_lineage",
      "scope_ref:autorefine"
    ]
  }
}
```

- Campaign bootstrap should provide this object as part of the initial campaign configuration/context before Phase 7 mutation design or Session Close resume-time steering begins.
- `meta_learnings_path` is the resolved config input for the current run.
- `curator_source` and `curator_version` are the reporting-grade curation lineage fields that downstream run output exports should carry unchanged.
- `target_context` is the normalized campaign-setup envelope used to evaluate applicability and optional relevance filters.
- `transfer_parameters` is the filter/export-friendly copy of the normalized transfer envelope for this run.
- `parsed_meta_learnings` is the derived runtime context payload reused by Phase 7 and resume flows; downstream steps should read this object instead of re-parsing markdown ad hoc.
- `transfer_traceability` carries the deterministic transfer signature plus filter refs for the current curated-learning selection event.
- Rebuild this object on every start/resume from `state.json.meta_learnings_path` plus the current target context. Do not persist parsed entry payloads back into `state.json`.

### Meta-Learning Reporting Export Surface

When reporting or exporting a run output, preserve the bootstrap envelope under `meta_learning_bootstrap_context` and derive a read-only `meta_learning_filter_index`:

```json
{
  "meta_learning_bootstrap_context": {
    "curator_source": "~/.claude/skills/autorefine/meta-learnings.md",
    "curator_version": "sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
    "transfer_parameters": {
      "skill_pattern": "pipeline",
      "agent_target": "claude_code",
      "scenario_target": "individual",
      "scope_type": "skill_lineage",
      "scope_ref": "autorefine"
    },
    "transfer_traceability": {
      "trace_id": "ml-transfer-3f9a2f8d1c4b",
      "transfer_signature": "sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
      "filter_refs": [
        "curator_source:~/.claude/skills/autorefine/meta-learnings.md",
        "curator_version:sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
        "transfer_signature:sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
        "skill_pattern:pipeline",
        "agent_target:claude_code"
      ]
    }
  },
  "meta_learning_filter_index": {
    "curator_sources": ["~/.claude/skills/autorefine/meta-learnings.md"],
    "curator_versions": ["sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8"],
    "transfer_signatures": ["sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8"],
    "filter_refs": [
      "curator_source:~/.claude/skills/autorefine/meta-learnings.md",
      "curator_version:sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
      "transfer_signature:sha256:4cfeaf2c4e1c69056d0c2d2d17296c3f79e7d08b618f6404fb756b39f5ccefd8",
      "skill_pattern:pipeline",
      "agent_target:claude_code"
    ]
  }
}
```

- `meta_learning_bootstrap_context` is the authoritative run-level envelope. Preserve `curator_source`, `curator_version`, `transfer_parameters`, and `transfer_traceability` unchanged on retrieval.
- `meta_learning_filter_index` is additive and derived. It exists so exports, dashboards, and production filters can reference curator source/version and transfer parameters without reparsing the full bootstrap context.

### Parsed Meta-Learning Entry Schema

Each item in `parsed_meta_learnings.entries[]` must preserve the markdown semantics while exposing a stable in-memory shape for campaign setup:

```json
{
  "entry_id": "ML-2026-04-11-001",
  "title": "Subtractive cleanup after additive streaks",
  "entry_type": "meta_learning_rule",
  "status": "active",
  "learning": "After 3 additive mutations in a row, try one subtractive pass before expanding the skill further.",
  "applicability_conditions": {
    "skill_patterns": ["pipeline"],
    "agent_targets": ["claude_code", "rovodev", "any_skill_md"],
    "scenario_targets": ["individual", "production"],
    "scope_type": "skill_lineage",
    "scope_ref": "autorefine",
    "skill_metadata_keywords": ["mutation", "evaluation"],
    "objective_keywords": ["reliability"],
    "when_to_apply": "The active run has already accepted multiple additive mutations.",
    "do_not_apply_when": "The current baseline is still missing a required capability."
  },
  "supporting_evidence": [],
  "confidence": "medium",
  "promotion_basis": "Observed in two prior AutoRefine campaigns with same-skill deltas.",
  "precedence": "high",
  "review_status": "approved",
  "supporting_case_ids": ["case-ds-trace", "case-ds-review"],
  "derived_from_entry_ids": ["rc-case-ds-trace-001"],
  "last_reviewed_at": "2026-04-11T18:05:00Z",
  "normalized_entry_type": "meta_learning_rule",
  "is_actionable": true,
  "block_reason": null
}
```

- `entry_id`, `title`, `status`, `learning`, `confidence`, `promotion_basis`, `precedence`, `review_status`, `supporting_case_ids[]`, `derived_from_entry_ids[]`, and `last_reviewed_at` map directly from the markdown entry.
- `applicability_conditions` and `supporting_evidence[]` preserve the original curation payload without forcing campaign setup to reopen the markdown file. `skill_metadata_keywords[]` matches against the normalized target skill metadata (`skill_id`, title, summary, tags, and known paths). `objective_keywords[]` matches against the normalized campaign objective text when present.
- `normalized_entry_type`: always `meta_learning_rule` for entries parsed from `meta-learnings.md`; this is the bridge into the shared research corpus schema.
- `is_actionable` is true only when the entry is active, approved, and matches the current `target_context`.
- When `skill_metadata_keywords[]` or `objective_keywords[]` are present, `is_actionable` also requires those optional relevance filters to match the normalized target skill metadata and campaign objective.
- `block_reason`: null when actionable. Otherwise use one of `status_not_active`, `pending_review`, `context_mismatch`, `relevance_mismatch`, or `insufficient_supporting_evidence` so humans can see why a parsed rule was withheld from setup-time steering.

#### `preference_signal`

Use when override behavior or confirmed preferences should influence future mutations.

Required `type_payload` fields:
- `preference_key`
- `preference_value`
- `preference_statement`
- `detected_from`
- `confirmation_state`
- `preference_scope`
- `expiry_policy`

`preference_key` is the stable machine-readable style/direction dimension for the signal. Allowed values:
- Canonical `preference_key` values: `verbosity`, `structure_change`, `mutation_operation`, `section_focus`, `voice_style`, `instruction_density`, `example_density`, or `reference_usage`.
- `verbosity`
- `structure_change`
- `mutation_operation`
- `section_focus`
- `voice_style`
- `instruction_density`
- `example_density`
- `reference_usage`

`preference_value` is the normalized value paired with `preference_key`:
- `verbosity`: `terse`, `balanced`, or `detailed`
- `structure_change`: `preserve`, `allow_local`, or `allow_major`
- `mutation_operation`: `prefer_add`, `prefer_modify`, `prefer_remove`, `avoid_add`, `avoid_modify`, or `avoid_remove`
- `section_focus`: `prefer`, `avoid`, or `deprioritize`; when used, `preference_scope.section_ids[]` must name the targeted `##` sections
- `voice_style`: `instructional`, `descriptive`, or `neutral`
- `instruction_density`: `lighter`, `balanced`, or `heavier`
- `example_density`: `fewer`, `balanced`, or `more`
- `reference_usage`: `inline`, `read_when`, or `minimal`

`detected_from` is a typed provenance object, not a free-form sentence. Required fields:
- `detection_mode`: `ambient_diff`, `mid_session_override_scan`, or `manual_entry`
- `source_kind`: `preferences_md`, `user_override_scan_task`, or `human_confirmation`
- `source_ref`: artifact ref or markdown anchor for the source record
- `support_count`: integer count of supporting signals used to produce the normalized preference
- `normalized_override_entries[]`: replayable supporting override rows. Required and non-empty when `detection_mode = mid_session_override_scan`; otherwise it may be empty
- `confidence_metadata`: aggregate confidence explanation for the normalized preference

Each `normalized_override_entries[]` row must preserve one supporting override in a replayable shape:
- `experiment_id`
- `completed_experiment_slot`
- `source_kind`
- `source_ref`
- `agent_verdict`
- `user_verdict`
- `override_direction`
- `changed_locations[]`
- `mutation_types[]`
- `preference_key`
- `preference_value`
- `source_confidence`
- `confidence_reason`

`confidence_metadata` fields:
- `signal_confidence`: `high`, `medium`, or `low`
- `source_confidence`: `high`, `medium`, or `low`
- `confidence_reason`
- `confirmation_bonus_applied`
- `support_count`

Guardrail: preference signals are local steering input. Do not auto-promote them into cross-campaign rules without human review.

#### `mutation_hypothesis`

Use when research has already been converted into an actionable Phase 7 change candidate.

Required `type_payload` fields:
- `hypothesis_statement`
- `target_section`
- `expected_effect`
- `evaluation_plan`
- `source_entry_ids`

Guardrail: every mutation hypothesis must point back to at least one non-hypothesis corpus entry through `source_entry_ids`.

### research-intake.md required sections

The artifact stays markdown-first for weak agents, but every persisted row below must normalize into the shared research corpus schema on read. At minimum, each extracted pattern becomes one `pattern_observation` entry and each mutation lead becomes one `mutation_hypothesis` entry.

```markdown
# Research Intake

## Target
- Skill: [workspace]/skill-under-test/SKILL.md
- Domain: <one-sentence target job>
- Pattern context: <selected_skill_pattern> via <selected_eval_strategy_id>

## Resolved Config
- resolution_mode: <default_only|pattern_default_only|explicit_override>
- enabled_source_kinds: <ordered list>
- max_total_sources: <N>
- max_sources_per_kind: <N>
- target_patterns_per_accepted_source: 3-5
- max_total_patterns: <N>
- max_mutation_leads: <N>

## Accepted Sources
- source_id: <id> | retrieval_id: <id> | kind: <reference_skill|design_doc|best_practice|article|repo> | location: <path-or-url> | canonical_location: <normalized-path-or-url> | analysis_goal: <goal> | retrieved_at: <ISO timestamp> | retrieval_started_at: <ISO timestamp> | retrieval_completed_at: <ISO timestamp> | snapshot_hash: <sha256-or-version-label> | selection_basis: <why this source was chosen>

## Source Snapshots
- source_id: <id> | raw_artifact_ref: <workspace-relative-path> | raw_artifact_kind: <markdown|html|json|txt|archive> | raw_artifact_sha256: <sha256> | citation_title: <title> | citation_author_or_org: <author-or-org> | citation_published_at: <ISO timestamp|null|unknown> | retrieval_started_at: <ISO timestamp> | retrieval_completed_at: <ISO timestamp>

## Rejected Sources
- source_id: <id> | reason: <duplicate_source|unsupported_source|unreadable_source|no_mutation_relevant_patterns>

## Extracted Patterns
- entry_id: <id> | entry_type: pattern_observation | source_id: <id> | trace_ref: <accepted-source row or anchor>
  pattern_label: <short label>
  applicability: <why it matters to this target skill/domain>
  evidence_reference:
    source_hash: <sha256-or-version-label>
    source_location:
      locator: <path/heading/URL fragment/line cue>
      section_id: <section-id-or-null>
      heading_path: [<heading-1>, <heading-2>]
    quote: <short quote|null>
    span:
      line_start: <N|null>
      line_end: <N|null>
      char_start: <N|null>
      char_end: <N|null>
      byte_start: <N|null>
      byte_end: <N|null>
      offset_basis: <normalized_text_utf8|unknown>
    retrieval_fingerprint: <stable-id|null>
  mutation_leverage: <what kind of mutation it suggests>
  confidence: high | medium | low

## Mutation Leads
- entry_id: <id> | entry_type: mutation_hypothesis | lead_id: <stable id> | derived_from: <source_id/pattern_label> | target_section: <section-or-behavior> | expected_effect: <hypothesis>

## Stage Outcome
- status: completed | partial | skipped | failed
- accepted_sources: <N>
- rejected_sources: <N>
- blocking_reason: <none or error code>
```

- `Accepted Sources` is the minimum attribution surface for normalizing `source_ref`, `retrieval_context`, and `source_timestamps`.
- Each `Extracted Patterns` row must point back to one accepted source through both `source_id` and `trace_ref`, and must include enough evidence detail to populate both `type_payload.evidence_reference` and `traceability.evidence_refs[]`.

### Validation rules

- `target_skill_path` is required and must resolve to a readable `SKILL.md`.
- `target_domain` is required and must be non-empty after trimming.
- `selected_skill_pattern` and `selected_eval_strategy_id` are required. If Phase 1 context is missing, the stage is invalid and must not improvise a generic route.
- Resolve `research_intake_config` before validating sources. If the override merge fails or a guardrail is weakened, stop with `error_code = invalid_research_intake_config`.
- Each reference source must have a unique `source_id`, a supported `source_kind`, and a readable `location`.
- Each accepted source must record `canonical_location`, `retrieved_at`, `snapshot_hash`, and `selection_basis` before it can produce normalized corpus entries.
- Each fetched external source must also record `citation_metadata`, `retrieval_started_at`, `retrieval_completed_at`, and `raw_artifact_ref` before extraction can succeed.
- Only `enabled_source_kinds` from the resolved config may be accepted for this run.
- `max_total_sources` and `max_sources_per_kind` apply after de-duplication. Extra sources beyond those caps must be rejected explicitly instead of being silently dropped.
- De-duplicate sources by normalized location. Keep the first occurrence and record later duplicates under `Rejected Sources`.
- Accept the stage only when at least one source yields at least one evidence-backed extracted pattern.
- Each extracted pattern must include `source_id`, `trace_ref`, `pattern_label`, `applicability`, `evidence_locator`, `mutation_leverage`, and `confidence`.
- Every normalized corpus entry derived from `research-intake.md` must preserve `source_ref`, `retrieval_context`, `source_timestamps`, and `traceability`; missing provenance is a blocking normalization error.
- Target 3-5 extracted patterns per accepted source, require at least 1, and never exceed `max_patterns_per_accepted_source`.
- Total extracted patterns across the run must not exceed `max_total_patterns`. Total mutation leads must not exceed `max_mutation_leads`.
- Trim `failure_focus[]` to `max_failure_focus_items` before extraction; reject extra focus items instead of silently inflating retrieval scope.
- `research-intake.md` is run-scoped: rewrite it from the current inputs instead of merging stale output from another target skill or domain.
- Phase 7 may read `research-intake.md` only when `state.json.research_intake.status` is `completed` or `partial`. `failed` is blocking; `skipped` means continue without research input.

### Failure / Error Handling

- User skips or provides zero sources: write `state.json.research_intake.status = "skipped"`, leave `research_intake_path = null`, log the reason, and continue to Phase 7 with internal analysis only.
- Invalid config or override payload: write `status = "failed"`, keep `research_intake_path = null`, log `invalid_research_intake_config`, and stop before reading sources.
- Unsupported, duplicate, or unreadable sources: reject them per-source, record the rejection reason, and continue only if at least one accepted source remains.
- Remote retrieval fails or writes only a partial snapshot: reject that source with `reason = retrieval_failed`, keep any partial artifact out of `Accepted Sources`, and continue only if at least one accepted source remains.
- Source extraction produces no mutation-relevant evidence-backed patterns: reject that source with `error_code = no_valid_sources` at the source level; do not pad the artifact with generic advice.
- User requested research but every source failed validation or extraction: write `status = "failed"`, preserve the blocking `error_code`, and stop before Phase 7 rather than pretending the mutation loop is research-informed.
- Artifact write failure: write `status = "failed"`, keep `research_intake_path = null`, log `artifact_write_failed`, and stop before Phase 7.

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
| 1 | `design_audit: "complete"`, `skill_pattern`, `phase1_context.selected_skill_pattern` |
| 1 | `design_audit: "complete"`, `skill_pattern`, `phase1_context.selected_skill_pattern`, `phase1_context.selected_eval_strategy_id` |
| 2 | `eval_audit: "complete"` |
| 3 | `traces_reviewed, sampled_trace_ids, sampling_strategy, taxonomy_summary` |
| 4 | `fixture_count, pass_count, fail_count, split_sizes, mutation_stage_split_access_policy` |
| 5 | `code_eval_count, judge_eval_count` |
| 6 | `validation_results` (TPR/TNR per judge) |
| 6.5 | `research_intake.status`, `research_intake.target_skill_path`, `research_intake.target_domain`, `research_intake.requested_sources`, `research_intake.accepted_sources`, `research_intake.rejected_sources`, `research_intake_path` |
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
3. Deserialize `state.json.phase1_context` and `state.json.mutation_stage_split_access_policy` into the loaded run context before routing or resuming later phases.
3. Deserialize `state.json.phase1_context`, `state.json.mutation_stage_split_access_policy`, and `state.json.iteration_state` into the loaded run context before routing or resuming later phases. If `phase1_context.selected_skill_pattern` and/or `phase1_context.selected_eval_strategy_id` exist, restore them unchanged so later phases can read the chosen pattern + resolved strategy from the loaded context. If `phase1_context.selected_skill_pattern` exists, restore it unchanged so later phases can read the chosen pattern from the loaded context. If the restored pattern and `state.json.skill_pattern` differ, treat it as state corruption and rerun Phase 1 Step 0 instead of continuing. If the restored strategy is missing or no longer maps back to the restored pattern through `Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector`, treat it as state corruption and rerun strategy selection before continuing. If split-scoped Phase 7 work is active and `mutation_stage_split_access_policy` is missing, read the same policy from `fixtures-manifest.md` or a stored Phase 4 `evaluation_metadata.config.mutation_stage_split_access_policy` snapshot, restore it into the loaded run context, and stop if the sources disagree. If `iteration_state` is present, resume from its persisted `next_action` and continue automatic eval->mutate->test->session_close progression until terminal success (`phase_status = "completed"`) or terminal failure (`phase_status = "blocked"`), without manual handoff.
4. Print resume context: "Resuming from checkpoint: {next_action}"
5. Set `checkpoint` to null (clear the checkpoint — it's been consumed). Preserve all non-checkpoint state, including `phase1_context`, when writing the updated `state.json`.
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

This is AutoRefine's explicit "preserves existing value" surface. Regression check is the contract that proves a candidate did not break previously established wins while chasing a new improvement.

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

Read `references.md > Iteration Run Record Schema` first when Phase 7 starts. The run record is the single-run metadata envelope created before any `iteration_000/` baseline artifacts exist; the iteration directory then stores per-experiment artifacts underneath that run.

## Iteration Run Record Schema

Read when: Phase 7 start, loop-back re-entry, or resume-time reopening of the active mutation run.

Create exactly one run record for each Phase 7 start trigger. Do this before Experiment 0 baseline scoring, before writing any `iteration_000/` artifacts, and before proposing mutations. The trigger must never append another run record for later experiments inside the same run.

Treat the same run-start write as the full baseline-in-progress recovery state for the new run. Before baseline scoring starts, set `state.json.current_experiment = 0`, persist `state.json.current_run_id`, persist `state.json.current_run_path`, initialize `state.json.iteration_state` / `results.json.iteration_state` to the eval-running baseline handoff record, initialize the default run-scoped cadence object with `scope_id = `state.json.current_run_path`` when `scope_type = experiment_series`, and clear any stale `state.json.final_only_evaluation` object back to null when it still points at an older run path.

### Storage Contract

- Persist the unique active run ID in `state.json.current_run_id`.
- Persist the run directory path in `state.json.current_run_path`.
- Persist the active baseline slot with `state.json.current_experiment = 0` before any `iteration_000/` artifacts exist.
- Persist the eval-running runner handoff in `state.json.iteration_state` and `results.json.iteration_state` before baseline scoring starts.
- When `iteration_000/eval_results.json` is written, update the same `iteration_state` object to the mutate-ready handoff for the same `run_id` / `run_path` instead of opening a second run.
- When `iteration_<NNN>/mutation.md` is written for a completed mutate phase that generated a candidate, update the same `iteration_state` object with `last_mutation_status`, `last_mutation_results_ref`, and a test-ready handoff (`active_phase = "test"`, `phase_status = "ready"`, `next_action = "phase7_test_phase"`) for the same `run_id` / `run_path`.
- When `iteration_<NNN>/mutation.md` is written for a skip/no-op mutate phase, update the same `iteration_state` object with `last_mutation_status = "skipped"` and `last_mutation_results_ref`, but do not advance into test, do not finalize the experiment, and do not alter `completion_cadence`.
- When test-phase validation completes for that experiment, update the same `iteration_state` object to a Session Close-ready handoff (`active_phase = "session_close"`, `phase_status = "ready"`, `next_action = "phase7_session_close"`) for the same `run_id` / `run_path`.
- Session Close completion must set terminal `iteration_state` on the same run: success writes `phase_status = "completed"` with `next_action = null`; unrecoverable closeout failure writes `phase_status = "blocked"` with `next_action = null`.
- Append the full run record to `results.json.iteration_runs[]`.
- Append one `session-log.json` entry of type `iteration_run_started`.

### Unique ID Rule

- `run_id` must be unique within the workspace.
- Default format: reuse the run-directory slug exactly: `run_YYYY-MM-DDTHH-MM-SS`.
- `run_path` must be `runs/<run_id>/`.

### Target Skill/Version Link Rule

- `target_skill.skill_path` points to the working-copy skill file that Phase 7 will evaluate: `skill-under-test/SKILL.md`.
- `target_version.snapshot_path` points to the same working-copy file path because that exact file is the baseline-evaluation input at run start.
- `target_version.snapshot_sha256` is computed from the exact working-copy skill file contents at trigger time so production systems can distinguish versions even before a keep/discard decision exists.
- `target_version.evaluation_label` is `baseline_candidate` on the first Phase 7 run for a skill, or the derived `vN` label for the latest kept version when a later Phase 7 run re-enters with an already-kept working baseline.
- `target_version.source_experiment_id` is null when `evaluation_label = baseline_candidate`; otherwise it points to the experiment record that produced the working baseline entering this run.
- `target_version.source_iteration_path` is null when `source_experiment_id` is null; otherwise it points to the iteration directory that produced the carried-forward working baseline.

### Example

```json
{
  "run_id": "run_2026-04-11T09-00-00",
  "trigger": "phase7_iteration_start",
  "started_at": "2026-04-11T09:00:00Z",
  "run_path": "runs/run_2026-04-11T09-00-00/",
  "target_skill": {
    "skill_name": "autorefine",
    "skill_path": "skill-under-test/SKILL.md"
  },
  "target_version": {
    "evaluation_label": "baseline_candidate",
    "source_experiment_id": null,
    "source_iteration_path": null,
    "snapshot_path": "skill-under-test/SKILL.md",
    "snapshot_sha256": "sha256:4b2859d8c0f1f1a9..."
  }
}
```

## Iteration State Schema

Read when: Phase 7 start, baseline finalization, later mutation/test transitions, Session Close completion, or resume-time reopening of the active run.

`iteration_state` is the runner's single-source-of-truth handoff record for whether the active `run_id` is still evaluating, ready for mutate/test/session_close, or has reached terminal success/failure. Persist the same object at the root of both `state.json` and `results.json`.

### Example

```json
{
  "run_id": "run_2026-04-11T09-00-00",
  "run_path": "runs/run_2026-04-11T09-00-00/",
  "experiment_id": 0,
  "active_phase": "mutate",
  "phase_status": "ready",
  "last_eval_status": "completed",
  "last_eval_results_ref": "runs/run_2026-04-11T09-00-00/iteration_000/eval_results.json",
  "next_action": "phase7_mutation_analysis"
}
```

### Rules

- On Phase 7 start, initialize `iteration_state` with `active_phase = "eval"`, `phase_status = "running"`, `experiment_id = 0`, `last_eval_status = null`, `last_eval_results_ref = null`, and `next_action = "phase7_baseline_eval"`.
- When the baseline eval finishes and `iteration_000/eval_results.json` exists, update the same object to `active_phase = "mutate"`, `phase_status = "ready"`, `last_eval_status = "completed"`, `last_eval_results_ref = "runs/.../iteration_000/eval_results.json"`, and `next_action = "phase7_mutation_analysis"`.
- This is the explicit eval-to-mutate handoff for the same run. Do not allocate a new `run_id`, create a second `run_path`, or append another run record just because the phase advanced.
- When later mutation evals finish, overwrite `experiment_id`, `last_eval_status`, and `last_eval_results_ref` for the current `iteration_<NNN>/eval_results.json` while keeping the same run identifiers. Use this record to reopen the newest eval output on resume instead of scanning the filesystem.
- When the mutate phase finishes for the same experiment and produces a candidate, record `last_mutation_status = "completed"` and `last_mutation_results_ref = "runs/.../iteration_<NNN>/mutation.md"`, then advance the same run into a test-ready handoff with `active_phase = "test"`, `phase_status = "ready"`, and `next_action = "phase7_test_phase"`.
- When the mutate phase finishes for the same experiment with `mutation_outcome.status = "skipped"`, record `last_mutation_status = "skipped"` and `last_mutation_results_ref = "runs/.../iteration_<NNN>/mutation.md"`, keep the run in `active_phase = "mutate"`, and continue from `next_action = "phase7_mutation_analysis"` until a real candidate is produced or the loop ends.
- When test-phase validation completes for that experiment, keep the same run identifiers and advance the same object into a Session Close-ready handoff with `active_phase = "session_close"`, `phase_status = "ready"`, and `next_action = "phase7_session_close"`.
- At Session Close completion, write a terminal state on the same object: success sets `active_phase = "session_close"`, `phase_status = "completed"`, `next_action = null`; unrecoverable failure sets `active_phase = "session_close"`, `phase_status = "blocked"`, `next_action = null`.
- Resume/load must continue from the persisted `next_action` while `phase_status` is `running|ready`, and stop handoff progression only when `phase_status` is terminal (`completed|blocked`).

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
~~~markdown
# Experiment N — [mutation description]

## Hypothesis
[Why this change should improve the skill]

## Changes
- [type: added|modified|removed] [location/section]: [1-3 line snippet]

## Mutation Type
[add | modify | delete]

## Mutation Artifact
```json
{
  "schema_version": 1,
  "artifact_role": "phase7_mutation_candidate_revision",
  "source_artifact_role": "phase7_eval_to_mutate_handoff",
  "source_artifact_schema_version": 1,
  "lineage_metadata": {
    "experiment_id": 3,
    "version_label": "v3"
  },
  "selected_mutation_target": {
    "target_id": "target-progressive-disclosure-read-when",
    "target_location": "Progressive Disclosure",
    "recommended_mutation_type": "modify"
  },
  "mutation_outcome": {
    "status": "candidate_generated",
    "skip_reason_code": null,
    "skip_summary": null,
    "next_recommended_action": "phase7_test_phase"
  },
  "candidate_skill_revision": {
    "format": "SKILL.md",
    "content_type": "text/markdown",
    "content": "# AutoRefine\n\nRead when: before expanding the answer, inspect the linked reference section."
  },
  "reviewer_confirmation_gate": {
    "required": false,
    "trigger_kinds": [],
    "status": "not_required",
    "reviewer_id": null,
    "confirmed_at": null,
    "notes": null
  },
  "version_artifact": {
    "version_id": "skill_version__run_2026-04-11T09-00-00__exp_003",
    "snapshot_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/SKILL.md"
  }
}
```

## Test Launch Payload
```json
{
  "schema_version": 1,
  "artifact_role": "phase7_mutation_to_test_launch",
  "candidate_version": {
    "version_id": "skill_version__run_2026-04-11T09-00-00__exp_003",
    "snapshot_path": "skill-versions/skill_version__run_2026-04-11T09-00-00__exp_003/SKILL.md"
  },
  "source_artifact_refs": {
    "mutation_artifact_ref": "runs/run_2026-04-11T09-00-00/iteration_003/mutation.md#mutation_artifact",
    "candidate_revision_artifact_ref": "runs/run_2026-04-11T09-00-00/iteration_003/mutation.md#candidate_skill_revision",
    "version_artifact_ref": "runs/run_2026-04-11T09-00-00/iteration_003/mutation.md#version_artifact",
    "skill_after_ref": "runs/run_2026-04-11T09-00-00/iteration_003/skill_after.md"
  },
  "eval_artifact_refs": {
    "eval_results_ref": "runs/run_2026-04-11T09-00-00/iteration_003/eval_results.json",
    "mutation_handoff_ref": "runs/run_2026-04-11T09-00-00/iteration_003/eval_results.json#mutation_handoff",
    "input_set_ref": "input-sets.json#phase4-dev-7f3c91ad",
    "input_ids": [
      "phase4-dev-7f3c91ad-I03",
      "phase4-dev-7f3c91ad-I05"
    ]
  },
  "test_bootstrap_metadata": {
    "active_phase": "test",
    "phase_status": "ready",
    "next_action": "phase7_test_phase"
  }
}
```
~~~
For baseline (iteration_000):
~~~markdown
# Experiment 0 — Baseline

No mutation applied. This is the initial scoring run.
~~~

**skill_before.md** — Full skill content before mutation was applied.
For baseline: content is `N/A — this is the baseline scoring run.`

**skill_after.md** — Full skill content after mutation (or current skill for baseline). For mutation iterations, `skill_after.md` must exactly mirror `mutation.md > Mutation Artifact > candidate_skill_revision.content`.

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
  "baseline_trials": [
    {
      "trial_index": 1,
      "trial_id": "baseline-trial-001",
      "run_index": 1,
      "score": 72.3,
      "pass_rate": 72.3,
      "timestamps": {
        "started_at": "2026-04-11T09:00:00Z",
        "completed_at": "2026-04-11T09:00:08Z"
      },
      "raw_outputs": [
        {
          "input_id": "phase4-dev-7f3c91ad-I03",
          "output_text": "Trial 1 output for fixture I03"
        }
      ],
      "trial_metadata": {
        "requested_operation": "baseline_scoring",
        "requested_split_id": "dev",
        "input_set_id": "phase4-dev-7f3c91ad",
        "input_set_ref": "input-sets.json#phase4-dev-7f3c91ad",
        "input_ids": ["phase4-dev-7f3c91ad-I03"]
      }
    },
    {
      "trial_index": 2,
      "trial_id": "baseline-trial-002",
      "run_index": 2,
      "score": 75.1,
      "pass_rate": 75.1
    },
    {
      "trial_index": 3,
      "trial_id": "baseline-trial-003",
      "run_index": 3,
      "score": 71.8,
      "pass_rate": 71.8
    }
  ],
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
Fields mirror the experiment record in results.json. `experiment_id` matches the iteration directory number (0 for baseline, 1+ for mutations). `input_set_id` records which stable scoring set this experiment used. `input_set_ref` points directly to the registered set entry, and `input_ids` preserve the exact stable inputs scored in finalized set order. Persist `completion_cadence` here too, using the finalized snapshot copied from the root cadence counter at the moment the experiment becomes final. Persist `requires_human_spot_check` here too, copying the finalized boolean written on the experiment record after the cadence increment instead of recomputing it on load. Every `eval_results[]` entry must preserve `pass_fail`, `reasoning_trace`, `evidence`, `supporting_items`, `weight`, `weight_source`, `weighted_points`, and `normalized_contribution`. `evidence[]` uses `Judge Verdict Evidence Schema` so each verdict can store output/input excerpts, metrics, and artifact references in a uniform shape. `supporting_items[]` uses `Judge Decision Support Schema` so each verdict also records which concrete evidence objects backed each individual sub-decision. Include `decision_breakdown`, `decision_explanation` (with `strongest_outcomes[]`), `mutation_handoff` (with `normalized_evaluation_scores`, `failure_reasons[]`, and `mutation_targets[]`), `regression_check`, and `discard_autopsy` when applicable (null otherwise).

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

## Challenger Mode Configuration Schema

Read when: Phase 7 mutation analysis is about to branch into bounded challenger search for the current experiment.

`challenger_mode` is the Phase 7 candidate-generation contract for the v4.2 research loop. It is not a second promotion system, not a new experiment lineage, and not a trust surface. Its job is to generate bounded candidate revisions on the same trusted dev-scored surface before one shortlisted winner re-enters the existing experiment path.

### Authoritative Home

Persist the configuration for one experiment at:

```text
runs/run_<timestamp>/iteration_<NNN>/challengers/challenger_mode.json
```

- This artifact is the single authoritative home for challenger search configuration for that experiment.
- `state.json`, `results.json`, iteration `eval_results.json`, or dashboard payloads may store refs to this artifact, but must not duplicate the full config payload as a second authoritative copy.
- The challenger config must never store `trust_gate`, holdout rows, or any promotion outcome. Final promotion remains authoritative only in `session_close_holdout/variant_results.json#trust_gate`.

### challenger_mode.json

```json
{
  "schema_version": 1,
  "artifact_type": "challenger_mode_config",
  "run_id": "run_2026-04-12T16-00-00",
  "iteration_id": 4,
  "authoritative_home": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/challenger_mode.json",
  "enabled": true,
  "execution_model": "isolated_pseudo_parallel",
  "execution_backend": "sequential_copy_on_write",
  "lane_count": 3,
  "lane_order": [
    "lane_01_incremental_cleanup",
    "lane_02_simplification",
    "lane_03_from_scratch"
  ],
  "lane_definitions": [
    {
      "lane_id": "lane_01_incremental_cleanup",
      "lane_label": "Incremental Cleanup",
      "lane_type": "incremental_cleanup",
      "candidate_home": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_01_incremental_cleanup/",
      "enabled": true
    },
    {
      "lane_id": "lane_02_simplification",
      "lane_label": "Simplification",
      "lane_type": "simplification",
      "candidate_home": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/",
      "enabled": true
    },
    {
      "lane_id": "lane_03_from_scratch",
      "lane_label": "From Scratch",
      "lane_type": "from_scratch",
      "candidate_home": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_03_from_scratch/",
      "enabled": true
    }
  ],
  "shared_input_surface": {
    "dataset_split_id": "dev",
    "input_set_id": "phase4-dev-7f3c91ad",
    "input_set_ref": "input-sets.json#phase4-dev-7f3c91ad",
    "input_ids": [
      "phase4-dev-7f3c91ad-I03",
      "phase4-dev-7f3c91ad-I05"
    ],
    "baseline_eval_results_ref": "runs/run_2026-04-12T16-00-00/iteration_003/eval_results.json",
    "research_intake_ref": "research-intake.md",
    "meta_learning_context_ref": "parsed_meta_learnings"
  },
  "plateau_breaker": {
    "enabled": true,
    "lane_id": "lane_03_from_scratch",
    "trigger_mode": "in_run_only",
    "trigger_conditions": [
      "no_kept_candidate_in_current_run",
      "repeated_discard_autopsy_classification"
    ]
  },
  "shortlist_policy": {
    "selection_mode": "automatic",
    "approval_model": "reuse_existing_experiment_confirmation_flow",
    "selection_formula": "dev_score_plus_stability",
    "max_shortlist_size": 1
  },
  "lineage_policy": {
    "lane_outputs_are_experiments": false,
    "shortlist_winner_enters_experiment_lineage": true,
    "shortlist_winner_may_create_version_artifact": true,
    "rejected_lanes_remain_lane_local": true
  },
  "promotion_boundary": {
    "mutation_time_surface": "iteration_<NNN>/challengers/shortlist.json",
    "final_promotion_surface": "session_close_holdout/variant_results.json#trust_gate",
    "holdout_access_during_lane_search": "forbidden"
  }
}
```

- `execution_model` is `isolated_pseudo_parallel` for v4.2. Lane logic is logically parallel but operationally isolated.
- `execution_backend` may be `sequential_copy_on_write` for deterministic first-slice execution. True concurrent shared-file mutation is out of scope.
- `lane_count` is fixed at `3` for the v4.2 slice.
- `lane_order` is fixed and explicit for replay.
- `shared_input_surface` is the authoritative statement that all lanes read the same trusted dev-scored surface. Do not attach holdout refs here.
- `plateau_breaker.trigger_mode` must remain `in_run_only` for this slice. Do not trigger from holdout outcomes or cross-run trust behavior.
- `shortlist_policy.selection_mode` is `automatic` for this slice. Do not add a second human gate before the existing experiment confirmation flow.
- `lineage_policy.lane_outputs_are_experiments` must stay `false`. Lane artifacts are candidate-generation artifacts only.
- `promotion_boundary.final_promotion_surface` must always point to the existing holdout artifact's `trust_gate` and must not be redefined anywhere in challenger-mode storage.

## Challenger Lane Artifact Schema

Read when: Phase 7 executes bounded challenger lanes for the current experiment.

Each lane writes into its own copy-on-write directory under the current experiment iteration. Lane artifacts are candidate-generation artifacts only. They do not append directly to `results.json.experiments[]`, they do not create version labels, and they do not enter final promotion unless chosen by the shortlist.

### Authoritative Homes

Per-lane authoritative homes:

```text
runs/run_<timestamp>/iteration_<NNN>/challengers/lane_0N_<lane_type>/
  candidate_SKILL.md
  candidate_revision.json
  lane_eval.json
  lane_summary.md
```

- `candidate_SKILL.md` is the human-readable lane candidate snapshot for that lane only.
- `candidate_revision.json` is the machine-readable canonical lane-candidate payload.
- `lane_eval.json` is the machine-readable lane-local evaluation and shortlist-input payload.
- `lane_summary.md` is a human-readable explanation surface only.
- No lane artifact may write `trust_gate`, mutate `state.json.final_only_evaluation`, or claim promotion.

### candidate_revision.json

```json
{
  "schema_version": 1,
  "artifact_type": "challenger_lane_candidate_revision",
  "run_id": "run_2026-04-12T16-00-00",
  "iteration_id": 4,
  "lane_id": "lane_02_simplification",
  "lane_type": "simplification",
  "candidate_id": "candidate-run_2026-04-12T16-00-00-exp_004-lane_02_simplification",
  "authoritative_home": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/candidate_revision.json",
  "source_candidate_kind": "shared_experiment_input",
  "source_experiment_id": 3,
  "source_eval_results_ref": "runs/run_2026-04-12T16-00-00/iteration_003/eval_results.json",
  "mutation_family": "simplification",
  "plateau_breaker_candidate": false,
  "candidate_skill_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/candidate_SKILL.md",
  "candidate_skill_sha256": "sha256:cbf0d699af9c6d7b...",
  "inputs_used": {
    "input_set_id": "phase4-dev-7f3c91ad",
    "input_set_ref": "input-sets.json#phase4-dev-7f3c91ad",
    "input_ids": [
      "phase4-dev-7f3c91ad-I03",
      "phase4-dev-7f3c91ad-I05"
    ],
    "research_intake_ref": "research-intake.md",
    "meta_learning_context_ref": "parsed_meta_learnings"
  },
  "change_summary": {
    "mutation_type": "modify",
    "changed_sections": [
      "Progressive Disclosure",
      "Mutation Handoff"
    ],
    "hypothesis": "Reduce instruction sprawl while preserving the current trusted phase boundaries."
  }
}
```

### lane_eval.json

```json
{
  "schema_version": 1,
  "artifact_type": "challenger_lane_eval",
  "run_id": "run_2026-04-12T16-00-00",
  "iteration_id": 4,
  "lane_id": "lane_02_simplification",
  "candidate_id": "candidate-run_2026-04-12T16-00-00-exp_004-lane_02_simplification",
  "authoritative_home": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/lane_eval.json",
  "evaluation_surface": {
    "split_id": "dev",
    "input_set_id": "phase4-dev-7f3c91ad",
    "input_set_ref": "input-sets.json#phase4-dev-7f3c91ad",
    "input_ids": [
      "phase4-dev-7f3c91ad-I03",
      "phase4-dev-7f3c91ad-I05"
    ],
    "holdout_used": false
  },
  "selection_metrics": {
    "dev_combined_score_pct": 81.2,
    "baseline_delta_pct": 4.3,
    "stability_signal": "stable",
    "regression_flag": false
  },
  "selection_verdict": {
    "eligible_for_shortlist": true,
    "shortlist_rank": 1,
    "selection_reason": "Highest dev-score gain without regression on the shared dev surface."
  },
  "lineage_boundary": {
    "is_experiment_record": false,
    "is_version_artifact": false,
    "requires_shortlist_win_for_lineage_entry": true
  }
}
```

- Lane-local `selection_metrics` are directional shortlist inputs only. They are not final promotion metrics.
- `evaluation_surface.holdout_used` must always be `false` for lane artifacts.
- `lineage_boundary` makes the experiment/version boundary explicit in the artifact itself so retrieval consumers do not accidentally treat every lane as a first-class experiment.

## Challenger Shortlist Artifact Schema

Read when: Phase 7 finishes lane evaluation and needs one winner to re-enter the existing experiment path.

The shortlist artifact is the only mutation-time machine-readable promotion surface inside challenger mode. It chooses at most one winner and defines how that winner re-enters the normal experiment/version lineage. This artifact does not contain or replace final promotion.

### Authoritative Home

Persist the shortlist artifact at:

```text
runs/run_<timestamp>/iteration_<NNN>/challengers/shortlist.json
```

- This is the single authoritative home for the mutation-time shortlist outcome.
- Only the shortlist winner may be copied into the current experiment's normal mutation artifact and later become a version artifact.
- Rejected lane candidates remain lane-local only and must never be injected directly into `results.json.experiments[]`.

### shortlist.json

```json
{
  "schema_version": 1,
  "artifact_type": "challenger_shortlist",
  "run_id": "run_2026-04-12T16-00-00",
  "iteration_id": 4,
  "authoritative_home": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/shortlist.json",
  "challenger_mode_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/challenger_mode.json",
  "selection_mode": "automatic",
  "selection_formula": "dev_score_plus_stability",
  "selected_lane_id": "lane_02_simplification",
  "selected_candidate_id": "candidate-run_2026-04-12T16-00-00-exp_004-lane_02_simplification",
  "selected_candidate_refs": {
    "candidate_revision_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/candidate_revision.json",
    "lane_eval_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/lane_eval.json",
    "candidate_skill_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/candidate_SKILL.md"
  },
  "ranked_candidates": [
    {
      "lane_id": "lane_02_simplification",
      "candidate_id": "candidate-run_2026-04-12T16-00-00-exp_004-lane_02_simplification",
      "rank": 1,
      "eligible_for_shortlist": true
    },
    {
      "lane_id": "lane_01_incremental_cleanup",
      "candidate_id": "candidate-run_2026-04-12T16-00-00-exp_004-lane_01_incremental_cleanup",
      "rank": 2,
      "eligible_for_shortlist": true
    },
    {
      "lane_id": "lane_03_from_scratch",
      "candidate_id": "candidate-run_2026-04-12T16-00-00-exp_004-lane_03_from_scratch",
      "rank": 3,
      "eligible_for_shortlist": false
    }
  ],
  "lineage_action": {
    "enter_existing_experiment_lineage": true,
    "lineage_entry_scope": "current_experiment_only",
    "may_create_version_artifact_if_kept": true,
    "rejected_candidates_remain_lane_local": true
  },
  "approval_flow": {
    "adds_new_human_gate": false,
    "reuse_existing_experiment_confirmation_flow": true
  },
  "final_promotion_boundary": {
    "final_promotion_surface": "session_close_holdout/variant_results.json#trust_gate",
    "trust_gate_written_here": false
  }
}
```

- `selected_candidate_refs` point to the winner's existing lane-local artifacts. Do not inline those payloads again here.
- `lineage_action.enter_existing_experiment_lineage` means exactly one shortlisted winner may continue as Experiment `N`.
- `approval_flow.adds_new_human_gate` must stay `false` for v4.2. Existing experiment confirmation remains the only human gate before Session Close.
- `final_promotion_boundary.trust_gate_written_here` must stay `false`. `shortlist.json` never becomes a trust artifact.

## Session Close Research-Memory Artifact Schema

Read when: Session Close summarizes what the bounded challenger search learned during the active run.

The research-memory artifact is run-local memory for the active Phase 7 run. It captures what challenger lanes were tried, which mutation families worked or failed, whether the plateau breaker helped, and how the shortlist resolved. It is not a curated cross-campaign rule store and it does not replace `meta-learnings.md`.

### Authoritative Home

Persist the artifact at:

```text
runs/run_<timestamp>/session_close/research-memory.json
```

- This is the single authoritative machine-readable home for run-local challenger research memory.
- Session Close may summarize this artifact elsewhere for humans, but no second machine-readable copy becomes authoritative.
- The artifact must not auto-promote itself into curated cross-campaign learnings. Human curation remains required before any rule enters `meta-learnings.md`.

### research-memory.json

```json
{
  "schema_version": 1,
  "artifact_type": "challenger_research_memory",
  "run_id": "run_2026-04-12T16-00-00",
  "authoritative_home": "runs/run_2026-04-12T16-00-00/session_close/research-memory.json",
  "challenger_mode_run": true,
  "source_shortlist_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/shortlist.json",
  "iterations_with_challenger_mode": [
    4
  ],
  "lane_outcomes": [
    {
      "iteration_id": 4,
      "lane_id": "lane_01_incremental_cleanup",
      "candidate_id": "candidate-run_2026-04-12T16-00-00-exp_004-lane_01_incremental_cleanup",
      "mutation_family": "incremental_cleanup",
      "activation_status": "executed",
      "shortlisted": false,
      "outcome": "rejected",
      "failure_mode": "insufficient_gain",
      "candidate_revision_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_01_incremental_cleanup/candidate_revision.json",
      "lane_eval_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_01_incremental_cleanup/lane_eval.json"
    },
    {
      "iteration_id": 4,
      "lane_id": "lane_02_simplification",
      "candidate_id": "candidate-run_2026-04-12T16-00-00-exp_004-lane_02_simplification",
      "mutation_family": "simplification",
      "activation_status": "executed",
      "shortlisted": true,
      "outcome": "winner",
      "failure_mode": null,
      "candidate_revision_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/candidate_revision.json",
      "lane_eval_ref": "runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/lane_eval.json"
    },
    {
      "iteration_id": 4,
      "lane_id": "lane_03_from_scratch",
      "candidate_id": null,
      "mutation_family": "from_scratch",
      "activation_status": "skipped",
      "shortlisted": false,
      "outcome": "skipped",
      "failure_mode": null,
      "candidate_revision_ref": null,
      "lane_eval_ref": null
    }
  ],
  "plateau_breaker_summary": {
    "triggered": false,
    "trigger_mode": "in_run_only",
    "trigger_reason": null,
    "lane_id": "lane_03_from_scratch",
    "helpfulness": "not_triggered"
  },
  "shortlist_summary": {
    "selected_lane_id": "lane_02_simplification",
    "selected_candidate_id": "candidate-run_2026-04-12T16-00-00-exp_004-lane_02_simplification",
    "selection_mode": "automatic",
    "selection_formula": "dev_score_plus_stability"
  },
  "final_trust_review": {
    "evaluated": true,
    "selected_candidate_experiment_id": 4,
    "trust_gate_outcome": "review_required",
    "dev_gain_survived_final_trust_review": false,
    "holdout_artifact_ref": "runs/run_2026-04-12T16-00-00/session_close_holdout/variant_results.json",
    "reason": "Selected candidate improved the dev score but did not clear final trust promotion."
  },
  "promotion_boundary": {
    "run_local_memory_only": true,
    "auto_promote_to_meta_learnings": false,
    "final_promotion_surface": "session_close_holdout/variant_results.json#trust_gate"
  }
}
```

- `lane_outcomes[]` is the replayable lane-result ledger for the run.
- `lane_outcomes[].activation_status` must record whether a lane executed or was skipped/dormant so replay/reporting does not have to infer lane absence from missing files.
- `failure_mode` should stay compact and machine-readable; prefer bounded reason codes over long prose.
- `plateau_breaker_summary` records the from-scratch challenger effect without turning it into a promotion rule.
- `final_trust_review` records whether the selected candidate's dev gains survived the existing final trust path. This stays run-local memory only; it does not become a second promotion surface.
- `promotion_boundary.auto_promote_to_meta_learnings` must remain `false`.
- `promotion_boundary.final_promotion_surface` makes the trust boundary explicit: research memory may explain the run, but only the existing `trust_gate` decides final promotion.

## Challenger Session-Log Entry Types

Read when: Phase 7 challenger-mode orchestration or Session Close research-memory persistence needs a structured audit event.

Use these additive session-log entry types when v4.2 challenger mode is active:

### `challenger_mode_started`

```json
{"phase":"7","type":"challenger_mode_started","run_id":"run_2026-04-12T16-00-00","iteration_id":4,"config_ref":"runs/run_2026-04-12T16-00-00/iteration_004/challengers/challenger_mode.json","execution_model":"isolated_pseudo_parallel","lane_ids":["lane_01_incremental_cleanup","lane_02_simplification","lane_03_from_scratch"]}
```

### `challenger_lane_completed`

```json
{"phase":"7","type":"challenger_lane_completed","run_id":"run_2026-04-12T16-00-00","iteration_id":4,"lane_id":"lane_02_simplification","candidate_id":"candidate-run_2026-04-12T16-00-00-exp_004-lane_02_simplification","candidate_revision_ref":"runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/candidate_revision.json","lane_eval_ref":"runs/run_2026-04-12T16-00-00/iteration_004/challengers/lane_02_simplification/lane_eval.json","eligible_for_shortlist":true}
```

### `challenger_plateau_breaker_triggered`

```json
{"phase":"7","type":"challenger_plateau_breaker_triggered","run_id":"run_2026-04-12T16-00-00","iteration_id":4,"lane_id":"lane_03_from_scratch","trigger_mode":"in_run_only","trigger_reason":"repeated_discard_autopsy_classification"}
```

### `challenger_shortlist_selected`

```json
{"phase":"7","type":"challenger_shortlist_selected","run_id":"run_2026-04-12T16-00-00","iteration_id":4,"shortlist_ref":"runs/run_2026-04-12T16-00-00/iteration_004/challengers/shortlist.json","selected_lane_id":"lane_02_simplification","selected_candidate_id":"candidate-run_2026-04-12T16-00-00-exp_004-lane_02_simplification","enters_existing_experiment_lineage":true}
```

### `challenger_research_memory_written`

```json
{"phase":"7","type":"challenger_research_memory_written","run_id":"run_2026-04-12T16-00-00","research_memory_ref":"runs/run_2026-04-12T16-00-00/session_close/research-memory.json","auto_promote_to_meta_learnings":false,"final_promotion_surface":"session_close_holdout/variant_results.json#trust_gate"}
```

- These entries are audit events only. They do not replace the authoritative JSON artifacts.
- `challenger_shortlist_selected.enters_existing_experiment_lineage = true` is the session-log mirror of the lineage boundary: only the shortlist winner enters the existing experiment/version path.
- `challenger_research_memory_written.final_promotion_surface` must always point back to the existing holdout artifact's `trust_gate`, not to the new research-memory artifact.

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
Gate all downstream Phase 1 processing on `phase1_context.selected_skill_pattern` being captured for the active run.
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

The version registry is a **derived view** — it is computed on demand from `results.json`, not stored as a separate file. The derived registry assigns human-facing lineage labels (`v0`, `v1`, ...) over finalized baseline/keep experiments, while each underlying experiment still keeps its immutable `version_artifact.version_id` and stored snapshot path. Use `version_artifact.lineage_store_path` plus `skill-versions/lineage.json` whenever the caller needs parent-child traversal rather than the filtered baseline/keep timeline.

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
        version_artifact = exp.get("version_artifact") or {}
        versions.append({
            "version": version_label,
            "version_id": version_artifact.get("version_id"),
            "experiment_id": exp["id"],
            "status": exp["status"],
            "score": exp.get("decision_breakdown", {}).get("combined_score_pct"),
            "description": exp["description"],
            "completion_cadence": exp.get("completion_cadence"),
            "requires_human_spot_check": exp.get("requires_human_spot_check"),
            "iteration_path": f"{run_path}iteration_{exp['id']:03d}/",
            "skill_snapshot": (
                version_artifact.get("snapshot_path")
                or f"{run_path}iteration_{exp['id']:03d}/skill_after.md"
            ),
            "version_artifact": version_artifact or None
        })
```

Carry the stored `completion_cadence` snapshot through the derived view unchanged. This lets dashboards or production consumers read the finalized cadence position for each version without recomputing it from partial run history.
Carry the stored `requires_human_spot_check` flag through the derived view unchanged. Do not recompute it from version index, cadence order, or filtered experiment order.
Carry the stored `version_artifact` object through unchanged when it exists. Do not rebuild `version_id`, `artifact_path`, or `snapshot_sha256` from the derived label or iteration path on the retrieval path.

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

## Final Holdout Variant Runner

Read when: Session Close step 0c.

This is the final evaluation runner for the adversarial holdout split. It reuses the existing variant-evaluation interface; do not invent a second holdout-only scoring path for Session Close.

### Inputs

- Completed variants from `Version Registry Schema` in version order. This means every `baseline` or `keep` experiment, and never `discard`.
- Holdout split metadata from Phase 4 (`split_id = adversarial_holdout`).
- The validated judge bundle already used for Phase 7 scoring.

### Procedure

1. Rebuild the completed variant lineage from `results.json` via `Version Registry Schema`.
2. For each completed variant, load its `skill_snapshot` and run the existing variant-evaluation interface against the holdout split.
3. Preserve the same result shape AutoRefine already uses for versioned evaluations: `input_set_id`, `input_set_ref`, `input_ids`, `score`, `max_score`, `pass_rate`, `final_score`, `evaluation_metadata`, `evaluation_metadata_validation`, `validation_results`, `eval_results`, `decision_breakdown`, and `decision_explanation`.
4. Populate the same per-run score surface (`score`, `max_score`, `pass_rate`, `final_score`) on the structured holdout result row before persistence so downstream comparison, export, and research consumers do not have to reopen the source experiment to recover basic metrics.
5. Do not invent a second holdout-only result schema. The holdout runner exists so version-to-version comparisons can reuse the exact same stored evaluation shape they already inspect elsewhere.
6. Each `variant_results[]` row reuses the existing evaluation record shape, but the ordered collection lives in a dedicated final-holdout artifact instead of mutation-time `results.json` storage.
7. Persist the ordered outputs inside the dedicated final-holdout artifact at `[current_run_path]/session_close_holdout/variant_results.json`.
8. Do not append Session Close holdout outputs to mutation-time `results.json.experiments[]`, iteration `eval_results.json`, or any other mutation-loop record. Those artifacts remain the dev-scored mutation history only.
9. Select the current final candidate using the existing Session Close rule (best kept version, or baseline if nothing was kept), mirror that candidate into `final_only_evaluation.evaluated_experiment_id`, and persist its authoritative final summary in `selected_candidate_summary` (`version`, `experiment_id`, `holdout_score`). Emit dev-side tuning diagnostics in the sibling `optimization_metrics` section with explicit non-authoritative labeling; at minimum store `optimization_metrics.selected_candidate.dev_score` and `optimization_metrics.selected_candidate.holdout_gap`.
10. Do not mirror those machine-readable holdout outputs into top-level state. `state.json.final_only_evaluation` keeps only the idempotence/ref metadata needed to reopen the dedicated artifact on resume.

### Artifact Shape

### session_close_holdout/variant_results.json

```json
{
  "schema_version":1,
  "artifact_type":"final_holdout_results",
  "stage_id": "session_close_holdout_validation",
  "run_path":"runs/run_2026-04-03T14-30-00/",
  "source_results_ref":"results.json",
  "evaluated_experiment_ids":[0,2,4],
  "variant_results": [
    {
      "version": "v0",
      "experiment_id": 0,
      "input_set_id": "phase4-adversarial_holdout-91ab77ce",
      "input_set_ref": "input-sets.json#phase4-adversarial_holdout-91ab77ce",
      "input_ids": ["phase4-adversarial_holdout-91ab77ce-I01"],
      "score": 0.914,
      "max_score": 1.0,
      "pass_rate": 91.4,
      "final_score": 91.4,
      "evaluation_metadata": {},
      "evaluation_metadata_validation": {"status": "valid", "issues": []},
      "validation_results": [
        {
          "eval":"E2",
          "dev_tpr_mean":0.92,
          "dev_tnr_mean":0.86,
          "dev_tpr_range":0.07,
          "dev_tnr_range":0.08,
          "test_tpr":0.89,
          "test_tnr":0.84,
          "aggregated_tpr_tnr_summary": {
            "dev": {
              "tpr_mean":0.92,
              "tpr_range":0.07,
              "tpr_confidence_range": {"lower_bound":0.85,"upper_bound":0.99,"half_width":0.07},
              "tnr_mean":0.86,
              "tnr_range":0.08,
              "tnr_confidence_range": {"lower_bound":0.78,"upper_bound":0.94,"half_width":0.08}
            },
            "test": {"tpr":0.89,"tnr":0.84}
          },
          "status":"APPROVED",
          "phase6_dev_fold_metrics": [
            {"fold_id":"fold_1","metric_object":{"sample_count":5,"human_pass_count":3,"human_fail_count":2,"true_positive_count":3,"true_negative_count":2,"tpr":1.0,"tnr":1.0}},
            {"fold_id":"fold_2","metric_object":{"sample_count":5,"human_pass_count":3,"human_fail_count":2,"true_positive_count":2,"true_negative_count":2,"tpr":0.667,"tnr":1.0}},
            {"fold_id":"fold_3","metric_object":{"sample_count":5,"human_pass_count":2,"human_fail_count":3,"true_positive_count":2,"true_negative_count":2,"tpr":1.0,"tnr":0.667}}
          ]
        }
      ],
      "eval_results": [],
      "decision_breakdown": {},
      "decision_explanation": {}
    }
  ],
  "selected_variant_version": "v2",
  "selected_experiment_id": 4,
  "selected_candidate_summary": {
    "version":"v2",
    "experiment_id":4,
    "holdout_score":0.857
  },
  "trust_gate": {
    "outcome":"review_required",
    "selected_candidate":{"version":"v2","experiment_id":4},
    "holdout_assessment":{
      "holdout_n":7,
      "interpretation_mode":"directional_only",
      "holdout_score":0.857,
      "baseline_holdout_score":0.791,
      "holdout_gap":-0.066,
      "holdout_gap_status":"moderate_gap"
    },
    "noise_assessment":{
      "noise_source":"baseline_trials",
      "combined_score_noise_threshold":0.021,
      "status":"outside_noise"
    },
    "disagreement_assessment":{
      "unresolved_contributing_disagreement":false,
      "unapproved_material_judge":false
    },
    "calibration_assessment":{
      "sample_count":8,
      "false_pass_rate":0.29,
      "false_fail_rate":0.17,
      "status":"review_required"
    },
    "hard_blockers": [
      {"code":"holdout_below_baseline_plus_noise","triggered":false},
      {"code":"unresolved_contributing_disagreement","triggered":false},
      {"code":"unapproved_material_judge","triggered":false},
      {"code":"calibration_block","triggered":false}
    ],
    "advisory_flags": [
      {"code":"directional_only_holdout","triggered":true},
      {"code":"calibration_review_required","triggered":true},
      {"code":"within_noise_floor","triggered":false}
    ]
  },
  "optimization_metrics": {
    "label":"Non-authoritative optimization/tuning metrics",
    "authoritative":false,
    "interpretation":"directional_signal_only",
    "note":"Intermediate tuning metrics are directional only. Use holdout_score for the authoritative final evaluation result.",
    "selected_candidate": {
      "dev_score":0.923,
      "holdout_gap":-0.066
    }
  }
}
```

- `schema_version`: currently `1` for the dedicated final-holdout artifact.
- `artifact_type`: always `final_holdout_results`.
- `status`: run-level artifact resolution state (`completed`, `skipped`, `failed`, or `aborted`).
- `reason`: coarse resolved exit reason for the final-only evaluation run. Use `no_adversarial_holdout_split` for the skip path, or the terminal failure/abort token for failed runs.
- `source_results_ref`: points back to the mutation-time `results.json` lineage that produced the completed variants.
- `evaluated_experiment_ids`: ordered lineage IDs scored in this holdout run. This should match `state.json.final_only_evaluation.evaluated_experiment_ids`.
- `variant_results[]`: ordered per-variant holdout rows. Reuse the existing evaluation record shape here rather than defining a second per-variant schema.
- Write this artifact even when final-only evaluation fails or exits early. In that case `variant_results[]` may be partial or empty, but the artifact is still the canonical machine-readable result for the resolved run.
- `variant_results[]` must persist the full per-run score surface (`score`, `max_score`, `pass_rate`, `final_score`) alongside the rest of the evaluation record so downstream consumers can compare runs without reopening mutation-time experiment rows.
- `variant_results[].validation_results`: preserve the stored Phase 6 judge-validation rows unchanged, including `aggregated_tpr_tnr_summary`, `confusion_matrix`, `confusion_examples`, plus the structured `tpr_confidence_range` / `tnr_confidence_range` objects, so downstream holdout comparison consumers can inspect calibration context without reopening mutation-time records.
- `failure_reasons[]`: structured final-only evaluation failure reasons. Populate this when `status` is `failed` or `aborted`, using rows with `reason_id`, `reason_code`, `stage`, and `summary`. If the runner only surfaced one coarse failure token, synthesize a single `failure_reasons[]` row from `reason` instead of dropping the detail.
- `selected_candidate_summary`: selected final candidate summary derived from the ordered holdout run. Keep this summary authoritative and limited to the final-candidate identity plus `holdout_score`.
- `selected_candidate_summary` is the authoritative final summary and must stay limited to `version`, `experiment_id`, and `holdout_score`.
- `trust_gate`: authoritative final promotion contract for the selected candidate. Downstream consumers must render trust/promotion state from `trust_gate`, not by inferring it from `selected_candidate_summary`, `optimization_metrics`, or top-level state.
- `trust_gate.holdout_assessment.interpretation_mode`: use `directional_only` when `holdout_n < 10`, `decision_grade` when `holdout_n >= 10`.
- `trust_gate.noise_assessment.noise_source`: always `baseline_trials` for v4.1. Do not derive trust-gate noise from a judge-only shortcut or from holdout-only variance.
- `trust_gate.hard_blockers[]`: enumerated blocking conditions. Use `holdout_below_baseline_plus_noise`, `unresolved_contributing_disagreement`, `unapproved_material_judge`, and `calibration_block`.
- `trust_gate.advisory_flags[]`: enumerated non-blocking trust warnings. Use explicit flags such as `directional_only_holdout`, `calibration_review_required`, and `within_noise_floor` so dashboards can render the reason for `review_required` without extra inference.
- Deterministic precedence for `trust_gate.outcome` is `block` > `review_required` > `promote`.
- `holdout_below_baseline_plus_noise` triggers when `holdout_score < baseline_holdout_score`.
- `within_noise_floor` triggers when `holdout_score` does not exceed `baseline_holdout_score + combined_score_noise_threshold`.
- Set `trust_gate.outcome = block` when any `hard_blockers[].triggered = true`.
- Set `trust_gate.outcome = review_required` when zero hard blockers are triggered but one or more `advisory_flags[].triggered = true`.
- Set `trust_gate.outcome = promote` only when zero hard blockers and zero advisory flags are triggered.
- Healthy means `false_pass_rate <= 0.25` and `false_fail_rate <= 0.33`.
- `review_required` calibration means `false_pass_rate > 0.25 and <= 0.40` or `false_fail_rate > 0.33 and <= 0.50`.
- `block` calibration means `false_pass_rate > 0.40` or `false_fail_rate > 0.50` with `sample_count >= 6`.
- If `sample_count < 6`, never emit `calibration_block`; emit `calibration_review_required` instead when the rate thresholds are exceeded.
- `optimization_metrics`: sibling tuning/optimization diagnostics for the same selected candidate. Label this section as non-authoritative and store directional-only metrics such as `selected_candidate.dev_score` and `selected_candidate.holdout_gap` here instead of mixing them into `selected_candidate_summary`.
- `optimization_metrics` is secondary diagnostics only and must not be promoted into `selected_candidate_summary` or `final_score`.
- Keep this artifact separate from mutation-time `results.json.experiments[]` storage. The holdout artifact exists so final validation can be reopened, compared, and audited without polluting the mutation-loop score history.
- Do not mirror `trust_gate` into `state.json.final_only_evaluation`. Top-level state remains the idempotence/ref surface only; the final holdout artifact is the single authoritative home for trust promotion data.

---

## Version Comparison Template

Read when: Phase 7 (after kept mutation, compare vs previous version) or Session Close (compare v0 vs vN).

### Prerequisites

Before rendering a comparison, run the comparison preflight from `Version Comparison Alignment` section. Only proceed if the preflight passes (same `input_set_id`, exact same `input_ids`).

### Per-Input Layout

For each shared-input comparison entry, render two explicitly labeled output panels: `Before` and `After`. Use a consistent two-column side-by-side layout on wider screens, and collapse to a stacked layout on narrow screens while preserving the same `Before` then `After` order. Within those panels, visually highlight only the sections that changed and leave unchanged sections unaccented for quick scanning.

### Baseline-Side Reference

If either comparison side is the Experiment 0 baseline, surface the baseline-side trial collection inline before the shared-input diff. Render it from `left_baseline_trials[]` or `right_baseline_trials[]` and reuse the same serialized `baseline_trials[]` rows from the baseline experiment so the comparison view preserves each pre-mutation run's score, raw outputs, timestamps, run index, and trial metadata.

When the left side is baseline, label the section `Baseline Trial Reference (Before)`. When the right side is baseline, label the section `Baseline Trial Reference (After)`.

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
Shared inputs     1 trusted improved / 1 trusted regressed / 0 unreliable / 3 unchanged
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
| Shared input outcomes | From `shared_input_summary.improved`, `shared_input_summary.regressed`, `shared_input_summary.unreliable`, and `shared_input_summary.unchanged`; counts must sum to `shared_input_summary.total_shared_inputs`, with `improved` / `regressed` reserved for trusted deltas once reliability gating is available |

### Skill Diff

Show a markdown diff of the skill content between versions. Prefer the immutable `version_artifact.snapshot_path` from each derived registry row, falling back to the legacy iteration snapshot only when the version artifact is absent:
- Left: `skill-versions/<left_version_id>/SKILL.md` (fallback: `runs/.../iteration_{left_exp}/skill_after.md`)
- Right: `skill-versions/<right_version_id>/SKILL.md` (fallback: `runs/.../iteration_{right_exp}/skill_after.md`)

Collapse by default — show only on user expansion. Highlight additions, deletions, and modifications.

### When to Show

1. **Phase 7, after kept mutation:** Compare the just-kept version against the previous kept version (or baseline if this is v1). Append to the Aggregation Explainer output.
2. **Session Close:** Compare v0 (baseline) against vN (final kept version). Part of the Version Comparison Summary.
3. **On user request:** "Compare v2 and v4" — compute both versions from the registry and render the template.

---

## External Compatibility Notes

SKILL.md frontmatter is forward-compatible with the SkillClaw superset — Claude Code silently ignores `metadata.skillclaw.*`, `metadata.openclaw.*`, and the optional top-level `category` field. Verified 2026-04-21 via smoke test at `_skillclaw-compat-smoke-test`.

---

## Gulf 1 Trace Record Schema

Canonical JSONL record shape emitted by `autorefine/scripts/record.py` (the trace recorder) and consumed by `autorefine/scripts/records-to-gulf1.py` (the Gulf 1 converter). Schema mirrors SkillClaw's `conversations.jsonl` structure (trimmed — PRM fields are SkillClaw-specific and skipped).

One JSON object per line. Each line represents **one conversational turn** captured from a Claude Code session (or any OpenAI/Anthropic-compatible client) routed through the local recording proxy.

### Required fields

| Field | Type | Description |
|---|---|---|
| `session_id` | string (UUID) | Stable per-recorder-process identifier. All turns captured by one `record.py` process share this ID and are written to one session file. Start one recorder process per live client session when distinct provenance is required. |
| `turn` | integer, 1-indexed | Monotonically-increasing turn counter within a session. First turn = 1. |
| `timestamp` | string (ISO 8601 UTC) | Wall-clock time the recorder received the request, e.g. `"2026-04-21T18:34:56.123Z"`. |
| `messages` | array of `{role, content}` objects | The `messages` array sent by the client in the request body, with credential-like tokens and URL secrets scrubbed by default. Each element has `role` (one of `system`, `user`, `assistant`, `tool`) and `content` (string or array of content blocks). Pass `--raw-records` only for a private, explicitly trusted capture that needs verbatim payloads. |
| `response_text` | string | The assistant's text response for this turn, with credential-like tokens scrubbed by default. If the response was streamed, the recorder concatenates final text deltas. Empty string if the response contained only tool calls and no text. |
| `tool_calls` | array of objects | List of tool invocations the assistant requested in this turn's response, with credential-like tokens scrubbed by default. Each element: `{"id": string, "name": string, "arguments": object}`. Empty array if the turn had no tool calls. |

### Optional fields

| Field | Type | Description |
|---|---|---|
| `skill_hint` | string, optional | If the recorder was started with `--skill <path>`, this field carries the target skill basename by default. Pass `--raw-records` only for a private, explicitly trusted capture that needs the absolute path. Used downstream so Gulf 1 can associate records with a specific skill-under-test. Omitted when no skill was named. |
| `upstream_model` | string, optional | Model identifier from the request (e.g. `"claude-opus-4-7"`). Recorded when present in the incoming request body. |
| `error` | string, optional | If the upstream call failed (network error, 4xx/5xx), populate this with a short description. The turn record is still written so Gulf 1 can see failure modes. Omitted on success. |

### What is NOT included (deliberate non-goals)

- **No PRM scores** (SkillClaw-specific, not used by AutoRefine).
- **No full PII redaction.** Records are local-only and may still contain sensitive conversation content. The recorder scrubs credential-like tokens and URL secrets by default, and `--raw-records` disables even that scrubbing for explicitly trusted private captures.
- **No full HTTP headers.** Only body-level fields above. Authentication headers are never logged.
- **No timing or latency data in v1.** Can be added later if Gulf 1 needs it; out of scope for the initial build.

### File layout

Written to `records/<skill_slug>/<session_id>.jsonl` relative to the current working directory when `record.py` is invoked, with sessions that cannot resolve a skill slug stored under `records/unclassified/<session_id>.jsonl`; files are append-only during a session and finalized on Ctrl-C or process exit. One recorder process corresponds to one trace session; run separate recorder processes when separate client sessions must not share a `session_id`.

### Consumer contract

`records-to-gulf1.py` reads one or more `.jsonl` files and emits Gulf 1 Phase 0.5 Option D input records. It must:

1. Tolerate missing optional fields (`skill_hint`, `upstream_model`, `error`) — treat as absent, not error.
2. Fail loudly (exit non-zero, clear error) if any required field is missing or malformed on any line.
3. Preserve `session_id` + `turn` identity through the conversion so Gulf 1 can cross-reference the original trace when diagnosing a failure mode.

### Example record (one line of a .jsonl file)

```json
{"session_id":"7d2a9f0e-5c4b-4a1b-b9e7-1f3c5d7e9a0b","turn":1,"timestamp":"2026-04-21T18:34:56.123Z","messages":[{"role":"user","content":"Help me debug this React component"}],"response_text":"I'll take a look — can you share the component source?","tool_calls":[],"skill_hint":"SKILL.md","upstream_model":"claude-opus-4-7"}
```
