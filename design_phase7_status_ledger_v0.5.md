# Design — Phase 7 Status Ledger (v0.5, script-only)

**Status:** Draft v0.5 — locked. Ready to implement.
**Date:** 2026-05-02
**Supersedes:** `design_phase7_status_ledger.md` (v1.3, archived)
**Reason for rescope:** v1.x tried to integrate the ledger into `autorefine/SKILL.md` routing. After 5 review cycles + 2 codex REVISE verdicts, evidence said the existing SKILL.md was never designed for resume-from-workspace entry — every fix exposed another architectural layer to retrofit. v0.5 sidesteps the entire SKILL.md routing problem by shipping the script as a **manual debugging tool** with no agent integration.

---

## 1. Problem (carried over)

User in-house Phase 7 run produced 3 failure modes (d1 context-loss, d4 sub-phase oscillation, d5 contract drift). Grill-me revealed the load-bearing observation: **the user themself got lost.** Mapped to 4 visibility gaps:
- L1: which experiment is active
- L2: what's the agent about to do
- L4: why did the agent decide that
- L6: where do I look to verify

v0.5 hypothesis: a script the **user** can `cat` or run manually solves L1+L2+L4+L6 *for the user* without needing any agent integration. If the ledger format proves useful, v1+ adds agent integration as a follow-up.

---

## 2. Scope

**IN scope (v0.5):**
- One Python script: `autorefine/scripts/render-phase7-status.py`
- Reads `state.json` + `results.json` + `eval_results.json` + contract files in a workspace
- Writes `phase7-status.md` (markdown, overwrites every call)
- Path-safe (rejects absolute / outside-workspace refs)
- Tests for happy path + key graceful-degradation cases
- One short paragraph in `autorefine/docs/troubleshooting.md` documenting "if you get lost, run this script"
- `.gitignore` line for `phase7-status.md`
- `CHANGELOG.md` bullet

**OUT of scope (deferred to v1+):**
- ANY edits to `autorefine/SKILL.md` or `autorefine/references/gulf3-generalization.md`
- Agent-driven invocation (user invokes manually)
- "Compact recovery acceptance criterion" (acceptance #9 from v1.3) — irrelevant if no agent integration
- Graduated failure policy (no SKILL.md rules to gate)
- All cross-run reconciliation, ledger-staleness warnings beyond timestamp
- HTML rendering, file watcher

The line is sharp: v0.5 ships a CLI tool. Period.

---

## 3. Design

### 3a. Script spec

```
File:    autorefine/scripts/render-phase7-status.py
Usage:   python3 render-phase7-status.py [workspace_path]
Output:  [workspace_path]/phase7-status.md (overwrites every call)
Deps:    Python stdlib only (json, pathlib, sys, argparse, datetime)
Reads:
  - [workspace]/state.json                   (always)
  - [workspace]/results.json                 (when current_run_path is set)
  - {iteration_state.last_eval_results_ref}  (when present, via resolve_workspace_ref)
  - {active_experiment_contract_path}        (when present, JSON, via resolve_workspace_ref)
  - [workspace]/contract/inferred-contract.md (fallback when active_experiment_contract_path is null)
Writes:
  - [workspace]/phase7-status.md
Exit codes:
  0 = success
  2 = bad workspace (missing/not-dir)
  3 = malformed state.json or results.json or active contract
  4 = cannot write phase7-status.md (disk full / readonly)
  5 = path escape (absolute ref OR resolves outside workspace)

Note: exit codes are informational. There's no SKILL.md rule reading them.
The user invokes the script manually; if it errors, they read the error and act.
```

### 3b. Key helper: `resolve_workspace_ref(workspace, ref)`

Per CONCERN from prior reviews. Always do these checks:
1. If `Path(ref).is_absolute()` → exit 5 with "Path escape: {ref} is absolute, refusing."
2. Resolve `(workspace / ref).resolve()`. Check it's a descendant of `workspace.resolve()`. If not → exit 5 with "Path escape: {ref} resolves outside workspace, refusing."
3. Else return the resolved path.

Reason: Python's `Path("/a") / "/b"` returns `/b` (absolute child discards parent), and `../` escapes unless explicitly normalized + bounds-checked. State.json could be corrupted or buggy.

### 3c. Output template (`phase7-status.md`)

```markdown
# Phase 7 Status — {skill_name}

_Generated: {ISO timestamp} by render-phase7-status.py (v0.5)_

{IF current_run_path != iteration_state.run_path: "⚠ STALE-MISMATCH: state.json says current_run_path={X} but iteration_state.run_path={Y}"}

## You Are Here
- Run: {current_run_id} ({current_run_path})
- Experiment: {iteration_state.experiment_id} (slot: {current_experiment})
- Stage: {iteration_state.active_phase} (status: {iteration_state.phase_status})
- Last mutation: {iteration_state.last_mutation_status}{IF last_mutation_results_ref: " (" + ref + ")"}
- Next action: {iteration_state.next_action → human label}
{IF iteration_state.next_action is None AND phase_status="completed": "✅ Run finished — see session_close_holdout/"}
{IF iteration_state.next_action is None AND phase_status="blocked":   "❌ Run blocked — see session-log.json"}

## Success Contract
{Source priority:
 1. JSON path: read {active_experiment_contract_path} as JSON. Render:
    - "Objective: {objective}"
    - "Primary metric: {primary_metric.metric_name} (threshold_pass: {primary_metric.threshold_pass})"
    - "Combined score threshold: {thresholds.combined_score}"
    - "Hard-fail dims: {comma-separated hard_fail_dimensions}" (if non-empty)
    Per references.md:2731+ schema. Use ACTUAL field names. (Codex CONCERN repeatedly flagged that v1.x designs hallucinated field names — read references.md first.)
 2. Markdown path: read [workspace]/contract/inferred-contract.md, find `## Success Criterion` heading, emit 2 lines below it.
 3. Else: "No contract on file."}

