#!/bin/bash
# AutoRefine Domain Adapter Schema Test Suite
# Locks the generic adapter contract and state-field documentation.

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

echo "=== Test Suite: AutoRefine Domain Adapter Schema ==="
echo ""

if [ ! -f "$REF_MD" ] || [ ! -f "$MAIN_SKILL" ]; then
  echo "FATAL: required prompt files are missing"
  exit 2
fi

STATE_SECTION="$(sed -n '/CONTRACT-ANCHOR:state_json:start/,/CONTRACT-ANCHOR:state_json:end/p' "$REF_MD")"

echo "--- Test Group 1: references.md Sections ---"
assert "references.md defines Domain Adapter Contract Schema section" \
  "$(grep -q '^## Domain Adapter Contract Schema' "$REF_MD"; echo $?)"
assert "references.md defines Experiment Contract Schema section" \
  "$(grep -q '^## Experiment Contract Schema' "$REF_MD"; echo $?)"
assert "references.md defines Adapter Resolution Rules section" \
  "$(grep -q '^## Adapter Resolution Rules' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 2: adapter contract fields ---"
for field in adapter_id skill_family input_schema output_schema runner normalizer primary_metric secondary_metrics failure_taxonomy gold_source trust_rule; do
  assert "adapter contract documents $field" \
    "$(grep -q "\"$field\"" "$REF_MD"; echo $?)"
done
echo ""

echo "--- Test Group 3: state schema fields ---"
for field in adapter_config_path selected_adapter_id active_experiment_contract_path domain_eval_config_path; do
  assert "state.json schema includes $field" \
    "$(echo "$STATE_SECTION" | grep -q "$field"; echo $?)"
done
assert "state schema documents domain_eval_config_path as legacy alias" \
  "$(echo "$STATE_SECTION" | grep -q 'legacy alias for `adapter_config_path`'; echo $?)"
echo ""

echo "--- Test Group 4: runtime restore wiring ---"
assert "SKILL.md restores selected_adapter_id from state.json" \
  "$(grep -q 'state\.json\.selected_adapter_id' "$MAIN_SKILL"; echo $?)"
assert "SKILL.md restores adapter_config_path from state.json" \
  "$(grep -q 'state\.json\.adapter_config_path' "$MAIN_SKILL"; echo $?)"
assert "SKILL.md restores active_experiment_contract_path from state.json" \
  "$(grep -q 'state\.json\.active_experiment_contract_path' "$MAIN_SKILL"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
