#!/bin/bash
# AutoRefine Pattern-to-Evaluation-Strategy Selector Test Suite
# Locks the Phase 1 selector contract that bridges skill classification
# to downstream evaluation strategy selection.

PASS=0
FAIL=0
TOTAL=0

ROOT="/Users/surahli/Documents/projects/skill-improvement/autorefine"
MAIN_SKILL="$ROOT/SKILL.md"
GULF1="$ROOT/references/gulf1-comprehension.md"
GULF2="$ROOT/references/gulf2-specification.md"
GULF3="$ROOT/references/gulf3-generalization.md"
REF_MD="$ROOT/references.md"

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

echo "=== Test Suite: AutoRefine Pattern Eval Strategy Selector ==="
echo ""

for file in "$MAIN_SKILL" "$GULF1" "$GULF2" "$GULF3" "$REF_MD"; do
  if [ ! -f "$file" ]; then
    echo "FATAL: required prompt file missing: $file"
    exit 2
  fi
done

echo "--- Test Group 1: State + Audit Schema ---"
assert "references.md state schema includes selected_eval_strategy_id" \
  "$(grep -q 'selected_eval_strategy_id' "$REF_MD"; echo $?)"
assert "Phase 1 structured audit payload includes selected_eval_strategy_id" \
  "$(grep -q '"selected_eval_strategy_id": "pipeline_eval_strategy"' "$REF_MD"; echo $?)"
assert "session-log schema includes eval_strategy_resolution entry type" \
  "$(grep -q 'eval_strategy_resolution' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 2: Selector Section ---"
assert "references.md defines Pattern-to-Evaluation-Strategy Selector section" \
  "$(grep -q '^### Pattern-to-Evaluation-Strategy Selector' "$REF_MD"; echo $?)"
assert "references.md defines Strategy Definitions section" \
  "$(grep -q '^### Strategy Definitions' "$REF_MD"; echo $?)"
python3 - <<'PY'
from pathlib import Path
import re
import sys

text = Path("/Users/surahli/Documents/projects/skill-improvement/autorefine/references.md").read_text()
match = re.search(
    r"### Pattern-to-Evaluation-Strategy Selector\n(.*?)\n### Pattern Identification Section",
    text,
    re.S,
)
if not match:
    print("selector section missing")
    sys.exit(1)
section = match.group(1)
rows = re.findall(r"- `([^`]+)` -> `([^`]+)`", section)
mapping = dict(rows)
expected = {
    "tool_wrapper": "tool_wrapper_eval_strategy",
    "generator": "generator_eval_strategy",
    "reviewer": "reviewer_eval_strategy",
    "inversion": "inversion_eval_strategy",
    "pipeline": "pipeline_eval_strategy",
}
if mapping != expected or len(rows) != len(expected):
    print("unexpected selector mapping", rows)
    sys.exit(1)
sys.exit(0)
PY
assert "selector maps all 5 canonical patterns to exactly one strategy id" "$?"
python3 - <<'PY'
from pathlib import Path
import sys

text = Path("/Users/surahli/Documents/projects/skill-improvement/autorefine/references.md").read_text()
required = [
    "`tool_wrapper_eval_strategy`",
    "`generator_eval_strategy`",
    "`reviewer_eval_strategy`",
    "`inversion_eval_strategy`",
    "`pipeline_eval_strategy`",
]
missing = [item for item in required if item not in text]
sys.exit(0 if not missing else 1)
PY
assert "all selector targets are defined in Strategy Definitions" "$?"
echo ""

echo "--- Test Group 3: Phase 1 Wiring ---"
assert "Gulf 1 persists selected_eval_strategy_id in phase1_context" \
  "$(grep -q 'selected_eval_strategy_id' "$GULF1"; echo $?)"
assert "Gulf 1 resolves strategy through Pattern-to-Evaluation-Strategy Selector" \
  "$(grep -q 'Pattern-to-Evaluation-Strategy Selector' "$GULF1"; echo $?)"
assert "Gulf 1 logs eval_strategy_resolution to session-log" \
  "$(grep -q 'eval_strategy_resolution' "$GULF1"; echo $?)"
assert "Gulf 1 structured audit output emits selected_eval_strategy_id" \
  "$(grep -q 'selected_eval_strategy_id' "$GULF1"; echo $?)"
echo ""

echo "--- Test Group 4: Downstream Consumption ---"
assert "Main SKILL resume restores selected_eval_strategy_id" \
  "$(grep -q 'phase1_context.selected_eval_strategy_id' "$MAIN_SKILL"; echo $?)"
assert "Main SKILL downstream entry resolves missing strategy via selector" \
  "$(grep -q 'If only the pattern is available, resolve the missing strategy' "$MAIN_SKILL"; echo $?)"
assert "Gulf 2 downstream contract loads selected_eval_strategy_id" \
  "$(grep -q 'selected_eval_strategy_id' "$GULF2"; echo $?)"
assert "Gulf 2 Phase 4 uses selected_eval_strategy_id for failure focus" \
  "$(grep -q 'selected_eval_strategy_id.*failure focus' "$GULF2"; echo $?)"
assert "Gulf 2 Phase 5 uses selected_eval_strategy_id for tactic bundle" \
  "$(grep -q 'selected_eval_strategy_id.*Phase 5/6 tactic bundle' "$GULF2"; echo $?)"
assert "Gulf 3 downstream contract loads selected_eval_strategy_id" \
  "$(grep -q 'selected_eval_strategy_id' "$GULF3"; echo $?)"
assert "Gulf 3 mutations use selected_eval_strategy_id mutation priority" \
  "$(grep -q 'selected_eval_strategy_id.*Phase 7 mutation priority' "$GULF3"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