## Last Verdict
{Branch on whether finalized record exists in results.json:

 IF results.json#experiments[].id == iteration_state.experiment_id has a `status`:
   - **Final decision:** {experiments[id].status}
   - **Score:** {score}/{max_score} ({pass_rate}%)
   - **Why:** {decision_explanation.summary, truncated at 280 chars + "…"}
   - **Full reasoning:** see {iteration_state.last_eval_results_ref}
   - {IF status differs from decision_breakdown.proposed_decision: "**Note:** user overrode agent's proposed `{proposed}` to `{status}`."}

 ELSE (in-flight):
   - **Proposed:** {decision_breakdown.proposed_decision} ({combined_score_pct}% vs threshold {threshold * 100}%) — awaiting user accept/override
   - **Why:** {decision_explanation.summary, truncated}
   - **Full reasoning:** see {iteration_state.last_eval_results_ref}}

## Files To Look At
- State:           state.json
- Results:         results.json
- Active run:      {current_run_path}/
- Last eval:       {iteration_state.last_eval_results_ref}
- Last mutation:   {iteration_state.last_mutation_results_ref} (if set)
- Contract:        {active_experiment_contract_path or contract/inferred-contract.md}
- Holdout (terminal): session_close_holdout/variant_results.json (if completed)
- Errors (terminal):  session-log.json (if blocked)
```

### 3d. Label maps

```python
NEXT_ACTION_LABELS = {
    "phase7_baseline_eval":      "Run baseline evaluation",
    "phase7_mutation_analysis":  "Analyze and propose next mutation",
    "phase7_test_phase":         "Test the mutated skill on the eval set",
    "phase7_session_close":      "Close the session — run holdout validation",
    None:                        "Loop terminal — see Stage status",
}

LAST_MUTATION_STATUS_LABELS = {
    "completed": "Completed → advancing to test",
    "skipped":   "Skipped → re-targeting",
    "invalid":   "Invalid → rejected before scoring",
    "blocked":   "Blocked → see session-log.json",
    None:        "First attempt",
}
```

### 3e. Graceful degradation

| State condition | Behavior |
|---|---|
| state.json missing | exit 2, message "Workspace not found at {path}" |
| state.json malformed JSON | exit 3, message "Cannot parse state.json" |
| state.json missing top-level keys (`phases`, `gates`) | render minimal header + "state.json appears truncated/legacy" |
| Workspace path is a file | exit 2 |
| current_run_path null | render "No active Phase 7 run" |
| iteration_state null | render "Phase 7 not yet started for this run" |
| experiment_id=0 AND last_eval_results_ref=null | render "Baseline in progress (no eval results yet)" |
| last_eval_results_ref points at missing file | render "Last eval file referenced but not found: {ref}" |
| eval_results.json malformed | render "Last eval file unreadable (parse error) — possibly mid-write" |
| decision_breakdown.combined_score is null OR proposed_decision="disagreement" | render "Multi-judge disagreement, awaiting human review" |
| results.json missing | render "results.json missing — finalized status unknown" — non-fatal, fall back to proposed |
| results.json malformed | exit 3 |
| active_experiment_contract_path malformed JSON | exit 3 |
| active_experiment_contract_path missing required field | render "Active contract incomplete: missing {field}" — non-fatal |
| inferred-contract.md exists but no `## Success Criterion` heading | render "Contract file exists but missing Success Criterion section" |
| current_run_path != iteration_state.run_path | render STALE-MISMATCH warning row at top |
| Path escape (absolute or `../`) | exit 5 |
| Write to phase7-status.md raises OSError | exit 4 with "Cannot write to {path}: ..." |

---

## 4. Implementation plan

1. **Branch:** `feature/phase7-status-ledger-v0.5` off `main`.
2. **Implement `autorefine/scripts/render-phase7-status.py`** (~250–350 LoC, stdlib only).
3. **Tests:** `autorefine/tests/test_render_phase7_status_py.py` — see §5 (24 tests).
4. **`.gitignore`:** add `phase7-status.md` line.
5. **Docs:** add 1 paragraph to `autorefine/docs/troubleshooting.md` titled "Lost in Phase 7? Render the status ledger." with the invocation, an example output snippet, and exit-code legend.
6. **Smoke test:** generate ~12 sample workspace fixtures covering §3e conditions. Run the script against each. Eyeball output.
7. **CHANGELOG.md:** one bullet under Unreleased.
8. **PR:** open against `main`, link to this design doc.

