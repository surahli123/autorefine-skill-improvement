# AutoRefine — Gulf 1: Comprehension

Phases 1-3 + Quick Start. Read when: starting a new campaign, resuming in Phases 1-3, or Quick Start path active.

Downstream phase-entry contract: on entry to Quick Start QS Step 2-4, Phase 2, or Phase 3, initialize pattern-aware context from `state.json.phase1_context.selected_skill_pattern` and `state.json.phase1_context.selected_eval_strategy_id`. Downstream phase-entry contract: on entry to Quick Start QS Step 2-4, Phase 2, or Phase 3, initialize pattern-aware context from `state.json.phase1_context.selected_skill_pattern`. If only the Phase 1 artifact is available, read the same canonical IDs from the top-level `selected_skill_pattern` and `selected_eval_strategy_id` fields in `design-audit.md` and hydrate the loaded run context from that persisted output. If only the Phase 1 artifact is available, read the same canonical ID from the top-level `selected_skill_pattern` field in `design-audit.md` and hydrate the loaded run context from that persisted output. If the artifact has only the pattern, resolve the missing strategy through `references.md > Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector` before continuing. Once hydrated, use the matching strategy row as the active downstream route for Quick Start bootstrap eval generation, Phase 2 eval-audit framing, and Phase 3 failure clustering/sampling. Do not continue with the generic Gulf 1 eval path while a valid `selected_eval_strategy_id` is present. Do not rerun Phase 1 Step 0 or trigger pattern classification again unless the persisted value is missing or mismatched with `state.json.skill_pattern`.

---

## Phase 0.5: Contract Collection

Read when: starting a new campaign with no contract, or `state.json.contract_status` is null, `"not_started"`, `"collecting"`, or `"inferred"`.

> **Optional but transformative.** 9 examples take ~15 min and anchor every downstream eval. Skip if you want generic eval generation (current behavior).

### Resume Detection

On entry, read `state.json.contract_status`:
- `null` or `"not_started"` → proceed to Step 1 (Offer Contract)
- `"collecting"` → mid-wizard resume, using row counts in `[workspace]/contract/*.jsonl` files to determine where to resume:
  - `success-examples.jsonl` has < 3 rows → resume at Step 2, continuing from example N+1 where N = current row count
  - `success-examples.jsonl` has 3 rows AND `failure-examples.jsonl` has < 3 rows → resume at Step 3, example N+1 where N = failure row count
  - Both above complete AND `do-not-trigger-examples.jsonl` has < 3 rows → resume at Step 4, example N+1 where N = DNT row count
  - All 3 JSONL files have 3 rows → advance `contract_status` to `"inferred"` (state was stale) and proceed to Step 5
- `"inferred"` → skip to Step 6 (Author Correction Loop), reading the existing `[workspace]/contract/inferred-contract.md`.
- `"confirmed"` or `"skipped"` → do not enter Phase 0.5, proceed to Phase 1 (routing handled by SKILL.md).

### Step 1: Offer Contract (1 min)

Present to user:
```
Your skill is loaded. Before building evals, I can collect 9 examples that define
what "effective" means for THIS skill:
  - 3 success examples (what done-right looks like)
  - 3 failure examples (what must never happen)
  - 3 do-not-trigger examples (when the skill should stay quiet)

This takes ~15 min and makes every downstream eval more targeted.

A) Collect examples (recommended — 15 min)
B) Skip — use generic eval generation
```

If user chooses B: set `state.json.contract_status = "skipped"`, log `{"phase":"0.5","type":"contract_skipped"}` to session-log.json, and proceed to Phase 1.

If user chooses A: set `state.json.contract_status = "collecting"`, ensure `[workspace]/contract/` exists (created by workspace init in SKILL.md), then proceed to Step 2.

### Step 2: Collect Success Examples (5 min)

Collect 3 success examples one at a time. For each:

