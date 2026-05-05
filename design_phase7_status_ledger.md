# Design — Phase 7 Status Ledger

**Status:** **ARCHIVED — SUPERSEDED by `design_phase7_status_ledger_v0.5.md`**
**Reason:** After 5 review cycles, codex returned REVISE twice with architectural BLOCKERs at successively deeper layers of the existing `autorefine/SKILL.md` routing. Per Circuit Breaker Protocol (CLAUDE.md), stopped iteration and rescoped to v0.5 (script-only, no SKILL.md integration). The v1+ full-integration design is deferred until v0.5 ships and we have real signal on whether the ledger format is useful in the first place.
**Original status (kept for record):** Draft v1.3 — CE + plan-eng-review (×2) + Codex adversarial-review applied; awaiting adversarial re-pass then ready to implement
**Date:** 2026-05-02
**Author:** Claude (with surahli, via /grill-me)
**Reviews:** CE (oh-my-claudecode:code-reviewer, worktree-isolated) + plan-eng-review v1.0 + plan-eng-review v1.1 re-pass + Codex adversarial v1.2 + Codex adversarial v1.3 (both returned REVISE). Full review logs at `reviews/2026-05-02-phase7-status-ledger-review.md`, `reviews/2026-05-02-phase7-status-ledger-adversarial.md`, and `reviews/2026-05-02-phase7-status-ledger-adversarial-v1.3.md`.
**Branch target:** new feature branch off `main`
**Scope:** v1 only — observability fix for AutoRefine Phase 7. F1 (Python orchestrator) explicitly deferred to v2.

---

## 1. Problem

### 1a. What broke

In a single in-house Phase 7 run on one skill, the user observed three failure modes:

- **d1 (context-loss after compact):** Agent lost track of the active experiment / sub-stage after auto-compact mid-Phase-7. Recovery via `state.json` worked but was incomplete — agent had to ask "which run am I on?".
- **d4 (stuck in sub-phase):** Agent oscillated between eval / mutate / test, asking the human to pick the next action.
- **d5 (lost the contract):** Occasionally drifted from the original success criterion mid-loop, optimizing a proxy.

### 1b. The reframe (load-bearing)

During grill-me, the user said: *"or actually myself got lost."*

That changes the diagnosis. **The user lost confidence because the user lost visibility.** Once visibility was lost, the user couldn't tell whether the agent was confused or whether they themselves were confused. Both fixes are different.

The user-side observability gaps (mapped from grill-me Q3):

| Code | What user couldn't figure out | Symptom |
|---|---|---|
| L1 | Which experiment is active right now | Run-id confusion |
| L2 | What is the agent about to do next | Next-action opacity |
| L4 | Why did the agent decide that | Reasoning trace buried in run-dir JSON |
| L6 | Where do I look to verify what just happened | File sprawl — 5+ places to check |

### 1c. Single-datapoint caveat

n=1 skill. The fix could be over-fitted to one failure mode. We mitigate by shipping the **cheapest possible** observability fix (a markdown ledger) before considering bigger architectural moves (F1: Python orchestrator).

---

## 2. Verification (evidence-grounded)

Three load-bearing claims were verified by reading the codebase before locking the design:

### 2a. CLAIM 1 — No ledger exists today
✅ **Confirmed.** `autorefine/dashboard.html` is template-only (no live state). `autorefine/scripts/run-campaign.py` is planning, not tracking. Building net-new, not duplicating.

### 2b. CLAIM 2 — `state.json` already has enough fields to render "you are here"
✅ **Confirmed (stronger than expected).** Per `autorefine/references.md` lines 13–88:

| Field | Solves | Format |
|---|---|---|
| `current_run_id` | L1 | string, e.g. `run_2026-04-03T14-30-00` |
| `current_run_path` | L1, L6 | `runs/run_*/` |
| `current_experiment` | L1 | int (experiment slot) |
| `iteration_state.experiment_id` | L1 | int |
| `iteration_state.active_phase` | L2 | `eval | mutate | test | session_close` |
| `iteration_state.phase_status` | L2 | `running | ready | completed | blocked` |
| `iteration_state.next_action` | L2 | `phase7_baseline_eval | phase7_mutation_analysis | phase7_test_phase | phase7_session_close | null` |
| `iteration_state.last_eval_results_ref` | L6 | path to most recent `eval_results.json` |
| `active_experiment_contract_path` | anti-drift / L7 | path to run-scoped success contract |

The renderer is mostly string interpolation — no schema changes required.

### 2c. CLAIM 3 — "Why" reasoning lives in artifacts, not just chat
✅ **Confirmed.** Per `autorefine/references.md` lines 175–186 + 199–202:

