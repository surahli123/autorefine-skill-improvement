# Execution Plan: Gate-Aware Gulf Campaign Orchestrator

## Purpose

Turn `autorefine/scripts/run-campaign.py` from a report-only campaign analyzer into a gate-aware Gulf stage coordinator.

The orchestrator should still be conservative in V1: it may prepare and report Gulf work, but it must not claim that Gulf 1, Gulf 2, or Gulf 3 is complete unless the required artifacts and human gates exist. Its job is to make the next legal action obvious for each skill or skill-combination target.

## Current Problem

`run-campaign.py` currently validates a campaign manifest, schedules independent/dependent/clustered skills, audits adjacency, and emits `gulf_analysis` work packets. That answers "which skills look related?" but not "where is each target in the Gulf pipeline, and what can safely run next?"

Root cause: Gulf stages are modeled as descriptive fields inside `gulf_analysis`, not as first-class orchestration states with inputs, outputs, gates, and runnable next actions.

## Goals

- Add a first-class `execution_plan` to the campaign report.
- Represent every standalone skill and every combination candidate as a target.
- Give every target explicit Gulf 1, Gulf 2, and Gulf 3 stage states.
- Schedule ready stages safely across independent, dependent, and clustered targets.
- Preserve AutoRefine trust boundaries:
  - Gulf 1 requires human-reviewed error analysis.
  - Gulf 2 requires approved eval fixtures and judge validation.
  - Gulf 3 Full mode requires approved Gulf 1 + Gulf 2 gates.
  - Gulf 3 Mini mode is allowed only when `quick_start.completed = true` and both Gulf gates are still pending; it is directional, not trusted.
  - Search retrieval keeps ranked `doc_id` metrics as the primary oracle.
- Keep V1 report/planning-first unless the CLI is explicitly run in a future execution mode.

## Non-Goals

- Do not rewrite or merge skills automatically.
- Do not execute Phase 7 by default.
- Do not bypass Gulf human gates.
- Do not move package/bundle hygiene back into scope.
- Do not introduce a new runtime language or dependency.

## Core Model

### Campaign Target

A target is the unit that can move through Gulf 1, Gulf 2, and Gulf 3.

Target types:

- `single_skill`: improve one existing skill in isolation.
- `combine_candidate`: evaluate whether exactly two skills should merge in V1.
- `parametric_parent_candidate`: evaluate whether adjacent skills should share a parent/template plus variants.
- `keep_separate`: record why a pair should not share an execution target.

V1 target grouping is intentionally pairwise. If analysis finds `A+B` and `B+C`, the orchestrator creates two separate pair targets and assigns both an `overlap_group_id` based on the shared source skill. It must not invent an `A+B+C` target automatically. Source-skill locks prevent overlapping pair targets from running concurrently. A later V2 can add deterministic connected-component grouping after the pairwise flow is proven.

Each executable target should include:

```json
{
  "target_id": "python_testing__test_driven_development",
  "target_type": "parametric_parent_candidate",
  "source_skill_ids": ["python_testing", "test_driven_development"],
  "overlap_group_id": null,
  "workspace_path": ".../campaign-python_testing__test_driven_development",
  "lock_id": "target:python_testing__test_driven_development",
  "recommendation": "extract_parametric_parent",
  "stages": []
}
```

### Gulf Stage

Each stage should expose status, blocking reason, expected artifacts, and next action.

```json
{
  "stage": "gulf1_comprehension",
  "status": "needs_human_gate",
  "blocked_by": [],
  "inputs": ["skill-under-test/SKILL.md"],
  "expected_outputs": [
    "contract/success-examples.jsonl",
    "contract/failure-examples.jsonl",
    "contract/do-not-trigger-examples.jsonl",
    "design-audit.md",
    "eval-suite.md",
    "gate-report-gulf-1.md"
  ],
  "gate": {
    "name": "gulf_1",
    "required": true,
    "approval_source": "state.json.gates.gulf_1"
  },
  "mode": "full",
  "trust_level": "trusted_after_gate",
  "next_action": "prepare_gulf1_workspace"
}
```

