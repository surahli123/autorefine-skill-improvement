# AutoRefine — Gulf 1: Comprehension

Phases 1-3 + Quick Start. Read when: starting a new campaign, resuming in Phases 1-3, or Quick Start path active.

Downstream phase-entry contract: on entry to Quick Start QS Step 2-4, Phase 2, or Phase 3, initialize pattern-aware context from `state.json.phase1_context.selected_skill_pattern` and `state.json.phase1_context.selected_eval_strategy_id`. Downstream phase-entry contract: on entry to Quick Start QS Step 2-4, Phase 2, or Phase 3, initialize pattern-aware context from `state.json.phase1_context.selected_skill_pattern`. If only the Phase 1 artifact is available, read the same canonical IDs from the top-level `selected_skill_pattern` and `selected_eval_strategy_id` fields in `design-audit.md` and hydrate the loaded run context from that persisted output. If only the Phase 1 artifact is available, read the same canonical ID from the top-level `selected_skill_pattern` field in `design-audit.md` and hydrate the loaded run context from that persisted output. If the artifact has only the pattern, resolve the missing strategy through `references.md > Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector` before continuing. Once hydrated, use the matching strategy row as the active downstream route for Quick Start bootstrap eval generation, Phase 2 eval-audit framing, and Phase 3 failure clustering/sampling. Do not continue with the generic Gulf 1 eval path while a valid `selected_eval_strategy_id` is present. Do not rerun Phase 1 Step 0 or trigger pattern classification again unless the persisted value is missing or mismatched with `state.json.skill_pattern`.

---

## Quick Start Path

Read when: Quick Start path active (State 1 from Preflight routing).

> **Preview mode.** Quick Start gives you a taste of autorefine in ~30 min. It does NOT validate Gulf 1 or Gulf 2 — bootstrap evals are directional, not calibrated. Run Standard to get validated results.

### QS Step 1: Phase 1 Design Audit (5 min)
Run Phase 1 as normal (see below). No changes.

*Why this step:* "This tells us what your skill *should* do based on best practices. But the real failures might be different — that's why Step 2 exists."

### QS Step 2: Mini Phase 3 — Observation (10 min)
Generate 5 inputs targeting the skill. Use Phase 1 findings as **focus areas** (not literal inputs — structural gaps like "missing gotchas" guide what scenarios to test, not what text to send). Sort findings by priority, take top 5 as focus areas, generate one diverse input per focus area that exercises the skill in a way where that gap would matter. If fewer than 5 gaps, fill remaining slots from the diversity spread (see `references.md > Quick Start > Mini Phase 3 Template`). For interactive or session-spanning skills, create synthetic output fixtures instead (same fallback as Standard Phase 3 Step 1). Before running them, register the batch in `[workspace]/input-sets.json` using `references.md > Input Set Identity Schema`. Reuse the stored IDs if the canonical set hash matches a prior run. Every observation input gets a stable `input_id`.

Run the skill on each input (read `[workspace]/skill-under-test/SKILL.md` and provide the input as if you were a user requesting the skill — capture the full output). If the skill errors on an input, record the trace as a Fail with note "skill execution error: [error message]" and continue to the next input. Present outputs one at a time for user judgment:
```
--- Trace 1/5 ---
Input ID: [input_id]
Input: [summary]
Output: [skill output]
Pass or Fail? (one-line note if Fail)
```

Append to session-log.json: `{"phase":"quick_start","step":"observation","type":"mini_observation","detail":"Reviewed 5 traces: N pass, M fail"}`.

*Why this step:* "You're reading actual outputs — not imagining what could go wrong. Evals built from observation catch real failures. Evals built from imagination catch hypothetical ones."

**Graceful exit:** If Phase 1 found <=1 issue AND all 5 traces pass: set `quick_start.completed = true` and `quick_start.graceful_exit = true` in state.json (prevents re-entry into Quick Start on next run). Tell the user: "Your skill looks clean on this sample. Quick Start needs failure signal to work. Try Standard for a deeper look, or skip autorefine." Stop here.

