# AutoRefine References

Templates, schemas, methodology rationale, and detailed rubrics. SKILL.md references specific sections — read on demand, not upfront.

---

## Workspace Schemas

Read when: Initialize Workspace or resuming a session.

### state.json
```json
{"schema_version":4,"skill_name":"<name>","skill_path":"<path>","original_skill_path":"<path>","workspace_path":"<path>","started":"<today>","current_phase":1,"current_gulf":1,"phases":{},"gates":{"gulf_1":"pending","gulf_2":"pending"},"hamel_available":false,"loop_iteration":0,"locked_judges":[],"memory_path":null,"checkpoint":null,"consecutive_discards":0,"circuit_breaker":null,"current_run_path":null}
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

### results.json
```json
{"skill_name":"<name>","status":"running","current_experiment":0,"baseline_score":null,"best_score":null,"experiments":[],"eval_breakdown":[]}
```
Each experiment in `experiments[]`:
```json
{"id":N,"score":X,"max_score":Y,"pass_rate":Z,"status":"keep|discard|baseline","description":"...","changes":[{"type":"added|modified|removed","location":"section","snippet":"1-3 lines"}],"eval_results":[{"eval":"E1","result":"pass"},{"eval":"E2","result":"fail"}],"regression_check":null,"discard_autopsy":null}
```
- `eval_results`: per-eval Pass/Fail for this experiment. Used by regression checks to compare across experiments.
- `regression_check`: null (no check run), or `{"passed":true,"details":"..."}`, or `{"passed":false,"regressions":[{"experiment":1,"eval":"E2","was":"pass","now":"fail","detail":"..."}]}`
- `discard_autopsy`: null (experiment kept or baseline), or `{"classification":"wrong_target|wrong_params|wrong_type","reasoning":"1-sentence explanation"}`. Set after discard in Phase 7 step 2f. See `Discard Autopsy Heuristics` section.

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
- Checkpoint: `{"phase":"3","type":"checkpoint","detail":"Saved checkpoint at Phase 3 boundary. Resume prompt written."}`
- Regression: `{"phase":"7","type":"regression","experiment":3,"detail":"E2 regressed: was pass (exp 1), now fail. Gotcha section removed by mutation.","user_action":"discard"}`
- Circuit breaker: `{"phase":"7","type":"circuit_breaker","diagnosis":"content_ceiling|strategy_review","consecutive_discards":3,"experiments":[3,4,5]}`
- Circuit breaker override: `{"phase":"7","type":"circuit_breaker_override","reason":"user chose to continue"}`
- Discard autopsy: `{"phase":"7","type":"discard_autopsy","experiment":N,"classification":"wrong_target|wrong_params|wrong_type","reasoning":"1-sentence explanation"}`
- Canonical headings: `{"phase":"7","type":"canonical_headings","sections":["section1","section2","..."]}`
- Iteration write: `{"phase":"7","type":"iteration_write","experiment":N,"path":"runs/run_.../iteration_NNN/"}`
- Derived registry snapshot: `{"phase":"7","type":"derived_registry_snapshot","experiment":N,"sections_explored":{"section1":{"count":2,"best_delta":0.12,"last_tried":3,"autopsy_pattern":"wrong_target"},...},"mutation_types":{"add":3,"modify":2,"delete":1},"diversity_score":0.6}`
- Apply back: `{"type":"apply_back","applied":true,"source":"[workspace]/skill-under-test/SKILL.md","target":"[original-skill-path]/SKILL.md"}`
- Ambient learning: `{"type":"ambient_learning","rules_extracted":2,"diff_size":12}` or `{"type":"ambient_learning","skipped":true,"reason":"full_rewrite","diff_size":180}`

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
{"id":N,"score":X,"max_score":Y,"pass_rate":Z,"status":"keep|discard|baseline","description":"...","changes":[{"type":"added|modified|removed","location":"section","snippet":"1-3 lines"}],"eval_results":[{"eval":"E1","result":"pass"}],"regression_check":null,"discard_autopsy":null}
```

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
3. Output: `Critique: [reasoning]` then `Result: Pass or Fail`

Dispatch as a subagent or evaluate in main context. Run judges sequentially (not parallel) to avoid context contamination.

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
Output: Critique: [reasoning] then Result: Pass or Fail
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
| 1 | `design_audit: "complete"` |
| 2 | `eval_audit: "complete"` |
| 3 | `traces_reviewed, sampled_trace_ids, sampling_strategy, taxonomy_summary` |
| 4 | `fixture_count, pass_count, fail_count, split_sizes` |
| 5 | `code_eval_count, judge_eval_count` |
| 6 | `validation_results` (TPR/TNR per judge) |
| 7 | `current_experiment, best_score, consecutive_discards, circuit_breaker` |

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
    "files_to_read_on_resume": ["state.json", "results.json", "eval-suite.md", "changelog.md"],
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
3. Print resume context: "Resuming from checkpoint: {next_action}"
4. Set `checkpoint` to null (clear the checkpoint — it's been consumed)
5. Proceed from `checkpoint.next_action`

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
3. For each eval: compare current result against the BEST prior result for that eval across kept experiments.
   - If an eval was `pass` in ANY prior kept experiment and is now `fail` → regression detected.
4. Record `regression_check` in the current experiment record.

### Presenting Results

**No regressions:**
"Score: {X}%. Regression check: all prior improvements stable. {Recommend keep/discard based on score}."

**Regressions found:**
"Score: {X}%. **Regression warning:** {N} eval(s) that previously passed now fail:
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
  "pass_rate": 0.75,
  "score": 6,
  "max_score": 8,
  "eval_results": [
    {"eval": "E1", "result": "pass"},
    {"eval": "E2", "result": "fail"}
  ],
  "regression_check": null,
  "discard_autopsy": null
}
```
Fields mirror the experiment record in results.json. `experiment_id` matches the iteration directory number (0 for baseline, 1+ for mutations). Include `regression_check` and `discard_autopsy` when applicable (null otherwise).

**decision.md** — Keep/discard verdict with full reasoning.
```markdown
# Experiment N — [KEEP | DISCARD | BASELINE]

## Score
[X]/[Y] ([Z]%)  |  Delta: [+/-N]pp vs baseline

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
