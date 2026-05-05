# Review — Phase 7 Status Ledger Design

**Target:** `design_phase7_status_ledger.md` (v1 draft)
**Date:** 2026-05-02
**Reviews completed:** CE (oh-my-claudecode:code-reviewer, background, worktree-isolated) + plan-eng-review (gstack)
**Verdict (combined):** **Buildable with fixes.** No design-blocking architectural problems. 2 spec-level holes (terminal-state ambiguity + skip-state invisibility) must be patched before implementation. Several concerns + suggestions worth folding in.

---

## CE review summary

CE focused on logic defects, contract precision, and data-flow completeness. Most additive findings come from CE (it had a fresh-context worktree-isolated read of references.md and gulf3-generalization.md schemas).

### Findings (CE-numbered)

| # | Severity | Issue | Location | Recommended fix |
|---|---|---|---|---|
| 1 | **BLOCKER** | `last_mutation_status = "skipped"` not surfaced; ledger says "Analyze and propose next mutation" without telling reader the prior mutate was skipped → re-targeting | §3d enum | Add `last_mutation_status` to "You Are Here". Label states: `skipped → re-targeting`, `completed → advancing`, `null → first attempt`. |
| 2 | **BLOCKER** | Terminal `phase_status ∈ {completed, blocked}` both render as "Loop terminal" — user can't tell win from fail. Defeats L2. | §3f | Differentiate. `completed`: "Run finished — see `session_close_holdout/`". `blocked`: "Run blocked — see last error in `session-log.json`". |
| 3 | CONCERN | `current_experiment=0` could mean "baseline running" OR "baseline cleared." Reader can't tell. | §2b table | Add explicit "Baseline in progress (no eval results yet)" rendering when `experiment_id=0 AND last_eval_results_ref=null`. |
| 4 | CONCERN | Multi-judge disagreement state ignored. `decision_breakdown.combined_score = null` (or `proposed_decision = "disagreement"`) breaks `combined_score_pct` interpolation. | §3c, §3f | Add §3f row: render "Multi-judge disagreement, awaiting human review." |
| 5 | CONCERN | Contract source priority brittle. `inferred-contract.md` first 2 lines = title/heading, not success criterion. | §3c | Parse `## Success Criterion` heading + 2 lines below it. Don't blindly take first 2 lines. |
| 6 | CONCERN | `last_eval_results_ref` is RELATIVE path (`runs/.../iteration_NNN/...`). Script must resolve as `workspace / last_eval_results_ref`. Not stated → impl risk. | §3b | State path resolution rule explicitly. |
| 7 | CONCERN | §2b table omits `last_mutation_status` + `last_mutation_results_ref` (cited in schema line 28). Mutate→test handoff invisible. | §2b table + §3c template | Extend "You Are Here" with "Last mutation: {status} ({ref})". |
| 8 | SUGGESTION | T11 (truncation budget 280 chars) untested | §5 | Add T11. |
| 9 | SUGGESTION | "Stale ledger" scenario untested. Cheap insurance vs §6a residual risk. | §5, §3c | Add T12 + render "STALE — re-render" warning when ledger >5min old (read header timestamp). |
| 10 | SUGGESTION | §3a W3 rejection ("hook breaks portability") understated. Real disqualifier = lock-in to specific hook event names, not write permission. | §3a | Tighten reasoning. |
| 11 | SUGGESTION | §4 step 5 says "5 fixtures covering §3f conditions" but §3f has 7 conditions. Off-by-2. | §4 | Bump to 7 fixtures or reuse explanation. |
| 12 | SOLID | Script SRP intact. SKILL.md addition truly minimal. | — | Pass. |

### Open questions CE raised (design must answer)

