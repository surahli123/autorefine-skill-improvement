# AutoRefine — Gulf 2: Specification

Phases 4-6. Read when: Gulf 1 gate approved, entering Phases 4-6, or looping back from Phase 7.

Downstream phase-entry contract: on entry to Phases 4-6, initialize pattern-aware context from `state.json.phase1_context.selected_skill_pattern` and `state.json.phase1_context.selected_eval_strategy_id`. Downstream phase-entry contract: on entry to Phases 4-6, initialize pattern-aware context from `state.json.phase1_context.selected_skill_pattern`. If only Phase 1 output is loaded in the current context, read the same canonical IDs from the top-level `selected_skill_pattern` and `selected_eval_strategy_id` fields in `design-audit.md` and hydrate the loaded run context from that persisted output before continuing. If only Phase 1 output is loaded in the current context, read the same canonical ID from the top-level `selected_skill_pattern` field in `design-audit.md` and hydrate the loaded run context from that persisted output before continuing. If only the pattern is available, resolve the missing strategy through `references.md > Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector` before continuing. Once restored, route Phase 4-6 through the matching strategy row in `references.md > Skill Pattern Eval Strategy > Strategy Definitions`. The selected strategy is the active downstream execution route for fixture expansion, eval classification, judge writing, and validation, not a soft preference layered on top of a generic path. Do not trigger pattern classification again while entering these phases; rerun Phase 1 Step 0 only if the persisted pattern is missing or mismatched with `state.json.skill_pattern`.

---

## Phase 4: Expand Inputs

**Step 1:** Count labeled fixtures from Phase 3.
**Step 2:** Define 3 failure-prone dimensions from the taxonomy. Read the current run's `selected_eval_strategy_id` failure focus from `references.md > Skill Pattern Eval Strategy > Strategy Definitions` and use that strategy route as the canonical source for choosing the dimensions. Do not build a generic dimension mix once the strategy is resolved. Format: `references.md > Dimension Template`.
**Step 3:** Generate fixtures via dimension tuples. Draft 15-20 with user, LLM generates 10 more. Target 30-40 total.
**Step 4:** Split into train (~12%) / dev (~35%) / test (~35%) / adversarial_holdout (~18%). Train = few-shot examples only. Dev = mutation/refinement scoring. Test = final Phase 6 judge measurement. `adversarial_holdout` = dedicated evaluation-only split, hidden from mutation/refinement until Session Close. Use the stable `input_id`s from `[workspace]/input-sets.json` when assigning split membership. Write `fixtures-manifest.md` with counts plus the exact `input_id` list for each split, and emit split metadata using `references.md > Evaluation Split Metadata Schema`. Also record `mutation_refinement_split_datasets[]` snapshots in `evaluation_metadata.config.mutation_refinement_split_datasets[]` for every split used during mutation/refinement (`train`, `dev`, `test`) so downstream consumers can validate the boundary without reopening the workspace. Also persist `references.md > Mutation-Stage Split Access Policy` in `evaluation_metadata.config.mutation_stage_split_access_policy`: Phase 7 mutation-time operations may read `dev` only. `train`, `test`, and `adversarial_holdout` are inaccessible at mutation time. Mirror that exact object into `state.json.mutation_stage_split_access_policy` as the active Phase 7 dataset-read gate so entry, resume, scoring, regression checks, and same-run version comparison all reuse the same persisted policy rather than reconstructing it from prose. Before Phase 4 exits, validate that the holdout `input_id` list has zero overlap with every mutation/refinement snapshot. If any shared `input_id` appears, fail Phase 4 immediately and log a flagged holdout-boundary error instead of continuing. Never renumber an existing set on reruns, and never collapse `adversarial_holdout` back into `dev` or `test`.

**Output:** `fixtures-manifest.md`. **State:** advance to Phase 5.

---

## Phase 5: Write Judges

**Step 1: Classify evals** as code-based (counting, regex, field presence -> bash/python) or agent-as-judge (semantic judgment -> judge prompt file). Exhaust code options first. Before writing the split, read the current run's `selected_eval_strategy_id` in `references.md > Skill Pattern Eval Strategy > Strategy Definitions` and use that strategy's Phase 5/6 tactic bundle to decide which evals should dominate. The matching Phase 5/6 tactic bundle is the route, not an advisory weighting hint. Write `eval-classification.md`.

**Step 1b: Assign eval category tags (NEW — v4.0).** For each eval in eval-suite.md, assign a `Category` tag from the following values:

| Category | Measures | Examples |
|----------|----------|----------|
| `structural` | Presence of required sections/artifacts | "Gotchas section exists", "Has 3+ examples" |
| `task-completion` | Whether the skill completes its intended task | "Output addresses primary entity", "All steps executed" |
| `quality` | Output quality, style, rubric adherence | "Voice is instructional", "Disclosure is progressive" |

Write the tag inline in eval-suite.md using per-eval metadata:
```
EVAL 1: [Gotchas Section Present]
Type: code-based | Category: structural
...

EVAL 2: [Output Addresses Primary Entity]
Type: agent-as-judge | Category: task-completion
...
```