1. Ask: "Describe a scenario where your skill works correctly. What's the input?"
2. After user provides input, ask: "What should the output look like? Describe the shape (not exact text)."
3. Ask: "Can you paste or write a concrete example output?" (This becomes `actual_output`.)
4. Auto-generate `output_shape.schema` from the description + actual_output:
   - If output looks structured (JSON, lists, tables): generate a JSON Schema draft and show it with: "I generated a schema from your example. Keep it, edit it, or skip?"
   - If output is prose/unstructured: set `schema: null`, say: "Output is unstructured — I'll use the description for judging."
5. Write row to `[workspace]/contract/success-examples.jsonl` using `references.md > Contract Example Schema > Success Example Row`. Assign `id: "success-N"` where N increments from 1.

After 3 success examples, print: "Got 3 success examples. Next: 3 failure examples."

### Step 3: Collect Failure Examples (5 min)

Collect 3 failure examples one at a time. For each:

1. Ask: "Describe a scenario where your skill fails or produces unacceptable output. What's the input?"
2. Ask: "What did the skill produce (or what would bad output look like)?"
3. Ask: "Why is this unacceptable? (one sentence)"
4. Write row to `[workspace]/contract/failure-examples.jsonl` using `references.md > Contract Example Schema > Failure Example Row`. Assign `id: "failure-N"` where N increments from 1.

After 3 failure examples, print: "Got 3 failure examples. Next: 3 do-not-trigger examples."

### Step 4: Collect Do-Not-Trigger Examples (3 min)

Collect 3 do-not-trigger examples one at a time. For each:

1. Ask: "Describe an input that LOOKS like it's for your skill but should NOT activate it. What's the input?"
2. Ask: "What should happen? (one of: decline / route_elsewhere / ignore)"
3. Write row to `[workspace]/contract/do-not-trigger-examples.jsonl` using `references.md > Contract Example Schema > Do-Not-Trigger Example Row`. Assign `id: "dnt-N"` where N increments from 1.

After 3 do-not-trigger examples: set `state.json.contract_status = "inferred"` to mark collection complete, then print: "Got all 9 examples. Generating your effectiveness contract..."

### Option D: Record live sessions (trace recorder input)

When the user has already recorded real agent traces for the skill-under-test via `autorefine/scripts/record.py`, the wizard can import those traces as Phase 0.5 inputs instead of collecting 9 interactive examples.

**Step D.1: Convert recorded traces.** Ask the user for the records directory or file path. Run:
```
python3 autorefine/scripts/records-to-gulf1.py --input <path> --output [workspace]/contract/recorded-traces.jsonl --classify auto
```
If `[workspace]/contract/recorded-traces.jsonl` already exists and the author is intentionally regenerating it, pass `--force`; otherwise the converter fails closed to avoid clobbering an existing trace artifact.

This converts the JSONL session records to Gulf 1 Phase 0.5 input shape with heuristic classification.

**Step D.2: Classify and append to buckets.** Read the converted file. For each record, check the author's existing example counts. Surface low- and medium-confidence items to the author for quick confirmation before committing them to the bucket files. high-confidence items (explicit error -> failure classification) may auto-commit without prompting. Append records to the appropriate example JSONL files with stable IDs:
- Success classifications → append to `[workspace]/contract/success-examples.jsonl` with `id: "success-N"` (do not exceed 3 unless author requests richer contract)
- Failure classifications → append to `[workspace]/contract/failure-examples.jsonl` with `id: "failure-N"` (max 3)
- Do-not-trigger classifications → append to `[workspace]/contract/do-not-trigger-examples.jsonl` with `id: "dnt-N"` (max 3)

**Verification.** After import:
- Each converted record preserves `source_trace: {session_id, turn}` so Gulf 1 can cross-reference failing turns back to the original raw trace during debugging.
- Heuristic classifications include `classification_confidence` — surface low- and medium-confidence items to the author for quick confirmation before committing them to the bucket files. high-confidence items (explicit error -> failure classification) may auto-commit without prompting.

**See also:** `references.md > Gulf 1 Trace Record Schema` for canonical JSONL shape and `records-to-gulf1.py` consumer contract.

### Step 5: Generate Inferred Contract (2 min)