**Estimated effort:** 4–6 hours. (No SKILL.md edits; no agent-integration tests; no acceptance criterion #9.)

---

## 5. Test plan

`autorefine/tests/test_render_phase7_status_py.py`:

| # | Test | Assertion |
|---|---|---|
| T1 | Workspace missing | exits 2 |
| T2 | state.json malformed JSON | exits 3 |
| T3 | Workspace path is a file (not dir) | exits 2 |
| T4 | state.json valid but missing required keys | renders minimal header + "truncated/legacy" warning |
| T5 | Fresh workspace, current_run_path null | renders "No active Phase 7 run" |
| T6 | Mid-eval state, no last_eval_results_ref yet | renders "No verdict yet" |
| T7 | Mid-mutate state with full decision_breakdown + decision_explanation | renders full ledger; quotes summary verbatim |
| T8 | Post-discard (in-flight, no results.json entry yet) | "Proposed: discard ⚠ awaiting user accept/override" |
| T9 | Post-keep (in-flight) | "Proposed: keep ⚠ awaiting user accept/override" |
| T10 | Finalized experiment match: results.json#experiments[id].status = proposed | "Final decision: {status}" — no override note |
| T11 | Finalized experiment override: proposed=discard, status=keep | "Final decision: keep" + "Note: user overrode agent's proposed `discard` to `keep`" |
| T12 | results.json missing entirely (current_run_path set) | renders proposed with "results.json missing" note |
| T13 | results.json malformed | exits 3 |
| T14 | Multi-judge disagreement (combined_score null) | renders "Multi-judge disagreement" — no NoneType crash |
| T15 | Truncation: oversized decision_explanation.summary (>280 chars) | truncated + "…" suffix |
| T16 | active_experiment_contract_path JSON valid: renders objective, primary_metric.threshold_pass, thresholds.combined_score, hard_fail_dimensions | uses ACTUAL schema field names per references.md:2731+ |
| T17 | active_experiment_contract_path malformed JSON | exits 3 |
| T18 | active_experiment_contract_path missing `objective` field | renders "Active contract incomplete: missing objective" — non-fatal |
| T19 | inferred-contract.md fallback: parses `## Success Criterion` heading + 2 lines below | renders those 2 lines |
| T20 | inferred-contract.md missing `## Success Criterion` heading | renders "missing Success Criterion section" |
| T21 | last_eval_results_ref absolute path | exits 5 (path escape) |
| T22 | last_eval_results_ref `../../etc/passwd` style | exits 5 |
| T23 | State mismatch: current_run_path ≠ iteration_state.run_path | STALE-MISMATCH warning at top |
| T24 | Output write OSError (read-only path) | exits 4 with clear message |

24 tests. All stdlib `unittest`. Fixtures in-test (no external files).

---

## 6. Risks

### 6a. The ledger format might be wrong
Real risk for v0.5: the user runs the script, reads phase7-status.md, and finds it doesn't actually answer the questions they have. Mitigation: ship cheap, iterate based on real usage. v0.5 is a 4-6h investment, easy to throw away if format is wrong.

### 6b. Manual invocation friction
User has to remember to run the script when lost. Mitigation: doc it in troubleshooting. If friction proves real, v1 adds agent integration (with the lessons codex's two REVISE passes taught us).

### 6c. Schema field names
v1.x designs hallucinated field names twice. v0.5 implementation must read references.md FIRST and use actual schema. T16 enforces this.

---

## 7. Acceptance criteria

Done when:
1. `autorefine/scripts/render-phase7-status.py` exists, all 24 tests pass.
2. `phase7-status.md` is in `.gitignore`.
3. One paragraph added to `autorefine/docs/troubleshooting.md`.
4. Smoke test against a real workspace produces a readable, accurate `phase7-status.md`.
5. PR merged to `main`, CHANGELOG updated.

Validated when:
6. User runs the script in a real Phase 7 session that gets confusing. Reports back: did the ledger help? Were the right things on it? What's missing?
7. Based on user feedback, decide whether to scope v1 (agent integration) or kill the project.

---

## 8. v1 deferral (parking lot)

If v0.5 proves the ledger is useful, v1 adds agent integration. The lessons from the v1.x design + codex reviews go into v1's design from day 1:
- Trigger must live at the ROOT of `autorefine/SKILL.md`, not inside Phase 7 file (codex BLOCKER #1)
- Resume-by-workspace-path must be a first-class entry mode in Preflight, not bolted on after target-skill validation (codex v1.3 BLOCKER)
- Graduated failure policy with exit codes 2/3/5 = BLOCKING for the agent
- Compact-recovery acceptance criterion: agent invokes ledger from fresh prompt with workspace path only

These notes live here so v1's design doesn't re-discover them. Full review history: `reviews/2026-05-02-phase7-status-ledger-*.md`.
