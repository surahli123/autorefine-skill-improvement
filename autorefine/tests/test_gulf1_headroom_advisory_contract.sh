#!/bin/bash
# docs-lint: asserts that the default-policy wording exists in shipped prose.
# This is a documentation-consistency tripwire, NOT a runtime behavior proof.
# AutoRefine U4 Gulf 1 headroom + Gulf 3 noise-gated keep-rule prose tripwire.
# Run locally:  bash autorefine/tests/test_gulf1_headroom_advisory_contract.sh

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF_MD="$PROJECT_ROOT/autorefine/references.md"
GULF1="$PROJECT_ROOT/autorefine/references/gulf1-comprehension.md"
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

slice_ref() {
  local start="$1"
  local stop="$2"
  awk -v start="$start" -v stop="$stop" '
    $0 ~ start { f=1 }
    f && $0 ~ stop { f=0 }
    f { print }
  ' "$REF_MD"
}

echo "=== Test Suite: Gulf 1 Headroom + Gulf 3 Noise-Gated Keep Rule ==="
echo ""

for path in "$REF_MD" "$GULF1" "$GULF3"; do
  if [ ! -f "$path" ]; then
    echo "FATAL: missing file $path"
    exit 2
  fi
done

GOTCHAS="$(slice_ref '^## Gotchas$' '^## Failure Taxonomy Template$')"
DECISION_BREAKDOWN="$(slice_ref '^### decision_breakdown fields$' '^### decision_explanation fields$')"
AGG_EXPLAINER="$(slice_ref '^## Aggregation Explainer Template$' '^## Loop-Back Protocol$')"
GULF1_EXIT="$(awk '/^### Gate: Gulf 1 Exit/{f=1} f && /^---$/{f=0} f{print}' "$GULF1")"
GULF3_PHASE7="$(awk '/^## Phase 7: AutoResearch Loop/{f=1} f{print}' "$GULF3")"

if [ -z "$GOTCHAS" ] || [ -z "$DECISION_BREAKDOWN" ] || [ -z "$AGG_EXPLAINER" ] || [ -z "$GULF1_EXIT" ] || [ -z "$GULF3_PHASE7" ]; then
  echo "FATAL: one or more section slices were empty"
  echo "GOTCHAS chars: ${#GOTCHAS}"
  echo "DECISION_BREAKDOWN chars: ${#DECISION_BREAKDOWN}"
  echo "AGG_EXPLAINER chars: ${#AGG_EXPLAINER}"
  echo "GULF1_EXIT chars: ${#GULF1_EXIT}"
  echo "GULF3_PHASE7 chars: ${#GULF3_PHASE7}"
  exit 2
fi

echo "--- Test Group 1: references.md Phase 3 fail-rate wording ---"
assert "When AutoRefine Doesn't Help uses the <30% fail-rate lead" \
  "$(echo "$GOTCHAS" | grep -qF '2. **Phase 3 fail rate <30%.**'; echo $?)"
assert "When AutoRefine Doesn't Help has no stale <20% fail-rate threshold" \
  "$(! echo "$GOTCHAS" | grep -qF 'Phase 3 fail rate <20%'; echo $?)"
echo ""

echo "--- Test Group 2: references.md decision_breakdown + explainer margin contract ---"
assert "decision_breakdown JSON example stores margin" \
  "$(echo "$DECISION_BREAKDOWN" | grep -qF '"margin": -0.034'; echo $?)"
assert "decision_breakdown prose defines margin formula and default borderline band" \
  "$(echo "$DECISION_BREAKDOWN" | grep -qF 'margin = combined_score - (threshold + noise_floor)' && echo "$DECISION_BREAKDOWN" | grep -qF 'default borderline band'; echo $?)"
assert "Aggregation Explainer shows threshold + noise_floor keep bar" \
  "$(echo "$AGG_EXPLAINER" | grep -qF 'threshold + noise_floor'; echo $?)"
assert "Aggregation Explainer shows decision_breakdown.margin" \
  "$(echo "$AGG_EXPLAINER" | grep -qF 'decision_breakdown.margin'; echo $?)"
echo ""

echo "--- Test Group 3: gulf1-comprehension.md Gulf 1 Exit headroom advisory ---"
assert "Gulf 1 Exit writes headroom_advisory" \
  "$(echo "$GULF1_EXIT" | grep -qF 'headroom_advisory'; echo $?)"
assert "Gulf 1 Exit keeps <30% as a default advisory threshold" \
  "$(echo "$GULF1_EXIT" | grep -qF 'If Phase 3 fail rate is <30% (default advisory threshold)'; echo $?)"
assert "Gulf 1 Exit labels small-n readings directional_only" \
  "$(echo "$GULF1_EXIT" | grep -qF 'directional_only'; echo $?)"
assert "Gulf 1 Exit preserves both low-fail-rate readings" \
  "$(echo "$GULF1_EXIT" | grep -qF 'fixtures too easy' && echo "$GULF1_EXIT" | grep -qF 'genuinely strong target'; echo $?)"
echo ""

echo "--- Test Group 4: gulf3-generalization.md noise-gated keep/discard rule ---"
assert "Gulf 3 keep/discard rule is noise-gated by default with stored margin" \
  "$(echo "$GULF3_PHASE7" | grep -qF 'The keep/discard rule is noise-gated by default:' && echo "$GULF3_PHASE7" | grep -qF 'combined_score >= threshold + noise_floor' && echo "$GULF3_PHASE7" | grep -qF 'decision_breakdown.margin' && echo "$GULF3_PHASE7" | grep -qF 'margin < 0.05'; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
