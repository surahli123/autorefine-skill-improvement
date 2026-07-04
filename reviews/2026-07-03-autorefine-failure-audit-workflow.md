# AutoRefine Bundle — Adversarial Failure Audit

**Scope:** `/Users/surahli/Documents/projects/skill-improvement/autorefine/` (SKILL.md 260L, references.md 6106L, 3 gulf files, 21 lib modules, 8 scripts, 34 tests)
**Governing question for every finding:** would this defect *invalidate results* or *block a user pointing autorefine at another skill*?
**Method note:** every finding below reproduced on inspection. Severities are the **adversarially-corrected** tiers, not the originally-claimed ones — the verification pass systematically walked back the alarm level of nearly every "P0/P1" claim. That walk-back is itself a load-bearing result (see §1, §5).

---

## 1. Executive Verdict

**Can autorefine be trusted to improve another skill today? Qualified yes on mechanism, one real trust hole on eval-validity.**

The loop *mechanism* is verified working: in the only clean end-to-end run (`runs/20260614T200407Z-c-handover-recovery/RESULT.md`) mutation discovered and removed a self-inflicted defect unprompted, and holdout scored 3/3 vs baseline 0/3. The runtime a user actually invokes — SKILL.md + `lib/` (21 modules) + `scripts/` (8 CLIs) — carries **zero** hardcoded home paths and runs cleanly.

But the audit surfaced exactly **one result-invalidating defect (P0)** and, notably, **zero genuine usability blockers (P1)** — every claimed P1 collapsed to maintenance-grade under scrutiny because the affected surfaces (self-tests, orphan doc sections, opt-in sub-features) are off the user's improvement path. The honest read: the tool *runs* reliably for a new user; the risk is that it can *certify a bad judge with full confidence*, and it lacks the guardrails that would stop a user wasting a run or being misled mid-loop.

**Top 3 blockers (impact-ranked):**

1. **P0 — Phase 6 can certify a shortcut judge as validated.** A judge that exploits a spurious feature (length, keyword, formatting) correlating with the label scores TPR/TNR = 100%, the confusion-matrix "trust surface" is empty, the confidence card reads High — and that 100% flows into Phase 7 as agent-judge weight `(TPR+TNR)/2 = 1.0`. This exact failure happened 1/1 in the only real run (`RESULT.md:18-20`, "INFLATED … trivially separable by length"); the fix was owner eval-expertise *outside* the shipped procedure. This is the product's core claim (validate the judges) failing silently.

2. **Two missing eval-validity guardrails** (both P2 but converging): no automated pre-Phase-7 headroom/saturation gate (`gulf1-comprehension.md:556-560`) — the tool burns up to 3 mutation experiments on a saturated baseline before its only saturation check fires reactively; and intra-loop keep/discard is not noise-gated (`gulf3-generalization.md` step 2e vs `references.md:5968`) — mutations are scored once, so the mid-loop changelog can show "kept +Npp" from noise, only corrected at the terminal holdout gate. These are the two ways a competent user gets a misleading or wasteful run.

3. **The bundle cannot be self-verified on a standalone install.** 6 of 21 shell contract tests hardcode the author's homedir and `exit 2` FATAL; 5 depend on a private `dev/` submodule that never ships; the fix (PR #61) is still **OPEN/unmerged** so the defect is live on `main` today. A cautious user who runs `tests/` to sanity-check what they installed gets a mix of FATAL crashes and vacuous silent-passes — no trustworthy signal.

**Bottom line:** ship-usable for a hands-on operator who brings their own eval judgment; **not** yet trustworthy for a naive user who relies on "Phase 6 said the judge is validated" or "CI is green."

---

## 2. P0 — Invalidates Results

### P0-1. Phase 6 judge validation has no defense against trivially-separable dev/test fixtures
`autorefine/references/gulf2-specification.md:127-142` · `autorefine/references.md:1514-1600`

