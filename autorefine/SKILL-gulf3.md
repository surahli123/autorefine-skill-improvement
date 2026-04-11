# AutoRefine — Gulf 3: Generalization

Phase 7 + Session Close. Read when: Gulf 2 gate approved (or Quick Start returning), entering Phase 7 or Session Close.

Downstream phase-entry contract: on entry to Phase 7 or Session Close, initialize pattern-aware context from `state.json.phase1_context.selected_skill_pattern` and `state.json.phase1_context.selected_eval_strategy_id`. Also initialize split-aware context from `state.json.mutation_stage_split_access_policy`. If only the persisted Phase 1 artifact is available, read the same canonical IDs from the top-level `selected_skill_pattern` and `selected_eval_strategy_id` fields in `design-audit.md` and hydrate the loaded run context before scoring, mutation analysis, or version comparison. If only the pattern is available, resolve the missing strategy through `references.md > Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector` before continuing. If the active context does not already hold `mutation_stage_split_access_policy`, read the exact policy from `fixtures-manifest.md` or a stored Phase 4 `evaluation_metadata.config.mutation_stage_split_access_policy` snapshot and hydrate the loaded run context before scoring, mutation analysis, regression checks, version comparison, or any other dataset read. Once restored, route Phase 7 scoring, mutation analysis, and version comparison through the matching strategy row in `references.md > Skill Pattern Eval Strategy > Strategy Definitions`. Treat the restored mutation-stage policy as the active dataset-read gate for baseline scoring, mutation scoring, mutation analysis, regression checks, same-run version comparison, and resume-time dataset reopen. Stop and repair Phase 4 state if the policy is missing, malformed, or disagrees across sources. Do not trigger pattern classification again while entering Gulf 3; rerun Phase 1 Step 0 only if the persisted pattern is missing or mismatched with `state.json.skill_pattern`.

---

## Phase 7: AutoResearch Loop

The Karpathy-style mutation-test-keep/discard cycle. Requires `eval-suite.md` + judges.

**Mode detection (check in this order):**
1. If both `gates.gulf_1` = "approved" AND `gates.gulf_2` = "approved" → **Full mode** (validated evals, confidence-weighted scoring). Budget: ask user — Quick (3), Standard (5), Deep (8-10).
2. Else if `quick_start.completed` = true AND both gates = "pending" → **Mini mode** (bootstrap evals, simplified weighting, directional labeling). Budget: 2-3 experiments.
3. Else → STOP and tell the user to run Standard pipeline first.

