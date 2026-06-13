# TODOS

## Cross-model portability spot-check before any AutoRefine apply-back

- **What:** Before any optimized candidate is applied back to shipped `autorefine/`, run a
  handful of decision-contract scenarios through at least one non-Claude model.
- **Why:** The Fable 5 loop (`docs/plans/2026-06-10-001-fable5-darwin-skillopt-e2e-loop-design.md`)
  optimizes SKILL.md against a Sonnet target. The text may drift toward Claude-specific
  phrasing, while AutoRefine's design promises portability to the in-house agent
  (Read/Write/Bash only).
- **Pros:** Catches Claude-overfit before it ships into the portable bundle.
- **Cons:** Extra gate step; requires a non-Claude channel at apply-back time.
- **Context:** Decision D3 of the 2026-06-10 `/plan-eng-review` declared portability a
  non-goal for the optimization lane and parked the risk here. Trigger when the first
  candidate enters apply-back review.
- **Depends on / blocked by:** First successful candidate reaching the apply-back gate.
- **Added:** 2026-06-10 by /plan-eng-review (D10).
- **Status (2026-06-12, R3-T5):** FIRED for the Round 3 targeted bundle-repair apply-back.
  One Codex (non-Claude) blind exec answered the two target items' 10 surfaces against
  the candidate bundle; output attached to the R3 apply-back PR as informational evidence
  (disagreement is recorded, not an automatic block — eng-review D1①). Gate remains armed
  for future apply-backs.

## Fresh adversarial holdout — only for genuine OPTIMIZATION candidates (RESCOPED 2026-06-12)

- **What:** When a genuine *optimization* candidate (mutation-search / new-capability change to
  `autorefine/`) enters apply-back review, author a fresh adversarial holdout batch using the
  Round 2 v2 authoring protocol (panel + derivability + contested marking). Existing v1
  holdout is 6 items from the saturated era.
- **Rescoped (2026-06-12, R3-T5, eng-review D1②):** This does NOT trigger for *targeted
  bundle-repair* apply-backs (e.g. Round 3, which clarifies measured ambiguities and is gated
  by the v1+v2 robust regression suites). The original premise — "a fresh holdout makes the
  apply-back final exam match candidate-era difficulty" — is **voided by the dual-metric
  saturation finding**: the Sonnet+bundle channel is saturated on knowledge/stability, so a
  freshly authored holdout would saturate identically and prove nothing more than the existing
  suites already do. Re-arm only when the candidate changes the task surface (multi-step
  execution, tool-use fidelity, cross-file synthesis) such that a non-saturated holdout is
  actually constructible.
- **Why (original):** D4 of the R2 plan correctly deferred holdout authoring (no consumer yet).
- **Context:** docs/plans/2026-06-11-001 Decision 4; rescoped by R3 eng-review D1② + the R2
  dual-metric saturation result.
- **Depends on / blocked by:** first genuine OPTIMIZATION candidate (not a bundle repair).
- **Added:** 2026-06-11 by /plan-eng-review. **Rescoped:** 2026-06-12 (R3-T5).