These tags enable per-category score reporting at Session Close (see `SKILL-gulf3.md > Session Close`). Schema details: `references.md > Eval Category Tags Schema`.

**Step 2: Build code-based evaluators.** One-liner or short script per eval. Test on 3 dev fixtures.

**Step 3: Build agent-as-judge prompts.** Each judge has 4 components: task+criterion, Pass/Fail definitions, 3 few-shot examples (TRAIN split only — never dev/test), critique-before-verdict output format. The coding agent itself IS the judge — no external API needed. **Anti-rigidity rule:** Score on outcome achievement, not path matching. A judge that fails outputs for using different structure or wording than the reference is penalizing creativity, not catching errors. Multi-judge activation is `category + instability`, not category alone. `structural` evals remain single-judge. `task-completion` stays single-judge by default and escalates to panel mode only when `phase6_dev_fold_metrics` or human calibration shows instability. `quality` evals are eligible for panel review, but activate panel mode only when `phase6_dev_fold_metrics` or human calibration shows instability, or when the user explicitly forces it. When panel mode is used, write 2+ independent prompts with different framing and record `agreement_rule: unanimous` in the eval metadata so a single judge cannot decide the verdict alone. Keep the panel contract consistent with `references.md > Multi-Judge Verdict Schema`. Full template: `references.md > Judge Prompt Template`.

**Step 4: Write to workspace.** Save single-judge prompts to `judges/judge-E{N}-{name}.md`. Save multi-judge prompt bundles to `judges/judge-E{N}-a-{name}.md`, `judges/judge-E{N}-b-{name}.md`, etc., plus any code eval to `judges/code-E{N}-{name}.sh`.

**Output:** `eval-classification.md` + `judges/` directory. **State:** advance to Phase 6.

---

## Phase 6: Validate Judges

Calibrate agent-as-judge evaluators against human labels. Code-based evals skip (deterministic).

**Steps 1-4 (dev split — human reviews):** Run each judge on dev split. Before the first validation pass, derive deterministic 3-fold assignments for the dev split from stable input data: `stable_fold_key = <input_id>|<content_hash>`. Every persisted Phase 6 dev record must also carry `source_sample_group_id`, derived from that same frozen sample identity: `source_sample_group_id = stable_fold_key`. Reuse the same `source_sample_group_id` for every dev record emitted from the same underlying sample across judges, disagreement analysis, and reruns. Sort the unique `source_sample_group_id` values for the frozen dev split and assign groups round-robin (`fold_1`, `fold_2`, `fold_3`, repeating). Every `source_sample_group_id` must land in exactly one fold, and every persisted Phase 6 dev record in that group inherits the same `fold_id`. Do not derive folds from runtime order, directory listing order, batch-review order, or randomness. Do not derive sample-group IDs from runtime order, directory listing order, batch-review order, or randomness. Present judge verdicts vs human labels using batch review format (`references.md > Batch Review Format`). Compute per-fold TPR/TNR plus overall mean/range, but treat the aggregate `confusion_matrix` plus `confusion_examples` on each `validation_results[]` row as the primary Phase 6 trust surface for false-pass / false-fail review. Keep `phase6_dev_fold_metrics` plus `aggregated_tpr_tnr_summary` as the secondary stability diagnostic. Inspect disagreements — False Pass → strengthen Fail defs; False Fail → clarify Pass defs. Iterate until stable. Formulas + fold contract: `references.md > TPR/TNR Reference`.

**Step 5 (test split — automated, NO human review):** Final measurement on test split. Run once, record, do NOT iterate. The human does NOT see test examples, and `adversarial_holdout` remains untouched because it is reserved for evaluation-only Session Close validation. Write `judge-validation-report.md`. Write the finalized fold map into `judge-validation-report.md` as `phase6_dev_fold_assignments` so later reruns can prove they used the same cross-validation boundary.

**Step 6: Generate judge confidence cards.** For each agent-as-judge eval, generate a confidence card showing the aggregate `confusion_matrix`, representative `confusion_examples`, TPR/TNR interpretation, and known blind spots. Review `confusion_matrix` / `confusion_examples` first, then use `phase6_dev_fold_metrics` plus `aggregated_tpr_tnr_summary` to judge stability across folds. Template: `references.md > Judge Confidence Card Template`. Walk the human through each card with narration. If the `aggregated_tpr_tnr_summary` range implies a TPR-TNR gap > 20 points, flag the asymmetry explicitly.

### Gate: Gulf 2 Exit
Generate `gate-report-gulf-2.md` with: classification, TPR/TNR per judge, code eval results. Append to session-log.json: `{"phase":"gate_2","type":"gate_decision","detail":"APPROVED"}` (or REJECTED). **Override logging:** if user rejects judges, also append: `{"phase":"gate_2","type":"override","detail":"...","reason":"..."}`

**STOP. Wait for user approval.**

**State:** Mark Phase 6 complete.

---

After Gulf 2 gate is approved → read `SKILL-gulf3.md` for Phase 7 + Session Close.