Read all 9 examples from the 3 JSONL files in `[workspace]/contract/`. Generate `[workspace]/contract/inferred-contract.md` using `references.md > Inferred Contract Template`.

For each section, cite which example IDs informed it. Apply these inference rules:
- **Intent**: synthesize from success examples — what common job do they describe?
- **Success Criteria**: merge `output_shape.description` fields from success examples
- **Non-Goals**: derive from do-not-trigger examples — what adjacent tasks are out of scope?
- **Must-Catch Failure Modes**: rank failure examples by severity (from `failure_reason`), extract the pattern
- **Trigger Conditions**: success inputs = should-fire, do-not-trigger inputs = should-not-fire
- **Domain Metric**: run Phase 1 pattern classification on the skill. If pattern suggests a domain metric (see `references.md > Skill Pattern Eval Strategy`), propose it with threshold and reasoning. Otherwise set "null — no domain metric applies".
- **Evaluation Dimensions**: propose which Phase 5 eval categories map to which contract sections (e.g., Success Criteria → task-completion evals, Must-Catch Failure Modes → quality evals)

Save the generated file. Do NOT advance state yet — wait for Step 6 corrections.

### Step 6: Author Correction Loop (2 min)

Present inferred-contract.md to the user section by section. For each section:

```
--- INTENT ---
[inferred intent text]

Based on: success-1, success-2, success-3

Correct? (y to accept / paste corrected text)
```

For each correction:
- Record in the Correction Log section with `ORIGINAL:` (exact prior text, max 3 lines) and `CORRECTED:` (new text) blocks.
- Check if dependent sections need updating:
  - Corrected Intent → re-check Non-Goals alignment
  - Corrected Success Criteria → re-check Evaluation Dimensions mapping
  - Corrected Non-Goals → re-check Trigger Conditions
- If a dependency check flags a mismatch, surface it: "Your correction to Intent may affect Non-Goals. Want me to re-infer? (y/n)"

Log each correction to session-log.json:
```
{"phase":"0.5","type":"contract_correction","section":"intent|success_criteria|...","section_index":N}
```

### Step 7: Domain Eval Setup (optional, 2 min)

Determine whether Step 7 runs:
1. Read the Domain Metric section of `[workspace]/contract/inferred-contract.md`. If null, Phase 1 pattern classification found no applicable domain metric — skip Step 7 entirely, proceed to Step 8.
2. If non-null, check the canonical adapter config pointer first:
   - If `state.json.adapter_config_path` is set, use it.
   - Else if the legacy alias `state.json.domain_eval_config_path` is set, hydrate `state.json.adapter_config_path` from that alias and continue.
   - If both are null: proceed with the normal Step 7 options A/B/C/D flow below.
   - If either is already set (resume case): run the Domain Eval Integrity Check from `SKILL.md` Step A before trusting it. If the check passes, keep both fields aligned and skip Step 7 (domain eval already configured correctly). If the check fails (file missing, corrupted, or author_confirmed=false), clear BOTH `state.json.adapter_config_path` and `state.json.domain_eval_config_path` to null and re-enter Step 7 from the top.

The integrity-first approach prevents a partial-state resume from treating a broken domain eval as valid.

If Step 5's inferred contract has a non-null Domain Metric section (pattern classification suggested one):

Present to user:
```
Based on your skill's pattern (PATTERN_NAME), I think the right effectiveness metric is:
  Metric: [suggested metric, e.g., NDCG@5]
  Reasoning: [why this metric fits your skill's domain]
  Threshold: [suggested pass threshold]

Options:
A) Use this metric — I'll generate the eval script, you provide labeled data
B) Use a different metric — you specify
C) Bring your own eval script + golden set — provide paths
D) Skip domain eval — use LLM judges only (current default)
```

