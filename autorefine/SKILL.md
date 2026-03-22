---
name: autorefine
description: Iterate and improve any skill using eval-grounded autoresearch. Combines v2.0 design audit, Hamel's Three Gulfs eval methodology, and Karpathy-style mutation optimization. Use when you want to assess skill quality, build evals from scratch, run error analysis, or optimize a skill through experiments.
---

# AutoRefine

Guided pipeline for improving any skill — from zero evals to optimized and validated.

Three gulfs to cross, in order: **Comprehension** (what does this skill actually do?) → **Specification** (do our judges measure what matters?) → **Generalization** (does it work on unseen inputs?).

## Quick Start

Point at a skill directory: `/autorefine path/to/my-skill/`
The agent detects your progress and picks up where you left off.

## Preflight

1. **Target exists.** Confirm the path contains a SKILL.md. If not, ask for the correct path.
2. **Detect enhancements.** Search for Hamel's `eval-audit` and `error-analysis` skills. If found, note in state.json. These enhance but are NOT required.
3. **Report tier:** Full (Hamel's detected) or Basic (core methodology only, works on any agent with Read/Write/Bash).

## Initialize Workspace

If `autoresearch-<skill>/` doesn't exist in the target directory:

1. Create `autoresearch-<skill>/` and `autoresearch-<skill>/traces/`
2. Generate `state.json`:
```json
{"skill_name":"<name>","skill_path":"<path>","started":"<today>","current_phase":1,"current_gulf":1,"phases":{},"gates":{"gulf_1":"pending","gulf_2":"pending"},"hamel_available":false}
```
3. Generate empty `results.json`:
```json
{"skill_name":"<name>","status":"running","current_experiment":0,"baseline_score":null,"best_score":null,"experiments":[],"eval_breakdown":[]}
```
4. Generate `results.tsv` with header: `experiment\tscore\tmax_score\tpass_rate\tstatus\tdescription`
5. Generate empty `changelog.md` and `eval-suite.md` from formats shown in Phase 7
6. Copy `dashboard.html` from this skill's directory, replace `{{SKILL_NAME}}` in title

If workspace exists **with** `state.json`: read it and print pipeline status.

If workspace exists **without** `state.json` (created by a different tool): back up to `autoresearch-<skill>-prev/` and create a fresh workspace. The backup preserves prior artifacts as ground truth for Phase 2 comparison.

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
```

---

## Phase 1: Design Audit

Assess structural quality against v2.0 skill design patterns.

**Read the target SKILL.md and score 4 dimensions:**

| Dimension | At Standard | Partial | Missing |
|-----------|-------------|---------|---------|
| **Gotchas** | 5-9 numbered failure modes, each names the failure + why + consequence | 1-4 or buried in other sections | None |
| **Voice** | "Do X because Y" throughout | Mix of instructional and descriptive | Purely descriptive |
| **Progressive Disclosure** | References tagged `Read when: [condition]`, folder structure | Some separation | Single flat file |
| **Scripts** (if any) | `__all__`, type hints, `Use when:` docstrings | Partial | No composability |

For each Partial/Missing dimension, write: what's wrong (quote actual text), recommended fix (concrete action), priority (HIGH/MEDIUM/LOW).

**Output:** Write `design-audit.md` in workspace with scores table + findings.
**State:** Mark phase 1 complete, advance to phase 2. For detailed rubric, read `references.md`.

---

## Phase 2: Eval Audit

Assess existing eval infrastructure, or document its absence.

**Check the target skill directory for:** eval-suite.md, evals.json, test fixtures, results files, autoresearch artifacts.

**If evals exist, audit against 6 categories:**
1. **Error analysis grounding** — Were evals built from observed failures, or brainstormed? Look for error-analysis-traces.md or failure taxonomy.
2. **Evaluator design** — Binary pass/fail? Or vague Likert scales? Are holistic evals bundling multiple failure modes?
3. **Judge validation** — Any TPR/TNR measurements? Golden dataset? Or untested judges?
4. **Train/test split** — Same fixtures for iteration AND measurement? (= data leakage)
5. **Labeled data** — How many labeled examples? Target: >50. Under 25 is critical gap.
6. **Maintenance** — Process for re-auditing after skill changes? Or "set and forget"?

**If no evals exist:** Document: "No eval infrastructure. Phase 3 builds the foundation."

### Enhancement: eval-audit (Hamel)
If `hamel_available` is true in state.json, invoke the `eval-audit` skill for deeper analysis. It runs the same 6 diagnostics above but with richer heuristics: flags class imbalance in metrics, detects stale analyses, and recommends specific next skills.

**How to invoke:** Provide the eval artifacts (eval-suite.md, results files, fixture paths) as context. The skill produces a structured findings report with problem title, status, explanation, and recommended fix for each diagnostic.

**Output:** Write `eval-audit-report.md` with findings and remediation priorities.
**State:** Mark phase 2 complete, advance to phase 3.

---

## Phase 3: Error Analysis

Close the Gulf of Comprehension. This is the most important phase. CANNOT BE AUTOMATED.

### Step 1: Prepare fixtures
Check existing test inputs in the skill directory. If fewer than 15 diverse inputs exist, help generate additional ones covering: different input types, lengths, quality levels, edge cases, at least 2 with planted flaws.

### Step 2: Run the skill
Invoke the target skill on each fixture (15-25 inputs). Save each output to `traces/trace-T01.md` through `traces/trace-T25.md`.

**Session-spanning skills:** Some skills run *during* an entire session (e.g., tracing, monitoring, coaching) rather than producing output on a single input. For these:
- Don't try to invoke the skill 15+ times — it's not a one-shot tool.
- Instead, create **synthetic output fixtures** that simulate what the skill would produce across different scenarios (clean session, error-heavy, short session, edge cases).
- Also include any **real outputs** from prior runs if they exist (e.g., from a previous autoresearch).
- The goal is the same: give the human diverse outputs to review. The generation method adapts to the skill type.

### Step 3: Human reviews outputs
Present traces in batches of 5. User can stop after any batch.

For each trace, ask:
- **Pass or Fail?** (overall quality judgment)
- **If Fail:** What went wrong? (free text — no pre-defined categories)
- **If Pass:** Anything surprising or borderline?

Record in `error-analysis-traces.md`:
```
| # | Fixture | Pass/Fail | Notes |
|---|---------|-----------|-------|
| T01 | fixture-name.md | FAIL | Location references too vague, used "throughout" |
```

**Mid-phase resume:** Track `traces_reviewed` in state.json. Next session says: "You reviewed N of M traces. Continue with T-XX?"

### Step 4: Build failure taxonomy
After all traces reviewed, cluster failure notes into categories. Let categories EMERGE — do NOT use existing eval categories as starting taxonomy. Present to user for approval.

Write `failure-taxonomy.md`:
```
## Failure Taxonomy: <skill>
1. [Category Name] — [description] — observed in N/M traces
2. ...
```

### Step 5: Generate initial eval suite
Convert top failure categories into binary evals in `eval-suite.md`:
```
EVAL 1: [Name]
Question: [specific yes/no question]
Pass: [what success looks like]
Fail: [what failure looks like]
Why: [which observed failure mode this catches]
```

### Gate: Gulf 1 Exit
Generate `gate-report-gulf-1.md`:
- Traces reviewed, fail rate, top failure categories
- Proposed eval suite (from Step 5)
- Decision: "Approve this taxonomy and eval suite to proceed?"

**STOP. Wait for user approval before Phase 4.**

### Enhancement: error-analysis (Hamel)
If `hamel_available` is true, invoke the `error-analysis` skill to structure the review process. Adaptations for skills vs. LLM pipelines:
- Hamel's skill expects ~100 production traces → use 20-25 fixture outputs instead
- Hamel's skill uses LLM-assisted clustering after ~30 traces → use manual clustering (our trace count is smaller)
- Hamel's skill recommends random/stratified/outlier sampling → use fixture diversity instead (we control inputs)
- The core protocol is the same: read every output → judge Pass/Fail → capture root cause (not explanation) → cluster into 5-10 categories → compute failure rates

### Enhancement: generate-synthetic-data (Hamel)
If `hamel_available` is true, use the `generate-synthetic-data` skill to prepare diverse fixtures in Step 1. It generates inputs via dimension-based tuples:
1. Define 3 failure-prone dimensions (e.g., Document Type × Quality Level × Domain)
2. Draft 20 tuples with user feedback
3. LLM generates more tuples, user validates
4. Convert tuples to natural language test inputs
This produces more systematically diverse fixtures than ad hoc generation.

**State:** Mark phase 3 complete. Record traces_reviewed and taxonomy summary.

---

## Phase 4: Expand Inputs

Build a diverse, labeled fixture set and split it for judge training and validation.

### Step 1: Inventory existing fixtures
Count labeled fixtures from Phase 3 (`traces/` directory). Record Pass/Fail counts.

### Step 2: Define dimensions
Choose 3 failure-prone dimensions based on the Phase 3 failure taxonomy. Each dimension is an axis of variation that targets where the skill fails.

```
Dimension 1: [Name] — [What it captures]
  Values: [value_a, value_b, value_c, ...]
```

Example for ds-trace: Session Length × Domain Type × Error Density.

### Step 3: Generate fixtures via tuples
1. Draft 15-20 tuples (dimension combinations) with user feedback. The user knows which combinations are realistic.
2. Use an LLM to generate 10 more tuples, varying across dimensions.
3. Convert each tuple to a concrete test input (the fixture content).
4. Combine with Phase 3's existing fixtures.

**Target: 30-40 total labeled fixtures.** This is pragmatic for skill improvement — users have limited attention and token budgets. TPR/TNR will be directional, not statistically rigorous.

### Step 4: Split into train / dev / test
Split following Hamel's methodology — train is small because it's ONLY for few-shot examples in judge prompts:

| Split | Size | Purpose | Rules |
|-------|------|---------|-------|
| **Train** | ~15% (5-6 fixtures) | Few-shot examples for judge prompts | Only clear-cut Pass and Fail cases |
| **Dev** | ~42% (13-17 fixtures) | Iterative judge refinement | Never include in judge prompts |
| **Test** | ~43% (13-17 fixtures) | Final unbiased measurement | Do NOT look at during development |

Write `fixtures-manifest.md` documenting: fixture ID, which split, Pass/Fail label, source (Phase 3 or Phase 4).

### Enhancement: generate-synthetic-data (Hamel)
If available, use `generate-synthetic-data` for systematic tuple generation. Adaptations for skills:
- Hamel targets ~100 traces → use 30-40 for skills (attention + token pragmatism)
- Hamel's Step 6 says "run through full pipeline" → for session-spanning skills, generate synthetic output fixtures instead (same adaptation as Phase 3)

**Output:** `fixtures-manifest.md` in workspace with labeled, split fixture inventory.
**State:** Mark phase 4 complete. Record fixture_count, pass_count, fail_count, and split sizes in state.json. Advance to phase 5.

---

## Phase 5: Write Judges

Build evaluators for each eval in the suite. Code-based for deterministic checks, LLM judges only for subjective criteria.

### Step 1: Classify evals as code-based or judge-based
Review each eval in `eval-suite.md`. Exhaust code-based options before reaching for an LLM judge:

| Check type | Use when | Implementation |
|-----------|----------|----------------|
| **Code-based** | Eval can be verified by counting, regex, or field presence | Bash/grep/python one-liner |
| **LLM judge** | Eval requires semantic judgment (quality, depth, reasoning) | Judge prompt with 4 components |

Examples of code-based: "Does the trace mention ≥4 distinct tool types?" → count tool names. "Does 'What went wrong' say 'nothing'?" → regex check.

Examples requiring LLM judge: "Is the artifact an actual code snippet vs tool metadata?" → requires semantic understanding. "Does the decision include genuine reasoning?" → requires judgment.

Write the classification to `eval-classification.md`:
```
| Eval | Type | Implementation |
|------|------|----------------|
| E1: Tool breadth | CODE | grep -c distinct tool names in Execution blocks, check ≥4 |
| E6: Artifact capture | JUDGE | LLM judge: is the artifact real code or just a tool name? |
```

### Step 2: Build code-based evaluators
For each code-based eval, write the check as a one-liner or short script. Test on 3 fixtures from the dev split (1 known Pass, 1 known Fail, 1 borderline) to verify.

### Step 3: Build LLM judge prompts
For each judge-based eval, write a prompt with **all 4 components**:

**Component 1 — Task and criterion:**
```
You are an evaluator assessing whether [specific criterion from failure taxonomy].
```
One failure mode per judge. Never bundle multiple criteria.

**Component 2 — Pass/Fail definitions:**
```
PASS: [what success looks like — concrete, observable]
FAIL: [what failure looks like — concrete, with examples from Phase 3 traces]
```
These definitions come directly from the eval-suite.md entries.

**Component 3 — Few-shot examples (from TRAIN split only):**
Include at least 3 examples: one clear Pass, one clear Fail, one borderline. Borderline examples teach nuance and are the most valuable.

Each example must include a **critique** (detailed assessment) BEFORE the verdict. This forces the judge to articulate reasoning.

```
### Example 1: PASS
Input: [fixture excerpt]
Critique: [why this passes — reference specific evidence]
Result: Pass

### Example 2: FAIL
Input: [fixture excerpt]
Critique: [why this fails — reference what's missing or wrong]
Result: Fail

### Example 3: PASS (borderline)
Input: [fixture excerpt]
Critique: [why this narrowly passes despite appearing weak]
Result: Pass
```

**NEVER use dev or test examples as few-shots.** This is data leakage.

**Component 4 — Structured output:**
```json
{
  "critique": "string — detailed assessment before verdict",
  "result": "Pass or Fail"
}
```
Critique before verdict — forces reasoning before commitment.

### Step 4: Write judges to workspace
Save each judge prompt to `judges/judge-E{N}-{name}.md`. Save code-based checks to `judges/code-E{N}-{name}.sh` or inline in the classification doc.

### Enhancement: write-judge-prompt (Hamel)
If available, invoke `write-judge-prompt` for each judge-based eval. It enforces the 4-component structure and provides guidance on model selection and what to feed the judge.

**Output:** `eval-classification.md` + `judges/` directory with all evaluators.
**State:** Mark phase 5 complete. Record code_eval_count, judge_eval_count in state.json. Advance to phase 6.

---

## Phase 6: Validate Judges

Calibrate LLM judges against human labels. Code-based evals skip this phase (they're deterministic).

### Step 1: Run judges on dev split
For each LLM judge, run it on every fixture in the dev split. Compare judge verdicts to human labels.

### Step 2: Compute TPR and TNR per judge

```
TPR = (judge says Pass AND human says Pass) / (human says Pass)
TNR = (judge says Fail AND human says Fail) / (human says Fail)
```

**Target: TPR >90% AND TNR >90%.** With 30-40 total fixtures (~15 dev), these are directional — treat them as signal, not proof.

### Step 3: Inspect disagreements
For each case where judge disagrees with human:

| Type | Judge | Human | Action |
|------|-------|-------|--------|
| False Pass | Pass | Fail | Judge too lenient → strengthen Fail definitions or add edge-case examples |
| False Fail | Fail | Pass | Judge too strict → clarify Pass definitions or adjust examples |

### Step 4: Iterate
Refine judge prompts and re-run on dev set. Repeat until TPR and TNR stabilize.

**If alignment stalls:**
- Both low → use a more capable model for the judge
- One metric low → inspect disagreements for that metric specifically
- Both plateau below 80% → decompose the criterion into smaller, more atomic checks

### Step 5: Final measurement on test split
Run each judge **exactly once** on the held-out test set. Record final TPR and TNR. Do NOT iterate after seeing test results.

Write `judge-validation-report.md`:
```
| Judge | Dev TPR | Dev TNR | Test TPR | Test TNR | Status |
|-------|---------|---------|----------|----------|--------|
| E6: Artifact | 92% | 88% | 89% | 85% | APPROVED |
```

### Gate: Gulf 2 Exit
Generate `gate-report-gulf-2.md`:
- Judge classification (code vs LLM)
- Validation results (TPR/TNR per judge)
- Code-based eval test results
- Decision: "Approve these judges for autoresearch?"

**STOP. Wait for user approval before Phase 7.**

### Enhancement: validate-evaluator (Hamel)
If available, invoke `validate-evaluator` for deeper calibration. Adaptations for skills:
- Hamel targets ~100 labeled examples → use 30-40 for skills
- Hamel recommends Rogan-Gladen correction → skip for skills (not enough data for meaningful correction)
- Hamel recommends bootstrap CI → skip for skills (same reason)
- The core protocol applies: dev iteration → test once → report TPR/TNR

**Output:** `judge-validation-report.md` + `gate-report-gulf-2.md` in workspace.
**State:** Mark phase 6 complete. Record validation results.

---

## Phase 7: AutoResearch Loop

The Karpathy-style mutation-test-keep/discard cycle. Requires a populated `eval-suite.md` (from Phase 3 or manually created).

### The Loop

```
1. Read eval-suite.md for criteria and fixtures
2. Run baseline: invoke skill on all fixtures, score against all evals → Experiment 0
3. Record in results.json, results.tsv, changelog.md
4. LOOP:
   a. Analyze failures: which evals fail on which fixtures? What pattern?
   b. Hypothesize: what ONE change to SKILL.md would fix the failing pattern?
   c. Mutate: make the change to a copy (<skill>-optimized.md)
   d. Test: run mutated skill on all fixtures, score against all evals
   e. Decide:
      - Score improved → KEEP. Update baseline. Record in changelog.
      - Score same/worse → DISCARD. Revert. Record in changelog.
   f. Update results.json, results.tsv, dashboard refreshes automatically
   g. Repeat until: all evals pass, or budget exhausted (default: 5 experiments)
```

### Changelog Format
```markdown
## Experiment N — [keep/discard]
**Score:** X/Y (Z%)
**Change:** [what was mutated in the skill]
**Reasoning:** [why this change should help]
**Result:** [what happened — which evals flipped]
**Failing outputs:** [remaining failures, or "None"]
```

### Results Schema
Append to `results.json.experiments[]`:
```json
{"id":N,"score":X,"max_score":Y,"pass_rate":Z,"status":"keep|discard|baseline","description":"...","changes":[{"type":"added|modified|removed","location":"section or line ref","snippet":"the actual text changed"}]}
```
The `changes` array captures what was mutated — the dashboard renders these as expandable details per experiment. Keep snippets short (1-3 lines each). The `location` field says WHERE in the skill, `snippet` shows WHAT changed.
Append to `results.tsv`:
```
N\tX\tY\tZ%\tkeep\tdescription
```

### Key Rules
- **One mutation per experiment.** Multi-variable changes make attribution impossible.
- **Score the MUTATED copy, not the original.** Keep original SKILL.md untouched as the baseline.
- **If score improves, the mutated copy becomes the new baseline** for next experiment.
- **Budget cap: ask the user before starting.** Present three options:
  - **Quick (3 experiments)** — for low-priority skills or token-conscious users. Targets the 2-3 worst evals only.
  - **Standard (5 experiments)** — default. Covers the major failure categories.
  - **Deep (8-10 experiments)** — for critical skills the user wants to fully optimize. Extends into edge cases and sparse-trace handling.

  Say: "How many experiments do you want to run? Quick (3), Standard (5), or Deep (8-10)? Quick is best for low-priority skills, Deep for skills you use daily."
- **Target baseline 60-80%.** If baseline >90%, evals are too easy — harden them first.

### Enhancement: skill-creator subagents
If skill-creator is available, use its specialized subagents to strengthen the loop:

**Grader** — After each experiment run, dispatch the grader subagent with the eval expectations and skill output. It returns structured pass/fail verdicts with evidence, verifies claims from the output, AND critiques the evals themselves (flags assertions that would pass bad outputs). Provide: expectations list, output files, transcript.

**Comparator** — For rigorous A/B testing between the baseline and mutated skill, dispatch the comparator with both outputs (blinded — it doesn't know which is which). It scores on content + structure rubrics and picks a winner. Use when score deltas are small and you need confidence the mutation actually helped.

**Analyzer** — After the comparator picks a winner, dispatch the analyzer with both skills + transcripts. It explains WHY the winner won and produces prioritized improvement suggestions. Use to inform your next mutation hypothesis.

### Serving the Dashboard
```bash
cd autoresearch-<skill>/
python3 -m http.server 8080
# Open http://localhost:8080/dashboard.html
```

**State:** Update after each experiment. Mark phase 7 complete when loop ends.

---

## Gotchas

1. **Don't skip Gulf 1.** A 100% score on narrow evals is an artifact, not evidence of quality. Comprehension first, always.

2. **Error analysis cannot be automated.** Phase 3 requires the human to read outputs. An LLM doing it for you is comprehension theater.

3. **100% on narrow evals ≠ quality.** Target 60-80% baseline. If baseline passes everything, harden your evals.

4. **Let categories emerge.** In Phase 3, don't start with existing eval categories. Fresh eyes, fresh taxonomy.

5. **One mutation per experiment.** Multi-variable changes make attribution impossible.

6. **Keep rate matters more than final score.** 60% → 85% through 4 keeps out of 10 teaches more than 95% → 100% in 1.

7. **High Phase 3 fail rates are expected.** A 60-100% fail rate in error analysis means your fixtures are diverse and your reviewer is rigorous — this is healthy. It produces a rich failure taxonomy that drives meaningful evals. A low fail rate (<30%) usually means the fixtures are too easy or the reviewer is too generous.

8. **Dashboard needs HTTP serving.** `python3 -m http.server 8080` from the autoresearch directory. Direct `file://` won't work (CORS). Dashboard also requires internet for Chart.js CDN — if blocked, download `chart.umd.min.js` locally and update the script src.

9. **Never run two sessions on the same skill.** state.json has no locking. Parallel sessions will overwrite each other's results, producing corrupted state and lost experiments.

10. **"Invoke" means "read and follow."** When this skill says "invoke eval-audit" or "dispatch the grader subagent," it means: read that skill's SKILL.md and follow its instructions inline. Not all agents support direct skill invocation — reading the instructions works everywhere.

## When AutoRefine Doesn't Help

These are failure modes of autorefine itself. Know when to step back.

1. **Everything scores "At Standard" but the skill is still bad.** The design audit checks structural patterns (Gotchas, voice, disclosure). A well-structured skill can still produce wrong outputs. If Phase 1 passes but users complain, skip to Phase 3 (error analysis) — the problem is in the logic, not the structure.

2. **Phase 3 fail rate is very low (<20%).** This usually means your fixtures aren't diverse enough, or you're being too generous in review. Add harder fixtures — edge cases, adversarial inputs, inputs from different domains. If fail rate is still low, the skill may actually be good and autorefine isn't needed.

3. **AutoResearch loop plateaus — no improvement after 3+ experiments.** Your evals may not be discriminating enough (too easy or too binary to capture nuance). Or the skill's failure mode requires architectural change, not prompt mutation. Consider: rewriting the skill from scratch vs. mutating it, or adding new eval dimensions you haven't measured.

4. **Fixtures don't represent real usage.** If all your test inputs are clean, well-formatted examples but real users send messy, ambiguous inputs, the autoresearch loop optimizes for the wrong surface. Include at least 3-5 "ugly" real-world inputs in your fixture set.

## References

- `references.md` — Read when: user asks "why this order", "why can't I skip to autoresearch", or needs the v2.0 audit rubric details
