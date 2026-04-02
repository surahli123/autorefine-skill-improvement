---
name: autorefine
description: Iterate and improve any skill using eval-grounded autoresearch. Combines v2.0 design audit, Hamel's Three Gulfs eval methodology, and Karpathy-style mutation optimization. Use when you want to assess skill quality, build evals from scratch, run error analysis, or optimize a skill through experiments.
---

# AutoRefine

Guided skill improvement pipeline. Point at a skill: `/autorefine path/to/my-skill/`

## Preflight

### Step 0: Environment Check (MANDATORY — runs first, < 15 seconds)

Fast-fail checks. If ANY fail, STOP immediately with an actionable error message. Do NOT retry or explore alternatives silently.

1. **Target skill path.** If user provided a path, use it. If not, ask: "Which skill should I improve? Provide the full path to the skill directory."
2. **Target readable.** Run: `head -5 [skill-path]/SKILL.md`. If this fails → STOP: "I can't read your skill at [skill-path]. If you're in a sandboxed environment, copy your skill into my working directory first: `cp -r [skill-path] ./skill-under-test/` then re-invoke with `./skill-under-test/`"
3. **Workspace location.** Ask the user (ONE question, wait for answer):
   ```
   Where should I create the AutoRefine workspace?
     a) /tmp/autorefine-[skill-name]/  ← recommended (safe, no repo interference)
     b) Next to your skill: [skill-parent]/autorefine-[skill-name]/
     c) Custom path
   ```
   Default to (a) if user says "whatever" or "default." NEVER create the workspace without this confirmation.
4. **Workspace writable.** Run: `mkdir -p [chosen-workspace] && touch [chosen-workspace]/.preflight-test && rm [chosen-workspace]/.preflight-test`. If this fails → STOP: "I can't write to [chosen-workspace]. Try option (a) /tmp/ which is always writable, or specify a different path."
5. **Skill import.** Copy the entire skill directory into the workspace: `cp -r [skill-path]/ [chosen-workspace]/skill-under-test/`. All subsequent reads and writes operate ONLY on `[workspace]/skill-under-test/`, never on the original skill path. This protects the user's real skill from accidental modification.
6. **Persist paths.** Record in state.json: `original_skill_path: [skill-path]`, `workspace_path: [chosen-workspace]`. These are needed for Session Close (Apply Back gate) and session resume.

After Step 0 completes, print:
```
✓ Preflight passed
  Target skill: [skill-path]/SKILL.md
  Workspace: [chosen-workspace]/
  Working copy: [chosen-workspace]/skill-under-test/SKILL.md
  Original path saved for apply-back: [skill-path]
  Original skill is UNTOUCHED until you approve changes.
```

### Step 1: Detect & Configure

