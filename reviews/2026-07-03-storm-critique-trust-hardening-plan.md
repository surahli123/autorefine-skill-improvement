I have verified all load-bearing claims against the source files. Every critical file:line reproduces. Report follows.

# STORM Arbiter Report — AutoRefine Trust Hardening Plan

**Verdict: NEEDS REWORK (not approvable as-is).** The plan's two load-bearing work packages both have confirmed defects that would misfire on execution. WP2's headroom gate cites the wrong heuristic (verified across the source files, independently flagged by 5 of 6 perspectives), and its own verify case is a target its gate structurally cannot catch. WP1's only executable verification is n=1 on the training example with gitignored, uncommitted fixtures. The scope and sequencing (WP4/WP5/WP6/WP7 ordering) are recoverable with edits; the WP2/WP1 defects require rework before owner approval.

---

## (b) Confirmed BLOCKERs

**B1 — WP2 cites the wrong heuristic for the metric it gates on.** *(5/6 perspectives — the single strongest cross-perspective signal.)*
Verified: `gulf3-generalization.md:223` ("Target baseline 60-80% (>90% = evals too easy)") sits inside the Phase-7 mutation-loop "Key rules" block ("One mutation per experiment. Mutate a copy…") — it is a **Phase-7 mutation-baseline SCORE band, post-Gulf-2**, not a Gulf-1 fail rate. The metric WP2 actually gates (Gulf-1 / Phase-3 fail rate) has its *own* heuristics in the bundle, and they are (a) inverse in direction and (b) mutually inconsistent: `references.md:3013` "High Phase 3 fail rates are healthy… <30% = too easy" (a **fail**-rate, high=good) vs `references.md:3022` "Phase 3 fail rate <20%. Fixtures too easy" (different threshold). The plan (`:40`) also internally mixes units — "compare baseline **fail-rate** to a band (reuse the 60-80% target…); Baseline **pass-rate** ≥ threshold → STOP." Implemented as written, the gate compares the wrong quantity in the wrong direction. **Fix: gate on the Phase-3 fail-rate heuristic (`references.md:3013`), first reconciling the 3013/3022 <30%/<20% contradiction; drop the gulf3:223 citation.**

**B2 — WP2's own verify case is a case its gate cannot catch.** *(red-team + naive-adopter.)*
Verify (`:42`) says "ds-writer-dogfood-like **saturated** baseline must trigger the headroom STOP." Verified against `NEGATIVE-RESULT.md:9`: ds-writer scored mean composite **5.36/10, 0/11 ≥7 → "real headroom"** — it is explicitly *not* a saturation case. It failed because a capable baseline + a wrong-direction mutation, not because the target was saturated (`RESULT.md:39-43` confirms the three headroom points, and this one is "strong baseline," not "no measurable signal"). A saturation gate keyed on pass-rate would have let ds-writer proceed — which is what happened. WP2's motivating example does not support WP2's mechanism. **Fix: pick a verify fixture that is actually saturated (high pass-rate), or re-scope WP2's claim to "wasteful-run avoidance on saturated targets" and stop implying it would have caught ds-writer.**

**B3 — WP5 breaks WP4's "stay green" claim; verify omits the two importing tests.** *(maintainer-architect; reproduced directly.)*
`grep` confirms `tests/test_campaign_readiness_py.py:3` (`from autorefine.lib.campaign_readiness import …`) and `tests/test_prepare_gulf_gate_pack_py.py` (loads `gate_pack`) live in the **public** `autorefine/tests/`. WP5 option (a) moves that lib chain to `dev/`; WP5's verify (`:59`) only mentions `compileall` + "no prose dangles," never pytest — while WP4's verify (`:55`) asserts "existing 202 pytest… stay green." Executing WP5(a) as written red-lines those two tests. **Fix: WP5(a) must relocate/delete both pytest files with the modules and update the pytest count; add pytest to WP5's verify.**