`runs/run_*/iteration_NNN/eval_results.json` contains:
- `decision_breakdown` — components, weighted_points, total_weight, combined_score, threshold, proposed_decision
- `decision_explanation.summary` — **one-sentence human-readable** "why kept/discarded" (example from references: *"E2 withheld 19.1% of the available score, while E1 added 21.3%; the mutation still finished below threshold."*)
- Per-eval `reasoning_trace` — ordered "criterion check → evidence → verdict link" prose
- Per-eval `evidence[]` — structured citations with `kind`, `source`, `locator`

L4 ("why did agent decide that") is solvable. The ledger doesn't need to embed reasoning — it points at the artifact and quotes the one-line summary.

---

## 3. Design

### 3a. Decision: standalone renderer script (W2)

Three trigger models were considered:
- (W1) Agent writes ledger inline at end of every turn — **REJECTED.** Same failure mode that produced d1: agent forgets / drifts / writes inconsistently.
- (W2) Standalone Python renderer; agent invokes at start of every Phase 7 turn — **CHOSEN.** Deterministic, testable in isolation, human can run it manually, agent never authors free-form ledger content.
- (W3) Hook-driven (`PostToolUse`) — **REJECTED.** Real disqualifier: couples the skill to specific hook event names (e.g. `PostToolUse`) that vary across harnesses (Claude Code vs other agents). Users running the skill in a harness without that hook silently get no ledger. W2 + manual `python3` invocation has no such lock-in.

### 3b. Script spec

```
File:    autorefine/scripts/render-phase7-status.py
Usage:   python3 render-phase7-status.py [workspace_path]
Output:  [workspace_path]/phase7-status.md (overwrites every call)
Deps:    Python stdlib only (json, pathlib, sys, argparse, datetime)
Reads:
  - [workspace]/state.json                        (always)
  - [workspace]/results.json                      (always when current_run_path is set; needed
                                                   for finalized experiment status — Codex BLOCKER #2)
  - {iteration_state.last_eval_results_ref}       (when present)
  - {active_experiment_contract_path}             (when present, preferred — adapter-aware, JSON)
  - [workspace]/contract/inferred-contract.md     (fallback when active_experiment_contract_path is null, markdown)
Path resolution (Codex CONCERN #1 fix):
  - All paths in state.json (last_eval_results_ref, current_run_path,
    active_experiment_contract_path) are RELATIVE to workspace root per
    references.md line 28.
  - Use a single helper `resolve_workspace_ref(workspace, ref)` that:
    1. Rejects absolute paths (`Path(ref).is_absolute()` → exit 5).
    2. Resolves `(workspace / ref).resolve()` and checks the result is
       a descendant of `workspace.resolve()`. If not (escape via `../`),
       exit 5.
    3. Returns the resolved path otherwise.
  - Rationale: `Path("/a") / "/b"` returns `/b` in Python — naive joining
    discards the parent. `../` also escapes unless explicitly normalized
    and bounds-checked.
Writes:
  - [workspace]/phase7-status.md                  (markdown, overwrites)
Exit codes (graduated failure policy, Codex CONCERN #3 fix):
  0 = success
  2 = bad workspace (missing/not-dir) — BLOCKING (no ledger renderable)
  3 = malformed state.json or results.json or active contract — BLOCKING
      (state is unreliable; agent must STOP Phase 7 mutation/test until repaired)
  4 = cannot write phase7-status.md (disk full / readonly fs) — NON-BLOCKING
      (state is fine; agent continues but should surface the warning)
  5 = path escape detected (ref is absolute or resolves outside workspace) — BLOCKING
      (potential malicious or corrupted state.json)

  The SKILL.md rule (§3e) reads exit code and applies the right policy.
Integrity check (Q2 from earlier review):
  - When state.json.current_run_path is set AND iteration_state.run_path is set,
    compare them. If they disagree, render a STALE-MISMATCH warning row at the
    top of the ledger (don't crash — render whatever state says).
Override-aware decision lookup (Codex BLOCKER #2 fix):
  - For the "Last Verdict" section, look up the active experiment in
    results.json#experiments[] by matching `id == iteration_state.experiment_id`.
  - If a finalized record exists (`status` is one of "keep", "discard", "baseline"),
    render that status as **Final decision** (label: "Final").
  - If no finalized record exists yet, fall back to
    `eval_results.json#decision_breakdown.proposed_decision` and label as
    **Proposed decision** (label: "Proposed — awaiting user accept/override").
  - Never silently substitute proposed for final or vice versa.
```

### 3c. Output template (`phase7-status.md`)

```markdown
# Phase 7 Status — {skill_name}

_Generated: {ISO timestamp} by render-phase7-status.py_

{IF state mismatch detected (Q2): emit a "⚠ STALE-MISMATCH WARNING" line at the
 top showing both current_run_path and iteration_state.run_path side by side. Else omit.}

