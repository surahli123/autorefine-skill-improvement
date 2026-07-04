# Gulf 2 — Adversarial round 2 ("break all inflated parts") — 2026-06-14

8 probes targeting untested judge assumptions beyond the length confound. Blind Sonnet judge,
shuffled CASE-A..H, key withheld.

| case | probes | expected J1/J2 | judge J1/J2 | result |
|---|---|---|---|---|
| A | clean J2-fail (goal + FA only) | PASS/FAIL | PASS/FAIL | ✓ |
| B | J2 two-of-three threshold | PASS/PASS | PASS/PASS | ✓ |
| C | FA with reason, NO error string | PASS/PASS | PASS/PASS | ✓ (J1 accepts reason) |
| D | decision-not-failure (rejected ≠ tried) | FAIL/PASS | FAIL/PASS | ✓ (J1 distinguishes) |
| E | re-worded adv-02 (consistency) | PASS/FAIL | PASS/FAIL | ✓ (self-consistent) |
| F | "no failures — first try worked" | ???/PASS | FAIL/PASS | ⚠ RUBRIC GAP |
| G | bare resume, no expected outcome | PASS/FAIL | PASS/FAIL | ✓ (J2 enforces (c)) |
| H | FA buried in prose, no header | PASS/PASS | PASS/PASS | ✓ (J1 not header-matching) |

## Result
- **J1: 7/7 on clear cases.** Hardest probes passed: distinguishes tried-and-failed from
  considered-and-rejected (D), finds a failed approach in prose with no header (H), accepts a reason
  without a literal error string (C), self-consistent (E = adv-02 re-worded).
- **J2: 8/8.** Clean fail (A), enforces the expected-outcome requirement (G), threshold holds (B).
  The adversarial-1 J2 miss (adv-04) was a muddy probe (code-context leaked state), not a weak judge.
- **One real finding — a RUBRIC GAP, not a judge fault (F):** J1 as written FAILs a handover that
  correctly reports "no failed approaches — first try worked." A perfect handover for failure-free
  work is wrongly penalized. Does NOT affect this run (all C fixtures have failures by design); a fix
  would add "if the work credibly had no failures, J1 is N/A, not FAIL."

## Combined (adversarial-1 + adversarial-2)
- **J1: 11/11** on clear cases (length-invariant, not keyword/header-matching, distinguishes
  tried-vs-rejected, accepts reason-or-error, self-consistent).
- **J2: 11/12** (the single miss = the muddy adv-04 probe).

## Verdict
We tried hard to break the ruler across 12 adversarial cases; it held. The original 100/100 WAS
inflated by a trivially-separable good-vs-degraded set (the user's suspicion was correct), but under
adversarial pressure both judges are genuinely substantive. Honest residual caveats:
1. **J1 no-failure rubric gap** (non-biting here).
2. **Task softness is unchanged** — a trustworthy ruler does not make "recover an obvious
   self-contradictory rule" a hard test. That softness was accepted when we chose C-on-an-obvious-defect.

Cleared to run Gulf 3 with confidence in the MEASUREMENT (not in the difficulty).