**B4 — WP1's only executable verification is circular, n=1, and on uncommitted local files.** *(eval-scientist + product-owner + naive-adopter + risk-auditor — 4 perspectives.)*
Verify (`:37`) replays "the C-run's Gulf 2 on the archived fixtures." Confirmed: `runs/` is gitignored (`.gitignore` `runs/*`), so the fixtures exist only on this machine and are not a durable regression test. It is also n=1 on the *exact* case the fix was reverse-engineered from — it proves the fix catches its own training example, not that the new Phase-6 step generalizes to an unseen shortcut judge on a new skill (the whole point of a trust fix). The committed artifact WP1 does ship — a contract test asserting the prose exists (`:36`) — is the same vacuous-pass pattern the audit flags at P2-7/P2-9 (verified `audit:68,72`): a prose-existence grep proves words present, not efficacy. **Fix: copy the fixtures into a tracked path (e.g. `autorefine/tests/fixtures/`) and make the replay a permanent regression test; add at least one held-out confound *type* (not just length); demote the prose-grep test to a tripwire, not the trust proof.**

---

## (c) Confirmed CONCERNs (ranked)

**C1 — Hard percentage STOP at n=5-10 is statistically unsound and ignores the bundle's own n-aware machinery.** Verified: Gulf-1 fail rate is computed on 8-10 traces (`gulf1:540`), user may stop at ≥5 (`gulf1:544`). The bundle already downgrades even n=30-40 to "directional signal" (`references.md:1523`) and formalizes `directional_only` (n<10) vs `decision_grade` (n≥10) at the terminal trust_gate (`references.md:5964`). A hard auto-STOP band an order of magnitude below the bundle's own "directional only" bar is indefensible. **Fix: make the gate an advisory flag to the human already stopped at the Gulf-1 Exit approval gate, not an automated abort; import the n<10 `directional_only` framing.**

**C2 — "Hands-off user" goal is contradicted by the tool's own non-automatable gate.** *(naive-adopter.)* Verified `SKILL.md:239` Gotcha 2 ("Error analysis cannot be automated. Phase 3 requires the human to read outputs") and `gulf1:559` ("STOP. Wait for user approval"). Neither WP1 nor WP2 touches Phase 3. The goal (`:16`) should read "human-supervised, eval-trustworthy," not "hands-off." This also fixes the internal contradiction where WP7(a) calls Gulf-1 passes "cheap" (`:67`) when Gulf 1 contains the most expensive human-time step.

**C3 — WP6's seeded entries mostly cannot reach the only channel that steers a run.** *(eval-scientist + red-team.)* Verified: `meta-learnings.md:12` requires "at least two supporting cases before marking active"; `references.md:3636` "Only entries with status=active and review_status=approved may appear in actionable_entry_ids"; `meta-learnings.md:9` "Manual promotion only… explicit human approval." The n=1 findings WP6 wants to seed (dogfood Goodhart, C-run calibration, J1 rubric gap) land as `candidate` → excluded from steering by design. WP6's rationale ("makes the cross-campaign mechanism real instead of decorative") directly contradicts the audit's refutation of that framing (`audit:132`: an empty store is the correct cold-start, not decorative). WP6 can still ship a human-visible curated store, but must not claim it makes steering "real." **Fix: reword WP6's justification; label which entries have ≥2 cases (only those can be `active`); drop the "feeds WP2's stop messages" claim for n=1 entries.**