Allowed statuses:

- `blocked`
- `ready`
- `running`
- `needs_human_gate`
- `complete`
- `skipped`

## Stage Semantics

### Gulf 1: Comprehension

Gulf 1 answers: "Do we understand what this skill or candidate target is supposed to do, and where it fails?"

For `single_skill` targets:

- Copy the source skill into `[workspace]/skill-under-test/SKILL.md`.
- Detect or prepare contract examples:
  - `success-examples.jsonl`
  - `failure-examples.jsonl`
  - `do-not-trigger-examples.jsonl`
- Optionally import recorded traces through `records-to-gulf1.py`.
- Produce or expect:
  - `design-audit.md`
  - `eval-suite.md`
  - `gate-report-gulf-1.md`

For `combine_candidate` and `parametric_parent_candidate` targets, V1 computes the future campaign workspace shape but does not create it in `plan-only` mode:

- Future workspace layout:
  - `sources/<skill_id>/SKILL.md` for each source skill.
  - `skill-under-test/SKILL.md` as the candidate synthesis surface.
  - `comparison-matrix.md` describing shared intent and distinct responsibilities.
- Gulf 1 must compare:
  - source skill A behavior
  - source skill B behavior
  - proposed combined or parent/variant behavior
- The output should answer:
  - What behavior must remain separate?
  - What behavior is duplicated?
  - What trigger boundaries must be protected?
  - What contract examples are missing?

Gulf 1 exits only when `state.json.gates.gulf_1 = "approved"` or equivalent gate evidence exists. Otherwise the target remains `needs_human_gate`.

### Gulf 2: Specification

Gulf 2 answers: "Do we have validated fixtures and judges that can prove improvement without hiding regressions?"

Gulf 2 is blocked until Gulf 1 is approved.

For all executable targets, expect:

- `fixtures-manifest.md`
- `eval-classification.md`
- `judges/`
- `judge-validation-report.md`
- `gate-report-gulf-2.md`

For combined or parent targets, Gulf 2 must include these eval categories:

- `routing_boundaries`
- `behavior_parity`
- `negative_trigger_examples`
- `regression_suite`
- `shared_fixture_coverage`
- `parametric_variant_coverage`

For search retrieval targets:

- The primary oracle must be ranked `doc_id` retrieval scoring.
- Explanation quality is secondary only.
- The plan must preserve `search_retrieval_v1` experiment contract fields:
  - primary metric, such as `ndcg_at_5`
  - stable identity source, `doc_id`
  - companion metric, such as `recall_at_5`

Gulf 2 exits only when `state.json.gates.gulf_2 = "approved"` or equivalent gate evidence exists.

### Gulf 3: Generalization

Gulf 3 answers: "Can the approved target improve on trusted dev scoring without behavioral regression, and can the final result pass holdout/trust checks?"

Gulf 3 has two legal modes:

- `full`: allowed only when `state.json.gates.gulf_1 = "approved"` and `state.json.gates.gulf_2 = "approved"`.
- `mini`: allowed only when `state.json.quick_start.completed = true` and both gates are still `"pending"`. Mini mode uses directional bootstrap evals and must never be reported as trusted promotion evidence.

Expected Phase 7 artifacts:

- `runs/run_*/experiment-contract.json`
- `runs/run_*/iteration_000/eval_results.json`
- `runs/run_*/iteration_*/mutation.md`
- `results.json`
- `session-log.json`
- `session_close_holdout/variant_results.json`

Trusted Gulf 3 completion must be read from the final promotion surface:

- `session_close_holdout/variant_results.json#trust_gate`
- `trust_gate.outcome` must be one of `promote`, `review_required`, or `block`.
- Precedence remains `block` > `review_required` > `promote`.
- `state.json.final_only_evaluation` is only an idempotence/ref surface; it may point to the holdout artifact but must not be treated as the authoritative trust result.