### QS Step 3: Bootstrap Eval Generator (3 min)
Auto-generate lightweight evals from Phase 1 findings (-> structural checks) + Mini Phase 3 failures (-> behavioral checks). Write each eval using the `references.md > Eval Suite Template` format (`EVAL N: [Name]...`). See `references.md > Quick Start > Bootstrap Eval Generator` for conversion rules and the simplified zero-shot judge template.

**Eval types:** Code-based where possible (deterministic). Agent-as-judge only for subjective criteria — use the zero-shot bootstrap template (NO few-shot examples, NO train split).

**Write judge files:** For each agent-as-judge eval, write the judge prompt to `judges/judge-E{N}-bootstrap-{name}.md` using the Bootstrap Judge Template from `references.md > Quick Start > Bootstrap Eval Generator`. For each code-based eval, write to `judges/code-E{N}-bootstrap-{name}.sh`. Phase 7 reads from `judges/` — if the files don't exist there, scoring will fail.

**Minimum floor:** 3 evals. If Phase 1 + Mini Phase 3 yield fewer, supplement with additional Phase 1 pattern checks.

**Labeling:** Tag every bootstrap eval in eval-suite.md with per-eval metadata: `Source: quick_start | Validated: false | Confidence: directional`. Apply this tag to EACH eval entry individually, not as a suite-level header.

Present all evals in a numbered list. User responds: "approved", "drop N", "change N to [description]", or "add [new eval]". Single interaction, not a gate.

*Why this step:* "These evals are rough — think of them as a first-draft relevance model. Useful for direction, not for production metrics. Run Standard to validate with TPR/TNR."

### QS Step 4: Mini Phase 7 — Targeted Mutations (10 min)
Generate 5-10 **fresh** scoring inputs — NOT the same as Mini Phase 3 traces (reusing = overfitting). Use the diversity spread from `references.md > Quick Start > Mini Phase 3 Template`, but target different Phase 1 gaps or different complexity levels than QS Step 2. Ensure zero overlap with the 5 QS Step 2 inputs by comparing `input_id`s, not just summaries. Register the scoring corpus in `[workspace]/input-sets.json` using `references.md > Input Set Identity Schema`, then save scoring inputs to `traces/qs-scoring-S01.md` through `traces/qs-scoring-S10.md`.

Run 2-3 mutations targeting the top Phase 1 + Mini Phase 3 findings. Score with bootstrap evals using simplified weighting: code evals = 1.0, agent-as-judge = 0.5 (flat discount, not empirical TPR/TNR). **Mini mode skips verification isolation** (Phase 7 step 2b) — bootstrap evals are already labeled "directional" and the overhead isn't justified for 2-3 experiments. Even in Mini mode, emit the same `decision_breakdown` structure as Full mode (see `references.md > Confidence-Weighted Scoring` for the structure); only the `weight_source` values differ (`mini_mode_code_default` vs `mini_mode_agent_discount`).

Present each mutation to the user with the Aggregation Explainer (diff, score change, per-eval weights, normalization step, proposed keep/discard). User confirms or overrides. Record in results.json + session-log.json.

**Time note:** Estimates assume skill execution < 30 sec per run. Slow skills may push total to ~35 min.

*Why this step:* "You're seeing your skill get better. But bootstrap evals are rough — a passing mutation might miss subtle regressions. Standard mode builds evals you can trust."

### QS Step 5: Results + Handoff (2 min)
Show before/after comparison. All results labeled "directional improvement, not validated."

**State update:** In state.json, set `quick_start.completed = true` with metadata (traces, evals, mutations, timestamp). Keep `gates.gulf_1` and `gates.gulf_2` as `"pending"`. Set `current_phase: 0` (integer — 0 means Quick Start complete; phases 1-7 use integers 1-7). Set `phases.design_audit: "complete"` (Phase 1 was run). Keep `schema_version` at 4 (do NOT downgrade).