**C4 — "Mutually independent / parallelizable" (`:84`) contradicts a real WP2→WP4 data dependency.** *(risk-auditor.)* Verified: WP2 wires `When AutoRefine Doesn't Help` (L3019) into its stop message (`:40`); WP4 lists that same section among the 13 orphans to "wire or prune" (`:54`, audit P2-16 confirms 3019-3027). A parallel executor pruning it first deletes WP2's dependency. **Fix: either give WP2 ownership of that section's wire-in (removing it from WP4's orphan list), or state an explicit WP2-before-WP4 ordering and delete the "mutually independent" claim.**

**C5 — Sequencing diverges from the audit's dependency order without stated rationale.** *(eval-scientist + product-owner — 2 perspectives.)* Verified: audit places P2-4/meta-learnings in "Phase E — Deferred… low-yield" (`audit:156-157`); the plan puts WP6 at order 4, ahead of WP3 (audit Phase C, self-verification integrity) and WP5. It also puts WP4 (cosmetic slop) ahead of WP3 (test integrity) despite audit Phase C > Phase D. This is a silent reprioritization. **Fix: either restore audit order or add one line per inversion justifying the override.**

**C6 — WP4/WP5 are scheduled before Open-Question #1 that gates their entire justification.** *(product-owner + maintainer-architect.)* The plan's own S5 (`:88`) says Q1 (private tool vs public asset) "gates whether WP4/WP5 aim at maintainer hygiene or adopter-facing polish." The luban audit's status quo is "private tool" (`luban:13`). If private, WP4 dedup/orphan-wiring and WP5 dead-code serve an audience of one who already knows the codebase. Additionally, WP5's move-to-`dev/` is a near-one-way door: `dev/` is a private submodule CI cannot reach (P2-9). **Fix: gate WP4/WP5 explicitly on Q1; if WP5 proceeds, `git rm` to history (recoverable) rather than framing the submodule move as reversible.**

**C7 — WP4 dedup of the decision_breakdown/Phase-7 prose is not gated by the Darwin robust eval.** *(risk-auditor.)* SKILL.md:227-228 verbatim duplicate confirmed; that prose region is what the Darwin lane calibrated over R2-R5. WP4's verify ("202 pytest stay green") does not include the Darwin decision-JSON robustness suite. WP4 step 2 already knows to "keep the one with the rejection rule" (good), but a wording edit could still perturb the calibrated decision text. **Fix: if WP4 touches decision_breakdown/Phase-7 wording, re-run the Darwin decision-JSON eval, not just pytest.**

**C8 — WP4 orphan pass has no net-surface default; will drift to net-ADD.** *(maintainer-architect.)* "Wire or prune" with no default, while the audit says wiring has ~zero runtime benefit (orphans loaded on pointer). **Fix: state a prune-biased default; wire only sections with a concrete inbound need.**

---

## (d) Adjudicated contradictions

- **"WP7 needs only WP1" (product-owner) vs "WP7's WP2 gate is unvalidated → circular" (red-team).** *Compatible, not contradictory.* Resolution: run WP7's headroom screen **manually** using the existing Phase-3 fail-rate heuristic after WP1 lands; do **not** gate WP7 on the unbuilt WP2 automated gate. Elevate WP7 in priority (it is the plan's actual stated goal and the cheapest falsification of the headroom question), but correct the "cheap Gulf-1 pass" framing (C2) — a real screen still costs human Phase-3 reading.
- **Is WP6 a BLOCKER or CONCERN?** Two perspectives raised it; the "can't reach `actionable`" fact is real but WP6 retains value as a human-curated store. Adjudicated to **CONCERN + reprioritize** (C3/C5), not blocker.
- **red-team's WP1 "scoping ~6/8 robustness" mapping.** The `pitfalls-r3:16-22` additive-vs-scoping finding is real, but "100/100 = red flag" is arguably an additive positive instruction, not a trigger-scoping carve-out like AMB-1 — the exact 6/8 number does not transfer cleanly. The underlying point (n=1 verify is insufficient) survives independently via B4. **Demote the specific 6/8 claim; keep B4.**

---

## (e) Revision list (numbered, actionable)