## You Are Here  (L1, L2)
- **Run:** {current_run_id}  ({current_run_path})
- **Experiment:** {iteration_state.experiment_id}  (slot: {current_experiment})
- **Stage:** {iteration_state.active_phase}  (status: {iteration_state.phase_status})
- **Last mutation:** {iteration_state.last_mutation_status → label}{IF last_mutation_results_ref is set: " (" + ref + ")" — else omit parens entirely (C1 fix: don't render `(None)` literally)}
- **Next action:** {iteration_state.next_action → human label, see §3d}

## Success Contract  (anti-drift; bonus L7)
{Source priority — TWO DIFFERENT FORMATS (Codex CONCERN #2 fix):
 1. JSON path: {active_experiment_contract_path} → read as JSON, render:
    - "Objective: {objective}"
    - "Primary metric: {primary_metric.metric_name} ≥ {thresholds.primary_threshold}"
    - "Hard-fail dims: {comma-separated hard_fail_dimensions}" (if non-empty)
    Per references.md:2731 schema. Do NOT look for a "success criterion" field — it
    does not exist in this schema. v1.2 fabricated that field name.
 2. Markdown path: [workspace]/contract/inferred-contract.md → locate the
    `## Success Criterion` heading and emit the 2 lines below it (NOT the file's
    first 2 lines, which are title/header).
 3. Else "No contract on file. Run Phase 0.5 to anchor success criteria."}

## Last Verdict  (L4)
{Branch on whether a finalized experiment record exists in results.json (Codex BLOCKER #2 fix):

 IF results.json#experiments[].id == iteration_state.experiment_id has a `status`:
   - **Final decision:** {experiments[id].status}  (one of keep | discard | baseline)
   - **Score:** {experiments[id].score}/{experiments[id].max_score} ({experiments[id].pass_rate}%)
   - **Why:** {decision_explanation.summary, truncated at 280 chars + "…"}
   - **Full reasoning:** see {iteration_state.last_eval_results_ref}
   - {IF experiments[id].status differs from decision_breakdown.proposed_decision: emit
     "**Note:** user overrode the agent's proposed `{proposed_decision}` to `{status}`."}

 ELSE (no finalized record yet — experiment in flight):
   - **Proposed decision:** {decision_breakdown.proposed_decision}  ({decision_breakdown.combined_score_pct}% vs threshold {decision_breakdown.threshold * 100}%)  ⚠ awaiting user accept/override
   - **Why:** {decision_explanation.summary, truncated at 280 chars + "…"}
   - **Full reasoning:** see {iteration_state.last_eval_results_ref}}

## Files To Look At  (L6)
- State:           state.json
- Active run:      {current_run_path}/
- Last eval:       {iteration_state.last_eval_results_ref}
- Last mutation:   {iteration_state.last_mutation_results_ref}  (if set)
- Skill snapshot:  skill-versions/{latest}/SKILL.md  (if exists)
- Contract:        {active_experiment_contract_path or contract/inferred-contract.md}
- Holdout (terminal): session_close_holdout/variant_results.json  (if phase_status=completed)
- Errors (terminal): session-log.json  (if phase_status=blocked)
```

### 3d. State → human label maps

```python
NEXT_ACTION_LABELS = {
    "phase7_baseline_eval":      "Run baseline evaluation",
    "phase7_mutation_analysis":  "Analyze and propose next mutation",
    "phase7_test_phase":         "Test the mutated skill on the eval set",
    "phase7_session_close":      "Close the session — run holdout validation",
    None:                        "Loop terminal — see Stage status for win/fail",
}

# CE BLOCKER #1: surface mutation-skip distinctly.
LAST_MUTATION_STATUS_LABELS = {
    "completed": "Completed → advancing to test",
    "skipped":   "Skipped → re-targeting (the mutation actor declined to propose a candidate)",
    "invalid":   "Invalid → mutation rejected before scoring",
    "blocked":   "Blocked → see session-log.json",
    None:        "First attempt — no prior mutation in this run",
}

# CE BLOCKER #2: terminal disambiguation. Read iteration_state.phase_status.
PHASE_STATUS_TERMINAL_LABELS = {
    "completed": "✅ Run finished successfully — see session_close_holdout/ for holdout score",
    "blocked":   "❌ Run blocked (unrecoverable) — see session-log.json for the last error",
    # "running" / "ready" handled inline by Stage row, not here.
}
```

When `iteration_state.next_action is None`, the renderer must consult
`iteration_state.phase_status` and use `PHASE_STATUS_TERMINAL_LABELS` to
differentiate success from failure. Never render bare "Loop terminal" — that
defeats L2 at exactly the moment it matters most.

### 3e. SKILL.md edits (TWO insertion points — Codex BLOCKER #1 fix)

**v1.2 had a circular dependency:** the trigger lived in `gulf3-generalization.md`, but the agent only reads that file if it knows it's in Phase 7 — which is exactly the state lost on compact. Fixed in v1.3 by adding a **root-level trigger** that fires on every session start regardless of perceived phase.

**Edit 1 (NEW, root-level): `autorefine/SKILL.md` Initialize Workspace section.**

Add immediately after the existing checkpoint recovery + ambient learning steps, before "Pipeline Status":

> **Step C: Render Phase 7 status ledger (compact-recovery anchor).**
> If `state.json.iteration_state` is non-null OR `state.json.current_run_path` is non-null, run:
> ```
> python3 autorefine/scripts/render-phase7-status.py [workspace]
> ```
> Read `[workspace]/phase7-status.md` before printing Pipeline Status. This anchors active run state and re-reads the success contract on every session start, including after auto-compact.
>
> **Failure policy (graduated, see §3b exit codes):**
> - Exit 0 → continue normally
> - Exit 4 (write failure, non-blocking) → log warning and continue; ledger is stale but state is fine
> - Exit 2/3/5 (BLOCKING) → STOP. Do not proceed to Phase 7 mutation/test/session_close. Surface the exact error to the user and wait for repair.

This rule is at the root because session resume *cannot* depend on knowing the phase — that knowledge is in state.json + iteration_state, which the ledger surfaces.

**Edit 2 (kept, belt-and-suspenders): Phase 7 entry in `autorefine/references/gulf3-generalization.md`.**

Add at the top of Phase 7:

> **Step 0 (every Phase 7 turn): Re-render and re-read the status ledger.**
> Run `python3 autorefine/scripts/render-phase7-status.py [workspace]` and re-read `[workspace]/phase7-status.md` before any mutation/test/session_close action. (The root-level trigger in `autorefine/SKILL.md` fires once per session; this rule fires per Phase 7 turn to refresh after each scoring cycle.) Apply the same graduated failure policy as the root rule.

Total SKILL.md change: ~10 lines across 2 files. Two insertion points, same script, complementary purposes (root = recover from compact; Phase 7 = refresh per turn).

### 3f. Graceful degradation

The renderer must handle every state-shape combination without crashing:

| State condition | Behavior |
|---|---|
| `state.json` missing | exit 2, message "Workspace not found at {path}" |
| `state.json` malformed (invalid JSON) | exit 3, message "Cannot parse state.json — see error above" |
| `state.json` valid but missing required top-level keys (`phases`, `gates`) | render minimal header + "state.json appears truncated/legacy — proceed with caution" |
| Workspace path is a file, not a directory | exit 2, message "Workspace path must be a directory: {path}" |
| `current_run_path` is null | render with header + "No active Phase 7 run." Other sections empty. |
| `iteration_state` is null | render with run header + "Phase 7 not yet started for this run." |
| `experiment_id=0 AND last_eval_results_ref=null` (CE #3) | render "Baseline in progress (no eval results yet)" instead of empty Last Verdict |
| `last_eval_results_ref` is null | "Last Verdict" section says "No verdict yet for this experiment." |
| `last_eval_results_ref` set but file missing on disk | "Last verdict file referenced but not found: {ref}" — don't crash |
| `eval_results.json` malformed (mid-write) | "Last verdict file unreadable (parse error: {short msg}) — possible mid-write" |
| `decision_breakdown.combined_score is null OR proposed_decision = "disagreement"` (CE #4) | render "Multi-judge disagreement, awaiting human review — see {last_eval_results_ref}" instead of attempting `combined_score_pct` interpolation |
| `decision_explanation` missing from `eval_results.json` (legacy) | fall back to "{combined_score_pct}% vs {threshold*100}% — see eval_results.json" |
| `phase_status = "completed"` (CE BLOCKER #2) | render "✅ Run finished successfully — see `session_close_holdout/`" |
| `phase_status = "blocked"` (CE BLOCKER #2) | render "❌ Run blocked — see `session-log.json` for the last error" |
| `current_run_path` ≠ `iteration_state.run_path` (Q2) | emit STALE-MISMATCH warning row at top, render whatever state.json says |
| `active_experiment_contract_path` is null AND `contract/inferred-contract.md` missing | "No contract on file." |
| `inferred-contract.md` exists but has no `## Success Criterion` heading (CE #5) | "Contract file exists but missing `## Success Criterion` section" |
| **Write to `phase7-status.md` raises OSError** (disk full, read-only fs, permission denied) (R1 fix) | wrap `Path.write_text()` in try/except OSError. Exit 4 with "Cannot write to {output_path}: {short OSError msg}". Do NOT crash with traceback. |
| **Path escape detected** — `last_eval_results_ref` or `active_experiment_contract_path` is absolute OR resolves outside workspace (Codex CONCERN #1) | `resolve_workspace_ref()` exits 5 with "Path escape detected: {ref} resolves outside {workspace}. Refusing to read." BLOCKING. |
| **`results.json` missing** when `current_run_path` is set | render verdict from `eval_results.json` only, label as "Proposed (results.json missing — finalized status unknown)" — non-fatal |
| **`results.json` malformed** (invalid JSON) | exit 3, message "Cannot parse results.json — see error above". BLOCKING. |
| **`active_experiment_contract_path` malformed JSON** (Codex CONCERN #3) | exit 3, BLOCKING. Active contract is the run-scoped success criterion; reading garbage there recreates d5 (contract drift). |
| **`active_experiment_contract_path` set, JSON parses, but missing required field** (`objective` or `primary_metric`) | render "Active contract incomplete: missing {field name}" — non-fatal, render what's present. |

---

## 4. Implementation plan

Ordered, small, each step independently verifiable:

1. **Branch:** `feature/phase7-status-ledger` off `main`.
2. **Implement `render-phase7-status.py`** (target: 350–450 lines after v1.3 fixes, stdlib only).
   - Argparse + workspace path validation (file-vs-dir check, exit 2 if file)
   - `resolve_workspace_ref(workspace, ref) -> Path` — Codex CONCERN #1 fix; rejects absolute paths, rejects outside-workspace resolution. Exits 5 on either.
   - `read_state(workspace) -> dict` — fail-soft (returns `{}` if missing); validates required top-level keys; exits 3 on parse fail
   - `read_results(workspace) -> dict | None` — Codex BLOCKER #2 fix; reads results.json when current_run_path is set; exits 3 on parse fail
   - `find_finalized_experiment(results, experiment_id) -> dict | None` — looks up experiments[].id matching iteration_state.experiment_id; returns the row if status is keep/discard/baseline, else None
   - `read_last_eval(state, workspace) -> dict | None` — uses resolve_workspace_ref; catches JSONDecodeError as "mid-write"
   - `read_active_contract_json(state, workspace) -> dict | None` — Codex CONCERN #2 fix; parses experiment-contract.json schema (objective, primary_metric, thresholds, hard_fail_dimensions)
   - `read_inferred_contract_md(workspace) -> str` — parses `## Success Criterion` heading from contract/inferred-contract.md
   - `format_contract_section(active_json, inferred_md) -> str` — renders the right format depending on which source is available
   - `detect_state_mismatch(state) -> str | None` — Q2 stale-warning row
   - `format_last_verdict(decision_breakdown, finalized_experiment) -> str` — Codex BLOCKER #2 fix; branches on whether experiment is finalized
   - `format_ledger(state, results, last_eval, contract_section, mismatch_warning, now) -> str`
   - `truncate(text, n=280)` — §3c summary truncation
   - `main()` — orchestrates, applies graduated exit codes per §3b
3. **Tests:** `autorefine/tests/test_render_phase7_status_py.py` — see §5 (32 tests after v1.3).
4. **SKILL.md edits (TWO files now — Codex BLOCKER #1 fix):**
   - `autorefine/SKILL.md`: add Step C (root-level Phase 7 status ledger trigger) in Initialize Workspace section, before Pipeline Status. ~6 lines.
   - `autorefine/references/gulf3-generalization.md`: add Step 0 (per-Phase-7-turn refresh). ~3 lines.
   - One commit, two file changes. Both must include the graduated failure policy reference.
5. **`.gitignore`:** add `phase7-status.md` line per Q4.
6. **Smoke test:** generate 14 sample workspace state.json + results.json fixture pairs (v1.3: §3f now has 22 conditions; 14 direct fixtures + 8 conditions covered transitively via parametrization). Critical: include override fixtures (proposed=discard, status=keep) and absolute-path fixtures.
7. **Compact-recovery validation (Codex SUGGESTION):** start a fresh prompt with ONLY the workspace path. The agent must run the root-level rule, recover next action, and resume without being told it is in Phase 7. This validates BLOCKER #1's fix end-to-end. Counts toward Acceptance Criterion #9.
8. **CHANGELOG.md:** one bullet under Unreleased.
9. **PR:** open against `main`, link to this design doc, request review.

Estimated effort: **1–1.5 days** (v1.3 grew the script ~50 LoC + added 8 tests + a second SKILL.md edit; previously 0.5–1 day). Still no architectural risk; all changes named.

---

## 5. Test plan

`autorefine/tests/test_render_phase7_status_py.py`:

| # | Test | Assertion |
|---|---|---|
| T1 | Empty workspace (no state.json) | exits 2, doesn't crash |
| T2 | Malformed state.json (invalid JSON) | exits 3, doesn't crash |
| T3 | Fresh workspace, state.json exists but `current_run_path` null | renders header + "No active Phase 7 run" |
| T4 | Mid-eval state (active_phase=eval, no last_eval_results_ref yet) | renders "You Are Here" + "No verdict yet" |
| T5 | Mid-mutate state (last_eval_results_ref points at iteration_000/eval_results.json with decision_breakdown + decision_explanation) | renders full ledger including decision_explanation.summary verbatim |
| T6 | Post-discard state | "Decision: discard" + summary correctly quoted |
| T7 | Post-keep state | "Decision: keep" + summary correctly quoted |
| T8 | Legacy eval_results.json without decision_explanation | falls back to "%/threshold" line |
| T9 | Idempotency | two consecutive calls produce byte-identical output (modulo timestamp) |
| T10 | All known `next_action` values map to a non-empty label | exhaustive enum check (NEXT_ACTION_LABELS + LAST_MUTATION_STATUS_LABELS + PHASE_STATUS_TERMINAL_LABELS) |
| T11 | Oversized `decision_explanation.summary` (>280 chars) (CE #8) | truncated to 280 chars + "…" suffix; tail not bare-cut at byte boundary |
| T12 | Workspace path is a file, not a directory | exits 2, message names the file |
| T13 | SKILL.md sanity (plan-eng B) | loads `autorefine/references/gulf3-generalization.md`, asserts the new "Step 0 (every Phase 7 turn)" rule string is present at the expected location |
| T14 | Malformed `eval_results.json` (mid-write, JSONDecodeError) | renders "Last verdict file unreadable" — does not crash |
| T15 | `phase_status="completed"` (CE BLOCKER #2) | renders "✅ Run finished successfully" |
| T16 | `phase_status="blocked"` (CE BLOCKER #2) | renders "❌ Run blocked" |
| T17 | `last_mutation_status="skipped"` (CE BLOCKER #1) | "Last mutation: Skipped → re-targeting" appears in You Are Here |
| T18 | `experiment_id=0 AND last_eval_results_ref=null` (CE #3) | renders "Baseline in progress" — does not show empty Last Verdict |
| T19 | Multi-judge disagreement (`decision_breakdown.combined_score=null`) (CE #4) | renders "Multi-judge disagreement, awaiting human review" — no NoneType crash |
| T20 | State mismatch (`current_run_path` ≠ `iteration_state.run_path`) (Q2) | STALE-MISMATCH warning row at top; ledger still renders |
| T21 | `inferred-contract.md` exists but no `## Success Criterion` heading (CE #5) | renders "Contract file exists but missing `## Success Criterion` section" |
| T22 | `active_experiment_contract_path` set, takes priority over `inferred-contract.md` (Q3) | reads from adapter-aware contract path first |
| T23 | state.json valid JSON but missing top-level required keys (`phases`, `gates`) (T1 fix from v1.1 review) | renders minimal header + "state.json appears truncated/legacy — proceed with caution" — does not crash |
| T24 | Output path is read-only / write raises OSError (T2 fix from v1.1 review) | exits 4 with "Cannot write to {path}: ..." message — no traceback |
| T25 | `last_eval_results_ref` is an absolute path (Codex CONCERN #1) | `resolve_workspace_ref` exits 5; output names the offending ref |
| T26 | `last_eval_results_ref` contains `../../etc/passwd`-style escape (Codex CONCERN #1) | resolves outside workspace → exits 5; output names the resolved path |
| T27 | Finalized experiment override: `decision_breakdown.proposed_decision = "discard"` but `results.json#experiments[id].status = "keep"` (Codex BLOCKER #2) | renders "Final decision: keep" + "Note: user overrode the agent's proposed `discard` to `keep`" |
| T28 | Finalized experiment matches proposal: status = proposed_decision | renders "Final decision: {status}" — no override note |
| T29 | In-flight experiment: results.json has no entry for current experiment_id | renders "Proposed decision: ... ⚠ awaiting user accept/override" — falls back to decision_breakdown |
| T30 | results.json missing entirely but current_run_path is set | renders "Proposed (results.json missing — finalized status unknown)" — non-fatal |
| T31 | results.json malformed JSON | exits 3 — BLOCKING |
| T32 | active_experiment_contract_path JSON parses, has objective/primary_metric/thresholds (Codex CONCERN #2) | renders "Objective: ..." + "Primary metric: ... ≥ ..." + hard-fail dims if present. Does NOT look for nonexistent "success criterion" field. |
| T33 | active_experiment_contract_path JSON missing required field (e.g., no `objective`) | renders "Active contract incomplete: missing objective" — non-fatal, partial render |
| T34 | active_experiment_contract_path malformed JSON | exits 3 — BLOCKING (active contract drives mutation policy; can't continue blind) |
| T35 | Compact-recovery sanity (Codex BLOCKER #1) | autorefine/SKILL.md contains the root-level Step C rule string at the expected location, gated on iteration_state OR current_run_path |

All tests use stdlib `unittest`, fixtures in-test (no external files). 32 tests total (was 10 v1.0 → 22 v1.1 → 24 v1.2 → 32 v1.3).

---

## 6. Risks & open issues

### 6a. Residual risk: agent forgets to call the renderer
The single `Step 0` rule in SKILL.md is not enforced by the harness — the agent could skip it after compact, or read it once and not re-render. Mitigations:
- The rule is at the **start** of Phase 7 entry (highest visibility).
- The script is cheap to run manually if the user notices the ledger is stale.
- If this proves insufficient on a 2nd or 3rd skill, escalate to F5 (pre-mutation sanity check) or F1 (Python orchestrator).

### 6b. n=1 datapoint
Fix could be over-fitted to one user's failure mode. Mitigation: ship cheap, observe on more skills before bigger changes.

### 6c. `decision_explanation.summary` length not bounded
References doc shows ~25-word example. If real instances are 200+ words, the ledger gets ugly. Mitigation: truncate at 280 chars + "…" in `format_ledger`.

### 6d. Ledger nobody reads = file sprawl gets worse
If the agent fails to read the rendered file, we've added file #6 to the file sprawl. Acceptable risk because the ledger is also useful to the human directly (the user can `cat phase7-status.md` to check on a run).

### 6e. Cross-run state reconciliation NOT in v1 (Q1)
If `state.json.iteration_state` references a previously terminated run while a new run has begun without clearing it, the ledger renders the stale data verbatim. We do NOT add cross-run reconciliation logic — `state.json` is the source of truth, and stale state is a state.json bug, not a ledger bug. The Q2 mismatch warning catches the most common case (`current_run_path` vs `iteration_state.run_path` disagree); deeper reconciliation deferred until evidence shows it matters.

---

## 7. Out of scope (deferred)

| Idea | Why deferred | Trigger to revisit |
|---|---|---|
| **F1: Python Phase 7 orchestrator** | Major architectural shift. Contradicts existing handover constraint ("Phase 7 is the LLM agent, NOT a Python program"). Premature on n=1. | If ledger fails to fix d1+d4 on 2+ additional skills. |
| **F3: Subagent dispatch per sub-phase** | Doesn't address the user-visibility problem that this design targets. Orthogonal. | If d4 persists after ledger ships. |
| **F5: Pre-mutation sanity check** | Overlaps with this fix. Re-evaluate after ledger lands. | If d5 (contract drift) still occurs after ledger ships. |
| **Live-update / file watcher** | Premature. Agent invokes on demand. | Only if a use case emerges. |
| **HTML / dashboard rendering** | Markdown is enough for v1. Reuse existing `dashboard.html` separately if needed. | If users want a multi-skill rollup view. |
| **`render-phase7-status.py --watch` mode** | Premature. | If users complain about manual invocation. |

---

## 8. Acceptance criteria

This design is "done" when:

1. `autorefine/scripts/render-phase7-status.py` exists, all 32 tests pass.
2. `autorefine/SKILL.md` has the Step C addition (root-level trigger, Codex BLOCKER #1 fix).
3. `autorefine/references/gulf3-generalization.md` has the Step 0 addition (per-Phase-7-turn refresh).
4. `phase7-status.md` is added to repo `.gitignore`.
5. Smoke test against a real workspace (fresh AutoRefine run on any skill) produces a readable, accurate `phase7-status.md`.
6. PR merged to `main`, CHANGELOG updated.

This design is "validated" (separate, post-merge) when:

7. **First, the same failing skill (Q5):** Re-run AutoRefine Phase 7 on the same skill that produced the original d1+d4+d5 failure. Confirm the ledger renders correctly through compact, that the user can answer L1/L2/L4/L6 from the ledger alone, and that the prior failure modes are reduced or eliminated.
8. **Then, n>=2 skills:** After step 7 passes, exercise the ledger on at least one additional skill (different shape, different adapter if applicable) to catch over-fitting.
9. **Compact-recovery validation (Codex SUGGESTION):** Start a fresh prompt with ONLY the workspace path, no mention of Phase 7. The agent must independently invoke the root-level Step C trigger, render and read the ledger, recover the active run state, and resume the next action. If the agent has to ask the user "where am I?", BLOCKER #1's fix didn't take. This is the canonical test for the architectural fix.
10. After 2+ skills + compact-recovery validation, decide whether to escalate to F5 or F1 — or close the loop as solved.

---

## 9. Decision log

### From /grill-me (v1 draft)
- **Initial framing:** "Phase 7 is broken, externalize the runner (F1)" — rejected after grill-me revealed L1/L2/L4/L6 visibility gaps as the real diagnosis.
- **Trigger model:** W2 (standalone renderer) chosen over W1 (agent inline) and W3 (hook-driven) on grounds of determinism + portability.
- **L4 solvability:** Initially feared L4 lived only in conversation. Verification proved `decision_explanation.summary` exists in artifacts.
- **Scope discipline:** F1, F3, F5 explicitly deferred. v1 is the cheapest intervention that addresses verified failure modes.

### From CE + plan-eng-review (v1.1 revision)
- **2 BLOCKERs fixed:** (1) `last_mutation_status="skipped"` now surfaced distinctly; (2) terminal `phase_status` differentiates win (✅) from fail (❌). Both were spec holes that would have rendered the ledger useless at exactly the moments it matters most.
- **Multi-judge disagreement state added:** `combined_score=null` no longer crashes the renderer (CE #4).
- **Contract source priority clarified (Q3):** `active_experiment_contract_path` (adapter-aware) takes priority over `inferred-contract.md`. Parsing locates `## Success Criterion` heading, not blind first-2-lines.
- **Path resolution rule stated explicitly (CE #6):** all `state.json` paths are workspace-relative.
- **Stale state mismatch warning (Q2):** non-blocking warning row when `current_run_path` ≠ `iteration_state.run_path`.
- **Test count grew 10 → 22.** Most added for the new graceful-degradation cases.
- **Cross-run reconciliation (Q1) deferred.** State.json is source of truth; deeper reconciliation only if evidence demands it.
- **Cross-model agreement:** CE (worktree-isolated, fresh-context) and plan-eng-review (in-context fresh-eye) converged on the same fix set with no disagreement on architecture or scope. CE caught more spec-level issues; plan-eng-review added the prompt-change observability finding (T13).

### From plan-eng-review v1.1 re-pass (v1.2 revision)
- 4 P3 findings + 1 internal-consistency finding folded in: write-OSError graceful exit (R1 → exit code 4), `(None)` parens cosmetic fix in Last mutation row (C1), 2 missing tests added (T23 missing-keys, T24 write-failure), fixture count corrected 7 → 12 (I1 — table grew from 7 → 16 rows, fixture count had drifted again).
- Test count: 22 → 24.
- No BLOCKERs found in the re-pass. v1.1 fixes were internally consistent and did not regress.
- Outside voice (3rd review pass) skipped during this re-pass — already had CE on v1.0; running another would be 5th review on a v1 fix.

### From Codex adversarial-review (v1.3 revision)
- **Verdict: REVISE.** Codex caught what 3 prior review passes missed: 2 BLOCKERs + 3 CONCERNs + 1 SUGGESTION.
- **BLOCKER #1 (architectural):** v1.2's W2 trigger lived only in `gulf3-generalization.md`, which the agent only reads if it knows it's in Phase 7 — circular dependency that defeats the whole compact-recovery purpose. **Fix:** added a root-level Step C trigger in `autorefine/SKILL.md` Initialize Workspace section, gated on `iteration_state OR current_run_path`. Phase 7 entry rule kept as belt-and-suspenders for per-turn refresh.
- **BLOCKER #2 (correctness):** v1.2 rendered `decision_breakdown.proposed_decision` as "Decision" but Phase 7 supports user override; final lives in `results.json#experiments[].status`. **Fix:** script now reads results.json, prefers finalized status when present, labels in-flight verdicts as "Proposed" with explicit override note when user changed it.
- **CONCERN #1 (security):** Naive `Path(workspace) / ref` discards parent on absolute ref and escapes via `../`. **Fix:** new `resolve_workspace_ref()` helper that rejects both. Exit code 5 (BLOCKING) on path escape. Tests T25, T26.
- **CONCERN #2 (fabricated field):** v1.2 referenced "success criterion field" in `experiment-contract.json` — that field does not exist in the schema. **Fix:** render `objective`, `primary_metric.metric_name`, threshold, hard_fail_dimensions per actual references.md:2731 schema. Two-format parsing (JSON vs markdown) explicit in §3c.
- **CONCERN #3 (failure policy):** v1.2's "log and continue manually" recreated d1/d5 on state-parse failures. **Fix:** graduated exit codes — code 4 (write fail) is non-blocking; codes 2/3/5 (state/parse/path issues) BLOCK Phase 7 mutation/test until repaired. SKILL.md rule reads exit code and applies the right policy.
- **SUGGESTION:** new acceptance criterion #9 — fresh compacted prompt with workspace path only must recover without being told it's Phase 7. Validates BLOCKER #1's fix end-to-end.
- Test count: 24 → 32. Script size estimate: 250–350 LoC → 350–450 LoC. Effort: 0.5–1 day → 1–1.5 days.
- **Why prior reviews missed BLOCKER #1:** all 3 absorbed the design's stated framing (Step 0 lives in the Phase 7 file). Codex traced "what does the agent do FIRST after compact?" and found the routing dependency was circular. Canonical case for outside-context adversarial review.
