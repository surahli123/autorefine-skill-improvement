#!/bin/bash
# AutoRefine trust-gate contract test suite
# Locks the final promotion surface, precedence rules, and calibration thresholds.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF_MD="$PROJECT_ROOT/autorefine/references.md"

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

echo "=== Test Suite: AutoRefine Trust Gate Contract ==="
echo ""

if [ ! -f "$REF_MD" ]; then
  echo "FATAL: required files are missing"
  exit 2
fi

echo "--- Test Group 1: authoritative surface ---"
assert "references.md documents trust_gate as authoritative final promotion contract" \
  "$(grep -q '`trust_gate`: authoritative final promotion contract' "$REF_MD"; echo $?)"
assert "references.md keeps trust_gate out of top-level state" \
  "$(grep -q 'Do not mirror `trust_gate` into `state\.json\.final_only_evaluation`' "$REF_MD"; echo $?)"
assert "references.md anchors trust-gate noise to baseline_trials" \
  "$(grep -q '`trust_gate\.noise_assessment\.noise_source`: always `baseline_trials` for v4\.1' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 2: precedence and thresholds ---"
assert "references.md documents deterministic trust-gate precedence" \
  "$(grep -q 'Deterministic precedence for `trust_gate\.outcome` is `block` > `review_required` > `promote`' "$REF_MD"; echo $?)"
assert "references.md documents healthy calibration thresholds" \
  "$(grep -q 'Healthy means `false_pass_rate <= 0\.25` and `false_fail_rate <= 0\.33`' "$REF_MD"; echo $?)"
assert "references.md documents review_required calibration thresholds" \
  "$(grep -q '`review_required` calibration means `false_pass_rate > 0\.25 and <= 0\.40` or `false_fail_rate > 0\.33 and <= 0\.50`' "$REF_MD"; echo $?)"
assert "references.md documents block calibration thresholds" \
  "$(grep -q '`block` calibration means `false_pass_rate > 0\.40` or `false_fail_rate > 0\.50` with `sample_count >= 6`' "$REF_MD"; echo $?)"
assert "references.md blocks calibration_block when sample_count < 6" \
  "$(grep -q 'If `sample_count < 6`, never emit `calibration_block`' "$REF_MD"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