Handle each option:
- **A**: generate `[workspace]/domain-eval/eval-metric.py` and `[workspace]/domain-eval/config.json` using `references.md > Domain Eval Config Schema`. Set `author_confirmed: true`. Tell user: "When you have labeled data, save it to `[workspace]/domain-eval/golden-set.jsonl` and domain eval will activate in Phase 7." Set BOTH `state.json.adapter_config_path` and `state.json.domain_eval_config_path` to `[workspace]/domain-eval/config.json`.
- **B**: ask for metric name + threshold. Generate script + config.json with those values. Set `author_confirmed: true` and `suggested_by_autorefine: false`. Set BOTH `state.json.adapter_config_path` and `state.json.domain_eval_config_path`.
- **C**: ask for paths to eval script + golden set. Validate both files exist using `ls <path>`. If either file is missing, tell the user: `File not found at [path]. Please provide the correct path or type 'cancel' to return to the option menu.` Re-prompt up to 3 times. If the user types 'cancel', return to the A/B/C/D option menu. Do NOT generate config.json until both files are confirmed to exist. Once validated, generate config.json pointing at those paths with `suggested_by_autorefine: false` and `author_confirmed: true`. Set BOTH `state.json.adapter_config_path` and `state.json.domain_eval_config_path`.
- **D**: leave BOTH `state.json.adapter_config_path` and `state.json.domain_eval_config_path` as null. Continue to Step 8.

If Step 5 produced no Domain Metric (pattern classification found no applicable metric): skip Step 7 entirely, continue to Step 8.

### Step 8: Finalize Contract

Set `state.json.contract_status = "confirmed"`. Set `state.json.contract_path = "[workspace]/contract/"`.

Log to session-log.json:
```json
{"phase":"0.5","type":"contract_confirmed","success_count":3,"failure_count":3,"dnt_count":3,"domain_eval":"<configured|skipped>","corrections":N,"pattern_classification":"<pattern_name>"}
```

Substitute `<configured|skipped>` with `"configured"` if `state.json.adapter_config_path` was set in Step 7 (or restored from the legacy alias and kept aligned), otherwise `"skipped"`. Substitute `<pattern_name>` with the classification result from Phase 1, or `"unclassified"` if pattern classification wasn't run yet.

Print:
```
Contract confirmed.
  9 examples saved to [workspace]/contract/
  Inferred contract: [workspace]/contract/inferred-contract.md
  Domain eval: [configured with METRIC | skipped]
  Author corrections: N

Moving to Phase 1 Design Audit + Effectiveness Floor...
```

Proceed to Phase 1.

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

Follow the fixed-order procedure in `references.md > Pattern Classification Procedure`. If overlap remains after the three checks, resolve it with `references.md > Boundary-Case Resolution Examples` rather than improvising a new hybrid label. Choose the primary pattern only when its stated `purpose` matches the skill, its `required characteristics` are present, and its `exclusion boundaries` are not violated by the dominant behavior. If no pattern clears all three checks, use the documented fallback and still assign exactly one primary pattern. Persist the chosen primary pattern in both `state.json.skill_pattern` and `state.json.phase1_context.selected_skill_pattern` before any downstream Phase 1 scoring. Record that single canonical ID in `state.json.skill_pattern` as a string. Then resolve the downstream evaluation strategy through `references.md > Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector`. Persist both the chosen primary pattern and the resolved strategy before any downstream Phase 1 scoring. Write `state.json.phase1_context = {"selected_skill_pattern":"<pattern_id>","selected_eval_strategy_id":"<strategy_id>","selection_scope":"current_run","source_skill_path":"skill-under-test/SKILL.md"}`. Treat `state.json.phase1_context.selected_skill_pattern` as the current run's source of truth for downstream pattern-aware Phase 1 logic. Treat `state.json.phase1_context.selected_skill_pattern` as the current run's classification source of truth and `state.json.phase1_context.selected_eval_strategy_id` as the current run's downstream evaluation-strategy source of truth. Never persist candidate arrays, composite labels, or secondary-pattern lists in the run-scoped Phase 1 context. Hard gate before Step 1-6: do not score `gotchas`, `voice`, `progressive_disclosure`, `anti_railroading`, `description_quality`, or `scripts` until `state.json.phase1_context.selected_skill_pattern` is present for the active run and matches `state.json.skill_pattern`. Hard gate before Step 1-6: do not score `gotchas`, `voice`, `progressive_disclosure`, `anti_railroading`, `description_quality`, or `scripts` until `state.json.phase1_context.selected_skill_pattern` is present for the active run, matches `state.json.skill_pattern`, and `state.json.phase1_context.selected_eval_strategy_id` resolves back to that same pattern through the selector table. If the chosen pattern was not captured cleanly, treat it as a blocking Phase 1 state error rather than defaulting, inferring, or continuing. If the chosen pattern or the resolved strategy was not captured cleanly, treat it as a blocking Phase 1 state error rather than defaulting, inferring, or continuing. Log to session-log: `{"phase":"1","type":"pattern_classification","pattern":"pipeline","reasoning":"1-sentence justification with any secondary signals noted textually only"}` followed by `{"phase":"1","type":"eval_strategy_resolution","skill_pattern":"pipeline","strategy_id":"pipeline_eval_strategy","reasoning":"1-sentence justification for why this downstream strategy applies"}`.
If the classifier-orchestration boundary rejects the result, stop before downstream routing and surface the structured error payload in the run output/log.

