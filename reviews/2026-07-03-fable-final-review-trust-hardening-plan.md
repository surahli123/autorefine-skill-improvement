# Fable final review — AutoRefine trust-hardening plan v1 (2026-07-03)

Reviewing: `docs/plans/2026-07-03-001-autorefine-trust-hardening-plan.md` (my own draft — reviewed against the STORM panel, not rubber-stamped).
Inputs: STORM arbiter report (`reviews/2026-07-03-storm-critique-trust-hardening-plan.md`, verdict NEEDS REWORK, 4 blockers / 8 concerns / 19 revisions) + my independent re-verification of the load-bearing citations.

## Verdict: I CONCUR with NEEDS REWORK. The draft cannot be executed as written.

Independent verification (done by me, this session, not delegated):
- **B1 reproduces.** `gulf3-generalization.md:223`'s "Target baseline 60-80% (>90% = evals too easy)" sits in the Phase-7 mutation-loop Key rules — it is an *eval-suite score* band, not a Gulf-1 *trace fail-rate*. The bundle's actual fail-rate heuristics disagree with each other: Gotcha 5 (`references.md:~3013`) says `<30% fail = too easy`, "When AutoRefine Doesn't Help" item 2 (`:~3022`) says `<20%`, and item 2's remedy is "Add harder inputs" — the opposite of my draft's STOP. My WP2 as written gates the wrong quantity in the wrong direction and wires in a doc that contradicts its own stop message. This is the worst defect in the draft; 5/6 panel perspectives caught it independently.
- **B2 reproduces.** ds-writer was NOT saturated (mean composite 5.36/10) — my draft's own verify example cannot trigger the gate my draft proposes. I conflated "no measurable headroom on a strong baseline" (capability ceiling) with "saturated evals" (pass-rate ceiling). These need different detectors.
- **B3 reproduces.** `tests/test_campaign_readiness_py.py:3` imports the lib chain WP5(a) would delete; my WP5 verify omitted pytest. Executing as written breaks WP4's "202 pytest stay green."
- **B4 reproduces.** `runs/` is gitignored; my WP1 verify rested the P0 trust fix on uncommitted local fixtures + a prose-existence grep — the same vacuous-pass pattern the audit itself flagged (P2-7/P2-9). Embarrassingly circular: I wrote an audit-driven plan that repeats an audited anti-pattern.

## Adjudication of the 19 STORM revisions

**Accept as-is:** 1, 2, 3, 4, 6, 7, 9, 11, 12, 13, 14, 15, 16, 17, 19.
**Accept with modification:**
- **Rev 5 (noise gate):** accept "wire existing noise_floor, don't 2× score" — cheaper, reuses `gulf3:60` machinery. Add: log the margin (`combined_score − threshold − noise_floor`) in `decision_breakdown` so borderline keeps are visible.
- **Rev 8 (confound-identification guidance):** accept, and make it concrete: instruct the Phase-6 step to first LIST candidate surface correlates for this skill's failure taxonomy (length, section headers, keywords, formatting), then build one minimal pair per listed correlate — a checklist an agent can execute, not "be creative like the owner."
- **Rev 10 (WP5 via `git rm`):** accept; also gate on owner answer to Q2 (already an open question in the draft).
- **Rev 18 (WP7 timing):** accept the manual-screen reframe; REJECT running WP7 *before* WP1. A value screen scored through an unhardened judge pipeline inherits P0-1 — its verdicts wouldn't be trustworthy either direction. Order stays WP1 → WP7-screen, with WP2's automated gate no longer a WP7 dependency.
**Concur with panel rejections** (§f): the 6/8-robustness figure transfer, the P2-10 cross-model item (out of fence), the sizing quibble.

## What the panel missed (my additions for the final plan)

1. **Threshold reconciliation should land on Gotcha 5's <30%, not WADH's <20%** — it is consistent with the owner's global eval-calibration rule (baseline should fail 30-40%; >80% pass = too lenient). Fix WADH item 2 to match in the same edit (it's already in WP4's orphan-wire scope — one reconciled number everywhere).
2. **The final plan's spine should be inverted to match the owner's actual question** ("what makes autorefine not usable on other skills"): Trust fix (WP1) → honest headroom screen (WP7-as-screen, manual) → guardrails (WP2 advisory) are the value path; WP3/4/5/6 are hygiene and should be explicitly labeled as such, batchable, never blocking the value path.
3. **Session sizing / checkpoint discipline:** each WP must be executable in one session with committed artifacts (per owner's checkpoint rule; today's session-limit outage is the cautionary tale).
4. **B2's deeper lesson for the final plan:** "headroom" needs a two-detector definition — (a) eval saturation (pass-rate near ceiling → evals can't measure improvement) and (b) capability ceiling (strong baseline, real failures, but mutations can't beat it — only detectable by the existing 3-consecutive-discards breaker). The final plan should stop promising to detect (b) upfront; it can't.

## Disposition
Produce plan v2 via /writing-plans incorporating: STORM revisions (as adjudicated above) + my 4 additions. v1 stays on disk for the paper trail.
