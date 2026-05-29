#!/bin/bash
# AutoRefine Iteration Run Record Test Suite
# Locks the prompt/schema contract for the Phase 7 run-start record.

PASS=0
FAIL=0
TOTAL=0

SKILL_GULF3_MD="/Users/surahli/Documents/projects/skill-improvement/autorefine/references/gulf3-generalization.md"
REF_MD="/Users/surahli/Documents/projects/skill-improvement/autorefine/references.md"
DEV_DOC="/Users/surahli/Documents/projects/skill-improvement/dev/docs/design-autorefine-v4-skill-eval-platform.md"

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

echo "=== Test Suite: AutoRefine Iteration Run Record ==="
echo ""

if [ ! -f "$SKILL_GULF3_MD" ] || [ ! -f "$REF_MD" ] || [ ! -f "$DEV_DOC" ]; then
  echo "FATAL: required prompt or design files are missing"
  exit 2
fi

echo "--- Test Group 1: Cross-References ---"
assert "Gulf 3 references 'references.md > Iteration Run Record Schema'" \
  "$(grep -q 'references\.md > Iteration Run Record Schema' "$SKILL_GULF3_MD"; echo $?)"
assert "references.md defines '## Iteration Run Record Schema'" \
  "$(grep -q '^## Iteration Run Record Schema' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 2: Phase 7 Trigger Contract ---"
assert "Gulf 3 says a single iteration-start trigger creates the run record at Phase 7 start" \
  "$(grep -q 'single iteration-start trigger' "$SKILL_GULF3_MD" && grep -q 'Phase 7 start' "$SKILL_GULF3_MD"; echo $?)"
assert "Gulf 3 persists the active run identifier in state.json.current_run_id" \
  "$(grep -q 'state\.json\.current_run_id' "$SKILL_GULF3_MD"; echo $?)"
assert "Gulf 3 appends the run record to results.json.iteration_runs\\[\\]" \
  "$(grep -q 'results\.json\.iteration_runs\[\]' "$SKILL_GULF3_MD"; echo $?)"
echo ""

echo "--- Test Group 3: state.json + results.json Schema ---"
assert "state.json schema includes current_run_id" \
  "$(grep -q '"current_run_id"' "$REF_MD"; echo $?)"
assert "results.json schema includes iteration_runs[]" \
  "$(grep -q '"iteration_runs"' "$REF_MD"; echo $?)"
assert "results.json iteration run record stores a unique run_id" \
  "$(grep -q '"run_id"' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 4: Run Record Fields ---"
RUN_RECORD_SECTION="$(sed -n '/CONTRACT-ANCHOR:iter_run_record:start/,/CONTRACT-ANCHOR:iter_run_record_full:end/p' "$REF_MD")"
assert "Iteration Run Record Schema includes trigger field" \
  "$(echo "$RUN_RECORD_SECTION" | grep -q '"trigger"'; echo $?)"
assert "Iteration Run Record Schema includes run_path field" \
  "$(echo "$RUN_RECORD_SECTION" | grep -q '"run_path"'; echo $?)"
assert "Iteration Run Record Schema includes target_skill.skill_path" \
  "$(echo "$RUN_RECORD_SECTION" | grep -q '"skill_path"'; echo $?)"
assert "Iteration Run Record Schema includes target_version.evaluation_label" \
  "$(echo "$RUN_RECORD_SECTION" | grep -q '"evaluation_label"'; echo $?)"
assert "Iteration Run Record Schema includes target_version.snapshot_path" \
  "$(echo "$RUN_RECORD_SECTION" | grep -q '"snapshot_path"'; echo $?)"
assert "Iteration Run Record Schema includes target_version.snapshot_sha256" \
  "$(echo "$RUN_RECORD_SECTION" | grep -q '"snapshot_sha256"'; echo $?)"
echo ""

echo "--- Test Group 5: Session Log + Design Doc ---"
assert "session-log schema includes iteration_run_started entry" \
  "$(grep -q 'iteration_run_started' "$REF_MD"; echo $?)"
assert "design doc describes the iteration run record and unique run_id" \
  "$(grep -q 'iteration run record' "$DEV_DOC" && grep -q 'run_id' "$DEV_DOC"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