The classification shapes downstream evaluation strategy. See `references.md > Skill Pattern Eval Strategy > Strategy Definitions` for the full pattern-to-eval mapping bundle after the selector resolves the active strategy.

**Adapter suggestion pass (generic, optional):** After persisting the pattern and downstream evaluation strategy, check whether the current skill and available evidence suggest a domain adapter per `references.md > Adapter Resolution Rules`. A suggestion is allowed only when the domain signal is concrete enough to name a plausible primary oracle or gold source. Examples: a retrieval/search skill with labeled ranking data available, or a code-verification skill with executable tests/static checks. If an adapter is plausible:
- present it as a suggestion, not an activation
- explain the likely primary oracle in one sentence
- ask the author whether to activate it now

If the author confirms:
- write `state.json.selected_adapter_id`
- write `state.json.adapter_config_path` when the config already exists
- mirror the same path into `state.json.domain_eval_config_path` when the config lives at `[workspace]/domain-eval/config.json`

If the author declines or required assets do not yet exist:
- leave `selected_adapter_id = null`
- continue on the LLM-judge-only path

Do not auto-activate an adapter from classification alone.

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
4a. **`not_for_clause_hint` sub-signal:** After assigning the Present/Partial/Missing anchor, compute `description_quality.not_for_clause_hint`. This is informational only — it does NOT affect the anchor score and is silent when `[workspace]/contract/do-not-trigger-examples.jsonl` has ≥1 row. See `references.md > Dimension 5: Description Quality / Trigger Precision > not_for_clause_hint` for the full diagnostic sub-signal rules, trigger conditions, silencing rule, and output payload shape.
5. **Canonical routing-fixture pipeline:** If you replay the production routing fixtures while auditing this dimension, normalize them into `expected_routing_fixtures[]` first, then build one Phase 1 routing evaluation input per canonical `prompt_cases[]` entry. Downstream evaluation must read the canonical fields (`description_quality.score`, `routing_rationale`, `source.*`, and `prompt_case.expected_routing_outcome`) rather than manifest-era keys. If you persist per-case routing evaluation results, emit one canonical result per `input_id` with `fixture_identity`, `evaluator_outcome`, and `routing_decision`. Preserve `fixture_identity.fixture_skill` + `fixture_identity.trigger_metadata` so the expected fixture route stays inspectable, and derive `evaluator_outcome.fixture_route_match_status` from the normalized comparison. When writing the structured Phase 1 payload, aggregate the full ordered batch under top-level `phase1_routing_fixture_result_collection` with `fixture_set_id`, `comparison_key`, `total_results`, `aggregate_trigger_precision`, `per_skill_trigger_precision`, and `phase1_routing_fixture_results`. `aggregate_trigger_precision` must summarize the full replay with `total_matches`, `total_evaluated_routes`, and `overall_precision`. `per_skill_trigger_precision` must group the same comparison results by `fixture_identity.fixture_skill`, recompute precision inside each skill bucket, and include `mismatch_details` for every incorrect route decision in that bucket. Also surface the replayed trigger-precision evidence under top-level `description_quality`, with one report per evaluated skill containing `score`, `evidence`, and `mismatches`.

