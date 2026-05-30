#!/bin/bash
# AutoRefine CONTRACT-ANCHOR Sentinel Integrity Test
# Guards the prose-contract sentinels in references.md. The decoupled contract
# tests slice schema sections BETWEEN these markers (see ADR-0001), so this test
# fails fast if a future edit duplicates, drops, or reorders a marker — the gap
# Codex flagged in the PR #47 adversarial review (no test of the test infra).
#
# KNOWN GAP (pre-existing, tracked as a follow-up): CI (.github/workflows/verify.yml)
# currently sweeps only dev/tests/test*.sh, so this guard — like all 20 sibling
# contract tests in autorefine/tests/ — is NOT yet run by CI. Run it locally:
#   bash autorefine/tests/test_contract_anchor_integrity.sh
# Wiring autorefine/tests/*.sh into CI (or relocating contract tests per the
# bundle policy in autorefine/README.md) is a separate, repo-wide decision.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
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

echo "=== Test Suite: CONTRACT-ANCHOR Sentinel Integrity ==="
echo ""

if [ ! -f "$REF_MD" ]; then
  echo "FATAL: references.md is missing"
  exit 2
fi

# Expected sentinel ids. Each start pairs with the matching end, EXCEPT
# iter_run_record: ONE start, TWO ends (initstate + full) — see ADR-0001 follow-up.
STARTS="state_json mutation_candidate_revision experiment_contract search_adapter corpus_provenance research_intake_sections research_intake_stage version_registry iter_run_record"
ENDS="state_json mutation_candidate_revision experiment_contract search_adapter corpus_provenance research_intake_sections research_intake_stage version_registry iter_run_record_initstate iter_run_record_full"

marker_line() {  # marker_line <id> <start|end> -> first matching line number (empty if absent)
  grep -nE "^<!-- CONTRACT-ANCHOR:${1}:${2} -->$" "$REF_MD" | head -1 | cut -d: -f1
}

echo "--- Test Group 1: each marker appears exactly once ---"
for id in $STARTS; do
  c=$(grep -cE "^<!-- CONTRACT-ANCHOR:${id}:start -->$" "$REF_MD")
  assert "start marker '${id}' appears exactly once (found ${c})" "$([ "$c" -eq 1 ]; echo $?)"
done
for id in $ENDS; do
  c=$(grep -cE "^<!-- CONTRACT-ANCHOR:${id}:end -->$" "$REF_MD")
  assert "end marker '${id}' appears exactly once (found ${c})" "$([ "$c" -eq 1 ]; echo $?)"
done
echo ""

echo "--- Test Group 2: no unexpected markers ---"
total_markers=$(grep -cE "^<!-- CONTRACT-ANCHOR:[a-z_]+:(start|end) -->$" "$REF_MD")
assert "exactly 19 CONTRACT-ANCHOR markers present (found ${total_markers})" \
  "$([ "$total_markers" -eq 19 ]; echo $?)"
echo ""

echo "--- Test Group 3: ordering invariants (start precedes end) ---"
for id in state_json mutation_candidate_revision experiment_contract search_adapter corpus_provenance research_intake_sections research_intake_stage version_registry; do
  s=$(marker_line "$id" start)
  e=$(marker_line "$id" end)
  assert "'${id}' start precedes end (${s:-?} < ${e:-?})" \
    "$([ -n "$s" ] && [ -n "$e" ] && [ "$s" -lt "$e" ]; echo $?)"
done
# iter_run_record shares one start with two ends — the order invariant Codex asked us to make explicit.
S=$(marker_line iter_run_record start)
I=$(marker_line iter_run_record_initstate end)
F=$(marker_line iter_run_record_full end)
assert "iter_run_record order start < initstate_end < full_end (${S:-?} < ${I:-?} < ${F:-?})" \
  "$([ -n "$S" ] && [ -n "$I" ] && [ -n "$F" ] && [ "$S" -lt "$I" ] && [ "$I" -lt "$F" ]; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
