#!/bin/bash
# AutoRefine Phase 7 skip-outcome contract test suite
# Locks no-op mutation semantics so skip is distinct from missing or failed work.

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

echo "=== Test Suite: AutoRefine Phase 7 Skip Outcome ==="
echo ""

if [ ! -f "$REF_MD" ] || [ ! -f "$GULF3" ]; then
  echo "FATAL: required files are missing"
  exit 2
fi

echo "--- Test Group 1: schema presence ---"
assert "references.md documents mutation_outcome in the mutation artifact" \
  "$(grep -q '"mutation_outcome"' "$REF_MD"; echo $?)"
for field in '"status": "candidate_generated"' '"skip_reason_code"' '"skip_summary"' '"next_recommended_action"'; do
  assert "references.md documents mutation_outcome field $field" \
    "$(grep -q "$field" "$REF_MD"; echo $?)"
done
echo ""

echo "--- Test Group 2: skip semantics ---"
assert "references.md documents skipped last_mutation_status" \
  "$(grep -q 'last_mutation_status\":\"completed|skipped|invalid|blocked|null' "$REF_MD"; echo $?)"
assert "gulf3 says skip writes no candidate version artifact" \
  "$(grep -q 'It does not write `candidate_skill_revision`, does not write `version_artifact`' "$GULF3"; echo $?)"
assert "gulf3 says skip does not finalize experiment or increment cadence" \
  "$(grep -q 'does not finalize a new experiment record, and does not increment `completion_cadence`' "$GULF3"; echo $?)"
assert "gulf3 keeps skip in mutate with phase7_mutation_analysis next_action" \
  "$(grep -q 'keep `active_phase = \"mutate\"`, and keep `next_action = \"phase7_mutation_analysis\"`' "$GULF3"; echo $?)"
assert "references.md says skip does not emit test launch payload" \
  "$(grep -q 'Do not emit `## Test Launch Payload` when `mutation_outcome\.status = skipped`' "$REF_MD"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