Remaining dimensions: `references.md > V2.0 Design Audit Rubric`.

**Output:** `design-audit.md` (includes pattern classification + Gotchas section with taxonomy, evidence, confidence levels, and probe results). When writing a structured audit payload, preserve the canonical dimension order and keys from `references.md > Phase 1 Design Audit Dimension Schema`. Emit the chosen primary pattern as the top-level `selected_skill_pattern` field in that payload. Emit the resolved downstream selector as the top-level `selected_eval_strategy_id` field in that payload. Source it from `state.json.phase1_context.selected_skill_pattern` for the active run rather than inferring it from prose or rereading state later. If routing fixtures were replayed, persist their comparable wrapper as top-level `phase1_routing_fixture_result_collection`. Source all three from the active run's canonical Phase 1 state/results rather than inferring them from prose or rereading raw manifests later. Append to session-log.json: `{"phase":"1","type":"design_audit","detail":"Pattern: [pattern]. Eval strategy: [strategy_id]. Scored 6 dims: Gotchas=X (N categories matched, M confirmed), Voice=X, Disclosure=X, Anti-Railroading=X, Description Quality=X, Scripts=X"}`. Phase 3 inherits `suspected` gotcha items as targeting input. **State:** advance to Phase 2.

---

## Phase 1b: Effectiveness Floor (5 min)

Read when: Phase 1 Design Audit complete, before Phase 2. Produces `[workspace]/effectiveness-floor.md`.

Evaluates 6 behavioral dimensions per `references.md > Effectiveness Floor Schema > Dimension Definitions`. Result is a **warning, not a gate** — print the result and continue to Phase 2 regardless of status.

### Step 1: Input Selection

Check `state.json.contract_status` and determine whether Phase 1b has enough data to run deterministically:

**Case A — `contract_status = "confirmed"` (full data path, 6 dimensions):**
Use contract examples as test inputs (3 success, 3 failure, 3 do-not-trigger from `[workspace]/contract/*.jsonl`). Run all 6 dimensions. Proceed to Step 2.

**Case B — `contract_status = "skipped"` or null, AND `state.json.phases.error_analysis = "complete"` (Phase 3 done, 4 dimensions):**
Phase 3 completed in a prior session or earlier in this pipeline run. Use Phase 3 traces as proxy inputs with this deterministic mapping:
- Outcome quality: use the first 3 labeled-pass traces from `error-analysis-traces.md` as "expected success" inputs
- Robustness: use Phase 3 traces with perturbation rules from Step 2c (applied by trace index: trace-1 → paraphrase, trace-2 → omit context, trace-3 → noise)
- Recovery: use the first 3 labeled-fail traces from `error-analysis-traces.md` as "expected failure" inputs
- Efficiency: run the 3 labeled-pass traces and measure per-input token/tool counts

