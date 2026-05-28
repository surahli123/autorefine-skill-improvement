#!/bin/bash
# AutoRefine Phase 7 edit-budget contract test suite
# Locks the bounded-edit-budget contract (Step A): a per-experiment cap on the
# number of discrete (##-section) changes a mutation makes, applied as a
# GENERATION-TIME constraint (not a post-hoc clip), activated by default at
# Phase 7 run-start, disabled via an explicit "unbounded" schedule, preserved
# across resume, recorded in the canonical mutation artifact, honored by
# challenger lanes, and read by a budget-aware content-ceiling guard.
#
# NOTE: these are prose/schema contract assertions. They prove the instructions
# and schema exist and are internally consistent; they do NOT exercise an agent
# honoring the budget at runtime. Runtime proof requires an /autorefine run.

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

echo "=== Test Suite: AutoRefine Phase 7 Edit Budget ==="
echo ""

if [ ! -f "$REF_MD" ] || [ ! -f "$GULF3" ]; then
  echo "FATAL: required files are missing"
  exit 2
fi

echo "--- Test Group 1: state schema + semantics ---"
assert "references.md state schema includes edit_budget field" \
  "$(grep -q '"edit_budget":null' "$REF_MD"; echo $?)"
assert "references.md documents edit_budget object shape (schedule/max_edits/current_budget)" \
  "$(grep -q '"schedule":"constant","max_edits":N,"current_budget":N' "$REF_MD"; echo $?)"
assert "references.md frames the budget as a generation-time constraint (not a post-hoc clip)" \
  "$(grep -q 'generation-time constraint' "$REF_MD"; echo $?)"
assert "references.md defines a discrete change canonically as distinct ## sections vs baseline" \
  "$(grep -q 'distinct .##. sections added, removed, or modified versus the baseline' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 2: activation, disable, validation, persistence, drift ---"
assert "gulf3 initializes edit_budget at iteration-start so it is active by default" \
  "$(grep -q 'Edit budget initialization:' "$GULF3"; echo $?)"
assert "gulf3 default budget is max_edits=3" \
  "$(grep -q '"schedule":"constant","max_edits":3,"current_budget":3' "$GULF3"; echo $?)"
assert "references.md documents iteration-start initialization of edit_budget" \
  "$(grep -q 'Phase 7 iteration-start initializes .edit_budget.' "$REF_MD"; echo $?)"
assert "disable is an explicit unbounded schedule, not null (no contradiction)" \
  "$(grep -q 'set .edit_budget = {"schedule":"unbounded"}. before Phase 7 start' "$REF_MD"; echo $?)"
assert "gulf3 validates schedule in {constant,unbounded} and max_edits >= 1" \
  "$(grep -q 'must be .>= 1' "$GULF3"; echo $?)"
assert "references.md preserves edit_budget on serialize and restores it on resume" \
  "$(grep -q 'preserve .edit_budget. unchanged' "$REF_MD"; echo $?)"
assert "references.md recomputes current_budget = max_edits on load/resume (drift guard)" \
  "$(grep -q 'recompute .current_budget = max_edits.' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 3: generation-time application, artifact field, run-start, lanes ---"
assert "gulf3 step 2a applies the edit budget" \
  "$(grep -q 'Apply the edit budget:' "$GULF3"; echo $?)"
assert "gulf3 constrains generation to at most current_budget discrete changes" \
  "$(grep -q 'make at most .edit_budget.current_budget. discrete changes' "$GULF3"; echo $?)"
assert "gulf3 defines a canonical change_count independent of the changes\[\] summary" \
  "$(grep -q 'compute .change_count. by comparing the candidate .content. against the baseline' "$GULF3"; echo $?)"
assert "gulf3 makes no cap when null or schedule=unbounded" \
  "$(grep -q 'is null or .schedule = "unbounded"., make no cap' "$GULF3"; echo $?)"
assert "the canonical mutation artifact schema defines edit_budget_applied" \
  "$(grep -q '.edit_budget_applied.: null when .state.json.edit_budget.' "$REF_MD"; echo $?)"
assert "the run-start storage contract initializes edit_budget" \
  "$(grep -q 'Initialize .state.json.edit_budget. in the same run-start write' "$REF_MD"; echo $?)"
assert "gulf3 requires challenger lanes + shortlist winner to obey the budget" \
  "$(grep -q 'every lane candidate AND the promoted shortlist winner must obey' "$GULF3"; echo $?)"
echo ""

echo "--- Test Group 4: budget-aware circuit breaker (P0 guardrail) ---"
assert "gulf3 content-ceiling diagnosis has a budget guard checked first" \
  "$(grep -q 'Budget guard (check first):' "$GULF3"; echo $?)"
assert "gulf3 budget guard reads edit_budget before concluding a ceiling" \
  "$(grep -q 'Before concluding a content ceiling, read .state.json.edit_budget.' "$GULF3"; echo $?)"
assert "gulf3 budget guard defines budget-binding via change_count hitting current_budget" \
  "$(grep -q 'budget-binding' "$GULF3"; echo $?)"
assert "gulf3 budget guard recommends raising max_edits before declaring done" \
  "$(grep -q 'Recommend raising .edit_budget.max_edits.' "$GULF3"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
