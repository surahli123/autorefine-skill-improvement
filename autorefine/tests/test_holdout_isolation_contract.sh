#!/bin/bash
# AutoRefine holdout-isolation contract test suite
# Locks mutation-time holdout blocking and dev-only calibration sampling.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF_MD="$PROJECT_ROOT/autorefine/references.md"
GULF3="$PROJECT_ROOT/autorefine/references/gulf3-generalization.md"

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

echo "=== Test Suite: AutoRefine Holdout Isolation Contract ==="
echo ""

if [ ! -f "$REF_MD" ] || [ ! -f "$GULF3" ]; then
  echo "FATAL: required files are missing"
  exit 2
fi

echo "--- Test Group 1: mutation-time blocking ---"
assert "references.md marks adversarial_holdout inaccessible during mutation-time operations" \
  "$(grep -q '`adversarial_holdout`: inaccessible during mutation-time operations' "$REF_MD"; echo $?)"
assert "references.md requires holdout access attempts to fail closed" \
  "$(grep -q 'reject the read as a blocked holdout access attempt' "$REF_MD"; echo $?)"
assert "gulf3 keeps Session Close holdout outside the mutation-stage accessor" \
  "$(grep -q 'Do not route holdout reads through `references\.md > Restricted Mutation-Stage Dataset Access Path`' "$GULF3"; echo $?)"
echo ""

echo "--- Test Group 2: dev-only calibration sampling ---"
assert "baseline cadence task remains dev-only" \
  "$(grep -q 'dev-only sample set; never surface `adversarial_holdout` examples' "$GULF3"; echo $?)"
assert "per-experiment cadence task remains dev-only" \
  "$(grep -q 'dev-only surfaced samples; do not let cadence-triggered human review surface `adversarial_holdout` examples' "$GULF3"; echo $?)"
assert "Session Close spot-check task never surfaces holdout examples" \
  "$(grep -q 'never surface `adversarial_holdout` examples or holdout-derived evidence through Session Close calibration' "$GULF3"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