1. **Detect enhancements.** Search for Hamel's `eval-audit` and `error-analysis` skills. If found, note in state.json. These enhance but are NOT required.
2. **Report tier:** Full (Hamel's detected) or Basic (core methodology only).
3. **Choose pipeline depth:**
   - **Quick** — Context-aware. Routes based on workspace state (~15-30 min). See routing below.
   - **Standard** — Full pipeline (Phases 1-7). For skills needing eval methodology from scratch. ~60-90 min.
   - **Deep** — Standard + expanded fixture set (30+ fixtures). For critical skills requiring statistical rigor.

   **Quick tier routing (3 states):**
   ```
   State 1: No workspace exists
     → Quick Start path (~30 min)
     → "First time? Let's find what your skill actually does wrong."
   State 1b: Workspace exists with schema_version 2 (legacy v2.1), no quick_start field
     → Standard/Deep only (legacy workspace — Quick Start not available)
     → "This workspace was created before Quick Start. Use Standard or Deep."
   State 2: quick_start.completed = true, both gates still "pending"
     → Quick Returning (~15 min): Run Phase 1 (design audit), then skip to Phase 7 in Mini mode. Show directional warning at start.
     → Steps: (1) Run Phase 1 as normal. (2) Skip Phases 2-6. (3) Run Phase 7 — it auto-detects Mini mode from state. (4) Run Session Close.
     → "Your evals haven't been validated — results are still directional."
   State 3: Both gulf_1 and gulf_2 = "approved" in state.json
     → Quick Returning (~15 min): Run Phase 1 (design audit), then skip to Phase 7 in Full mode.
     → Steps: (1) Run Phase 1 as normal. (2) Skip Phases 2-6. (3) Run Phase 7 — it auto-detects Full mode from state. (4) Run Session Close.
   ```

   If workspace has approved gates: offer Quick as default. If quick_start_complete: offer Quick with directional note. Otherwise default to Standard (offer Quick Start as faster alternative).

## Initialize Workspace

**Workspace path** was confirmed in Preflight Step 0. The workspace is at `[chosen-workspace]/` and the working copy of the skill is at `[chosen-workspace]/skill-under-test/`.

If workspace `traces/` and `judges/` subdirectories don't exist: create them. Generate these files (see `references.md > Workspace Schemas` for exact formats):
- `state.json` — pipeline state (schema_version:4 for new workspaces — see `references.md > Workspace Schemas`)
- `results.json` — experiment results for dashboard
- `results.tsv` — append-only experiment log
- `session-log.json` — per-session audit trail
- `changelog.md`, `eval-suite.md`, `error-analysis-traces.md` — empty, formatted in later phases
- Copy `dashboard.html` from this skill's directory, replace `{{SKILL_NAME}}`

If workspace exists **with** `state.json`: read it and print pipeline status.

**Ambient learning check (on resume only, AFTER checkpoint recovery):**
This runs AFTER the checkpoint resume logic completes (not before — overwriting the workspace copy before checkpoint recovery would corrupt in-progress experiments).

Guard: `state.json.original_skill_path` must exist and be readable. If unreadable (sandbox, deleted), skip ambient learning silently and continue.

1. Run `diff state.json.original_skill_path/SKILL.md [workspace]/skill-under-test/SKILL.md`. If the `diff` command fails (sandbox restriction), skip ambient learning and continue.
2. If no diff → skill unchanged. Continue.
3. If diff exists → size gate:
   - **Small diff (≤20 lines changed):** likely preference signal. Proceed to step 4.
   - **Large diff (>20 lines, ≤50% of file):** warn: "Large diff detected (N lines). Treat as preference signal or new baseline?" If user says baseline → skip to step 5.
   - **Rewrite (>50% of file):** skip rule extraction. Log `{"type":"ambient_learning","skipped":true,"reason":"full_rewrite","diff_size":N}`. Go to step 5.
4. **Extract preference rules.** Show the diff to the user. Ask: "Should I learn from these edits? (y/n)". If yes, extract rules using this format:
   ```
   RULE: [one-sentence preference]
   EVIDENCE: [quote removed text] → [quote added text] (max 2 lines each)
   CONFIDENCE: high (clear intent) | medium (inferred) | low (ambiguous)
   ```
   Only auto-log `high` and `medium` rules. Present `low` rules for user confirmation. Distinguish preference edits from bug fixes (if the user fixed a typo or corrected a factual error, that's a fix, not a preference — skip it). Log to `[workspace]/preferences.md` (separate from `learnings.md` used by Session Close) and session-log: `{"type":"ambient_learning","rules_extracted":N,"diff_size":N}`.
5. **Sync workspace copy.** Always update: `cp [original]/SKILL.md [workspace]/skill-under-test/SKILL.md`. This ensures the next mutation cycle starts from the user's current version. **Check for checkpoint:** if `state.json.checkpoint` is not null and has `next_action`, enter resume mode — read all files in `checkpoint.files_to_read_on_resume` (skip any missing files and note which were missing), print "Resuming from checkpoint: {next_action}", clear the checkpoint (set to null), and proceed from `next_action`. See `references.md > Checkpoint Schema > Resume Detection`. Rotate `session-log.json` (rename to `session-log-<session_start, colons→dashes>.json`, create fresh). If `session-log.json` missing (pre-v2 workspace), create it. Legacy workspaces (schema_version 2 or 3) are read-compatible — checkpoint fields default to null.

If workspace exists **without** `state.json`: back up the workspace to `[chosen-workspace]-prev/` and create a fresh workspace at `[chosen-workspace]/`.

## Pipeline Status

Print at every session start:
```
AutoRefine: <name>
================================================================
Quick Start                        [STATUS]
Gulf 1: Comprehension
  Phase 1: Design Audit          [STATUS]
  Phase 2: Eval Audit             [STATUS]
  Phase 3: Error Analysis         [STATUS]  [N/M traces]
  >>> Gate: Approve taxonomy      [STATUS] <<<
Gulf 2: Specification
  Phase 4: Expand Inputs           [STATUS]  [N fixtures]
  Phase 5: Write Judges            [STATUS]  [N code / N judge]
  Phase 6: Validate Judges         [STATUS]  [TPR/TNR]
  >>> Gate: Approve judges         [STATUS] <<<
Gulf 3: Generalization
  Phase 7: AutoResearch Loop      [STATUS]  [best score]
================================================================
> Gulf 1 builds the scorer. Gulf 3 uses the scorer.
> Skip Gulf 1 and you optimize against a fantasy.
```
STATUS values: `not started`, `in progress`, `complete`, `skipped`. Read from `state.json.phases`.

---

## Quick Start Path

Read when: Quick Start path active (State 1 from Preflight routing).

> **Preview mode.** Quick Start gives you a taste of autorefine in ~30 min. It does NOT validate Gulf 1 or Gulf 2 — bootstrap evals are directional, not calibrated. Run Standard to get validated results.

### QS Step 1: Phase 1 Design Audit (5 min)
Run Phase 1 as normal (see below). No changes.

*Why this step:* "This tells us what your skill *should* do based on best practices. But the real failures might be different — that's why Step 2 exists."

### QS Step 2: Mini Phase 3 — Observation (10 min)
Generate 5 inputs targeting the skill. Use Phase 1 findings as **focus areas** (not literal inputs — structural gaps like "missing gotchas" guide what scenarios to test, not what text to send). Sort findings by priority, take top 5 as focus areas, generate one diverse input per focus area that exercises the skill in a way where that gap would matter. If fewer than 5 gaps, fill remaining slots from the diversity spread (see `references.md > Quick Start > Mini Phase 3 Template`). For interactive or session-spanning skills, create synthetic output fixtures instead (same fallback as Standard Phase 3 Step 1).

Run the skill on each input (read `[workspace]/skill-under-test/SKILL.md` and provide the input as if you were a user requesting the skill — capture the full output). If the skill errors on an input, record the trace as a Fail with note "skill execution error: [error message]" and continue to the next input. Present outputs one at a time for user judgment:
```
--- Trace 1/5 ---
Input: [summary]
Output: [skill output]
Pass or Fail? (one-line note if Fail)
```

Append to session-log.json: `{"phase":"quick_start","step":"observation","type":"mini_observation","detail":"Reviewed 5 traces: N pass, M fail"}`.

*Why this step:* "You're reading actual outputs — not imagining what could go wrong. Evals built from observation catch real failures. Evals built from imagination catch hypothetical ones."

**Graceful exit:** If Phase 1 found ≤1 issue AND all 5 traces pass: set `quick_start.completed = true` and `quick_start.graceful_exit = true` in state.json (prevents re-entry into Quick Start on next run). Tell the user: "Your skill looks clean on this sample. Quick Start needs failure signal to work. Try Standard for a deeper look, or skip autorefine." Stop here.

### QS Step 3: Bootstrap Eval Generator (3 min)
Auto-generate lightweight evals from Phase 1 findings (→ structural checks) + Mini Phase 3 failures (→ behavioral checks). Write each eval using the `references.md > Eval Suite Template` format (`EVAL N: [Name]...`). See `references.md > Quick Start > Bootstrap Eval Generator` for conversion rules and the simplified zero-shot judge template.

**Eval types:** Code-based where possible (deterministic). Agent-as-judge only for subjective criteria — use the zero-shot bootstrap template (NO few-shot examples, NO train split).

**Write judge files:** For each agent-as-judge eval, write the judge prompt to `judges/judge-E{N}-bootstrap-{name}.md` using the Bootstrap Judge Template from `references.md > Quick Start > Bootstrap Eval Generator`. For each code-based eval, write to `judges/code-E{N}-bootstrap-{name}.sh`. Phase 7 reads from `judges/` — if the files don't exist there, scoring will fail.

**Minimum floor:** 3 evals. If Phase 1 + Mini Phase 3 yield fewer, supplement with additional Phase 1 pattern checks.

**Labeling:** Tag every bootstrap eval in eval-suite.md with per-eval metadata: `Source: quick_start | Validated: false | Confidence: directional`. Apply this tag to EACH eval entry individually, not as a suite-level header.

Present all evals in a numbered list. User responds: "approved", "drop N", "change N to [description]", or "add [new eval]". Single interaction, not a gate.

*Why this step:* "These evals are rough — think of them as a first-draft relevance model. Useful for direction, not for production metrics. Run Standard to validate with TPR/TNR."

### QS Step 4: Mini Phase 7 — Targeted Mutations (10 min)
Generate 5-10 **fresh** scoring inputs — NOT the same as Mini Phase 3 traces (reusing = overfitting). Use the diversity spread from `references.md > Quick Start > Mini Phase 3 Template`, but target different Phase 1 gaps or different complexity levels than QS Step 2. Ensure zero overlap with the 5 QS Step 2 inputs. Save scoring inputs to `traces/qs-scoring-S01.md` through `traces/qs-scoring-S10.md`.

Run 2-3 mutations targeting the top Phase 1 + Mini Phase 3 findings. Score with bootstrap evals using simplified weighting: code evals = 1.0, agent-as-judge = 0.5 (flat discount, not empirical TPR/TNR).

Present each mutation to the user (diff, score change, proposed keep/discard). User confirms or overrides. Record in results.json + session-log.json.

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

Read the workspace copy of the target skill at `[workspace]/skill-under-test/SKILL.md` (established in Preflight Step 0). Score 4 dimensions: **Gotchas**, **Voice**, **Progressive Disclosure**, **Scripts** (if any). For each Partial/Missing: quote the problem, recommend a fix, assign priority.

**Gotchas dimension — 3-stage detection:**
1. **Taxonomy scan:** Check skill against 6 gotcha categories (shell execution, path handling, state mutation, concurrent access, auth/secrets, external APIs). Skills touching NONE → score "N/A." Full category list: `references.md > Gotcha Taxonomy`.
2. **Static evidence:** For each matched category, cite the specific line(s) creating the risk. Example: "Line 47: `$B goto $URL` — no URL sanitization."
3. **Smoke probe:** For the top 2 highest-risk findings, construct a minimal test input and run the target skill with it. Narrate before each probe. Record as `confirmed` or `not_confirmed`. For session-spanning skills, skip probes and record as `suspected`. Details: `references.md > Gotcha Taxonomy > Smoke Probe Instructions`.

Remaining dimensions: `references.md > V2.0 Design Audit Rubric`.

**Output:** `design-audit.md` (Gotchas section includes taxonomy, evidence, confidence levels, and probe results). Append to session-log.json: `{"phase":"1","type":"design_audit","detail":"Scored 4 dims: Gotchas=X (N categories matched, M confirmed), Voice=X, Disclosure=X, Scripts=X"}`. Phase 3 inherits `suspected` gotcha items as targeting input. **State:** advance to Phase 2.

---

## Phase 2: Eval Audit

Check for existing eval infrastructure (eval-suite.md, evals.json, test fixtures, results files). Audit against 6 categories: error analysis grounding, evaluator design, judge validation, train/test split, labeled data count, maintenance process. If no evals exist, document: "No eval infrastructure. Phase 3 builds the foundation."

Detail on each category: `references.md > Eval Audit Categories`.

**Output:** `eval-audit-report.md`. **State:** advance to Phase 3.

---

## Phase 3: Error Analysis

Close the Gulf of Comprehension. **Most important phase. CANNOT BE AUTOMATED.**

**Step 1: Prepare fixtures.** If fewer than 15 diverse inputs exist, generate more covering different types, lengths, quality levels, edge cases, at least 2 with planted flaws. For session-spanning skills (tracing, monitoring), create synthetic output fixtures instead.

**Step 2: Run the skill.** Invoke on each fixture (15-25). Save outputs to `traces/trace-T01.md` through `traces/trace-T25.md`.

**Step 3: Smart sampling.** Select 8-10 traces using stratified sampling. On first run, infer dimensions from fixture properties (input length, source, planted flaw). On re-runs, use Phase 4 dimensions. Ensure every dimension value represented at least once. Show the user which traces were selected and why. Append to session-log.json: `{"phase":"3","type":"sampling","detail":"Selected N/M traces..."}`. Methodology: `references.md > Smart Sampling Methodology`.

**Step 4: Preliminary clustering.** Assign each sampled trace a category ID (C1, C2, C3...) by surface patterns (adapt to skill type). Target 3-5 clusters. If <3, skip consistency checks. Write clusters to `error-analysis-traces.md` header.

**Step 5: Human reviews.** Present sampled traces in batches of 5 using the worksheet format. For each trace, the user provides: Pass or Fail, and a note if Fail. Record in `error-analysis-traces.md` (columns: #, Fixture, Cluster, Pass/Fail, Notes). User can stop after ≥5 traces. Format details: `references.md > Batch Review Format`.

**Consistency check (after ≥5 reviews):** If same-cluster traces got different verdicts, flag it. Append: `{"phase":"3","type":"consistency_flag","detail":"T03 and T07 match C2, judged differently"}`. If user confirms both verdicts, log resolution.

**Mid-phase resume:** Track `traces_reviewed` and `sampled_trace_ids` in state.json.

**Step 6: Build failure taxonomy.** Cluster failure notes into categories — let them EMERGE. If <3 failures in sample, review additional traces. Write `failure-taxonomy.md`.

**Step 7: Generate eval suite.** Convert top failures into binary evals. Write `eval-suite.md`. Format: `references.md > Eval Suite Template`.

### Gate: Gulf 1 Exit
Generate `gate-report-gulf-1.md` with: sample stats, fail rate, categories, consistency flags, proposed evals. Append to session-log.json: `{"phase":"gate_1","type":"gate_decision","detail":"APPROVED"}` (or REJECTED). **Override logging:** if user removes evals or rejects categories, also append: `{"phase":"gate_1","type":"override","detail":"Removed E4","reason":"..."}`

**STOP. Wait for user approval.**

**State:** Mark Phase 3 complete. Record traces_reviewed, sampling_strategy, taxonomy.

---

## Phase 4: Expand Inputs

**Step 1:** Count labeled fixtures from Phase 3.
**Step 2:** Define 3 failure-prone dimensions from the taxonomy. Format: `references.md > Dimension Template`.
**Step 3:** Generate fixtures via dimension tuples. Draft 15-20 with user, LLM generates 10 more. Target 30-40 total.
**Step 4:** Split into train (~15%) / dev (~42%) / test (~43%). Train = few-shot examples only. Dev = iteration. Test = final measurement, never peek. Write `fixtures-manifest.md`.

**Output:** `fixtures-manifest.md`. **State:** advance to Phase 5.

---

## Phase 5: Write Judges

**Step 1: Classify evals** as code-based (counting, regex, field presence → bash/python) or agent-as-judge (semantic judgment → judge prompt file). Exhaust code options first. Write `eval-classification.md`.

**Step 2: Build code-based evaluators.** One-liner or short script per eval. Test on 3 dev fixtures.

**Step 3: Build agent-as-judge prompts.** Each judge has 4 components: task+criterion, Pass/Fail definitions, 3 few-shot examples (TRAIN split only — never dev/test), critique-before-verdict output format. The coding agent itself IS the judge — no external API needed. **Anti-rigidity rule:** Score on outcome achievement, not path matching. A judge that fails outputs for using different structure or wording than the reference is penalizing creativity, not catching errors. Full template: `references.md > Judge Prompt Template`.

**Step 4: Write to workspace.** Save to `judges/judge-E{N}-{name}.md` and `judges/code-E{N}-{name}.sh`.

**Output:** `eval-classification.md` + `judges/` directory. **State:** advance to Phase 6.

---

## Phase 6: Validate Judges

Calibrate agent-as-judge evaluators against human labels. Code-based evals skip (deterministic).

**Steps 1-4 (dev split — human reviews):** Run each judge on dev split. Present judge verdicts vs human labels using batch review format (`references.md > Batch Review Format`). Compute TPR and TNR. Inspect disagreements — False Pass → strengthen Fail defs; False Fail → clarify Pass defs. Iterate until stable. Formulas: `references.md > TPR/TNR Reference`.

**Step 5 (test split — automated, NO human review):** Final measurement on test split. Run once, record, do NOT iterate. The human does NOT see test examples — this preserves the holdout. Write `judge-validation-report.md`.

**Step 6: Generate judge confidence cards.** For each agent-as-judge eval, generate a confidence card showing TPR/TNR with interpretation, evidence examples, and known blind spots. Template: `references.md > Judge Confidence Card Template`. Walk the human through each card with narration. If TPR-TNR gap > 20 points, flag the asymmetry explicitly.

### Gate: Gulf 2 Exit
Generate `gate-report-gulf-2.md` with: classification, TPR/TNR per judge, code eval results. Append to session-log.json: `{"phase":"gate_2","type":"gate_decision","detail":"APPROVED"}` (or REJECTED). **Override logging:** if user rejects judges, also append: `{"phase":"gate_2","type":"override","detail":"...","reason":"..."}`

**STOP. Wait for user approval.**

**State:** Mark Phase 6 complete.

---

## Phase 7: AutoResearch Loop

The Karpathy-style mutation-test-keep/discard cycle. Requires `eval-suite.md` + judges.

**Mode detection (check in this order):**
1. If both `gates.gulf_1` = "approved" AND `gates.gulf_2` = "approved" → **Full mode** (validated evals, confidence-weighted scoring). Budget: ask user — Quick (3), Standard (5), Deep (8-10).
2. Else if `quick_start.completed` = true AND both gates = "pending" → **Mini mode** (bootstrap evals, simplified weighting, directional labeling). Budget: 2-3 experiments.
3. Else → STOP and tell the user to run Standard pipeline first.

**Mini mode differences:** Fresh scoring corpus (5-10 generated inputs, NOT reusing Quick Start traces). Simplified weighting: code evals = 1.0, agent-as-judge = 0.5. All results labeled "directional." No confidence weighting from Phase 6 (evals aren't validated).

**The Loop:**
1. Run baseline on all fixtures, score against all evals → Experiment 0. Record `eval_results` per eval.
2. LOOP:
   a. Analyze failures → hypothesize ONE change. If `[workspace]/preferences.md` exists, read it first — do NOT propose mutations that contradict learned user preferences. **Save backup** (`[workspace]/<skill>-optimized-prev.md`) → mutate a copy
   b. **Score mutation (with bias reduction for agent-as-judge evals):**
      - For **code-based evals**: run directly (deterministic, no bias risk).
      - For **agent-as-judge evals**: the agent that hypothesized the mutation is biased toward finding it improved. Reduce this bias using the strongest available mechanism:

        **Tier 1 — Subagent dispatch (strong isolation, use when available):**
        Write `[workspace]/eval-tasks/exp{N}-E{M}.md` containing ONLY: the judge prompt (from `judges/`), the fixture input, and the skill output to evaluate (the mutated output — judge scores ONE output per invocation, same format as Phase 6 validation). Do NOT include: baseline output, mutation hypothesis, or Phase 1-3 findings. Dispatch a subagent with ONLY this file as input. Subagent produces Critique + Pass/Fail. Parent reads the verdict.

        **Fork economics (Tier 1 only):** When dispatching eval subagents, omit `subagent_type` to trigger a fork instead of a spawn. The fork inherits the parent's cached prompt prefix — judge prompts, fixtures, and workspace context are already loaded. Only the eval-task file content differs per experiment. This means each eval subagent pays cache price (1/10) for the shared prefix and full price only for the new eval-task content (~500 tokens). With 5 agent-as-judge evals across 5 experiments = 25 dispatches, fork saves ~80% vs spawn. If fork is unavailable (in-house agent), fall back to Tier 2.

        **Tier 2 — Behavioral instruction (bias reduction, for Read/Write/Bash-only agents):**
        If subagent dispatch is unavailable: score each agent-as-judge eval by reading ONLY the judge prompt file and the skill output. Before scoring, explicitly state: "I am now evaluating this output against the rubric only. I am disregarding my prior reasoning about why this mutation was made." This is a *heuristic* that reduces but does not eliminate self-certification bias.

        Keep eval-task files in `[workspace]/eval-tasks/` for debugging (clean up at Session Close, not per-eval). Record `eval_results` per eval.
   c. **Regression check:** Compare current `eval_results` against prior kept experiments. If any eval that previously passed now fails → regression detected. Details: `references.md > Regression Check Schema`. Skip on experiments 0 and 1 (baseline has no prior kept experiments to compare against).
   d. **Present to user** — show mutation diff, score change, regression status, proposed keep/discard. One decision point.
   e. User accepts or overrides → record in results.json (with `eval_results` + `regression_check`) + results.tsv + changelog.md
   f. If discarded (regression or user choice): restore backup as current baseline
   g. **Circuit breaker check** — see below
3. Repeat until all evals pass, budget exhausted, or circuit breaker stops the loop

**Circuit breaker:**
Track `consecutive_discards` in state.json (integer, starts at 0). Update **after step (e)**, using the final keep/discard outcome:
- Experiment **kept** (by agent or user override) → reset `consecutive_discards = 0`
- Experiment **discarded** (regression, low score, or user override to discard) → increment `consecutive_discards += 1`

Disabled in Mini mode (`quick_start.completed = true` AND `gates.gulf_1 = "pending"`). Reset to 0 on Phase 7 re-entry after loop-back.

If `consecutive_discards >= 3`: STOP mutations and classify:

1. **Content ceiling** — if current baseline score > 80% AND all 3 discarded experiments scored within 5 percentage points of the current baseline:
   → "Your skill scores [X]%. The last 3 mutations all scored [Y-Z]%, unable to push past baseline. Either the skill is done, or add harder eval fixtures targeting dimensions not yet covered."

2. **Strategy review needed** — all other cases. Present the raw data:
   → "3 consecutive discards. Here's the data for your review:"
   - Last 3 experiments: scores, sections targeted (`changes[].location`), eval results, AND discard reason (regression / low score / user override)
   - If < 5 total experiments have run: "Not enough data to pinpoint the cause. Consider: wrong mutation targets, evals that can't discriminate, or judge noise."
   - If >= 5 total experiments: "Possible causes: mutation direction exhausted (check if all 3 targeted the same section), evals can't discriminate (check if scores are flat across experiments), or judge noise (check if scores swing >15pp between adjacent experiments)."
   → "Recommendation: review eval-suite.md. Consider looping back to Phase 5-6, targeting different SKILL.md sections, or accepting current quality."

Report format (only show "Continue?" if budget remains):
```
⚠ Circuit breaker: 3 consecutive discards
  Best score achieved: [X]% (Experiment [N])
  Diagnosis: [content ceiling | strategy review needed]
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

**Confidence-weighted scoring:** Weight each eval by its judge's validated TPR/TNR. Code evals = 1.0. Agent evals = (TPR+TNR)/2. Experiment score = weighted sum / sum of weights.

**User verdict confirmation:** After each experiment, present the score change, regression status, and proposed keep/discard to the user. If the user overrides (e.g., keeps despite regression, or discards despite clean score), log as `type: "judge_gap"` in session-log.json: `{"phase":"7","type":"judge_gap","experiment":N,"agent_verdict":"keep","user_verdict":"discard","reason":"..."}`. These indicate judge blind spots and feed the loop-back prompt. Regression overrides also log: `{"phase":"7","type":"regression",...,"user_action":"keep_override"}`.

**Eval dimension pruning:** After the loop completes, check results.json for evals that passed 100% across ALL experiments (baseline + mutations). Flag them: "E{N} passed every experiment. This eval may no longer discriminate — consider whether the model has outgrown it or the criterion is too lenient."

**Mutation history:** Record discarded experiments with the same detail as kept ones — full `changes[]` diff, `eval_results`, and `regression_check`. Discarded mutations have diagnostic value: patterns in what fails reveal what the skill actually needs.

**State:** Update after each experiment (include `eval_results` and `regression_check`). **Dashboard:** serve workspace with `python3 -m http.server 8080`.

---

## Loop-Back Prompt

Phase 7 ends when: budget exhausted, all evals pass, user stops, OR circuit breaker fires and user chose stop. All exit paths trigger this check.

If session-log has ≥2 `judge_gap` entries:

> "You overrode N experiment verdicts, suggesting judge blind spots:
> - [reason 1]
> - [reason 2]
> Loop back to Phase 5 to refine judges, then re-run Phase 7? Or accept current results?"

If user loops back: Phase 5 enters append mode (`locked_judges` prevents modifying approved judges). Phase 6 validates only new judges. Phase 7 re-runs with expanded suite. Score may drop — this is more accurate measurement, not regression. Explain this to the user. Max 2 loop-backs per session. Increment `loop_iteration` in state.json.

---

## Session Close

Runs after Phase 7, when user stops mid-pipeline, or when user explicitly pauses. Minimum: session-log must have ≥3 entries for learning summary.

0. **Apply back gate** — If any mutations were kept, ask: "Apply the improved SKILL.md back to the original location ([original-skill-path])? (y/n)". If yes: `cp [workspace]/skill-under-test/SKILL.md [original-skill-path]/SKILL.md`. If no: tell the user where the improved version lives. Log the decision to session-log.json: `{"type":"apply_back","applied":true/false,"source":"[workspace]/skill-under-test/SKILL.md","target":"[original-skill-path]/SKILL.md"}`. **If the copy fails** (e.g., sandbox restriction): don't retry. Print the full path and tell the user to copy manually: `cp [workspace path] [original path]`.
1. **Save checkpoint** — update `state.json.checkpoint` with current state and write `resume-prompt.txt` to workspace root. See `references.md > Checkpoint Schema`. Append to session-log: `{"type":"checkpoint",...}`.
2. **Synthesize** session-log.json into 3-5 bullet learning summary (what worked, what was overridden, patterns emerged)
3. **User curates** — present summary, ask for edits or approval
4. **Persist** to agent memory system (path from `state.json.memory_path`, or ask on first run and record). If no memory system exists, write to `[chosen-workspace]/learnings.md` as fallback.
5. **Present resume prompt** — "You can resume anytime. Paste this into a new session:" followed by the resume prompt from `resume-prompt.txt`.
6. **Archive** — rename session-log.json to `session-log-<timestamp>.json`

If <3 entries: still save checkpoint (step 1), skip learning summary. Say: "Not enough data for a learning summary yet. Checkpoint saved — you can resume later."

**Phase boundary checkpoints:** At every phase completion (not just Session Close), update `state.json.checkpoint` and write `resume-prompt.txt`. This is automatic — no user interaction needed. Log to session-log.

---

## Gotchas

See `references.md > Gotchas` for the full list. Critical ones:

1. **Don't skip Gulf 1.** A 100% score on narrow evals is an artifact, not evidence.
2. **Error analysis cannot be automated.** Phase 3 requires the human to read outputs.
3. **session-log.json is best-effort.** If corrupted or missing, recreate and continue. Never blocks.
4. **Never run two sessions on same skill.** state.json has no locking.
5. **"Invoke" means "read and follow."** Not all agents support direct skill invocation.
6. **Quick Start is a preview, not validation.** Bootstrap evals are directional, not calibrated. Quick Start does NOT satisfy Gulf 1 or Gulf 2. Run Standard to validate results.
7. **Critical state lives in files, not conversation.** Keep mutation rationale, eval scores, and pipeline state in workspace files (state.json, results.json). Auto-compact at ~85% context erases conversation history — only the skill file (loaded via system prompt) survives.
8. **Never write to the original skill path during the pipeline.** All work happens on the workspace copy at `[workspace]/skill-under-test/`. The original is only touched during Session Close "Apply back gate" with explicit user approval.
9. **Sandbox environments block cross-directory access.** If Preflight Step 0 fails on read/write, use `/tmp/` as workspace and copy the skill in. Don't spend time debugging sandbox paths — use the workaround.
10. **Agent-as-judge evals should not see mutation reasoning.** The agent that hypothesized a mutation is biased toward finding it improved. Tier 1 (subagent dispatch) achieves real isolation — the judge has no mutation context. Tier 2 (behavioral instruction) reduces but does not eliminate bias — the agent still has mutation context in conversation history. Tier 2 is a heuristic, not a guarantee. If scoring feels unreliable, loop back to Phase 5-6 to add more code-based evals (which are immune to this bias).
11. **Workspace location must be confirmed, never assumed.** The agent must NEVER create a workspace directory without asking the user where. Default recommendation is `/tmp/autorefine-[skill-name]/` (safest). Creating inside a repo risks breaking git state, CI, or other tools.

---

## References

`references.md` — Templates, schemas, methodology rationale, detailed rubrics, gotchas.