Skip `activation_quality` and `boundary_discipline` (require do-not-trigger examples that don't exist without a contract). Mark as `"status": "skipped"`. Run remaining 4 dimensions. Proceed to Step 2.

**Case C — `contract_status = "skipped"` or null, AND Phase 3 not yet complete (DEFERRED):**
Phase 1b cannot run deterministically on a fresh first-time run with no contract and no Phase 3 data. Any proxy inputs the agent invents would cause non-deterministic floor results across runs.

Skip Phase 1b for now. Write a stub `[workspace]/effectiveness-floor.md`:

```
# Effectiveness Floor — DEFERRED

No contract examples and no Phase 3 traces available yet. Phase 1b deferred until Phase 3 error analysis completes. Floor will auto-run after Phase 3 Gate 1 approval.

Status: DEFERRED (ran 0 of 6 dimensions)
```

Set `state.json.effectiveness_floor = {"overall_status": "deferred", "deferred_reason": "no_contract_no_phase3_data", "evaluated_at": null, "dimensions": []}` so the dashboard displays "deferred" instead of empty.

Log to session-log.json: `{"phase":"1b","type":"effectiveness_floor_deferred","reason":"no_contract_no_phase3_data"}`.

Proceed to Phase 2. Phase 1b will re-run after Phase 3 completes, entering via Case B.

**Auto-run trigger after Phase 3:** After Phase 3 Gate 1 is approved, if `state.json.effectiveness_floor.overall_status == "deferred"`, re-enter Phase 1b via Case B before starting Phase 4. This is a one-time re-entry (not a loop). The re-run uses the same Case B inputs and produces a normal floor result that replaces the deferred stub.

### Step 2: Evaluate Each Dimension

Evaluate each of the 6 dimensions per `references.md > Effectiveness Floor Schema > Dimension Definitions`. For each dimension, follow the test method in the schema and assign `pass`, `concern`, or `fail` per the threshold columns.

#### 2a: Activation Quality

**Input variation mandate (NEW — Resolver-inspired):** For each of the 3 success-example inputs, generate 2 phrasing variations using this fixed assignment to keep runs reproducible:
- **Variation 1 — question/imperative flip:** if the original is imperative ('track this flight'), rephrase as a question ('is my flight on time?'). If the original is a question, rephrase as an imperative.
- **Variation 2 — synonym substitution:** replace the primary action verb and one key noun with synonyms (e.g., 'track' → 'monitor', 'flight' → 'trip').

Assign stable input IDs: `success-N-paraphrase-1` (question/imperative flip), `success-N-paraphrase-2` (synonym substitution).

Total: 3 success inputs × 3 phrasings = 9 should-fire inputs, plus the 3 do-not-trigger inputs as-is = 12 inputs total for this dimension.

Rationale: a skill that fires on one exact phrasing but misses rephrased versions has fragile activation — the classic "trigger description says `track this flight` but user says `is my flight delayed?`" failure mode.

Run the skill's activation check against all 12 inputs (route each input through a minimal skill-selection test: given the skill's `description` field and the input, would a routing LLM pick this skill?). Score using a proportion-based scaling of the schema's 6-input error rule ("All correct / 1 misfire or 1 miss / 2+ errors"). For the default 6-input case (no paraphrase variation), use schema thresholds directly. For the 12-input case (paraphrase variation active), scale the error proportion:

| Inputs | Pass (error rate) | Concern (error rate) | Fail (error rate) |
|--------|-------------------|----------------------|-------------------|
| 6 (schema default) | All correct (0 errors) | 1 error (16.7%) | 2+ errors (33%+) |
| 12 (paraphrase variation) | 0-1 errors (0-8.3%) | 2-3 errors (17-25%) | 4+ errors (33%+) |

Note: The 12-input "Pass 0-1" range is NOT equivalent to the schema's "all correct" (0 errors). It represents the proportion-scaled equivalent where 1 miss out of 12 corresponds to 0.5 misses out of 6 — below the schema's "1 error = concern" threshold when scaled. In practice: 12/12 correct is the strictest pass; 11/12 is still a pass by proportion, but a reviewer cross-referencing the schema should understand this is a scaling choice, not a looser bar. If you want schema-strict behavior, run the default 6-input test.

Record in the floor result: `test_inputs_used` includes all 12 input IDs (e.g., `success-1`, `success-1-paraphrase-1`, `success-1-paraphrase-2`, ..., `dnt-3`).

#### 2b: Outcome Quality

Run the 3 success examples through the skill. For each, judge the output against `output_shape.description` (from the contract) or against Phase 3 expected-output traces if no contract. Score per the schema (3 pass → pass, 1 marginal → concern, 2+ fail → fail).

#### 2c: Robustness

Take 3 success examples. Apply perturbations in this fixed order to keep runs reproducible:
- success-1 → paraphrase the primary request
- success-2 → remove one piece of context the skill would normally rely on
- success-3 → add 2-3 sentences of irrelevant noise before the actual request

Assign stable input IDs: `success-N-robustness` for each perturbed input.

Run perturbed inputs through the skill. Check if output quality holds (compared against the same `output_shape.description`). Score per the schema.

#### 2d: Recovery