| Q | Question | My recommended answer |
|---|---|---|
| Q1 | Stale `iteration_state` across runs (run terminated, new run started w/o clearing) — render new run's state or last persisted? | **Render whatever `state.json` currently says.** `state.json` is the source of truth. If state is stale, that's a state.json bug, not a ledger bug. Don't add cross-run reconciliation logic to v1. |
| Q2 | Mismatch detection between `current_run_path` and `iteration_state.run_path`? | **Yes — emit a warning row in the ledger if they disagree.** One-line check, defensive against manual workspace surgery. |
| Q3 | Should `active_experiment_contract_path` (run-scoped, adapter-aware) be in the contract fallback chain? | **Yes — it's the canonical run-scoped contract per `references.md` line 86.** Order: `active_experiment_contract_path` → `contract/inferred-contract.md` → "No contract on file." |
| Q4 | Ledger committed to git or `.gitignore`'d? | **`.gitignore`'d.** It's a generated, per-workspace artifact. Workspaces themselves are typically `/tmp/*` per Preflight Step 0.3. Add to `.gitignore` defensively for the rare case workspace lives inside the repo. |
| Q5 | Validation (acceptance criterion #5) — same failing skill or any skill? | **Same failing skill first** (reproduce d1+d4+d5 to prove the fix works), then any other skill (n>=2). Clarify in §8. |

---

## Plan-eng-review additions

CE was thorough on the design's architecture, contract, and tests. Plan-eng-review adds three things CE didn't cover, framed through eng-manager pattern recognition:

### A. Boring-by-default & reversibility (eng patterns #3, #6) — PASS

- Stack: Python stdlib. No new deps. Markdown output. Most boring possible choice. ✅
- Reversibility: Pure addition. SKILL.md edit is 3 lines, removable in seconds. No schema migration. ✅

### B. SKILL.md prompt-change risk — NEW FINDING

The 3-line addition to `gulf3-generalization.md` IS a prompt change. Per plan-eng-review's "If this plan touches LLM/prompt patterns, state which eval suites must be run":

- **No eval planned for the SKILL.md change itself.** The script is unit-tested but the prompt addition isn't validated against any rubric.
- **Mitigation (cheap):** Add a sanity test that loads `gulf3-generalization.md` and asserts the new "Step 0" rule string is present at the expected location. Catches accidental deletion during future edits. Not a quality eval, but cheap regression insurance.
- **Real eval (deferred):** AutoRefine itself is the eval system for skill changes. After ledger ships, dogfood the same `autorefine` skill on `autorefine` itself (meta) to see if Phase 7 behavior changes. Out of scope for v1 PR; capture as follow-up.

### C. Worktree parallelization

**Sequential implementation, no parallelization opportunity.** Single script + single SKILL.md edit + tests for the script. All dependencies serial.

---

## Consolidated decision summary

If we accept all CE recommendations + plan-eng additions, the design grows from ~370 lines to ~450 lines. The fixes are mostly clarifying language and additional graceful-degradation cases — no architectural change.

**Updates required to `design_phase7_status_ledger.md`:**

1. §3c template: add `Last mutation` row (CE #7), parse `## Success Criterion` heading not first 2 lines (CE #5), add `active_experiment_contract_path` to fallback chain (Q3).
2. §3d label map: add `last_mutation_status` distinction (CE #1).
3. §3f graceful degradation: add 4 new rows — terminal completed, terminal blocked, baseline-in-progress, multi-judge disagreement (CE #2, #3, #4).
4. §3b: state path resolution rule (CE #6).
5. §3a: tighten W3 rejection reasoning (CE #10).
6. §4 step 5: bump fixtures from 5 → 7 to match §3f (CE #11).
7. §5: add T11 (truncation), T12 (stale ledger warning) (CE #8, #9). Add T13: SKILL.md sanity-load assertion (plan-eng B).
8. §8: clarify acceptance criterion #5 — same failing skill first, then any other skill (Q5).
9. New §3.5 or appendix: "stale state mismatch" warning when `current_run_path` ≠ `iteration_state.run_path` (Q2).
10. Implementation step (§4): add `phase7-status.md` to `.gitignore` (Q4).

**Total additions:** ~80 lines of design doc, ~3 new tests, ~30 LoC of script logic for the new graceful-degradation cases. Still well within 0.5–1 day estimate.

**Items NOT to fold in:**
- Cross-run state reconciliation (Q1) — out of scope, not a ledger problem.
- Real eval for SKILL.md change (plan-eng B "real eval" tier) — defer.

---

## Verdict

**Buildable with fixes.** The 2 BLOCKERs are real spec holes (skip-state invisibility, terminal win/fail ambiguity) and must be patched. The CONCERNs harden the design against state shapes that exist in the schema. SUGGESTIONs are cheap quality wins.

**Recommendation:** apply all CE BLOCKERs + CONCERNs + SUGGESTIONs (12 fixes) and Q1–Q5 answers to `design_phase7_status_ledger.md`, then proceed to implementation. No second review pass needed — both passes converged on the same set of changes, and the design is now well-specified.

**Cross-model agreement:** CE (the worktree-isolated independent reviewer) and plan-eng-review (in-context fresh-eye pass) agreed that the design is buildable, agreed on scope discipline (F1/F3/F5 deferral defensible), and agreed that the v1 fix is the right shape. CE caught more spec-level issues because it had clean context; plan-eng-review added the prompt-change observability finding that CE missed. Together, they cover the design comprehensively.