Phase 6's whole purpose is to validate judges, but its Steps 1-6 (fold assignment, TPR/TNR, confusion-matrix review, confidence cards, Gulf 2 Exit gate) measure only judge-vs-human *agreement*. A shortcut judge that keys on a spurious feature perfectly correlated with the label agrees with humans on every fixture → **TPR/TNR = 100%, confusion matrix empty, confidence High**. `grep 'length bias|superficial|shortcut|spurious|adversarial harden'` across the whole bundle returns 0 hits — no minimal-pair / ablation / length-matched-fixture requirement exists anywhere. The inflated 100% then sets the agent-judge weight `(TPR+TNR)/2` in Phase 7 (`references.md:4005`, `gulf3-generalization.md:225`).

- **Demonstrated 1/1:** `runs/20260614T200407Z-c-handover-recovery/RESULT.md:18-20` — "Original set scored 100/100 — but that was INFLATED (good vs degraded were trivially separable by length). Adversarial hardening (12 cases over 2 rounds) → J1 11/11, J2 11/12." The hardening step that caught it is **not** in the shipped Phase 6.
- **Recurring, not coincidental:** injected/real skill defects commonly surface as surface correlates (missing section → shorter, formatting rule → format delta), so this failure mode generalizes to any new target skill.
- **Only backstop:** the human Gulf 2 Exit approval gate — which is uninstructed against this confound and, per `references.md:1523`, points the reviewer at ">90% both" as the *goal*, so 100/100 reads as success, not a red flag.

**Why P0, not usability:** the tool still runs (not a block) but it *certifies a shortcut judge as validated and weights meaningless keep/discard decisions at full confidence* — invalidating the eval-validity claim for a general user. Fix is coupled to P2-13 below (add an empty-correct / minimal-pair guard to the judge template *and* an adversarial-hardening step to Phase 6).

---

## 3. P1 — Blocks Usability

**None survived verification.** Every finding originally tagged P1 (and the two tagged P0-invalidates on tests/CI) was downgraded to P2 because the affected surface is off the user's improvement path: the shell self-tests are never invoked by the SKILL.md workflow; the orphan references.md sections are loaded section-by-section on pointer, so an un-pointed section is simply never read at runtime; the challenger/campaign/meta-learnings subsystems are opt-in or dormant and never touch a user's target skill. The absence of any true usability blocker is a genuine (mildly reassuring) result — but read it alongside §5, where the *reason* several were downgraded is that a claimed safety net (Phase 6 TPR/TNR) is exactly what P0-1 shows to be blind.

---

## 4. P2 — Maintenance

### Eval-validity hardening gaps (the substantive cluster)

**P2-1. No pre-Phase-7 headroom/saturation gate** — `gulf1-comprehension.md:556-560`, `gulf3-generalization.md:183-188`. Gulf 1 Exit *reports* baseline fail-rate but attaches no threshold rule; the only automated saturation stop is the Phase 7 content-ceiling breaker at `consecutive_discards >= 3` (`gulf3:183`). On a competent target (the common case — MEMORY.md ds-writer dogfood: "strong baselines dominate") the tool wastes up to ~3 experiments rediscovering what the fail-rate already showed. Partially mitigated by the mandatory human STOP gate + the `gulf3:223` "target 60-80%, >90% = too easy" calibration heuristic.

**P2-2. Intra-loop keep/discard is not noise-gated** — `gulf3-generalization.md:60` (baseline gets 3 trials → noise_floor) vs step 2e keep math vs `references.md:5968` (trust_gate noise check fires only at Session Close). Mutations are scored once; `grep` confirms noise logic lives only in baseline derivation, the challenger shortlist heuristic, and the terminal trust_gate. A borderline-noisy fixture set can layer several noise-driven "kept +Npp" mutations mid-run; only the terminal holdout catches it (and only if a holdout split is configured — else the run is labeled `directional_only`, never falsely validated). `runs/pitfalls-r2.md` finding #10 (v2-val-002 flipping across encounters) is real evidence of signal-starved ambiguity.