1. **§1 goal (`:16`)** — replace "hands-off user" with "human-supervised user"; the tool's Phase-3 gate is non-automatable (Gotcha 2). *(C2)*
2. **WP2 headroom gate (`:40`)** — remove the `gulf3:223` citation; gate on the Phase-3 fail-rate heuristic (`references.md:3013`); first reconcile the `:3013` (<30%) vs `:3022` (<20%) contradiction and cite the survivor. Fix the fail-rate/pass-rate unit mix in the bullet. *(B1)*
3. **WP2 gate action (`:40`)** — change "STOP" to an advisory flag surfaced at the existing Gulf-1 Exit human approval gate; adopt the bundle's `directional_only` (n<10) framing rather than a hard auto-abort at n=5-10. *(C1)*
4. **WP2 verify (`:42`)** — drop the "ds-writer-like saturated baseline" replay (ds-writer had real headroom, not saturation); substitute a genuinely saturated fixture (high pass-rate), or narrow WP2's claim to wasteful-run avoidance. *(B2)*
5. **WP2 noise-gate (`:41`)** — resolve the open "pick one" now: wire the already-computed `noise_floor` (from baseline 3×, `gulf3:60`) into the per-experiment keep math; do **not** double per-experiment cost by scoring mutations 2×. *(eval-scientist SUGGESTION, accepted)*
6. **WP1 verify (`:37`)** — copy the C-run fixtures into a tracked path (`autorefine/tests/fixtures/`); make the replay a durable regression test; add ≥1 held-out confound *type* beyond length. *(B4)*
7. **WP1 contract test (`:36`)** — relabel the prose-existence grep as a tripwire, not the trust proof; the fixture replay (rev 6) is the trust proof. *(B4, maintainer-architect)*
8. **WP1 generalization prose (`:33`)** — the "length-matched / feature-ablated" instruction only names length; add guidance for an agent to *identify which feature to ablate* (the C-run's catch spanned ≥6 confound axes discovered iteratively, not length alone). *(eval-scientist + naive-adopter CONCERN)*
9. **WP5 (`:58-59`)** — option (a) must relocate/delete `test_campaign_readiness_py.py` and `test_prepare_gulf_gate_pack_py.py` with the lib chain and update the pytest count; add pytest to WP5's verify. *(B3)*
10. **WP5 (`:58`)** — gate on Q1; if proceeding, `git rm` to history rather than the one-way `dev/` submodule move. *(C6)*
11. **Sequencing table (`:73-84`)** — delete the "mutually independent / parallelizable" claim OR give WP2 ownership of the L3019 wire-in and remove it from WP4's orphan list. *(C4)*
12. **Sequencing table (`:78-81`)** — either restore audit order (WP3 before WP4; WP6 to last) or add a one-line rationale per inversion. *(C5)*
13. **WP6 (`:62`)** — reword "makes the cross-campaign mechanism real instead of decorative"; label which seeded entries have ≥2 supporting cases (only those can be `active`); the n=1 entries are `candidate` and will not steer runs or feed WP2. *(C3)*
14. **WP4 (`:54`)** — state a prune-biased default for the 13 orphans. *(C8)*
15. **WP4 (`:53`)** — if the dedup touches decision_breakdown/Phase-7 wording, add the Darwin decision-JSON eval to the verify, not just pytest. *(C7)*
16. **WP0 (`:27-29`)** — amend PR #61's body ("run for real in the submodule-gated job" is false per P2-9) *before* merge, so the known-false claim does not enter main's permanent history; tighten verify from "CI green" to "CI log shows the new shell-test step executing 16 pass / 5 skip." *(risk-auditor CONCERN + SUGGESTION)*
17. **WP3 (`:44-48`)** — either add P2-13 (apply-back gates have zero CI wiring) or explicitly list it in the scope fence as deferred; today it is silently dropped. *(eval-scientist SUGGESTION)*
18. **WP7 (`:65-69`)** — reframe as a manual headroom screen using the existing fail-rate heuristic, gated on WP1 only (not WP2's automated gate); note that "cheap Gulf-1 pass" still costs human Phase-3 time. Consider running it *earlier* as a falsification check given 3 converging headroom-negative points. *(product-owner + red-team, adjudicated)*
19. **All WPs** — add a one-line rollback note for WP1 (gate-semantics re-point) and WP2 (keep/discard threshold change), the two eval-semantics edits with only a single clean run as correctness proof. *(risk-auditor CONCERN)*

---

## (f) Points rejected / demoted

- **red-team WP1 "~6/8 scoping robustness" exact figure** — demoted; the AMB-1 carve-out analogy does not cleanly map to "100/100 = red flag" (additive positive instruction). The n=1-verify concern survives via B4.
- **red-team P2-10 references.md full-dump (cross-model)** — out of scope by the plan's own fence (`:23`, no cross-model work); audit defers to Phase E. Accept only the one-line ask: state the omission explicitly rather than silently inherit the P2-16 on-pointer-loading downgrade. Not a plan defect.
- **WP1 sized "M (1 session)" optimistic (product-owner SUGGESTION)** — noted as a sizing risk (Darwin AMB-1 took R3+R4), but not a correctness defect; left as caution, not a required edit.
- **P2-13 "confirmed but absent" framed as near-blocker** — it is a Phase-E deferred, low-yield item; dropping is defensible. Downgraded to rev 17 (make the omission explicit).