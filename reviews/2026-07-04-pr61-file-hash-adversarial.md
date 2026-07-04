# Adversarial review — PR #61 file_hash portability fix (2026-07-04)

VERIFIED_AGAINST: fix/autorefine-tests-portable-ci-gate @ 74f2e6a @ 2026-07-04 (disk-arbitrated vs HEAD)
Reviewer: Codex (codex-cli 0.142.5, independent context), read-only sandbox.
Artifact type: **shell (bash) code diff** → lens = correctness + portability + edge cases + trust regression.
Scope: commit `74f2e6a` — portable `file_hash()` helper replacing 4 BSD-only `md5 -q` sites in `autorefine/tests/test_preflight.sh`.

## Verdict: REVISE (1 BLOCKER, 1 CONCERN, 1 SUGGESTION)

## BLOCKER — vacuous-pass hole (CONFIRMED, I concur)
`file_hash` can return an empty string on failure, and the call sites compare equality only:
`[ "$ORIGINAL_HASH" = "$COPY_HASH" ]` is TRUE when both are `""`. If a hash tool is
absent, or the target file is missing (so `shasum` errors and the piped `awk` still exits 0
with empty stdout), the Group-1 "original skill unchanged (hashes match)" assert PASSES with
zero evidence. This is the exact vacuous-pass anti-pattern this repo's own audit flags
(P2-7/P2-9) — shipping it inside a *trust-hardening* PR is self-contradictory.

Two mechanics behind it: (a) `shasum "$1" | awk '{print $1}'` returns awk's status, not
shasum's — awk exits 0 on empty input even when shasum failed; (b) the call sites ignore the
assignment status and never check non-empty.

**Fix (adopted):** make hash acquisition prove success + non-empty before any comparison;
drop the `| awk` pipe (use `${out%% *}` param-expansion, which also removes the pipefail
exposure entirely); add `-n` guards at all call sites.

## CONCERN — availability-based vs success-based tool selection (adopted)
Fallback picks the *first tool present*, not the *first tool that succeeds*. For a trust test
the right semantics is fail-loudly: if the selected hasher errors, `return 1` rather than
compare garbage. (Codex: "resolve one working hasher, or fail before trust assertions.")
Adopted via `out=$(cmd "$1") || return 1` per branch. Not adopting "try next tool on failure"
— fail-loudly is correct for a trust gate. Cross-machine algorithm mismatch is a non-issue
(equality-only, single-machine per run) — Codex explicitly agreed this framing is correct.

## SUGGESTION — negative self-test (adopted)
Add a test that hashes a missing file and asserts `file_hash` returns non-zero AND emits
nothing — directly guarding the regression being fixed. Adopted.

## Full Codex output
Captured at `scratchpad/codex-out.txt` (session-local). Key excerpts inlined above.
Genuinely-strong note from Codex: the equality-only contract is the right framing.

---

## Round 2 — re-review of the revision (commit a164707)

VERIFIED_AGAINST: fix/autorefine-tests-portable-ci-gate @ a164707 @ 2026-07-04. CI: run 28693170552 `verify` = success.
Reviewer: Codex (independent context), read-only. Output: `scratchpad/codex-out-2.txt`.

### Verdict: APPROVED
The vacuous-pass BLOCKER is confirmed closed: failed hash commands `return 1` before emitting stdout, empty output is rejected, and both equality sites (`:113`, `:171`) require `-n` hashes before comparing — two empty strings can no longer satisfy the invariant. Codex also verified probe #3: filenames with spaces are safe (`*sum` output still starts with the hash; a line starting with a space parses to empty → fails closed).

### Residual (LOW, not blocking — a DIFFERENT/weaker gap than the original)
- **LOW CONCERN — malformed-success:** `file_hash` accepts any non-empty first token from a tool that exits 0. A (near-impossible on real runners) broken `shasum` printing `not-a-hash` and exiting 0 would be treated as evidence. Optional hardening: validate hash shape — `case "$out" in ""|*[!0-9a-fA-F]*) return 1;; esac` + length 32/64.
- **LOW CONCERN — wording:** the fallback is first-available/fail-closed, not success-based fallback. The shipped comment ("fails loudly if the selected tool errors") is accurate; no misleading claim was committed.
- **SUGGESTION:** a malformed-success self-test (fake `shasum` on PATH exiting 0 with garbage → assert `file_hash` fails).

**Disposition:** APPROVED + CI green. LOW items are defense-in-depth on a scenario that does not occur on GitHub Ubuntu/macOS runners; owner decision whether to apply the cheap hash-shape hardening or accept consciously and merge.
