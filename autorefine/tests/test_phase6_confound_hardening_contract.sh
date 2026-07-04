#!/bin/bash
# AutoRefine Phase 6 Confound-Hardening Prose Tripwire
# U3 (Phase 6 Confound Hardening) closes the P0 trust defect: shipped Phase 6
# could certify a shortcut judge (high TPR/TNR = mere agreement; a length-detector
# scored the original good-vs-degraded set 100/100). This test fails fast if the
# two prose guardrails that close that gap are ever removed:
#   (1) gulf2-specification.md Phase 6 "Step 4b: Confound check" requirement, and
#   (2) references.md Judge Prompt Template "empty-correct guard" (CASE-F rubric gap).
# Run locally:  bash autorefine/tests/test_phase6_confound_hardening_contract.sh

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GULF2_SPEC="$PROJECT_ROOT/autorefine/references/gulf2-specification.md"
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

echo "=== Test Suite: Phase 6 Confound-Hardening Prose Tripwire ==="
echo ""

if [ ! -f "$GULF2_SPEC" ]; then
  echo "FATAL: gulf2-specification.md is missing"
  exit 2
fi
if [ ! -f "$REF_MD" ]; then
  echo "FATAL: references.md is missing"
  exit 2
fi

# Slice the Phase 6 section (last ## section of the file) so greps are scoped.
PHASE6="$(awk '/^## Phase 6: Validate Judges/{f=1} f{print}' "$GULF2_SPEC")"
# Slice the Judge Prompt Template section (## Judge Prompt Template .. next ##).
JUDGE_TPL="$(awk '/^## Judge Prompt Template/{f=1} /^## TPR\/TNR Reference/{f=0} f{print}' "$REF_MD")"

echo "--- Test Group 1: gulf2-specification.md Phase 6 Step 4b confound-check ---"
assert "Phase 6 declares 'Step 4b: Confound check'" \
  "$(echo "$PHASE6" | grep -qF 'Step 4b: Confound check'; echo $?)"
assert "Step 4b requires listing surface correlates (shortcut-judge exploits)" \
  "$(echo "$PHASE6" | grep -qF 'surface correlate'; echo $?)"
assert "Step 4b requires a length-matched minimal pair per correlate" \
  "$(echo "$PHASE6" | grep -qF 'minimal pair'; echo $?)"
assert "Step 4b treats a near-perfect (>=95/95) score as a RED FLAG" \
  "$(echo "$PHASE6" | grep -qF '95/95'; echo $?)"
assert "Step 4b names the RED FLAG explicitly" \
  "$(echo "$PHASE6" | grep -qF 'RED FLAG'; echo $?)"
echo ""

echo "--- Test Group 2: references.md Judge Prompt Template empty-correct guard ---"
assert "Judge Prompt Template adds an 'Empty-correct guard'" \
  "$(echo "$JUDGE_TPL" | grep -qF 'Empty-correct guard'; echo $?)"
assert "guard covers 'first attempt worked' (no-failures case)" \
  "$(echo "$JUDGE_TPL" | grep -qF 'first attempt worked'; echo $?)"
assert "guard rules the failed-approaches criterion N/A (PASS not FAIL)" \
  "$(echo "$JUDGE_TPL" | grep -qF 'N/A'; echo $?)"
assert "guard is grounded in the CASE-F rubric gap" \
  "$(echo "$JUDGE_TPL" | grep -qF 'CASE-F'; echo $?)"
assert "guard conditions N/A on internal consistency (lying-empty guard)" \
  "$(echo "$JUDGE_TPL" | grep -qF 'Credibility condition'; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