**P2-3. Judge Prompt Template has no "absence-of-failure ≠ failure" guard** — `references.md:1476-1508`. Component 2 only offers `FAIL: [concrete failure…]`; no instruction distinguishes "empty because the skill succeeded" from "empty because the field is missing." `RESULT.md:21` records this exact rubric gap ("J1 wrongly fails 'no failures — first try worked'; non-biting here") and the fix was never fed back into the shipped template. Detection currently depends on the human-labeled set happening to contain such a case. **Pair this fix with P0-1.**

**P2-4. Meta-learnings cross-campaign store is empty** — `autorefine/meta-learnings.md` (76L template, 0 real entries), consumed at `gulf3-generalization.md:62` (`parsed_meta_learnings.actionable_entry_ids`). 5 rounds + 2 dogfoods of lessons live only in gitignored `runs/pitfalls-*.md`, never promoted. Handled gracefully (`load_status=empty`, cold-start), so it neither invalidates nor blocks — but "cross-campaign learning" is functionally decorative until curated. (`reviews/2026-06-14-luban-audit-autorefine.md` §4a row 3.)

### Portability / self-verification (blocks the *maintainer/CI*, not the user)

**P2-5. 6 shell tests hard-fail on standalone install** — `tests/test_pattern_eval_strategy_selector.sh:10,32-36` (+ `test_iteration_run_record.sh:29`, `test_research_intake_contract.sh:10`, and 3 others). Hardcode `/Users/surahli/Documents/projects/skill-improvement/...` as ROOT then `exit 2` FATAL on first missing path. 15/21 use portable `$(dirname "$0")/../..` roots — a partial fix left these 6 behind.

**P2-6. 5 tests depend on the private `dev/` submodule** — `tests/test_research_intake_contract.sh:13-15`, `test_iteration_run_record.sh:11`. Point at `$ROOT/dev/docs/...` and `dev/seeds/...` that exist only in the private `surahli123/autorefine-dev` repo — permanently non-portable by construction, not just by path.

**P2-7. Test suite gives inconsistent signal on missing paths** — `tests/test_preflight.sh:150-162` silently skips → net PASS, while the 5 dev-coupled tests `exit 2` FATAL on the same missing-path class. A user smoke-testing the bundle gets a mix of vacuous passes and hard crashes.

