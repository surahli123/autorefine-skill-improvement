# Codex Adversarial Review — Phase 7 Status Ledger v1.3 (re-pass)

**Date:** 2026-05-02
**Target:** `design_phase7_status_ledger.md` v1.3
**Reviewer:** Codex (high reasoning, read-only, fresh context)
**Verdict:** **REVISE** (still — second consecutive REVISE on this design)

## What v1.3 supposedly fixed
All 6 findings from the v1.2 codex review (1 BLOCKER, 3 CONCERNs, 1 SUGGESTION confirmed addressed in code).

## What v1.3 introduced or left unfixed

### BLOCKER

**1. Root compact recovery STILL fails the "workspace path only" case.**

AC #9 requires: fresh prompt with only the workspace path → agent recovers. But `autorefine/SKILL.md` Preflight Step 0 (lines 16-17) immediately runs `head -5 [skill-path]/SKILL.md` — treating the input as a SKILL path, not a workspace path. The working copy of an existing workspace lives at `[workspace]/skill-under-test/SKILL.md` (line 70). So if the user supplies `/tmp/autorefine-foo` (a workspace), the SKILL.md treats it as a skill directory to import, runs `head -5` on a nonexistent SKILL.md, and dies before Step C is reachable.

**Hard question:** when the user says only `/tmp/autorefine-foo`, how does the root skill distinguish "existing workspace to resume" from "target skill directory to import" BEFORE it runs the target-skill `head -5` check?

**Fix:** add a root resume preflight BEFORE target-skill validation. Pseudocode:
```
If user invokes with /path/to/X:
  IF /path/to/X/state.json exists:
    → "Resuming workspace from /path/to/X". Set [workspace] = that path.
    → Restore workspace_path / original_skill_path from state.json.
    → Run Step C (render & read ledger).
    → Skip Preflight Step 0 entirely.
  ELSE:
    → Proceed to existing Preflight Step 0 (treat as target skill path to import).
```

This must land at the very top of `autorefine/SKILL.md`, before "Step 0: Environment Check". Otherwise the routing is still circular at the input-disambiguation layer.

### CONCERN

**1. Step C insertion point is not clean enough.**

The current root `autorefine/SKILL.md` has multiple repeated "If workspace exists with state.json: read it... print pipeline status" resume clauses (lines 80, 83). v1.3 says to insert Step C between checkpoint recovery and Pipeline Status. But the existing duplicate resume clauses might run BEFORE Step C and route the agent past it.

**Fix:** design must require REPLACING/DEDUPING those stale clauses, not merely inserting Step C later in the flow.

**2. §3c still misreads the experiment-contract.json schema.**

v1.3 says `Primary metric: {primary_metric.metric_name} ≥ {thresholds.primary_threshold}` (line 165). The actual schema has:
- `primary_metric.threshold_pass` — not a sibling field of `metric_name` named "threshold"
- `thresholds.combined_score` — not `thresholds.primary_threshold`

(per references.md:2738 and :2748)

**Fix:** read the actual schema and use the actual field names. Stop guessing.

**3. AC #9 is split between pre-PR implementation and post-merge validation.**

§4 step 7 says compact-recovery validation happens before PR (counts toward AC #9). §8 acceptance criteria put #9 under "validated (separate, post-merge)". Contradiction.

**Fix:** if BLOCKER #1 is architectural, AC #9 should be merge-BLOCKING (move to the "done when" list, not the "validated when" list).

### SUGGESTION

**Test count internally inconsistent.** §4 says 32 tests; §5 runs T1–T35; §5 footer says 32 again. Off-by-3.

### What v1.3 got right
- proposed-vs-final distinction is mostly fixed
- `resolve_workspace_ref()` is strict enough on paper
- Exit codes 2/3/5 are enforceable, but only AFTER the Step C routing issue (BLOCKER #1) is fixed

---

## Pattern observation

Two consecutive codex passes have returned REVISE with architectural findings each time. The first found the routing-circularity at the SKILL.md / gulf3-generalization.md boundary (BLOCKER #1 v1.2). The second found the routing-circularity at the SKILL.md Preflight Step 0 layer (BLOCKER #1 v1.3 — the layer ABOVE).

Each fix pulled forward a deeper layer of the existing AutoRefine entry-point design that we hadn't accounted for. We've already spent 5 review cycles on a v1 fix.

**Diagnosis:** the design is trying to bolt compact-recovery onto a router (`autorefine/SKILL.md`) that was designed for the cold-start path (import a target skill, set up workspace, run pipeline). Resume-from-workspace was never a first-class entry mode. We're discovering that retrofit cost incrementally.
