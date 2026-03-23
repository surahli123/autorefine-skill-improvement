# AutoRefine References

Templates, schemas, methodology rationale, and detailed rubrics. SKILL.md references specific sections — read on demand, not upfront.

---

## Workspace Schemas

Read when: Initialize Workspace or resuming a session.

### state.json
```json
{"schema_version":2,"skill_name":"<name>","skill_path":"<path>","started":"<today>","current_phase":1,"current_gulf":1,"phases":{},"gates":{"gulf_1":"pending","gulf_2":"pending"},"hamel_available":false,"loop_iteration":0,"locked_judges":[],"memory_path":null}
```
- `schema_version`: increment when adding fields (2 for Standard/Deep, 3 for Quick Start)
- `loop_iteration`: tracks Phase 7→5 loop-backs (0 = first run)
- `locked_judges`: judge IDs approved in prior loops — don't re-validate

### results.json
```json
{"skill_name":"<name>","status":"running","current_experiment":0,"baseline_score":null,"best_score":null,"experiments":[],"eval_breakdown":[]}
```
Each experiment in `experiments[]`:
```json
{"id":N,"score":X,"max_score":Y,"pass_rate":Z,"status":"keep|discard|baseline","description":"...","changes":[{"type":"added|modified|removed","location":"section","snippet":"1-3 lines"}]}
```

### results.tsv
Header: `experiment\tscore\tmax_score\tpass_rate\tstatus\tdescription`

### session-log.json
```json
{"skill":"<name>","session_start":"<ISO-timestamp>","entries":[]}
```
Entry types:
- Design audit: `{"phase":"1","type":"design_audit","detail":"Scored 4 dims: Gotchas=Present, Voice=Partial, Disclosure=Missing, Scripts=N/A"}`
- Sampling: `{"phase":"3","type":"sampling","detail":"Selected 8/15 traces, stratified by 3 dimensions"}`
- Consistency flag: `{"phase":"3","type":"consistency_flag","detail":"T03 and T07 match C2, judged differently"}`
- Gate decision: `{"phase":"gate_1","type":"gate_decision","detail":"APPROVED"}`
- Override: `{"phase":"gate_1","type":"override","detail":"Removed E4","reason":"..."}`
- Judge gap: `{"phase":"7","type":"judge_gap","experiment":4,"agent_verdict":"keep","user_verdict":"discard","reason":"..."}`
- Mini observation (Quick Start): `{"phase":"quick_start","step":"observation","type":"mini_observation","detail":"Reviewed 5 traces: 3 pass, 2 fail"}`

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
Critique: [1-2 sentences of reasoning]
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
  "schema_version": 3,
  "skill_name": "<name>",
  "skill_path": "<path>",
  "started": "<today>",
  "current_phase": 0,
  "current_gulf": 1,
  "phases": {"design_audit": "complete"},
  "gates": {"gulf_1": "pending", "gulf_2": "pending"},
  "hamel_available": false,
  "loop_iteration": 0,
  "locked_judges": [],
  "memory_path": null,
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

**Schema migration:** When reading state.json with `schema_version: 2`, treat as legacy — Quick Start not available, proceed with Standard/Deep routing only. No migration needed; schema_version 3 is only written by Quick Start.

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

### Dimension 4: Composable Scripts (if applicable)
- `__all__`, type hints, `Use when:` docstrings, `if __name__` demos.

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
Critique: [why this passes — reference specific evidence]
Result: Pass
```
**NEVER use dev or test examples.** This is data leakage.

**Component 4 — Output format:**
```
Critique: [detailed assessment referencing specific evidence]
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
{"id":N,"score":X,"max_score":Y,"pass_rate":Z,"status":"keep|discard|baseline","description":"...","changes":[{"type":"added|modified|removed","location":"section","snippet":"1-3 lines"}]}
```

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
3. Output: `Critique: [reasoning]` then `Result: Pass or Fail`

Dispatch as a subagent or evaluate in main context. Run judges sequentially (not parallel) to avoid context contamination.

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
| 1 | `design_audit: "complete"` |
| 2 | `eval_audit: "complete"` |
| 3 | `traces_reviewed, sampled_trace_ids, sampling_strategy, taxonomy_summary` |
| 4 | `fixture_count, pass_count, fail_count, split_sizes` |
| 5 | `code_eval_count, judge_eval_count` |
| 6 | `validation_results` (TPR/TNR per judge) |
| 7 | `current_experiment, best_score` |

---

## Confidence-Weighted Scoring

Read when: Phase 7 active.

Formula: `score = sum(weight_i * pass_i) / sum(weight_i)` where `pass_i` is 1 (pass) or 0 (fail).

Weights:
- Code-based evals: `weight = 1.0`
- Agent-as-judge evals: `weight = (TPR + TNR) / 2` from Phase 6 validation

Example: 5 evals, 3 code (weight 1.0 each) + 2 agent (weights 0.92, 0.70). Mutation passes all code evals + fails both agent evals. Score = (1+1+1+0+0) / (1+1+1+0.92+0.70) = 3/4.62 = 64.9%. Without weighting: 3/5 = 60%. The weighting gives less influence to the noisy agent judge (0.70).

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
