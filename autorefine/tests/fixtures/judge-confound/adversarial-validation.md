# Gulf 2 — Adversarial judge validation — 2026-06-14

Trigger: the original good-vs-degraded set gave TPR/TNR 100/100, which is suspicious — those two
piles differ on EVERYTHING (length, structure, FA, completeness), so a mere "length-detector" judge
would also score 100%. Built 4 cases that break the length↔failed-approaches correlation; blind
Sonnet judge, shuffled as CASE-A..D, no hints; compared to a withheld key.

| case (true nature) | expected J1/J2 | judge J1/J2 | J1 | J2 |
|---|---|---|---|---|
| CASE-A = adv-02 (short, has FA+error) | PASS / FAIL | PASS / FAIL | ✓ | ✓ |
| CASE-B = adv-01 (long, complete, NO FA) | FAIL / PASS | FAIL / PASS | ✓ | ✓ |
| CASE-C = adv-04 (long, FA, weak resume) | PASS / FAIL | PASS / PASS | ✓ | ✗ |
| CASE-D = adv-03 (FA *header*, vague, no error) | FAIL / PASS | FAIL / PASS | ✓ | ✓ |

## Result: 7/8
- **J1 (failed-approaches) = 4/4.** It FAILed a long complete doc with no FA (B), PASSed a SHORT doc
  with FA (A), and FAILed a doc with a `Failed approaches` HEADER but vague content (D). A pure
  length-detector scores **1/4** on J1; a keyword-matcher passes D. The judge did neither →
  **J1 is a substantive, specific judge — NOT length, NOT keyword.**
- **J2 (resumability) = 3/4.** The miss (C/adv-04) is a DEFENSIBLE ambiguous call: that doc's
  `Code context` (current JWT-only entrypoint, `verifyApiKey` "not written yet", signatures) conveys
  enough state to resume, so PASS is arguable. The probe was muddy (code-context leaked resumability),
  not a clear judge error → **J2 is real but has a SOFT boundary.**

## Verdict
The original 100/100 WAS inflated by a trivially-separable set (suspicion correct). But under
adversarial pressure the judges substantially beat a length-detector (J1: 4/4 vs a length-detector's
1/4), and **J1 — the judge for the primary defect F1 (dropped failed-approaches) — is validated as
specific.** J2 is serviceable but soft at the margin.

## Decision input for Gulf 3
- Lean on **J1** as the primary recovery signal (validated). Treat **J2** as secondary/soft.
- Optional hardening before Gulf 3: tighten adv-04 into a clean J2-FAIL probe (strip the Code-context
  resumability leak) and re-test J2, if a hard J2 is required. Otherwise proceed.