**Handoff:** "Your skill is better. Here's what Standard gives you: validated evals with TPR/TNR, a full failure taxonomy, and confidence-weighted optimization. Everything you just built carries forward — Standard extends this workspace."

**Standard transition rules:** When Standard runs on a Quick Start workspace:
- Phase 1: Re-run (skill may have changed from mutations). Overwrite `design-audit.md`.
- Phase 2: Acknowledge existing bootstrap evals in eval-suite.md. Audit them alongside any other eval infrastructure.
- Phase 3: Start fresh with full 20+ traces. Reference QS mini observations as prior context but don't skip reviews. Overwrite `error-analysis-traces.md`.
- Phase 5: Keep bootstrap evals that align with the new failure taxonomy. Discard the rest. Write validated judges to replace bootstrap judges in `judges/`.
- Phase 6: Validate all judges (including promoted bootstrap ones). Update per-eval metadata: `Source: standard | Validated: true`.

---

## Phase 1: Design Audit

**Step 0: Skill Pattern Classification (NEW — v4.0)**

Run this classifier immediately when Phase 1 starts, before any other Phase 1 processing logic. Before scoring dimensions, classify the target skill into exactly one of 5 patterns. Read the workspace copy at `[workspace]/skill-under-test/SKILL.md`, `references.md > Pattern Identification Section`, `references.md > Pattern Classification Procedure`, `references.md > Boundary-Case Resolution Examples`, and `references.md > Skill Pattern Specification Schema`, then assign the primary pattern:

| Pattern | Description | Example |
|---------|-------------|---------|
| **Tool Wrapper** | On-demand context for a library/API | SDK reference skill |
| **Generator** | Consistent structured output from templates | Report generator |
| **Reviewer** | Score against a checklist by severity | Code review skill |
| **Inversion** | Interview/gather requirements before acting | Requirements elicitor |
| **Pipeline** | Strict multi-step workflow with checkpoints | AutoRefine itself |

Follow the fixed-order procedure in `references.md > Pattern Classification Procedure`. If overlap remains after the three checks, resolve it with `references.md > Boundary-Case Resolution Examples` rather than improvising a new hybrid label. Choose the primary pattern only when its stated `purpose` matches the skill, its `required characteristics` are present, and its `exclusion boundaries` are not violated by the dominant behavior. If no pattern clears all three checks, use the documented fallback and still assign exactly one primary pattern. Record that single canonical ID in `state.json.skill_pattern` as a string. Then resolve the downstream evaluation strategy through `references.md > Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector`. Persist both the chosen primary pattern and the resolved strategy before any downstream Phase 1 scoring. Write `state.json.phase1_context = {"selected_skill_pattern":"<pattern_id>","selected_eval_strategy_id":"<strategy_id>","selection_scope":"current_run","source_skill_path":"skill-under-test/SKILL.md"}`. Treat `state.json.phase1_context.selected_skill_pattern` as the current run's classification source of truth and `state.json.phase1_context.selected_eval_strategy_id` as the current run's downstream evaluation-strategy source of truth. Never persist candidate arrays, composite labels, or secondary-pattern lists in the run-scoped Phase 1 context. Hard gate before Step 1-6: do not score `gotchas`, `voice`, `progressive_disclosure`, `anti_railroading`, `description_quality`, or `scripts` until `state.json.phase1_context.selected_skill_pattern` is present for the active run, matches `state.json.skill_pattern`, and `state.json.phase1_context.selected_eval_strategy_id` resolves back to that same pattern through the selector table. If the chosen pattern or the resolved strategy was not captured cleanly, treat it as a blocking Phase 1 state error rather than defaulting, inferring, or continuing. Log to session-log: `{"phase":"1","type":"pattern_classification","pattern":"pipeline","reasoning":"1-sentence justification with any secondary signals noted textually only"}` followed by `{"phase":"1","type":"eval_strategy_resolution","skill_pattern":"pipeline","strategy_id":"pipeline_eval_strategy","reasoning":"1-sentence justification for why this downstream strategy applies"}`.
If the classifier-orchestration boundary rejects the result, stop before downstream routing and surface the structured error payload in the run output/log.