**Mini mode differences:** Fresh scoring corpus (5-10 generated inputs, NOT reusing Quick Start traces). Simplified weighting: code evals = 1.0, agent-as-judge = 0.5. All results labeled "directional." No confidence weighting from Phase 6 (evals aren't validated).

**The Loop:**

**Iteration directory (filesystem-as-memory):** At Phase 7 start, create a run directory: `[workspace]/runs/run_<timestamp>/` (timestamp format: `YYYY-MM-DDTHH-MM-SS`). After EACH experiment (including baseline), write 5 artifact files to `[workspace]/runs/run_<timestamp>/iteration_<NNN>/` — see `references.md > Iteration Directory Schema` for file formats. These files survive context compaction and session boundaries, making each experiment independently inspectable on disk. Iteration directories are written in both Full and Mini mode. Store the run directory path in `state.json.current_run_path`. Initialize `state.json.completion_cadence` if needed: default to `{"scope_type":"experiment_series","scope_id":"[current_run_path]","completed_experiments":0,...}` for this Phase 7 run, or reuse a previously chosen `scope_type:"skill"` counter if the campaign intentionally tracks cadence across multiple runs of the same skill. Log each write to session-log: `{"phase":"7","type":"iteration_write","experiment":N,"path":"runs/run_.../iteration_NNN/"}`.

1. Before Experiment 0 and every later Phase 7 dataset read, load the active `mutation_stage_split_access_policy` from the run context and enforce `references.md > Mutation-Stage Split Access Policy`: allowed split ids = `dev` only for baseline scoring, mutation scoring, mutation analysis, regression checks, and same-run version comparison. `train`, `test`, and `adversarial_holdout` are inaccessible during mutation-time operations. Reject the read if the requested operation is absent from `allowed_operations` or if the requested split is not in `allowed_split_ids`. Run baseline on the dev split fixtures only, score against all evals → Experiment 0. Record the active `input_set_id`, the exact `input_set_ref` (`input-sets.json#<set_id>`), and the finalized-order `input_ids` scored in this run with the experiment so later comparisons can prove they used the same scoring corpus and the same source inputs. `adversarial_holdout` is not part of the mutation loop scoring corpus; keep it hidden until Session Close evaluation-only validation. Record `eval_results` per eval, and require each decision to carry `pass_fail`, `reasoning_trace`, a structured `evidence` array, `supporting_items`, `weight`, `weight_source`, `weighted_points`, and `normalized_contribution`. `reasoning_trace` must be populated for every verdict as a concise, ordered explanation: `1) check the criterion`, `2) cite the concrete evidence`, `3) connect that evidence to the final Pass/Fail`. `evidence` must be a structured `evidence` array of objects (see `references.md > Judge Verdict Evidence Schema`). Required fields: kind, source, locator. Optional fields: `excerpt`, `metric`, or `artifact_ref`. `supporting_items` must capture the concrete intermediate judgment calls behind the verdict (see `references.md > Judge Decision Support Schema`). Each supporting item records the sub-decision, its local outcome, and `evidence_refs` pointing to the exact `evidence[]` objects used for that step. Roll these into a `decision_breakdown` object with `components` (ordered aggregation inputs for every eval used in the keep/discard math), `formula`, `weighted_points`, `total_weight`, `combined_score`, `combined_score_pct`, `threshold`, and `proposed_decision` (`baseline` for Experiment 0). Then derive `decision_explanation` from that `decision_breakdown`: store the final decision, a concise mixed-signal summary, and the strongest contributing eval outcomes with their impact on the final keep/discard. When both keep-supporting and discard-supporting signals exist, preserve one of each polarity and explain why the result still stayed keep or discard. **Canonical heading parse:** parse the target skill's `##` headings into a list of section names. Log to session-log: `{"phase":"7","type":"canonical_headings","sections":["heading1","heading2",...]}`. This list is the denominator for `diversity_score` in the derived mutation registry (see `references.md > Derived Mutation Registry`). **Write baseline iteration artifacts** to `iteration_000/`. Once those artifacts exist, baseline is finalized: increment `state.json.completion_cadence.completed_experiments` exactly once, set `requires_human_spot_check = true` iff the updated `state.json.completion_cadence.completed_experiments` value is divisible by 3 (every 3rd completed experiment; otherwise false), copy the updated cadence snapshot into the root of `results.json`, copy the same finalized cadence snapshot plus `requires_human_spot_check` into Experiment 0, and append a `session-log.json` entry of type `completion_cadence`. If `requires_human_spot_check` is true, resolve the current `evaluation_metadata.config.human_spot_check_calibration.sample_count` (default `2`, validation `>= 1`) and queue `[workspace]/checkpoint-tasks/exp0-human-spot-check.json` using `references.md > Human Spot-Check Task Schema` so the checkpoint pause carries the exact `sample_count` instead of recomputing it later.
2. LOOP:
   a. Analyze failures → hypothesize ONE change. If `[workspace]/preferences.md` exists, read it first — do NOT propose mutations that contradict learned user preferences. Read the current run's `selected_eval_strategy_id` in `references.md > Skill Pattern Eval Strategy > Strategy Definitions`. Use that strategy route as the canonical mutation path instead of generic edits. **Read prior iteration decisions** from the current run directory (`decision.md` files in the current run directory — path from `state.json.current_run_path`) for full keep/discard reasoning that survives context compaction. **If recent experiments were discarded, read their `discard_autopsy` classification** — avoid same target if `wrong_target`, try different params if `wrong_params`, try different mutation type (add<->delete<->modify) if `wrong_type`. **Check search diversity:** compute the derived mutation registry (see `references.md > Derived Mutation Registry`). If `diversity_score < 0.5`, prioritize unexplored sections. Log the snapshot to session-log. **Save backup** (`[workspace]/<skill>-optimized-prev.md`) → mutate a copy
   b. **Score mutation (with bias reduction for agent-as-judge evals):** Before reading fixture content or scored inputs for this experiment, re-apply the active `mutation_stage_split_access_policy` with requested operation = `mutation_scoring`; do not materialize blocked splits while scoring.
      - For **code-based evals**: run directly (deterministic, no bias risk).
      - For **agent-as-judge evals**: the agent that hypothesized the mutation is biased toward finding it improved. Reduce this bias using the strongest available mechanism:

        **Tier 1 — Subagent dispatch (strong isolation, use when available):**
        Write `[workspace]/eval-tasks/exp{N}-E{M}.md` containing ONLY: the judge prompt (from `judges/`), the fixture input, and the skill output to evaluate (the mutated output — judge scores ONE output per invocation, same format as Phase 6 validation). Do NOT include: baseline output, mutation hypothesis, or Phase 1-3 findings. Dispatch a subagent with ONLY this file as input. Subagent produces Critique + Pass/Fail. Parent reads the verdict.

        **Fork economics (Tier 1 only):** When dispatching eval subagents, omit `subagent_type` to trigger a fork instead of a spawn. The fork inherits the parent's cached prompt prefix — judge prompts, fixtures, and workspace context are already loaded. Only the eval-task file content differs per experiment. This means each eval subagent pays cache price (1/10) for the shared prefix and full price only for the new eval-task content (~500 tokens). With 5 agent-as-judge evals across 5 experiments = 25 dispatches, fork saves ~80% vs spawn. If fork is unavailable (in-house agent), fall back to Tier 2.

        **Tier 2 — Behavioral instruction (bias reduction, for Read/Write/Bash-only agents):**
        If subagent dispatch is unavailable: score each agent-as-judge eval by reading ONLY the judge prompt file and the skill output. Before scoring, explicitly state: "I am now evaluating this output against the rubric only. I am disregarding my prior reasoning about why this mutation was made." This is a *heuristic* that reduces but does not eliminate self-certification bias.

        Keep eval-task files in `[workspace]/eval-tasks/` for debugging (clean up at Session Close, not per-eval). Record `eval_results` per eval, preserving the final `pass_fail`, full `reasoning_trace`, the structured `evidence` array, and `supporting_items` for every verdict, alongside `weight`, `weight_source`, `weighted_points`, and `normalized_contribution`. Build `evidence[]` using the `Judge Verdict Evidence Schema` so each verdict carries stable `kind`, `source`, and `locator` fields plus any needed excerpt, metric, or artifact metadata. Build `supporting_items[]` using the `Judge Decision Support Schema` so every material judgment call is captured separately with its own outcome and `evidence_refs` back to the exact evidence objects that supported it. Whether the verdict came from Tier 1 or Tier 2, normalize the judge critique into the same ordered `reasoning_trace` shape: `1) check the criterion`, `2) cite the concrete evidence`, `3) connect that evidence to the final Pass/Fail`. Every material clause in `reasoning_trace` must have a matching supporting item, even when multiple clauses lead to the same final verdict. As soon as scoring completes for the experiment, populate `decision_breakdown` from those finalized verdicts before regression checks or user presentation. `decision_breakdown.components[]` is the canonical aggregation breakdown field: it must capture the intermediate per-eval math (`weight`, `weighted_points`, `normalized_contribution`), and the aggregate fields (`weighted_points`, `total_weight`, `combined_score`, `combined_score_pct`, `threshold`, `proposed_decision`) must match the keep/discard recommendation shown to the user. In the same scoring pass, derive `decision_explanation` from `decision_breakdown` plus the final recommendation: persist the strongest contributing eval outcomes, tag whether each one supports keep or discard, record each outcome's impact on the final keep/discard, and synthesize a balanced explanation that names both positive and negative pressure when both exist.
   c. **Regression check:** Compare current `eval_results` against prior kept experiments. If any eval that previously passed now fails → regression detected. Details: `references.md > Regression Check Schema`. Skip on experiments 0 and 1 (baseline has no prior kept experiments to compare against). If this check needs to reopen scored inputs, fixture text, or joined per-input outputs, first re-apply the active `mutation_stage_split_access_policy` with requested operation = `regression_check` and keep the read on the stored dev-scoped `input_set_id` + `input_ids` only.
   d. **Present to user** — show mutation diff, score change, regression status, and the Aggregation Explainer format (see `references.md > Aggregation Explainer Template`). The explainer must show every eval, its verdict, its `weight_source`, the normalization step (`weighted_points / total_weight`), the final `combined_score`, and the keep/discard threshold used for the recommendation. The explainer rows must match `decision_breakdown.components` 1:1 so the persisted record stays audit-ready. Also show the stored `decision_explanation` summary and strongest contributing eval outcomes so the user can see which outcomes most influenced the recommendation and how they impacted the final keep/discard. If you also show a version-to-version or baseline-to-mutation before/after view, first apply `references.md > Version Comparison Alignment` as a comparison preflight: require the same `input_set_id`, verify the two experiments contain the exact same set of stable `input_id`s, and surface any `missing_from_left`, `missing_from_right`, `extra_in_left`, or `extra_in_right` IDs before showing a diff. Treat any reopened per-input output or joined comparison payload as requested operation = `same_run_version_comparison` under the active `mutation_stage_split_access_policy`; if that read would cross into a blocked split, reject the comparison. If the comparison preflight fails, reject the comparison or return a flagged `invalid-comparison` status with the mismatch payload and stop there; you must not emit normal comparison results, delta rows, or before/after score summaries from a mismatched pair. Only after that preflight passes may you join per-input changes by stable `input_id`, never by display order. One decision point.
   e. User accepts or overrides → record in results.json (with `input_set_id` + `input_set_ref` + finalized-order `input_ids` + `eval_results` + `decision_breakdown` + `decision_explanation` + `regression_check`) + results.tsv + changelog.md. Every experiment in the run must preserve the same `input_set_id`, `input_set_ref`, and `input_ids`; if the scoring corpus changes, stop and start a new run instead of mixing versions scored on different inputs. The keep/discard threshold applies to `decision_breakdown.combined_score`, not raw pass count. If **kept**: assign a version label (see Version Registry below) and **write iteration artifacts** to `iteration_<NNN>/` now (verdict is final), then increment `state.json.completion_cadence.completed_experiments` exactly once, persist the updated root cadence in `results.json`, set `requires_human_spot_check` on this experiment from the updated cadence snapshot (true on every 3rd completed experiment; otherwise false), copy the same finalized cadence snapshot onto this experiment record, and log `{"phase":"7","type":"completion_cadence",...,"status":"keep"}`. If `requires_human_spot_check` is true, resolve the current `evaluation_metadata.config.human_spot_check_calibration.sample_count` (default `2`, validation `>= 1`) and queue `[workspace]/checkpoint-tasks/exp{N}-human-spot-check.json` using `references.md > Human Spot-Check Task Schema`; write the resolved `sample_count` into that task instead of leaving downstream pause consumers to infer it. If **discarded**: do NOT write or increment yet — step 2f writes after autopsy and only then finalizes the experiment.
   f. If discarded (regression or user choice): **discard autopsy first** (reads from `experiments[]` in results.json, not the skill file), then restore backup as current baseline. Classify why using `references.md > Discard Autopsy Heuristics` — `wrong_target` (section unlikely to respond), `wrong_params` (right section, wrong approach), or `wrong_type` (add/modify/delete mismatch). Record in `experiments[].discard_autopsy` and session-log: `{"phase":"7","type":"discard_autopsy","experiment":N,"classification":"...","reasoning":"1-sentence"}`. For kept experiments, `discard_autopsy` is null. **Write iteration artifacts** to `iteration_<NNN>/` now (includes autopsy classification). Once that write succeeds, the discard is finalized: increment `state.json.completion_cadence.completed_experiments` exactly once, persist the updated root cadence in `results.json`, set `requires_human_spot_check` on this experiment from the updated cadence snapshot (true on every 3rd completed experiment; otherwise false), copy the finalized cadence snapshot onto this experiment record, and log `{"phase":"7","type":"completion_cadence",...,"status":"discard"}`. If `requires_human_spot_check` is true, resolve the current `evaluation_metadata.config.human_spot_check_calibration.sample_count` (default `2`, validation `>= 1`) and queue `[workspace]/checkpoint-tasks/exp{N}-human-spot-check.json` using `references.md > Human Spot-Check Task Schema`; the queued payload must carry the resolved `sample_count`.
   g. **Circuit breaker check** — see below
3. Repeat until all evals pass, budget exhausted, or circuit breaker stops the loop

**Circuit breaker:**
Track `consecutive_discards` in state.json (integer, starts at 0). Update **after step (e)**, using the final keep/discard outcome:
- Experiment **kept** (by agent or user override) → reset `consecutive_discards = 0`
- Experiment **discarded** (regression, low score, or user override to discard) → increment `consecutive_discards += 1`

Disabled in Mini mode (`quick_start.completed = true` AND `gates.gulf_1 = "pending"`). Discard autopsy (step 2f) runs in all modes including Mini. Reset to 0 on Phase 7 re-entry after loop-back.

If `consecutive_discards >= 3`: STOP mutations and classify:

1. **Content ceiling** — if current baseline score > 80% AND all 3 discarded experiments scored within 5 percentage points of the current baseline:
   → "Your skill scores [X]%. The last 3 mutations all scored [Y-Z]%, unable to push past baseline. Either the skill is done, or add harder eval fixtures targeting dimensions not yet covered."

2. **Strategy review needed** — all other cases. Present the raw data:
   → "3 consecutive discards. Here's the data for your review:"
   - Last 3 experiments: scores, sections targeted (`changes[].location`), eval results, discard reason (regression / low score / user override), AND `discard_autopsy` classification
   - If all 3 autopsy classifications are `wrong_target`: "All 3 targeted unresponsive sections. Explore untried sections or add harder eval fixtures."
   - If all 3 are `wrong_params`: "Right sections but wrong approach. Try fundamentally different mutation strategies (e.g., rewrite vs. tweak, subtractive vs. additive)."
   - If all 3 are `wrong_type`: "Mutation type mismatch. Reverse direction: if adding, try deleting; if modifying, try replacing entirely."
   - If mixed or < 5 total experiments: present the autopsy breakdown and note: "Mixed signals — review the pattern before continuing."
   - If >= 5 total experiments with no clear autopsy pattern: "Possible causes: evals can't discriminate (scores flat across experiments), or judge noise (scores swing >15pp between adjacent experiments)."
   → "Recommendation: review eval-suite.md. Consider looping back to Phase 5-6, targeting different SKILL.md sections, or accepting current quality."

Report format (only show "Continue?" if budget remains):
Compute the derived mutation registry before presenting the diagnosis (see `references.md > Derived Mutation Registry`). Log the snapshot to session-log.

```
Circuit breaker: 3 consecutive discards
  Best score achieved: [X]% (Experiment [N])
  Diagnosis: [content ceiling | strategy review needed]
  Search diversity: [diversity_score] ([N]/[M] sections explored)
  Autopsy pattern: [summary of last 3 discard_autopsy classifications]
  Evidence: [raw data points including discard reasons]
  Recommendation: [specific action]

  [If budget remains] Continue anyway? (not recommended) / Stop and address diagnosis?
  [If budget exhausted] Budget exhausted. Review the diagnosis above.
```

If user continues: reset `consecutive_discards = 0` and resume the mutation loop (do NOT exit Phase 7). If breaker triggers again: "Circuit breaker triggered a second time (triggered_count: 2). The pattern of repeated discards suggests the current approach isn't working. Consider ending Phase 7." Still allow user to override.

Record in state.json: `circuit_breaker: {triggered_count: N, last_experiment: N, diagnosis: "..."}`. Record in session-log.json: `{"phase":"7","type":"circuit_breaker","diagnosis":"...","consecutive_discards":3,"experiments":[...]}`.

**After circuit breaker — two paths:**
- If user chose **stop**: exit the mutation loop. Phase 7 is done (early termination). Proceed to Loop-Back Prompt check, then Session Close.
- If user chose **continue**: reset counter, resume mutation loop at step (a). Do NOT proceed to Loop-Back Prompt yet — that only runs when the loop fully ends.

**Key rules:** One mutation per experiment. Mutate a copy (`[workspace]/<skill>-optimized.md`), not the workspace baseline. If score improves, the mutated copy becomes the new baseline for the next experiment. Target baseline 60-80% (>90% = evals too easy). **Mutation types:** add, modify, OR delete. After every 2-3 additive mutations, try one subtractive mutation — remove instructions and measure if performance improves. Shorter skills often outperform bloated ones. Formats: `references.md > Results & Changelog Schemas`.

**Confidence-weighted scoring:** Weight each eval by its judge's validated TPR/TNR. Code evals = 1.0. Agent evals = (TPR+TNR)/2. Experiment score = weighted sum / sum of weights. Persist this as `decision_breakdown`: each eval stores `weight`, `weight_source`, `weighted_points`, and `normalized_contribution`; the aggregate stores `formula`, `weighted_points`, `total_weight`, `combined_score`, `combined_score_pct`, `threshold`, and `proposed_decision`. In Mini mode, use the same structure with simplified weight sources (`mini_mode_code_default`, `mini_mode_agent_discount`).

**User verdict confirmation:** After each experiment, present the score change, regression status, and proposed keep/discard to the user. If the user overrides (e.g., keeps despite regression, or discards despite clean score), log as `type: "judge_gap"` in session-log.json: `{"phase":"7","type":"judge_gap","experiment":N,"agent_verdict":"keep","user_verdict":"discard","reason":"..."}`. These indicate judge blind spots and feed the loop-back prompt. Regression overrides also log: `{"phase":"7","type":"regression",...,"user_action":"keep_override"}`.

**Eval dimension pruning:** After the loop completes, check results.json for evals that passed 100% across ALL experiments (baseline + mutations). Flag them: "E{N} passed every experiment. This eval may no longer discriminate — consider whether the model has outgrown it or the criterion is too lenient."

**Mutation history:** Record discarded experiments with the same detail as kept ones — full `changes[]` diff, `eval_results`, and `regression_check`. Discarded mutations have diagnostic value: patterns in what fails reveal what the skill actually needs.

**State:** Update after each experiment (include `eval_results` and `regression_check`). **Dashboard:** serve workspace with `python3 -m http.server 8080`.

### Verdict Explanation Cards (v4.0)

The verdict evidence system ensures every judge verdict is transparent and inspectable. Each `eval_results[]` record preserves: `pass_fail`, `reasoning_trace` (3-step: criterion check, evidence citation, verdict link), structured `evidence[]` array (kind/source/locator), and `supporting_items[]` (intermediate judgments with `evidence_refs` back to evidence). Schemas: `references.md > Judge Verdict Evidence Schema` and `references.md > Judge Decision Support Schema`.

### Version Registry (v4.0 — derived view)

The version registry is a **derived view** from `results.json`, not a separate file. It provides version labels for kept experiments.

**Version numbering:**
- `v0` = baseline experiment (always exists, experiment id 0)
- `v1` = 1st kept mutation, `v2` = 2nd kept mutation, etc.
- Discarded experiments do NOT get version numbers (they remain in results.json for forensics)

**Computation (on demand):**
1. Read `results.json.experiments[]`
2. Filter for `status = "keep"` or `status = "baseline"`
3. Sort by `id` (experiment sequence number)
4. Assign version labels: v0 for baseline, vN for Nth kept experiment

**When to compute:** Any time version data is needed — after a kept mutation (show "Kept as v3"), at Session Close (show v0 → vN progression), or when the user requests version comparison.

Schema details: `references.md > Version Registry Schema`.

---

## Loop-Back Prompt

Phase 7 ends when: budget exhausted, all evals pass, user stops, OR circuit breaker fires and user chose stop. All exit paths trigger this check.

If session-log has >=2 `judge_gap` entries:

> "You overrode N experiment verdicts, suggesting judge blind spots:
> - [reason 1]
> - [reason 2]
> Loop back to Phase 5 to refine judges, then re-run Phase 7? Or accept current results?"

If user loops back: Phase 5 enters append mode (`locked_judges` prevents modifying approved judges). Phase 6 validates only new judges. Phase 7 re-runs with expanded suite — reset `consecutive_discards = 0` in state.json on re-entry (scoring changed, old counter is invalid). Score may drop — this is more accurate measurement, not regression. Explain this to the user. Max 2 loop-backs per session. Increment `loop_iteration` in state.json.

---

## Session Close

Runs after Phase 7, when user stops mid-pipeline, or when user explicitly pauses. Minimum: session-log must have >=3 entries for learning summary.

0. **Apply back gate** — If any mutations were kept: first sync the best kept mutation into the working copy (`cp [workspace]/<skill>-optimized.md [workspace]/skill-under-test/SKILL.md`) so the working copy reflects the latest improvements. Then ask: "Apply the improved SKILL.md back to the original location ([original-skill-path])? (y/n)". If yes: `cp [workspace]/skill-under-test/SKILL.md [original-skill-path]/SKILL.md`. If no: tell the user where the improved version lives. Log the decision to session-log.json: `{"type":"apply_back","applied":true/false,"source":"[workspace]/skill-under-test/SKILL.md","target":"[original-skill-path]/SKILL.md"}`. **If the copy fails** (e.g., sandbox restriction): don't retry. Print the full path and tell the user to copy manually: `cp [workspace]/skill-under-test/SKILL.md [original-skill-path]/SKILL.md`.
0b. **Clean up temporary files** — Remove `[workspace]/eval-tasks/` directory if it exists (debugging artifacts from Phase 7 verification isolation). Do NOT remove `[workspace]/runs/` — iteration directories are the forensic record and are retained indefinitely.
0c. **Adversarial holdout validation** — If `fixtures-manifest.md` exposes a split with `split_id=adversarial_holdout`, explicitly stop using the active `mutation_stage_split_access_policy` and switch to the evaluation-only `session_close_holdout_validation` scope before reading holdout fixtures. Score the best kept version (or baseline if nothing was kept) against that split only after the mutation loop is over. Treat it as evaluation-only: do not reopen Phase 5/6/7 refinement from these examples inside the same run. Record `state.json.holdout_score`, `state.json.holdout_gap`, and a session-log entry describing the final dev-vs-holdout comparison.
0d. **Session Close spot-check task** — Queue `[workspace]/checkpoint-tasks/session-close-human-spot-check.json` using `references.md > Human Spot-Check Task Schema`. Resolve `sample_count` from `evaluation_metadata.config.human_spot_check_calibration.sample_count` (default `2`, validation `>= 1`), then apply the mandatory closeout floor: `sample_count = max(sample_count, 5)`. Write that resolved value into the queued task payload with `trigger:"session_close"` and `minimum_sample_floor:5` so the closeout calibration task is explicit and reproducible.

### Version Comparison Summary (v4.0)

Before showing any baseline → final or Version N → Version N+1 results, apply the version comparison protocol:

1. **Compute version registry** — derive v0/v1/.../vN labels from results.json (see Version Registry above).
2. **Run comparison preflight** — read `references.md > Version Comparison Alignment` first. Require the same `input_set_id`, verify the two experiment records contain the exact same set of stable `input_id`s, and report any `missing_from_left`, `missing_from_right`, `extra_in_left`, or `extra_in_right` IDs if the sets do not line up. If the comparison preflight fails, mark the summary as `invalid-comparison` and stop; do not emit normal comparison results.
3. **Show side-by-side comparison** using the format from `references.md > Version Comparison Template`:
   ```
   Version Comparison: v0 -> vN
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Eval         v0        vN        Delta
   ────────────────────────────────────────────────────
   E1 (code)    Pass      Pass      --
   E2 (agent)   Fail      Pass      improved
   E3 (agent)   Pass      Fail      REGRESSED
   ────────────────────────────────────────────────────
   Pass rate    60.0%     80.0%     +20pp
   Weighted     62.3%     78.5%     +16.2pp
   Shared inputs  7 improved / 2 regressed / 11 unchanged
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Skill diff (v0 -> vN):  [expandable diff]
   ```
   The comparison result must also report `shared_input_summary` from the joined `per_input[]` rows: `total_shared_inputs`, `improved`, `regressed`, and `unchanged`.

### Per-Category Score Report (v4.0)

If eval category tags are present (see `SKILL-gulf2.md > Phase 5`), report separate scores per category:
```
Score by category:
  task-completion: 100% (3/3 evals passing)
  quality:          75% (3/4 evals passing)
  structural:      100% (2/2 evals passing)
```

### Remaining Session Close Steps

1. **Save checkpoint** — update `state.json.checkpoint` with current state and write `resume-prompt.txt` to workspace root. See `references.md > Checkpoint Schema`. Append to session-log: `{"type":"checkpoint",...}`.
2. **Synthesize** session-log.json into 3-5 bullet learning summary (what worked, what was overridden, patterns emerged)
3. **User curates** — present summary, ask for edits or approval
4. **Persist** to agent memory system (path from `state.json.memory_path`, or ask on first run and record). If no memory system exists, write to `[workspace]/learnings.md` as fallback.
5. **Present resume prompt** — "You can resume anytime. Paste this into a new session:" followed by the resume prompt from `resume-prompt.txt`.
6. **Archive** — rename session-log.json to `session-log-<timestamp>.json`

If <3 entries: still save checkpoint (step 1), skip learning summary. Say: "Not enough data for a learning summary yet. Checkpoint saved — you can resume later."

**Phase boundary checkpoints:** At every phase completion (not just Session Close), update `state.json.checkpoint` and write `resume-prompt.txt`. This is automatic — no user interaction needed. Log to session-log.
