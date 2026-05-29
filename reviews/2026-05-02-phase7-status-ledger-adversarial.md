# Codex Adversarial Review — Phase 7 Status Ledger v1.2

**Date:** 2026-05-02
**Target:** `design_phase7_status_ledger.md` v1.2
**Reviewer:** Codex (high reasoning, read-only, fresh context)
**Verdict:** **REVISE**
**Files codex read:** design_phase7_status_ledger.md, autorefine/SKILL.md, autorefine/references/gulf3-generalization.md, autorefine/references.md

---

## BLOCKER

**1. W2 does not actually solve compact recovery.**
The design rejects inline agent behavior because the agent may forget, then chooses "agent invokes at start of every Phase 7 turn" as the trigger ([design_phase7_status_ledger.md:84, :190](#)). That is the same failure mode with a deterministic renderer behind it. **If the agent loses Phase 7 context after compact, why would it remember to open `gulf3-generalization.md` and run Step 0?**

This needs to change: put the trigger in the **root resume/routing path in `autorefine/SKILL.md:80`, before Phase 7 routing**, keyed on `state.json.iteration_state` or `current_run_path`, not only inside the Phase 7 support file. Add a test that asserts the root entrypoint rule exists, not just the Gulf 3 rule.

**2. The ledger can report the proposed decision as if it were final.**
The script reads only `state.json`, `eval_results.json`, and contract files ([:96](#)), and the template renders `decision_breakdown.proposed_decision` as "Decision" ([:141](#)). But Phase 7 allows user accept/override and records the final keep/discard in `results.json` ([gulf3-generalization.md:168, references.md:173](#)).

**Hard question:** if the agent proposed discard and the user kept, should the recovery ledger say discard? It cannot be the status ledger unless it reads `results.json` and distinguishes `proposed_decision` from finalized `experiments[].status`. Add override fixtures.

---

## CONCERN

**1. Path safety is under-specified and `Path(workspace) / ref` is not enough.**
The design says all state paths are relative and "Never trust paths to be absolute" ([:101](#)), while `active_experiment_contract_path` is a workspace artifact ([references.md:86](#)). In Python, joining an absolute child path discards the parent; `../` also escapes unless normalized and checked.

**Concrete fix:** define `resolve_workspace_ref(ref)` that rejects absolute paths and rejects resolved paths outside `workspace.resolve()`. Add tests for absolute refs and `../`.

**2. Contract parsing assumes a field that the schema does not define.**
The design says to read `active_experiment_contract_path` and emit its "one-line success criterion field" ([:128](#)), but `experiment-contract.json` defines `objective`, `primary_metric`, `secondary_metrics`, `thresholds`, `hard_fail_dimensions`, `holdout_policy` — NOT a success-criterion field ([references.md:2731](#)).

**Concrete fix:** render `objective`, `primary_metric.metric_name`, threshold, and hard-fail dimensions from the actual schema. **Question:** is "success contract" meant to be human-readable objective, machine metric contract, or both?

**3. "If the script fails, log and continue manually" weakens the whole gate.**
Step 0 says the ledger anchors run state and re-reads the success contract, but failures are best-effort ([:194](#)). For malformed state or unreadable active contract, continuing manually recreates d1/d5.

**Change the failure policy:** output-write failures can be non-blocking; state parse failures, path escapes, and active contract read failures should BLOCK mutation/test actions until repaired.

---

## SUGGESTION

The strongest part is the reuse of existing `iteration_state.next_action` and `last_eval_results_ref`; those are already canonical runner handoff fields ([references.md:28](#)), so no schema migration is needed.

**Nice-to-have:** add one acceptance criterion that proves compact recovery from the root invocation path, not merely that `phase7-status.md` renders on a real workspace ([:328](#)). The validation should start from a fresh compacted prompt with only the workspace path and require the agent to recover without being told it is in Phase 7.

---

## Why this matters

Three prior reviews (CE + 2 plan-eng-review passes) all calibrated to the design's stated intent and missed BLOCKER #1 entirely. The whole architecture rests on the agent reading SKILL.md routing → routing to gulf3-generalization.md → reading Step 0 → invoking the script. **But routing depends on the agent knowing it's in Phase 7 — which is exactly the state lost on compact.** Codex traced "what does the agent do FIRST after compact?" and found the circular dependency.

This is the canonical case for outside-context adversarial review — same-context reviewers absorb the design's framing and stop questioning the load-bearing assumption.