The classification shapes downstream evaluation strategy. See `references.md > Skill Pattern Eval Strategy > Strategy Definitions` for the full pattern-to-eval mapping bundle after the selector resolves the active strategy.

**Step 1-6: Score dimensions.** Score 6 dimensions in this canonical order: **Gotchas** (`gotchas`), **Voice** (`voice`), **Progressive Disclosure** (`progressive_disclosure`), **Anti-Railroading** (`anti_railroading`), **Description Quality** (`description_quality`), **Scripts** (`scripts`, if any). Use the score types and allowed values from `references.md > Phase 1 Design Audit Dimension Schema`. For each Partial/Missing: quote the problem, recommend a fix, assign priority. For Anti-Railroading findings, also name the exact overspecific instruction and the likely edge case it mishandles.

**Gotchas dimension — 3-stage detection:**
1. **Taxonomy scan:** Check skill against 6 gotcha categories (shell execution, path handling, state mutation, concurrent access, auth/secrets, external APIs). Skills touching NONE → score "N/A." Full category list: `references.md > Gotcha Taxonomy`.
2. **Static evidence:** For each matched category, cite the specific line(s) creating the risk. Example: "Line 47: `$B goto $URL` — no URL sanitization."
3. **Smoke probe:** For the top 2 highest-risk findings, construct a minimal test input and run the target skill with it. Narrate before each probe. Record as `confirmed` or `not_confirmed`. For session-spanning skills, skip probes and record as `suspected`. Details: `references.md > Gotcha Taxonomy > Smoke Probe Instructions`.

**Anti-Railroading dimension — edge-case pressure test:**
1. **Load calibration profile:** Load `references.md > Anti-Railroading Calibration Profile Schema` for the current workspace copy at `[workspace]/skill-under-test/SKILL.md`.
2. **Resolve pattern profile:** Resolve the current skill-under-test's `state.json.skill_pattern` through `references.md > Skill-Pattern-to-Calibration-Profile Resolution` and record the selected `profile_id` before scoring. Read the active run's canonical pattern from `state.json.phase1_context.selected_skill_pattern`, confirm it matches the mirrored top-level `state.json.skill_pattern`, then continue. Use the classification produced for the active workspace copy, not a generic default and not a profile cached from another skill or prior version. Append to session-log: `{"phase":"1","type":"anti_railroading_profile_resolution","skill_pattern":"pipeline","profile_id":"pipeline_anti_railroading","resolution_mode":"exempt_no_penalty_stage_order","reasoning":"1-sentence justification for why this pattern-to-profile mapping applies"}`.
3. **Select pattern profile:** Select the profile whose `profile_id` and `applies_to_pattern` both match the current skill-under-test's resolved pattern. Reject generic calibration data and any profile resolved for a different skill or version.
4. **Constraint scan:** Sample the strongest constraints using that profile's `thresholds.strongest_constraints_sample` guidance.
5. **Invariant check:** For each instruction, ask whether the outcome truly depends on that exact path. If the same quality bar could be met through multiple valid approaches, the instruction is overspecific unless it names the invariant or acceptable fallback.
6. **Apply calibration:** Apply that profile's `thresholds`, `heuristic_settings`, and `required_evidence` before scoring `anti_railroading`. Apply the resolved profile at scoring runtime before deciding whether an anti-railroading penalty should fire.
7. **Exempt/no-penalty suppression:** If `resolution_mode` is `exempt_no_penalty_stage_order`, suppress the penalty whenever the only issue is stage ordering itself.
8. **Pipeline bypass:** If the resolved `skill_pattern` is `pipeline`, skip the anti-railroading penalty branch entirely.
9. **Edge-case flagging:** Mark Partial/Missing when an instruction hardcodes tool choice, path, ordering, or output shape in a way likely to fail already-complete work, missing prerequisites, partial state, unexpected errors, or alternate valid structures. For pipeline-pattern skills, record any stage-local rigidity only as audit notes and do not use it to trigger Partial/Missing penalties.
10. **Threshold accounting:** Do not count exempt stage-order invariants toward `partial_floor`, `missing_floor`, or overspecific-instruction totals.
11. **Pipeline exception:** Pipeline-pattern skills may enforce stage order. Treat stage order and stage-local implementation detail review as explanatory-only context once the pipeline bypass is active.