The orchestrator must not infer trusted completion from the existence of `results.json`, `session-log.json`, run directories, or any challenger artifact.

For V1, the orchestrator should only produce the correct `phase7_command` and stage readiness. Actual execution should remain off by default.

## Execution Plan Shape

Add this top-level object to the campaign report:

```json
{
  "execution_plan": {
    "mode": "plan_only",
    "summary": {
      "target_count": 8,
      "ready_stage_count": 3,
      "blocked_stage_count": 12,
      "human_gate_count": 5
    },
    "targets": [],
    "stage_schedule": []
  }
}
```

### Stage Schedule

The existing `schedule_campaign()` handles skill-level ordering. Add a stage-level scheduler:

- Gulf 1 can run in parallel for independent targets.
- Gulf 2 can run only after that target's Gulf 1 gate is approved.
- Gulf 3 Full mode can run only after that target's Gulf 2 gate is approved.
- Gulf 3 Mini mode can run only when Quick Start completed and both Gulf gates are pending.
- Same `cluster_id` runs sequentially under a cluster lock.
- Targets that share any mutable path must fail preflight.
- Combination targets lock all source skills so no related target mutates the same skill concurrently.

Example:

```json
{
  "stage_schedule": [
    {
      "step": 1,
      "mode": "parallel",
      "lock_id": "parallel",
      "target_ids": ["python_testing", "idea_refine"],
      "stage": "gulf1_comprehension"
    },
    {
      "step": 2,
      "mode": "sequential",
      "lock_id": "cluster:python_quality",
      "target_ids": ["python_testing__test_driven_development"],
      "stage": "gulf1_comprehension"
    }
  ]
}
```

## CLI Contract

Keep current default behavior:

```bash
python3 autorefine/scripts/run-campaign.py --manifest campaign.json
```

Default mode:

- validate manifest
- build campaign graph
- build Gulf execution plan
- write JSON/HTML if requested
- execute nothing

Future execution flags:

```bash
--stage-mode plan-only
--stage-mode prepare-workspaces
--stage-mode run-ready-stages
```

V1 should implement `plan-only`. `prepare-workspaces` can be added next if the stage schema proves stable.

## Implementation Steps

### Step 1: Add Tests First

Add tests to `autorefine/tests/test_campaign_orchestrator_py.py`:

- `test_execution_plan_blocks_gulf2_until_gulf1_gate`
- `test_execution_plan_blocks_gulf3_until_gulf2_gate`
- `test_execution_plan_allows_mini_mode_when_quick_start_completed`
- `test_execution_plan_computes_combination_target_workspace_path`
- `test_execution_plan_marks_overlapping_pair_targets`
- `test_execution_plan_schedules_independent_gulf1_targets_in_parallel`
- `test_execution_plan_serializes_clustered_targets`
- `test_execution_plan_preserves_search_primary_doc_id_metric`
- `test_execution_plan_trusts_only_session_close_trust_gate_for_gulf3_completion`
- `test_html_report_renders_execution_plan_stage_status`

### Step 2: Add Target Builder

New functions:

- `build_campaign_targets(manifest, gulf_analysis)`
- `build_single_skill_target(skill)`
- `build_candidate_target(candidate_group, skills)`
- `target_id_for(skill_ids)`

The target builder should avoid duplicate work:

- every skill gets one `single_skill` target
- each non-`keep_separate` candidate group gets one candidate target
- V1 candidate targets are pairwise only; overlapping pairs get an `overlap_group_id`, not an auto-created multi-skill target
- `keep_separate` pairs remain evidence in `gulf_analysis.pair_analysis`, not executable targets

### Step 3: Add Gate Detection

New functions:

- `read_workspace_state(workspace_path)`
- `gate_status(workspace_path, gate_name)`
- `artifact_exists(workspace_path, relative_path)`
- `read_trust_gate(workspace_path)`

Gate detection should be fail-soft:

