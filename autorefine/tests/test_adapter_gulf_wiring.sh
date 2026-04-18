#!/bin/bash
# AutoRefine Adapter Gulf Wiring Test Suite
# Locks the adapter suggestion, handoff, and Phase 7 experiment-contract flow.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GULF1="$PROJECT_ROOT/autorefine/references/gulf1-comprehension.md"
GULF2="$PROJECT_ROOT/autorefine/references/gulf2-specification.md"
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

echo "=== Test Suite: AutoRefine Adapter Gulf Wiring ==="
echo ""

if [ ! -f "$GULF1" ] || [ ! -f "$GULF2" ] || [ ! -f "$GULF3" ]; then
  echo "FATAL: required gulf prompt files are missing"
  exit 2
fi

echo "--- Test Group 1: Gulf 1 suggestion flow ---"
assert "Gulf 1 defines adapter suggestion pass" \
  "$(grep -q 'Adapter suggestion pass' "$GULF1"; echo $?)"
assert "Gulf 1 requires explicit author confirmation before activation" \
  "$(grep -q 'suggestion, not an activation' "$GULF1" && grep -q 'Do not auto-activate an adapter from classification alone' "$GULF1"; echo $?)"
assert "Gulf 1 Step 7 writes canonical adapter_config_path" \
  "$(grep -q 'state\.json\.adapter_config_path' "$GULF1"; echo $?)"
echo ""

echo "--- Test Group 2: Gulf 2 handoff ---"
assert "Gulf 2 restores adapter-aware context from state" \
  "$(grep -q 'restore adapter-aware context from `state.json.selected_adapter_id` and `state.json.adapter_config_path`' "$GULF2"; echo $?)"
assert "Gulf 2 documents primary oracle vs secondary judges" \
  "$(grep -q 'primary oracle' "$GULF2" && grep -q 'secondary judges' "$GULF2"; echo $?)"
assert "Gulf 2 documents adapter-aware handoff artifact" \
  "$(grep -q 'Adapter-aware handoff artifact' "$GULF2"; echo $?)"
assert "Gulf 2 domain-metric evals prefer canonical adapter config pointer" \
  "$(grep -q 'canonical adapter config pointer' "$GULF2"; echo $?)"
echo ""

echo "--- Test Group 3: Gulf 3 experiment contract ---"
assert "Gulf 3 defines adapter-aware experiment contract" \
  "$(grep -q 'Adapter-aware experiment contract' "$GULF3"; echo $?)"
assert "Gulf 3 requires writing experiment-contract.json before baseline scoring" \
  "$(grep -q 'experiment-contract.json' "$GULF3" && grep -q 'before baseline scoring' "$GULF3"; echo $?)"
assert "Gulf 3 preserves evaluator separation" \
  "$(grep -q 'mutation actor and the evaluator must both read the same artifact' "$GULF3"; echo $?)"
assert "Gulf 3 domain metric scoring prefers canonical adapter config pointer" \
  "$(grep -q 'canonical adapter config pointer' "$GULF3"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
