---
name: autorefine
description: Iterate and improve any skill using eval-grounded autoresearch. Combines v2.0 design audit, Hamel's Three Gulfs eval methodology, and Karpathy-style mutation optimization. Use when you want to assess skill quality, build evals from scratch, run error analysis, or optimize a skill through experiments.
---

# AutoRefine

Guided skill improvement pipeline. Point at a skill: `/autorefine path/to/my-skill/`

## Preflight

1. **Target exists.** Confirm the path contains a SKILL.md. If not, ask.
2. **Detect enhancements.** Search for Hamel's `eval-audit` and `error-analysis` skills. If found, note in state.json. These enhance but are NOT required.
3. **Report tier:** Full (Hamel's detected) or Basic (core methodology only).
4. **Choose pipeline depth:**
   - **Quick** — Phase 1 (design audit) + Phase 7 (autoresearch loop). For skills with known failure modes or existing evals. ~15 min.
   - **Standard** — Full pipeline (Phases 1-7). For skills needing eval methodology from scratch. ~60-90 min.
   - **Deep** — Standard + expanded fixture set (30+ fixtures). For critical skills requiring statistical rigor.

   If workspace already has approved gates (both `gulf_1` and `gulf_2` = `"approved"` in state.json) AND `eval-suite.md` + `judges/` exist: offer Quick as default. Otherwise default to Standard.

## Initialize Workspace

If `autoresearch-<skill>/` doesn't exist: create it with `traces/` and `judges/` subdirectories. Generate these files (see `references.md > Workspace Schemas` for exact formats):
- `state.json` — pipeline state (schema_version:2)
- `results.json` — experiment results for dashboard
- `results.tsv` — append-only experiment log
- `session-log.json` — per-session audit trail
- `changelog.md`, `eval-suite.md`, `error-analysis-traces.md` — empty, formatted in later phases
- Copy `dashboard.html` from this skill's directory, replace `{{SKILL_NAME}}`

If workspace exists **with** `state.json`: read it and print pipeline status. Rotate `session-log.json` (rename to `session-log-<session_start, colons→dashes>.json`, create fresh). If `session-log.json` missing (pre-v2 workspace), create it.

If workspace exists **without** `state.json`: back up to `autoresearch-<skill>-prev/` and create fresh.

## Pipeline Status

Print at every session start:
```
AutoRefine: <name>
================================================================
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

## Phase 1: Design Audit

Read the target SKILL.md. Score 4 dimensions: **Gotchas**, **Voice**, **Progressive Disclosure**, **Scripts** (if any). For each Partial/Missing: quote the problem, recommend a fix, assign priority.

Detailed rubric: `references.md > V2.0 Design Audit Rubric`.

**Output:** `design-audit.md`. **State:** advance to Phase 2.

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

**Step 5: Human reviews.** Present sampled traces one at a time. For each, ask: (1) Pass or Fail? (2) If Fail: what went wrong? (free text) (3) If Pass: anything surprising or borderline? Record in `error-analysis-traces.md` (columns: #, Fixture, Cluster, Pass/Fail, Notes). User can stop after ≥5 traces.

**Consistency check (after ≥5 reviews):** If same-cluster traces got different verdicts, flag it. Append: `{"phase":"3","type":"consistency_flag","detail":"T03 and T07 match C2, judged differently"}`. If user confirms both verdicts, log resolution.

**Mid-phase resume:** Track `traces_reviewed` and `sampled_trace_ids` in state.json.

**Step 6: Build failure taxonomy.** Cluster failure notes into categories — let them EMERGE. If <3 failures in sample, review additional traces. Write `failure-taxonomy.md`.

**Step 7: Generate eval suite.** Convert top failures into binary evals. Write `eval-suite.md`. Format: `references.md > Eval Suite Template`.

### Gate: Gulf 1 Exit
Generate `gate-report-gulf-1.md` with: sample stats, fail rate, categories, consistency flags, proposed evals. **Override logging:** if user removes evals or rejects categories, append: `{"phase":"gate_1","type":"override","detail":"Removed E4","reason":"..."}`

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

**Step 3: Build agent-as-judge prompts.** Each judge has 4 components: task+criterion, Pass/Fail definitions, 3 few-shot examples (TRAIN split only — never dev/test), critique-before-verdict output format. The coding agent itself IS the judge — no external API needed. Full template: `references.md > Judge Prompt Template`.

**Step 4: Write to workspace.** Save to `judges/judge-E{N}-{name}.md` and `judges/code-E{N}-{name}.sh`.

**Output:** `eval-classification.md` + `judges/` directory. **State:** advance to Phase 6.

---

## Phase 6: Validate Judges

Calibrate agent-as-judge evaluators against human labels. Code-based evals skip (deterministic).

**Step 1:** Run each judge on dev split. Compare verdicts to human labels.
**Step 2:** Compute TPR and TNR. Target: >90% both. Formulas: `references.md > TPR/TNR Reference`.
**Step 3:** Inspect disagreements — False Pass → strengthen Fail defs. False Fail → clarify Pass defs.
**Step 4:** Iterate on dev until stable. If stalled: both low → sharper definitions; one low → inspect that metric; both <80% → decompose criterion.
**Step 5:** Final measurement on test split. Run once, record, do NOT iterate. Write `judge-validation-report.md`.

### Gate: Gulf 2 Exit
Generate `gate-report-gulf-2.md` with: classification, TPR/TNR per judge, code eval results. **Override logging:** if user rejects judges, append: `{"phase":"gate_2","type":"override","detail":"...","reason":"..."}`

**STOP. Wait for user approval.**

**State:** Mark Phase 6 complete.

---

## Phase 7: AutoResearch Loop

The Karpathy-style mutation-test-keep/discard cycle. Requires `eval-suite.md` + judges. If either is empty (Quick tier without existing evals), STOP and tell the user to run Standard pipeline first.

**Budget:** Ask user — Quick (3), Standard (5), Deep (8-10).

**The Loop:**
1. Run baseline on all fixtures, score against all evals → Experiment 0
2. LOOP: analyze failures → hypothesize ONE change → mutate a copy → test → keep (score up) or discard (score same/worse) → record in results.json + results.tsv + changelog.md
3. Repeat until all evals pass or budget exhausted

**Key rules:** One mutation per experiment. Mutate a copy (`<skill>-optimized.md`), not the original. If score improves, the mutated copy becomes the new baseline for the next experiment. Target baseline 60-80% (>90% = evals too easy). Formats: `references.md > Results & Changelog Schemas`.

**Confidence-weighted scoring:** Weight each eval by its judge's validated TPR/TNR. Code evals = 1.0. Agent evals = (TPR+TNR)/2. Experiment score = weighted sum / sum of weights.

**Judge gap detection:** When user overrides a Phase 7 keep/discard, log as `type: "judge_gap"` in session-log.json (distinct from `type: "override"`). These indicate judge blind spots.

**State:** Update after each experiment. **Dashboard:** serve workspace with `python3 -m http.server 8080`.

---

## Loop-Back Prompt

After Phase 7, if session-log has ≥2 `judge_gap` entries:

> "You overrode N experiment verdicts, suggesting judge blind spots:
> - [reason 1]
> - [reason 2]
> Loop back to Phase 5 to refine judges, then re-run Phase 7? Or accept current results?"

If user loops back: Phase 5 enters append mode (`locked_judges` prevents modifying approved judges). Phase 6 validates only new judges. Phase 7 re-runs with expanded suite. Score may drop — this is more accurate measurement, not regression. Explain this to the user. Max 2 loop-backs per session. Increment `loop_iteration` in state.json.

---

## Session Close

Runs after Phase 7, or when user stops mid-pipeline. Minimum: session-log must have ≥3 entries.

1. **Synthesize** session-log.json into 3-5 bullet learning summary (what worked, what was overridden, patterns emerged)
2. **User curates** — present summary, ask for edits or approval
3. **Persist** to agent memory system (path from `state.json.memory_path`, or ask on first run and record). If no memory system exists, write to `autoresearch-<skill>/learnings.md` as fallback.
4. **Archive** — rename session-log.json to `session-log-<timestamp>.json`

If <3 entries: "Not enough data for a learning summary yet."

---

## Gotchas

See `references.md > Gotchas` for the full list. Critical ones:

1. **Don't skip Gulf 1.** A 100% score on narrow evals is an artifact, not evidence.
2. **Error analysis cannot be automated.** Phase 3 requires the human to read outputs.
3. **session-log.json is best-effort.** If corrupted or missing, recreate and continue. Never blocks.
4. **Never run two sessions on same skill.** state.json has no locking.
5. **"Invoke" means "read and follow."** Not all agents support direct skill invocation.

---

## References

`references.md` — Templates, schemas, methodology rationale, detailed rubrics, gotchas.
