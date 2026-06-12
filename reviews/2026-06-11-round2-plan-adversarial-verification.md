# Adversarial verification pass (Codex) — revised Round 2 plan — 2026-06-11

Second leg of duo review, AFTER 19 revisions (eng D1-D8 + outside-voice CX1-CX11) were applied.
Scope: did the revisions introduce NEW contradictions? Rubric: plan/system-design, PRECISION lens.
VERIFIED_AGAINST: main @ 4134705, plan file 327 lines.

## VERDICT: REVISE (4 BLOCKER / 5 CONCERN / 1 SUGGESTION)

## BLOCKERS
B1. Calibration gate contract inconsistent: Decision 2 says val-only 3-6 failures (25-50%); W1 step 5 and rubric item 2 still say 25-45% (3-5 of 12) and W1 still says "on v2 val+test" without restating val-only. Which integer set: {3,4,5} or {3,4,5,6}?
B2. Scoring authority ambiguous: W2 "scorer agent" writes receipts vs Reuse map's fail-closed comparator as authority. Why is any model scorer in the exact-primary path?
B3. Status vocabulary vs failure-mode table: invalid_repo_diff appears as FAIL status while Decision 8 claims only blocked_eval_headroom added. Prove it's carried R1 vocabulary or demote to ledger class.
B4. W-C drill mismatched: D7 `args: {mutationCap: 1}` contradicts D4 "caps only from args.contract"; ambiguous whether mutation rounds or call ceiling; expected ledger unstated.

## CONCERNS
C1. Model routing contradiction: Summary "every stage sonnet" vs D6 Fable-inherited Audit vs Non-goals "all-internal Sonnet" vs D5 Codex column.
C2. T6 "script finalization" after v2 manifest/PR can violate the CX5/D2 freeze order unless verification-only.
C3. Failure-spread >50% rule with 3 failures means 2-in-one-category fails — stricter than band suggests; specify integer handling.
C4. contested ≤25% lacks denominator (30 overall? per split?).
C5. Agent-mediated Gate weakens determinism claim unless receipt embeds command/exit-code/output-hash evidence.

## SUGGESTION
S1. Add a compact authoritative contract table before T1-T8 (calibration band, vocabulary, cap fields, scoring authority, model per stage).

## Disposition (all 10 addressed in plan rev 2, same date)
B1 ACCEPT — unified to owner-approved {3,4,5,6} of 12 val-only; W1 + rubric aligned, test scored for record only.
B2 ACCEPT — comparator (fail-closed) = sole scoring authority; "scorer agent" demoted to non-authoritative operator (scripts lack filesystem access); receipts embed command + exit code + comparator sha + output hash.
B3 REFUTE-AS-BLOCKER / FIX-AS-CLARITY — invalid_repo_diff IS carried R1 vocabulary (frozen in R1 run_contract legal_terminal_statuses); Decision 8 now enumerates the full carried list so readers can verify.
B4 ACCEPT — W-C injects modified frozen contract: args.contract.hard_caps.mutation_rounds_max=1; expected ledger enumerated; exhaustion_class=rounds.
C1 ACCEPT — Summary + Non-goals reworded to the real routing contract.
C2 ACCEPT — T6 demoted to verification/packaging only; any logic change re-triggers leak audit AND W0 re-probe; changes informed by v2 answers forbidden.
C3 ACCEPT — spread check waived at 3 failures; otherwise per-category max = floor(failures/2).
C4 ACCEPT — ≤7/30 overall AND ≤3/12 per claim-bearing split.
C5 ACCEPT — gate receipt embeds command line, exit code, stdout path + hash.
S1 ACCEPT — authoritative contract table added before tasks.

## Convergence (pass 3, same date)
10/10 fixes confirmed present and internally consistent by Codex. One residual found: stale
W-C row in the W3 run-series table still carried `{mutationCap:1}` + old wording — fixed to
the injected-contract form per Codex's prescription. Verdict: **APPROVED** (converged).