**Description Quality dimension — trigger audit:**
1. **Read the frontmatter field:** Inspect the exact `description:` value in `[workspace]/skill-under-test/SKILL.md`.
2. **Trigger check:** Ask whether it names specific user intents, conditions, or environment cues that would cause an agent to invoke this skill.
3. **Summary-vs-trigger check:** Mark Partial when the text mostly summarizes the skill rather than saying when to use it.
4. **Missing rule:** Mark Missing when the field is absent, tautological, or generic enough that invocation timing is still unclear. Never score `n/a` for `description_quality`.
5. **Canonical routing-fixture pipeline:** If you replay the production routing fixtures while auditing this dimension, normalize them into `expected_routing_fixtures[]` first, then build one Phase 1 routing evaluation input per canonical `prompt_cases[]` entry. Downstream evaluation must read the canonical fields (`description_quality.score`, `routing_rationale`, `source.*`, and `prompt_case.expected_routing_outcome`) rather than manifest-era keys. If you persist per-case routing evaluation results, emit one canonical result per `input_id` with `fixture_identity`, `evaluator_outcome`, and `routing_decision`. Preserve `fixture_identity.fixture_skill` + `fixture_identity.trigger_metadata` so the expected fixture route stays inspectable, and derive `evaluator_outcome.fixture_route_match_status` from the normalized comparison. When writing the structured Phase 1 payload, aggregate the full ordered batch under top-level `phase1_routing_fixture_result_collection` with `fixture_set_id`, `comparison_key`, `total_results`, `aggregate_trigger_precision`, `per_skill_trigger_precision`, and `phase1_routing_fixture_results`. `aggregate_trigger_precision` must summarize the full replay with `total_matches`, `total_evaluated_routes`, and `overall_precision`. `per_skill_trigger_precision` must group the same comparison results by `fixture_identity.fixture_skill`, recompute precision inside each skill bucket, and include `mismatch_details` for every incorrect route decision in that bucket. Also surface the replayed trigger-precision evidence under top-level `description_quality`, with one report per evaluated skill containing `score`, `evidence`, and `mismatches`.

Remaining dimensions: `references.md > V2.0 Design Audit Rubric`.

**Output:** `design-audit.md` (includes pattern classification + Gotchas section with taxonomy, evidence, confidence levels, and probe results). When writing a structured audit payload, preserve the canonical dimension order and keys from `references.md > Phase 1 Design Audit Dimension Schema`. Emit the chosen primary pattern as the top-level `selected_skill_pattern` field and the resolved downstream selector as the top-level `selected_eval_strategy_id` field in that payload. If routing fixtures were replayed, persist their comparable wrapper as top-level `phase1_routing_fixture_result_collection`. Source all three from the active run's canonical Phase 1 state/results rather than inferring them from prose or rereading raw manifests later. Append to session-log.json: `{"phase":"1","type":"design_audit","detail":"Pattern: [pattern]. Eval strategy: [strategy_id]. Scored 6 dims: Gotchas=X (N categories matched, M confirmed), Voice=X, Disclosure=X, Anti-Railroading=X, Description Quality=X, Scripts=X"}`. Phase 3 inherits `suspected` gotcha items as targeting input. **State:** advance to Phase 2.

---

## Phase 2: Eval Audit

Check for existing eval infrastructure (eval-suite.md, evals.json, test fixtures, results files). Frame the audit using the selected strategy's downstream route from `references.md > Skill Pattern Eval Strategy > Strategy Definitions`, especially its failure focus and eval category emphasis, rather than a generic audit lens. Audit against 6 categories: error analysis grounding, evaluator design, judge validation, train/test split, labeled data count, maintenance process. If no evals exist, document: "No eval infrastructure. Phase 3 builds the foundation."

