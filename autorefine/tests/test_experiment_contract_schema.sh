#!/bin/bash
# AutoRefine Experiment Contract Schema Test Suite
# Locks the run-scoped success-contract artifact and resume semantics.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF_MD="$PROJECT_ROOT/autorefine/references.md"
MAIN_SKILL="$PROJECT_ROOT/autorefine/SKILL.md"

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

echo "=== Test Suite: AutoRefine Experiment Contract Schema ==="
echo ""

if [ ! -f "$REF_MD" ] || [ ! -f "$MAIN_SKILL" ]; then
  echo "FATAL: required prompt files are missing"
  exit 2
fi

EXPERIMENT_SECTION="$(sed -n '/^<!-- CONTRACT-ANCHOR:experiment_contract:start -->$/,/^<!-- CONTRACT-ANCHOR:experiment_contract:end -->$/p' "$REF_MD")"

echo "--- Test Group 1: contract fields ---"
for field in run_id adapter_id objective fixture_refs primary_metric secondary_metrics thresholds hard_fail_dimensions holdout_policy mutation_scope evaluator_inputs; do
  assert "experiment contract documents $field" \
    "$(echo "$EXPERIMENT_SECTION" | grep -q "\"$field\""; echo $?)"
done
echo ""

echo "--- Test Group 2: contract semantics ---"
assert "experiment contract states mutation actor and evaluator read the same artifact" \
  "$(echo "$EXPERIMENT_SECTION" | grep -q 'mutation actor and evaluator must both read the same artifact'; echo $?)"
assert "experiment contract uses run-scoped experiment-contract.json path" \
  "$(grep -q '\[workspace\]/runs/<run-id>/experiment-contract\.json' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 3: runtime routing ---"
assert "SKILL.md treats active_experiment_contract_path as authoritative run-scoped success contract" \
  "$(grep -q 'authoritative run-scoped success contract' "$MAIN_SKILL"; echo $?)"
assert "SKILL.md does not silently downgrade from active adapter-aware run" \
  "$(grep -q 'Do not silently downgrade from an active adapter-aware run' "$MAIN_SKILL"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
