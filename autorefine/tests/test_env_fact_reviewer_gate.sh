#!/bin/bash
# AutoRefine env-fact reviewer-gate contract test suite
# Locks explicit confirmation for API/schema/filename mutations.

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

echo "=== Test Suite: AutoRefine Env-Fact Reviewer Gate ==="
echo ""

if [ ! -f "$REF_MD" ] || [ ! -f "$GULF3" ]; then
  echo "FATAL: required files are missing"
  exit 2
fi

echo "--- Test Group 1: schema presence ---"
assert "references.md documents reviewer_confirmation_gate" \
  "$(grep -q '"reviewer_confirmation_gate"' "$REF_MD"; echo $?)"
for field in '"required"' '"trigger_kinds"' '"status": "not_required"' '"reviewer_id"' '"confirmed_at"' '"notes"'; do
  assert "references.md documents reviewer gate field $field" \
    "$(grep -q "$field" "$REF_MD"; echo $?)"
done
echo ""

echo "--- Test Group 2: gating behavior ---"
assert "gulf3 requires reviewer gate when env facts are edited" \
  "$(grep -q 'If the candidate edits an externally constrained environment fact such as an API endpoint, schema, or filename, persist `mutation\.md > reviewer_confirmation_gate`' "$GULF3"; echo $?)"
assert "gulf3 blocks keep while reviewer gate is pending or rejected" \
  "$(grep -q 'If `mutation\.md > reviewer_confirmation_gate\.status` is `pending` or `rejected`, the candidate may not be kept' "$GULF3"; echo $?)"
assert "references.md documents reviewer gate statuses" \
  "$(grep -q '`reviewer_confirmation_gate\.status`: one of `not_required`, `pending`, `confirmed`, or `rejected`' "$REF_MD"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
