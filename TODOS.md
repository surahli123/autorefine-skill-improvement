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

## v2-era adversarial holdout before apply-back

- **What:** When apply-back review starts, author a fresh adversarial holdout batch using the
  Round 2 v2 authoring protocol (panel + derivability + contested marking). Existing v1
  holdout is 6 items from the saturated era.
- **Why:** D4 of the R2 plan correctly deferred holdout authoring (no consumer yet), but an
  apply-back gate scored against stale saturated-era holdout proves nothing about the candidate.
- **Pros:** apply-back final exam matches candidate-era difficulty.
- **Cons:** authoring cost at trigger time; stacks with the portability spot-check below.
- **Context:** docs/plans/2026-06-11-001 Decision 4 + eng-review TODO step, 2026-06-11.
- **Depends on / blocked by:** first candidate entering apply-back review (same trigger as
  the portability item above).
- **Added:** 2026-06-11 by /plan-eng-review.
