# OMC code-reviewer — U3 Phase 6 Confound Hardening (2026-07-04)

VERIFIED_AGAINST: u3-phase6-confound-hardening (worktree) vs origin/main c5d73b2 @ 2026-07-04.
Reviewer: oh-my-claudecode:code-reviewer (opus, read-only, independent pass). Verdict: **REVISE** (0 BLOCKER, 2 CONCERN reproduced, 2 SUGGESTION).

## Confirmed strong (evidence, not assertion)
- Both new tests CI-wired + gate non-zero: `verify.yml:66-73` auto-discovers `test_*.sh`; removing guardrails → contract exit 5, replay exit 3.
- Step 4b is a REAL gate, not cosmetic (`gulf2-specification.md:133-137`): (a)-list/(b)-minimal-pairs/(c)-red-flag is agent-executable and WOULD have caught the original 100/100. Caveat: it's a process gate (agent-compliance), not a mechanical assert — acceptable for spec-level guidance.
- Fixtures substantive: real length-inversion — `adv-02` (7 lines) → J1 PASS (has FA) vs `adv-01` (25 lines) → J1 FAIL (no FA). Short=PASS, long=FAIL breaks length↔label; a length-detector scores 1/4.
- Scope CLEAN: additive-only (+11/-0, +6/-0), no Darwin-surface edits, `dev` untouched.

## CONCERN 1 — replay test is vacuous ON FIXTURE CONTENT (the file_hash class, again)
`test_judge_confound_replay.sh` pins (a) filename INVENTORY (`find -type f | wc -l`) + (b) greps of the two prose validation docs. It never checks case-file CONTENT. **Proof: emptying every case fixture to 0 bytes still yields 12/12 PASS.** The header "DATA-SHAPE ... asserts the confound record survives" oversells — it pins prose+inventory, not shape. Grep targets are both fragile (a benign reword `4 of 4` breaks it → false alarm) and loose (an unrelated doc with `4/4`+`1/4`+`100/100` passes → false green).
→ **Fix:** add ≥1 fixture-CONTENT invariant so it earns "data-shape": every case file non-empty (`[ -s ]`), and pin the length-inversion the thesis rests on (`adv-02` line-count < `adv-01`).
→ **My correction:** I earlier told the owner the replay test "genuinely discriminates." That was only half right — it discriminates on prose-evidence removal, but is vacuous on fixture content. The reviewer is right; I over-endorsed.

## CONCERN 2 — empty-correct guard reopens a false-PASS (trust regression)
`references.md:1512-1516`. The guard grants N/A→PASS for "no failures — first try worked." A DEGRADED handover that dropped its failed approaches can type exactly `CASE-F.md:9` ("None — the first approach worked on the first try") and earn PASS. "credibly" gives a text-only judge no operational discriminator. Closes false-FAIL (CASE-F) but opens possible false-PASS — and for a P0 TRUST unit, false-PASS is the worse error. Already self-flagged residual in `adversarial2-validation.md:37`.
→ **Fix:** operationalize "credibly" — honor the claim ONLY when the handover is internally consistent with it (no mention of retries/iterations/errors/debugging elsewhere); if it contradicts itself, don't grant N/A. Honestly document the residual limit (a fully-consistent silent-deletion can't be caught by a text judge).

## Q4 shell-test plumbing — SOUND (no vacuous-pass in the plumbing; the gap is WHAT is checked, per CONCERN 1).

## Disposition
Both fixes cheap. A P0 trust fix whose headline test passes on empty fixtures and whose guard reopens a false-PASS should not ship un-tightened. Apply both → re-verify → re-review → then commit.

## Fixes applied (2026-07-04, inline, method a)
- **CONCERN 1 fix** — `test_judge_confound_replay.sh` gains "Test Group 5: fixture CONTENT invariants": every case file non-empty (`[ -s ]`) for adv-0[1-4] + CASE-[A-H], plus a length-inversion assert (`adv-02` line-count < `adv-01`, pinning short=PASS/long=FAIL). Attack reproduced: truncating `adv-01.md` to 0 bytes now flips 2 asserts → replay FAILs (exit 2); restored → 25/25.
- **CONCERN 2 fix** — `references.md` guard gains a **Credibility condition**: N/A honored only when the handover is internally consistent (no retries/iterations/errors/debugging traces); a "first try worked" claim co-occurring with such traces is not credible → evaluate normally. Residual limit (perfectly-consistent silent-deletion uncatchable by a text judge) documented honestly. Tripwire gains an assert grepping `Credibility condition` so it can't be silently stripped.
- **Re-verify (independent):** tripwire 10/10, replay 25/25, full shell suite 23/0, pytest 202, leak 0, additive-only (references.md +13/-0, gulf2-specification.md +6/-0, zero deletions, no Darwin edits, `dev` unstaged).
- **Re-review → APPROVED.** OMC code-reviewer re-ran its own attacks: CONCERN 1 closed (0-byte fixtures now FAIL 12/25 exit 13; length margin 18 lines = not brittle); CONCERN 2 closed (credibility condition catches the self-contradicting liar; tripwire guards it; no over-block of genuine no-failure handovers — targets positive failure references, PASS few-shot preserved). Scope clean, tripwires gate non-zero. Non-blocking note: credibility condition assumes a semantic (not keyword-matching) judge — handled by prose intent. **Final verdict: APPROVED.**