**P2-8. The fix (PR #61) is still OPEN/unmerged** — `gh pr view 61` → `state:OPEN, mergedAt:null`. Changelog PR #62 already merged past it, so `main` does **not** contain the portability fix; the defect is live on anything a user pulls today.

**P2-9. 5 tests can never run in CI even after #61 merges** — `.github/workflows/verify.yml:14-25,84`. `CI_SUBMODULE_TOKEN` does not exist (`gh api …/actions/secrets` → `total_count:0`), so the `verify-private-submodule` job's `if: has_submodule_token == 'true'` is permanently unreachable. Reproduced on #61's branch: `pass=16 skip=5 fail=0` — those 5 always SKIP, never FAIL, so a corrupted CONTRACT-ANCHOR in them keeps CI green forever. PR #61's body claims they "run for real in the submodule-gated job" — false for this repo's config.

**P2-10. references.md is 432KB/6106L and has a documented full-dump hang** — `runs/pitfalls-r3.md:42-47` (codex-exec author hung after dumping the whole file). SKILL.md:202's "don't preload all support files" guard scopes only the `references/` split files, not references.md's own ~150 sections. Only bites non-Claude-Code harnesses that eager-load; Claude Code paginates >2000L.

**P2-11. Cross-model portability is an explicit non-goal, spot-checked twice** — `TODOS.md:13-22`. The Decision Contract wording (AMB-1/AMB-2, PR #54/#55) was tuned against Sonnet with no systematic non-Claude regression gate; two Codex/gpt-5.5 execs passed 5/5 but disagreement is "recorded, not a block." Unverified-guarantee, not a demonstrated failure.

**P2-12. state.json v2/v3 legacy-read path has zero test coverage** — `SKILL.md:85,137`; every fixture in `tests/` constructs `schema_version:4`. No executable migration code exists (`grep` of lib/scripts for `schema_version==2/3` / `migrat` → 0), so the risk is a future non-defensive read on a returning user's stale workspace, partly covered incidentally by render_phase7 test T4's sparse-field fixture.

**P2-13. Two apply-back safety gates enforced only in a markdown TODO** — `TODOS.md:3-44`. `grep "TODOS.md" autorefine/ .github/` → nothing. Green CI is no proof the portability spot-check or fresh-holdout step ran. TODOS.md is repo-root maintainer process doc, not shipped in the bundle; the substantive holdout-leakage risk *is* separately enforced in SKILL.md's split policy (`:52,65-68,143`).

**P2-14. Meta-learnings loader has zero test coverage** — `lib/meta_learnings_loader.py` (~1150L), `grep -rl meta_learnings_loader tests/` → 0. Untested is the norm here (10 of 18 non-trivial lib modules have no referencing test), so not an outlier; loader does report `load_status=empty` as a first-class status.

### Dead / unreachable / orphaned documentation

**P2-15. Campaign orchestrator family is unreachable from the documented workflow** — `scripts/run-campaign.py`, `scripts/prepare-gulf-gate-pack.py`. `grep run-campaign|prepare-gulf-gate-pack` across SKILL.md/references.md/references/*.md → 0 hits (vs record.py=5). The whole `lib/campaign_planning.py` + `campaign_readiness.py` + `gate_pack.py` chain terminates at scripts no prose ever tells the agent to run; `runs/` shows no real invocation artifact — never exercised end-to-end outside unit tests since built 2026-04-24.

**P2-16. 13 orphaned `## ` sections in references.md (~355/6106L, 5.8%)** — fence-aware parse found 60 real sections; 13 have zero inbound pointers: Challenger Lane Artifact Schema (4909-5016), Challenger Session-Log Entry Types (5202-5243), Quick Start > State Schema (912-950), Directional Results Template (884-911), The Three Gulfs (951-977), Hamel Integration Details (4075-4100), Per-Phase State Fields (3979-3996), Loop-Back Protocol (4058-4074), Failure Taxonomy Template (3028-3039), Judge Validation Report Format (3967-3978), When AutoRefine Doesn't Help (3019-3027), External Compatibility Notes (6052-6057), Judge Execution Procedure body (3040-3050). The existing Test Group 10 guard only checks the reverse direction (pointers resolve), so orphans are uncaught. Never read at runtime (loaded on pointer), so cost is maintainer confusion when trimming, not per-session tokens.

**P2-17. Challenger Lane Artifact Schema unreachable from the instruction that writes it** — `references.md:4909-5016`. `candidate_revision.json`/`lane_eval.json` occur only inside references.md; `gulf3:113` describes writing lane artifacts in prose but never cites the schema by name (its sibling mutation artifacts at `gulf3:77` *are* cited). Opt-in v4.2 branch, no code consumer (`grep challenger lib/ scripts/` → nothing). One-line cross-reference fix.

**P2-18. Challenger Session-Log Entry Types never cited by anything that logs them** — `references.md:5202-5243`. The 5 event types (`challenger_mode_started` etc.) appear only in references.md; `gulf3:77` says generically "Log the snapshot to session-log." Audit-only events, explicitly "do not replace the authoritative JSON artifacts," zero consumers.

**P2-19. Quick Start Step 5 (State Schema + Directional Results Template, 67L) has no inbound pointer** — `references.md:884-950`, while QS Steps 2-4 *are* wired (`gulf1:220,238,242,253`). Asymmetric orphan; the v2/v3/v4 migration rules it holds are separately wired at Initialize Workspace, so not functionally lost.

**P2-20. Loop-Back Protocol section is dead and already drifted** — `references.md:4058-4074`. Content duplicated inline at `gulf3:280`, which has *already* added `reset consecutive_discards = 0` and `increment loop_iteration` that the orphaned section lacks (while the section holds append-mode Step 1-4 detail gulf3 lacks). `grep "Loop-Back Protocol"` → self only. Live drift trap.

**P2-21. docs/{quickstart,methodology,trust-model}.md are structurally disconnected from SKILL.md** — `autorefine/README.md:42-44`, `docs/*` (28-31L each). `grep "docs/" SKILL.md` → 0. The public onboarding docs assert the trust model is "fully realized" and never mention the NEGATIVE dogfood, headroom-boundedness, or dormant subsystems (those live only in `docs/handover-*.md`). Can drift arbitrarily with nothing in CI to flag it — but generic to all prose docs; onboarding stubs, not results.

### Slop / duplication / contradiction in SKILL.md

**P2-22. Phase 7 `decision_breakdown` instruction stated twice verbatim** — `SKILL.md:227-228`. Same trigger clause + object + action, divergent tails ("before user presentation" vs "and the final aggregate…") — append-then-forgot-to-delete artifact. Idempotent write, so no runtime harm; divergence hazard for a future editor.

**P2-23. Evidence-array schema stated 3× in a 30-line span with inconsistent strictness** — `SKILL.md:229,258,259`. Only L229 carries the rejection rule (reject verdicts with empty `evidence[]`); L258/259 restate the schema and drop the consequence, and are near-duplicates of each other on adjacent lines. An editor patching the References restatement can miss L229's rule.

**P2-24. `decision_breakdown` field list flattens per-component fields and omits required top-level ones** — `SKILL.md:227` lists `weight_source`/`normalized_contribution` (per-component, `references.md:204`) alongside aggregate `combined_score`, and omits required top-level `formula`/`total_weight`/`combined_score_pct`/`proposed_decision` (`gulf3:225`). Full nested schema loads in Phase 7 via routing, so imprecision is bounded; downstream consumer is `render-phase7-status.py`.

**P2-25. Two near-identical fallback sentences for `selected_skill_pattern` retrieval** — `SKILL.md:139`. Consecutive sentences, same read-from-design-audit.md→hydrate→continue structure, differing only on whether `selected_eval_strategy_id` is bundled. Copy-paste-modify slop; both drive the same action.

**P2-26. Hydration blocks at L111/L114/L137 are 150-350-word em-dash run-ons** — `SKILL.md:111,114,137`. L111 is one ~180-word sentence deserializing 9 fields + a `constant`-schedule recompute + style_preferences rebuild. Resume/reload-only path (fresh first run never hits it), and downstream re-hydration with fallbacks (L139/141/143) self-heals dropped fields — so execution risk is limited; the demonstrated harm is author-side list drift (see P2-23-adjacent).

**P2-27. SKILL.md Gotchas list is not a subset of references.md's "full list"** — `SKILL.md:236` claims "full list in references.md > Gotchas" then lists 11 items; the sole references.md Gotchas section (`3005-3017`) has 9, missing 6 of SKILL.md's (incl. "never write to the original skill path") and adding 4 SKILL.md lacks. Neither list is a superset — the "full list" claim is false both directions. Both safety-critical items *are* present inline in SKILL.md where users read, so impact is auditor confusion.

---

## 5. Refuted-but-Instructive

The PLAUSIBLE queue was empty; the instructive material is in the **severity refutations** — claims whose facts held but whose alarm level did not. Recording them prevents re-litigation:

- **"5 CI-dormant tests / hardcoded-path tests INVALIDATE results" (claimed P0) → refuted to P2.** They are autorefine's *own* dev-contract self-tests; a user improving another skill never runs `autorefine/tests/*.sh`, and `runs/` results don't gate on them. Instructive: the bundle's test surface splits cleanly into "self-tests" (portability-broken but off-path) vs "user runtime" (SKILL/lib/scripts, clean).

- **"Judge template rubric gap has no mechanism to catch it" (in P2-3) → refuted** — Phase 6 TPR/TNR *is* that mechanism for over-strict judges. **But note the tension with P0-1:** that same Phase 6 is blind when the judge is over-strict via a *spurious feature that correlates with the label*. The net lesson: Phase 6 catches judges that disagree with humans, and is defenseless against judges that agree with humans for the wrong reason.

- **"Orphan sections are permanent bloat every session pays for" → factually wrong.** references.md loads section-by-section on pointer, so un-pointed sections are never read at runtime. Real cost is maintainer trimming risk, not tokens.

- **"Safety-critical Gotchas missing from the full list" → overstated.** The items ("never write to the original skill path", "confirm workspace location") are present inline in SKILL.md; only the *pointer target* is short. Contradiction is real, safety impact is not.

- **"Cross-model portability spot-checked only once" → factually wrong** (`TODOS.md` framing). At least two cross-model execs ran (R3-T5 `portability_receipt.json` 5/5+5/5; R4-T5 real gpt-5.5 exec over 5 records), both passing. Risk is unverified-guarantee, not demonstrated failure.

- **"12 of 20 lib modules have tests (so meta_learnings_loader is an outlier)" → wrong.** Untested is the norm: 10 of 18 non-trivial modules have zero referencing test. The coverage gap is real but not module-specific.

- **"Meta-learnings mechanism is decorative / silently does nothing" → overstated.** `load_meta_learnings_bundle` sets `load_status="empty"` as a first-class reported status — an empty cross-campaign store is the *correct* cold-start for a new user's first run, not a fabricated success.

---

## 6. Dependency-Ordered Fix Sequence

**Phase A — Trust (do first; nothing else matters if the eval is wrong):**
1. **Fix P0-1 + P2-3 together.** Add to Phase 6 a required adversarial-hardening / minimal-pair step (length-matched, feature-ablated fixture pairs) so a shortcut judge can't hit 100% TPR/TNR; add an empty-correct few-shot example + guard to the Judge Prompt Template (`references.md:1476-1508`). Re-point the Gulf 2 Exit gate away from ">90% = success" toward "inspect *why* agreement is perfect." *Blocks nothing else; must land before autorefine is recommended to a naive user.*

**Phase B — Guardrails (independent of A, high user-impact):**
2. **P2-1** — add an automated pre-Phase-7 headroom gate that reads the Gulf 1 baseline fail-rate against a threshold (reuse the `gulf3:223` 60-80% heuristic) and warns before spend.
3. **P2-2** — noise-gate intra-loop keep/discard: either re-score mutations ≥2× or require `combined_score >= threshold + noise_floor` at the per-experiment decision, not only at Session Close.

**Phase C — Self-verification (ordered; each depends on the prior):**
4. **P2-8 — land PR #61 first** (prerequisite: it partially fixes P2-5/P2-6).
5. Then **finish what #61 leaves**: **P2-9** (add `CI_SUBMODULE_TOKEN` *or* restructure the 5 dev-tests against the tracked `dev/docs/archive` snapshots, *and* correct the PR's false "runs for real" claim); **P2-7** (make the missing-path convention uniform — pick FATAL or SKIP, not both); **P2-5/P2-6** residuals for any test #61 didn't touch.
6. **P2-12** — add one `schema_version:2/3` fixture once the test suite is portable.

**Phase D — Documentation & dead code (low-risk cleanup, batchable, no upstream deps):**
7. **P2-20** first (live drift trap): reconcile Loop-Back Protocol — delete the orphan section or merge its unique detail into `gulf3:280`.
8. **P2-27, P2-22, P2-23, P2-24, P2-25** — SKILL.md slop/contradiction pass (single edit session).
9. **P2-16, P2-17, P2-18, P2-19, P2-21** — orphan-section pass: add the missing cross-references or prune; add an *orphan-direction* check to the Test Group 10 guard so this doesn't regress.
10. **P2-15** — decide campaign orchestrator family: document it in SKILL.md (and give it one end-to-end test) or delete `run-campaign.py`/`prepare-gulf-gate-pack.py` + their lib chain.

**Phase E — Deferred (acknowledged, low-yield):**
11. **P2-4 / P2-14** — seed meta-learnings.md from `runs/pitfalls-*.md` and add loader tests, *or* explicitly document the store as manual-cold-start-by-design.
12. **P2-10, P2-11, P2-13** — extend the anti-preload guard to references.md's own sections; add a non-Claude regression spot-check to the apply-back checklist; wire a CI check that TODOS.md gates fired (or move them into `verify.yml`).

**Critical-path note:** Phase A is the only sequence-blocker for the trust verdict. Phases B, C, D are mutually independent and parallelizable. Within C, step 4 (merge #61) gates steps 5-6.