- missing workspace -> stage may be `ready` for Gulf 1 preparation
- missing state -> gate is not approved
- malformed state -> target status `blocked` with reason
- missing `session_close_holdout/variant_results.json` -> Gulf 3 is not trusted-complete
- malformed final holdout artifact -> Gulf 3 status `blocked` with reason

### Step 4: Add Stage Planner

New functions:

- `build_execution_plan(manifest, gulf_analysis)`
- `build_target_stage_plan(target)`
- `build_gulf1_stage(target)`
- `build_gulf2_stage(target)`
- `build_gulf3_stage(target)`

Stage readiness rules:

- Gulf 1:
  - `complete` if Gulf 1 gate approved
  - `needs_human_gate` if outputs exist but gate is pending
  - `ready` if workspace can be prepared
- Gulf 2:
  - `blocked` if Gulf 1 not approved
  - `complete` if Gulf 2 gate approved
  - `needs_human_gate` if outputs exist but gate is pending
  - `ready` if Gulf 1 approved
- Gulf 3:
  - `ready` in Full mode if both gates are approved and trusted completion is absent
  - `ready` in Mini mode if `quick_start.completed = true` and both gates are pending
  - `blocked` if neither Full nor Mini mode conditions are met
  - `complete` with `trust_level = "trusted"` only when `session_close_holdout/variant_results.json#trust_gate.outcome` is present
  - `complete` with `trust_level = "directional"` only for a terminal Mini-mode run, and never as promotion evidence

### Step 5: Add Stage Scheduler

New functions:

- `schedule_ready_stages(execution_plan)`
- `target_locks(target)`
- `stage_dependencies(target)`

Scheduling rules:

- schedule only `ready` stages
- respect target source locks
- respect `cluster_id`
- respect `depends_on`
- do not schedule two stages for the same target in one step

### Step 6: Render HTML

Add sections:

- Execution summary
- Target table
- Stage status table
- Ready next actions
- Blocked stages and reasons

The current Gulf work-packet section can remain, but the new execution plan should become the primary view.

### Step 7: Keep JSON Backward Compatible

Keep existing keys:

- `skills`
- `schedule`
- `adjacency_audit`
- `gulf_analysis`

Add:

- `execution_plan`

Do not rename current fields in the first patch.

## Acceptance Criteria

- Manifest validation still rejects shared mutable paths.
- Existing campaign tests remain green.
- New execution-plan tests prove Gulf 2 and Gulf 3 cannot run before gates.
- New execution-plan tests prove Mini mode is reported as directional when Quick Start completed and gates remain pending.
- New execution-plan tests prove trusted Gulf 3 completion requires the final holdout `trust_gate`.
- HTML clearly shows why each target is ready, blocked, complete, or waiting for human approval.
- Local 8-skill smoke report renders both candidate recommendations and gate-aware stage status.
- No Phase 7 command executes unless a future explicit execution flag is added.
- Search retrieval primary metric remains ranked `doc_id` scoring; explanation quality cannot override it.

## Risks

- The stage planner may become too large inside one script.
  - Mitigation: keep pure functions first; split later only if complexity grows.
- Gate detection may accidentally treat missing artifacts as complete.
  - Mitigation: trusted `complete` requires `session_close_holdout/variant_results.json#trust_gate.outcome`.
- Combination targets may over-lock and reduce parallelism.
  - Mitigation: V1 is pairwise and uses source-skill locks; optimize after evidence.
- Mini mode may be confused with trusted improvement.
  - Mitigation: emit `trust_level = "directional"` and never count Mini completion as promotion.
- HTML could become noisy.
  - Mitigation: show summary first, then expandable details later if needed.

## Recommended First Patch

Implement only `plan-only` execution planning:

1. Add tests for gate blocking and target/stage shape.
2. Add target builder.
3. Add stage planner.
4. Add `execution_plan` to JSON.
5. Render a compact execution-plan table in HTML.
6. Regenerate the local 8-skill report.

Do not implement workspace preparation or command execution in the first patch.
