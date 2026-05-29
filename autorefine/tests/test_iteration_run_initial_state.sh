#!/bin/bash
# AutoRefine Iteration Run Initial State Test Suite
# Locks the Phase 7 run-start contract for the recoverable initial state.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL_GULF3_MD="$PROJECT_ROOT/autorefine/references/gulf3-generalization.md"
REF_MD="$PROJECT_ROOT/autorefine/references.md"
PUBLIC_DOC="$PROJECT_ROOT/dev/docs/archive/design-autorefine-v4-skill-eval-platform-public-root-snapshot.md"
DEV_DOC="$PROJECT_ROOT/dev/docs/design-autorefine-v4-skill-eval-platform.md"

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

echo "=== Test Suite: AutoRefine Iteration Run Initial State ==="
echo ""

if [ ! -f "$SKILL_GULF3_MD" ] || [ ! -f "$REF_MD" ] || [ ! -f "$PUBLIC_DOC" ] || [ ! -f "$DEV_DOC" ]; then
  echo "FATAL: required prompt or design files are missing"
  exit 2
fi

STATE_SECTION="$(sed -n '/CONTRACT-ANCHOR:state_json:start/,/CONTRACT-ANCHOR:state_json:end/p' "$REF_MD")"
RUN_RECORD_SECTION="$(sed -n '/CONTRACT-ANCHOR:iter_run_record:start/,/CONTRACT-ANCHOR:iter_run_record_initstate:end/p' "$REF_MD")"
PUBLIC_STATE_SECTION="$(sed -n '/^### state.json extensions/,/^### fixtures-manifest.md extension/p' "$PUBLIC_DOC")"
DEV_STATE_SECTION="$(sed -n '/^### state.json extensions/,/^### fixtures-manifest.md extension/p' "$DEV_DOC")"

echo "--- Test Group 1: Phase 7 Run-Start Contract ---"
assert "Gulf 3 sets state.json.current_experiment = 0 when a new run starts" \
  "$(grep -q 'state\.json\.current_experiment = 0' "$SKILL_GULF3_MD"; echo $?)"
assert "Gulf 3 clears stale final_only_evaluation when the new run path changes" \
  "$(grep -q 'state\.json\.final_only_evaluation' "$SKILL_GULF3_MD" && grep -q 'clear it to null' "$SKILL_GULF3_MD"; echo $?)"
assert "Gulf 3 treats the run-start write as the baseline-in-progress recovery state" \
  "$(grep -q 'baseline-in-progress recovery state' "$SKILL_GULF3_MD"; echo $?)"
echo ""

echo "--- Test Group 2: references.md State Schema ---"
assert "state.json schema includes current_experiment" \
  "$(echo "$STATE_SECTION" | grep -q 'current_experiment'; echo $?)"
assert "state.json schema documents current_experiment = 0 for a new run" \
  "$(echo "$STATE_SECTION" | grep -q 'baseline-in-progress slot' && echo "$STATE_SECTION" | grep -q 'current_experiment = 0'; echo $?)"
assert "state.json schema documents clearing stale final_only_evaluation on new run start" \
  "$(echo "$STATE_SECTION" | grep -q 'clear it back to null as part of the same run-start write'; echo $?)"
assert "Iteration Run Record Schema documents initializing current_experiment = 0" \
  "$(echo "$RUN_RECORD_SECTION" | grep -q 'set `state.json.current_experiment = 0`'; echo $?)"
assert "Iteration Run Record Schema documents re-scoping completion_cadence to current_run_path" \
  "$(echo "$RUN_RECORD_SECTION" | grep -q 'scope_id = `state.json.current_run_path`'; echo $?)"
echo ""

echo "--- Test Group 3: Design Doc State Extensions ---"
assert "public design doc state extensions include current_run_path" \
  "$(echo "$PUBLIC_STATE_SECTION" | grep -q '\.current_run_path'; echo $?)"
assert "public design doc state extensions include current_experiment" \
  "$(echo "$PUBLIC_STATE_SECTION" | grep -q '\.current_experiment'; echo $?)"
assert "public design doc state extensions include completion_cadence" \
  "$(echo "$PUBLIC_STATE_SECTION" | grep -q '\.completion_cadence'; echo $?)"
assert "public design doc explains clearing stale final_only_evaluation at run start" \
  "$(echo "$PUBLIC_STATE_SECTION" | grep -q 'clear any stale `final_only_evaluation` object back to `null`'; echo $?)"
assert "dev design doc state extensions include current_run_path" \
  "$(echo "$DEV_STATE_SECTION" | grep -q '\.current_run_path'; echo $?)"
assert "dev design doc state extensions include current_experiment" \
  "$(echo "$DEV_STATE_SECTION" | grep -q '\.current_experiment'; echo $?)"
assert "dev design doc state extensions include completion_cadence" \
  "$(echo "$DEV_STATE_SECTION" | grep -q '\.completion_cadence'; echo $?)"
assert "dev design doc explains clearing stale final_only_evaluation at run start" \
  "$(echo "$DEV_STATE_SECTION" | grep -q 'clear any stale `final_only_evaluation` object back to `null`'; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