Run the 3 failure examples (inputs designed to cause problems). For each, check if the skill:
- Flags the problem explicitly (e.g., asks for clarification, surfaces missing info)
- OR recovers (attempts a reasonable fallback with clear acknowledgment)
- OR continues blindly (confident garbage)

Score per the schema (flags-or-recovers on 2+ → pass, on 1 → concern, blindly-continues on all → fail).

#### 2e: Efficiency

Measure token count + tool-call count per success example execution. Compare to:
- Phase 7 Experiment 0 `baseline_trials[].trial_metadata` in `results.json` if available
- Otherwise, absolute threshold: 20K tokens / 10 tool calls per success example

Score per the schema (within 2x baseline OR under 20K/10 → pass; 2-3x OR 20-40K → concern; >3x OR >40K → fail).

#### 2f: Boundary Discipline

**Part A:** Run 3 do-not-trigger examples. Skill should decline, route elsewhere, or ignore per each example's `expected_behavior` field.

**Part B:** Run 3 success examples and check for out-of-scope side effects. Specifically: did the skill modify files outside its stated scope? Did it call tools unrelated to its purpose? Did it persist state beyond what its `description` implies?

Score per the schema (all DNT declined + no side effects → pass; 1 partial activation or minor side effect → concern; activates on DNT or harmful side effects → fail).

### Step 3: Compute Overall Status

Per `references.md > Effectiveness Floor Schema > Floor Scoring Rules`:
- `overall_status = "fail"` if ANY dimension is `fail`
- `overall_status = "concern"` if ANY dimension is `concern` and none are `fail`
- `overall_status = "pass"` if ALL non-skipped dimensions are `pass`. (This extends the schema's `Floor Scoring Rules` — the schema predates the `skipped` status introduced when contract is unavailable. Skipped dimensions are excluded from the pass check.)

### Step 4: Write Floor Report

Write `[workspace]/effectiveness-floor.md` with this human-readable format:

```
# Effectiveness Floor — [skill_name]

Overall: [PASS / CONCERN / FAIL]     Date: [ISO date]     Contract: [available | skipped]

| Dimension | Status | Evidence |
|-----------|--------|----------|
| Activation Quality | [pass/concern/fail/skipped] | [one-line summary — e.g., "11/12 correct fire, including 2/3 paraphrase variations on success-2"] |
| Outcome Quality | ... | ... |
| Robustness | ... | ... |
| Recovery | ... | ... |
| Efficiency | ... | ... |
| Boundary Discipline | ... | ... |

## Details

[For each dimension with status = concern or fail, provide 2-3 sentences explaining:
- Which specific test inputs failed
- What the failure looked like
- What the author might investigate]
```

### Step 5: Persist Floor Result

Serialize the floor result object using `references.md > Effectiveness Floor Schema > Floor Result` (JSON shape). Store at `state.json.effectiveness_floor`. Include:
- `floor_version: "1.0"`
- `evaluated_at: <ISO timestamp>`
- `skill_name` from state
- `contract_available: true` if contract_status was "confirmed", else false
- `overall_status` from Step 3
- `dimensions[]` — one entry per dimension with id, name, status, evidence (one-line summary), test_inputs_used (input IDs), details (extended explanation if concern/fail)
- `dimension_count: {pass: N, concern: N, fail: N}` (exclude skipped from counts)

### Step 6: Present Result and Continue

Print to user:
```
Effectiveness Floor: [PASS / CONCERN / FAIL]
  [N pass, N concern, N fail, N skipped]
  [One-line summary of any concern/fail dimensions, or "No issues found."]

This is a warning, not a gate. Continuing to Phase 2...
```

Log to session-log.json:
```json
{"phase":"1b","type":"effectiveness_floor","overall":"<pass|concern|fail>","dimensions":{"activation_quality":"<status>","outcome_quality":"<status>","robustness":"<status>","recovery":"<status>","efficiency":"<status>","boundary_discipline":"<status>"}}
```

Proceed to Phase 2 regardless of result.

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

After Gulf 1 gate is approved → read `references/gulf2-specification.md` for Phases 4-6.