Detail on each category: `references.md > Eval Audit Categories`.

**Output:** `eval-audit-report.md`. **State:** advance to Phase 3.

---

## Phase 3: Error Analysis

Close the Gulf of Comprehension. **Most important phase. CANNOT BE AUTOMATED.**

**Step 1: Prepare fixtures.** If fewer than 15 diverse inputs exist, generate more covering different types, lengths, quality levels, edge cases, at least 2 with planted flaws. For session-spanning skills (tracing, monitoring), create synthetic output fixtures instead. Once the set is finalized, register it in `[workspace]/input-sets.json` using `references.md > Input Set Identity Schema`. Assign each fixture a deterministic `input_id`, and on reruns of the same canonical set reuse the stored IDs instead of renumbering.

**Step 2: Run the skill.** Invoke on each fixture (15-25). Save outputs to `traces/trace-T01.md` through `traces/trace-T25.md`, and include the corresponding `input_id` in each trace header.

**Step 3: Smart sampling.** Read the selected strategy's Phase 3 failure focus in `references.md > Skill Pattern Eval Strategy > Strategy Definitions`, then select 8-10 traces using stratified sampling that expose that route's highest-risk failures instead of a generic mix. On first run, infer dimensions from fixture properties (input length, source, planted flaw). On re-runs, use Phase 4 dimensions. Ensure every dimension value represented at least once. Show the user which traces were selected and why. Append to session-log.json: `{"phase":"3","type":"sampling","detail":"Selected N/M traces..."}`. Methodology: `references.md > Smart Sampling Methodology`.

**Step 4: Preliminary clustering.** Assign each sampled trace a category ID (C1, C2, C3...) by surface patterns (adapt to skill type). Target 3-5 clusters. If <3, skip consistency checks. Write clusters to `error-analysis-traces.md` header.

**Step 5: Human reviews.** Present sampled traces in batches of 5 using the worksheet format. For each trace, the user provides: Pass or Fail, and a note if Fail. Record in `error-analysis-traces.md` (columns: #, Fixture, Cluster, Pass/Fail, Notes). User can stop after >=5 traces. Format details: `references.md > Batch Review Format`.

**Consistency check (after >=5 reviews):** If same-cluster traces got different verdicts, flag it. Append: `{"phase":"3","type":"consistency_flag","detail":"T03 and T07 match C2, judged differently"}`. If user confirms both verdicts, log resolution.

**Saturation check (after every 5th trace review, once >=5 reviews exist):** Ask whether a new failure type appeared in the last 5 traces. If no new failure type appeared, suggest that the user can continue sampling or finalize taxonomy-building with the current evidence. This is an advisory saturation prompt, not a hard stop.

**Mid-phase resume:** Track `traces_reviewed` and `sampled_trace_ids` in state.json.

**Step 6: Build failure taxonomy.** Cluster failure notes into categories — let them EMERGE. If <3 failures in sample, review additional traces. Write `failure-taxonomy.md`.

**Step 7: Generate eval suite.** Convert top failures into binary evals. Write `eval-suite.md`. Format: `references.md > Eval Suite Template`.

### Gate: Gulf 1 Exit
Generate `gate-report-gulf-1.md` with: sample stats, fail rate, categories, consistency flags, proposed evals. Append to session-log.json: `{"phase":"gate_1","type":"gate_decision","detail":"APPROVED"}` (or REJECTED). **Override logging:** if user removes evals or rejects categories, also append: `{"phase":"gate_1","type":"override","detail":"Removed E4","reason":"..."}`

**STOP. Wait for user approval.**

**State:** Mark Phase 3 complete. Record traces_reviewed, sampling_strategy, taxonomy.

---

After Gulf 1 gate is approved → read `SKILL-gulf2.md` for Phases 4-6.
