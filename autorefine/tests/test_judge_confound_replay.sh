#!/bin/bash
# AutoRefine Judge-Confound Fixture Replay (DATA-SHAPE only, NO LLM call)
# U3 (Phase 6 Confound Hardening). Pins the confound-breaking evidence that shows
# the recovery judges are substantive, NOT shortcut (length/keyword/header) judges.
# The original good-vs-degraded set scored TPR/TNR 100/100, but the two piles
# differed on EVERYTHING (length, structure, failed-approaches, completeness), so a
# pure length-detector ALSO scores 100/100 — the shortcut-judge confound. The
# adversarial/ (ORIGINAL, breaks length<->FA correlation) and adversarial2/
# (HARDENED, non-length confound families) fixtures + their validation records are
# the evidence. This test replays their SHAPE and asserts the confound record
# survives; it does NOT call a judge.
# Run locally:  bash autorefine/tests/test_judge_confound_replay.sh

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FIX="$PROJECT_ROOT/autorefine/tests/fixtures/judge-confound"
ADV="$FIX/adversarial"
ADV2="$FIX/adversarial2"
ADV_VAL="$FIX/adversarial-validation.md"
ADV2_VAL="$FIX/adversarial2-validation.md"

assert() {
  TOTAL=$((TOTAL + 1))
  local desc="$1"
  local result="$2"
  if [ "$result" -eq 0 ]; then
    PASS=$((PASS + 1))
    echo "  ✓ $desc"
  else
    FAIL=$((FAIL + 1))
    echo "  ✗ FAIL: $desc"
  fi
}

echo "=== Test Suite: Judge-Confound Fixture Replay (data-shape, no LLM) ==="
echo ""

# Required fixture package — FATAL if the whole confound package is absent.
if [ ! -d "$FIX" ]; then
  echo "FATAL: judge-confound fixture package is missing ($FIX)"
  exit 2
fi
for req in "$ADV" "$ADV2" "$ADV_VAL" "$ADV2_VAL"; do
  if [ ! -e "$req" ]; then
    echo "FATAL: required confound fixture is missing ($req)"
    exit 2
  fi
done

echo "--- Test Group 1: fixture inventory (exact counts) ---"
adv_n=$(find "$ADV" -maxdepth 1 -type f -name 'adv-0[1-4].md' | wc -l | tr -d ' ')
assert "exactly 4 ORIGINAL cases adv-0[1-4].md in adversarial/ (found ${adv_n})" \
  "$([ "$adv_n" -eq 4 ]; echo $?)"
case_n=$(find "$ADV2" -maxdepth 1 -type f -name 'CASE-[A-H].md' | wc -l | tr -d ' ')
assert "exactly 8 HARDENED cases CASE-[A-H].md in adversarial2/ (found ${case_n})" \
  "$([ "$case_n" -eq 8 ]; echo $?)"
assert "adversarial key present" "$([ -f "$ADV/adversarial-key.md" ]; echo $?)"
assert "adversarial2 key present" "$([ -f "$ADV2/adversarial2-key.md" ]; echo $?)"
echo ""

echo "--- Test Group 2: leak gate (no absolute homedir in the tracked package) ---"
leak_n=$(grep -rn "/Users/" "$FIX" | wc -l | tr -d ' ')
assert "no '/Users/' homedir leak in judge-confound package (found ${leak_n})" \
  "$([ "$leak_n" -eq 0 ]; echo $?)"
echo ""

echo "--- Test Group 3: ORIGINAL-set confound record (length confound) ---"
assert "adversarial-validation.md names the length-detector shortcut" \
  "$(grep -qF 'length-detector' "$ADV_VAL"; echo $?)"
assert "adversarial-validation.md records the suspicious 100/100 (TPR/TNR)" \
  "$(grep -qF '100/100' "$ADV_VAL"; echo $?)"
assert "adversarial-validation.md shows J1 beats a length-detector (4/4 vs 1/4)" \
  "$(grep -qF '4/4' "$ADV_VAL" && grep -qF '1/4' "$ADV_VAL"; echo $?)"
echo ""

echo "--- Test Group 4: HARDENED-set coverage (non-length confounds) ---"
assert "adversarial2-validation.md documents length-invariant/length-matched reasoning" \
  "$(grep -qE 'length-invariant|length-matched' "$ADV2_VAL"; echo $?)"
assert "adversarial2-validation.md covers keyword/header-matching confound" \
  "$(grep -qE 'header-matching|keyword/header' "$ADV2_VAL"; echo $?)"
assert "adversarial2-validation.md covers tried-vs-rejected confound" \
  "$(grep -qE 'tried-vs-rejected|considered-and-rejected' "$ADV2_VAL"; echo $?)"
assert "adversarial2-validation.md covers error-vs-reason confound" \
  "$(grep -qE 'reason-or-error|reason without a literal error' "$ADV2_VAL"; echo $?)"
echo ""

echo "--- Test Group 5: fixture CONTENT invariants (not just inventory/prose) ---"
# Closes the vacuous-on-fixtures gap the U3 review found: Groups 1-4 only count
# filenames and grep the prose docs, so emptying every case file to 0 bytes still
# passed. These asserts read the case CONTENT and fail if a case is empty.
for c in "$ADV"/adv-0[1-4].md "$ADV2"/CASE-[A-H].md; do
  assert "case fixture non-empty: $(basename "$c")" "$([ -s "$c" ]; echo $?)"
done
# Pin the length-inversion the whole confound-break rests on: the SHORT case
# (adv-02 = a PASS that HAS failed-approaches) must be shorter than the LONG case
# (adv-01 = a FAIL that has none), so a pure length-detector cannot separate PASS
# from FAIL. If this inverts, the fixtures no longer break the length<->label link.
adv01_lines=$(wc -l < "$ADV/adv-01.md" | tr -d ' ')
adv02_lines=$(wc -l < "$ADV/adv-02.md" | tr -d ' ')
assert "length-inversion holds: adv-02 (short/PASS) < adv-01 (long/FAIL) [${adv02_lines}<${adv01_lines}]" \
  "$([ "$adv02_lines" -lt "$adv01_lines" ]; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
