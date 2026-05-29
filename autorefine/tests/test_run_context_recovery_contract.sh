#!/bin/bash
# AutoRefine Run Context Recovery contract test suite
#
# Locks the CONSOLIDATION of the run-context recovery instructions in SKILL.md:
#   1. exactly ONE canonical general-load hydration line (no divergent duplicate
#      copies — they accreted as each phase appended its own state field, which is
#      exactly the drift that left `edit_budget` out of recovery);
#   2. `edit_budget` is restored on BOTH the general-load path AND the Step A
#      checkpoint-resume path, asserted positionally (not by a gameable whole-file
#      count), so a resumed Phase 7 run does not silently drop its budget;
#   3. recovery RECOMPUTES `current_budget = max_edits` on load/resume (the
#      edit-budget contract forbids trusting a persisted `current_budget`);
#   4. no field carried by the original variant union is dropped (exact,
#      backtick-delimited checks so `..._signals` cannot pass on `..._signals_path`).
#
# NOTE: prose contract assertions. They prove the instructions are consolidated
# and list the right fields in the right sections; they do NOT exercise an agent
# performing the hydration at runtime.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL_MD="$PROJECT_ROOT/autorefine/SKILL.md"

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

echo "=== Test Suite: AutoRefine Run Context Recovery (consolidation) ==="
echo ""

if [ ! -f "$SKILL_MD" ]; then
  echo "FATAL: SKILL.md is missing"
  exit 2
fi

# The single canonical general-load instruction (gated to the non-checkpoint path).
GENLOAD="$(grep -F 'If workspace exists **with** `state.json`' "$SKILL_MD")"
# The Step A checkpoint-resume section (between the Step A and Step B headers).
STEP_A="$(awk '/\*\*Step A: Checkpoint recovery/,/\*\*Step B: Ambient learning/' "$SKILL_MD")"

echo "--- Test Group 1: recovery is consolidated (no divergent duplicates) ---"
LOAD_COUNT=$(grep -Fc 'If workspace exists **with** `state.json`' "$SKILL_MD")
assert "exactly one general-load recovery instruction, found $LOAD_COUNT" \
  "$([ "$LOAD_COUNT" -eq 1 ]; echo $?)"
# the stale duplicate resume-deserialize lines (phrase unique to the removed cluster) are gone
STALE=$(grep -c 'before routing or resuming later phases' "$SKILL_MD")
assert "stale duplicate resume-deserialize lines removed, found $STALE" \
  "$([ "$STALE" -eq 0 ]; echo $?)"
echo ""

echo "--- Test Group 2: edit_budget restored correctly on BOTH paths ---"
assert "the canonical general-load line lists edit_budget" \
  "$(printf '%s' "$GENLOAD" | grep -q 'edit_budget'; echo $?)"
assert "the Step A checkpoint-resume section deserializes state.json.edit_budget" \
  "$(printf '%s' "$STEP_A" | grep -q 'state.json.edit_budget'; echo $?)"
assert "the general-load line recomputes current_budget = max_edits (not verbatim)" \
  "$(printf '%s' "$GENLOAD" | grep -qF 'recompute `current_budget = max_edits`'; echo $?)"
assert "the Step A checkpoint-resume section recomputes current_budget = max_edits (not verbatim)" \
  "$(printf '%s' "$STEP_A" | grep -qF 'recompute `current_budget = max_edits`'; echo $?)"
echo ""

echo "--- Test Group 3: no field-drop vs the original variant union (exact checks) ---"
for field in phase1_context selected_skill_pattern selected_eval_strategy_id \
             mutation_stage_split_access_policy iteration_state edit_budget \
             mid_session_preference_signals mid_session_preference_signals_path \
             selected_adapter_id adapter_config_path active_experiment_contract_path; do
  # backtick-delimited so `mid_session_preference_signals` does not match `..._signals_path`
  assert "canonical line lists \`$field\`" \
    "$(printf '%s' "$GENLOAD" | grep -qF "\`$field\`"; echo $?)"
done
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit "$FAIL"
