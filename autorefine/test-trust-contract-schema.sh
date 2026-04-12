#!/bin/bash
# AutoRefine trust-contract regression test
# Locks the v4.1 trust contract in references.md and Gulf 2 wording.

PASS=0
FAIL=0
TOTAL=0

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REF_MD="$REPO_ROOT/autorefine/references.md"
GULF2_MD="$REPO_ROOT/autorefine/SKILL-gulf2.md"
GULF3_MD="$REPO_ROOT/autorefine/SKILL-gulf3.md"
DESIGN_DOC="$REPO_ROOT/docs/design-autorefine-v4.1-trust-architecture.md"
PLAN_DOC="$REPO_ROOT/docs/plan-autorefine-v4.1-trust-implementation.md"

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

echo "=== Test Suite: AutoRefine Trust Contract Schema ==="
echo ""

for file in "$REF_MD" "$GULF2_MD" "$GULF3_MD" "$DESIGN_DOC" "$PLAN_DOC"; do
  if [ ! -f "$file" ]; then
    echo "FATAL: required file missing: $file"
    exit 2
  fi
done

echo "--- Test Group 1: Spot-check selection metadata ---"
python3 - "$REF_MD" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text()
match = re.search(
    r"### Human Spot-Check Task Schema\n(.*?)\n### Human Review Judgment Schema",
    text,
    re.S,
)
if not match:
    print("missing Human Spot-Check Task Schema section")
    sys.exit(1)
section = match.group(1)
required = [
    '"selection_strategy":"priority_order"',
    '"selection_priority":[',
    '"multi_judge_disagreement"',
    '"quality_eval"',
    '"near_threshold"',
    '"deterministic_fallback"',
    '"selection_reason":"multi_judge_disagreement"',
]
missing = [item for item in required if item not in section]
if missing:
    print("missing spot-check selection fields", missing)
    sys.exit(1)
sys.exit(0)
PY
assert "Human Spot-Check Task Schema includes prioritized selection metadata" "$?"
echo ""

echo "--- Test Group 2: Aggregate confusion matrix schema ---"
python3 - "$REF_MD" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text()
match = re.search(
    r"### Phase 6 Validation Result Payload\n(.*?)\n### Disagreement Actions",
    text,
    re.S,
)
if not match:
    print("missing Phase 6 Validation Result Payload section")
    sys.exit(1)
section = match.group(1)
required = [
    '"confusion_matrix":{',
    '"tp":',
    '"tn":',
    '"fp":',
    '"fn":',
    '"confusion_examples":{',
    '"false_positives":[',
    '"false_negatives":[',
]
missing = [item for item in required if item not in section]
if missing:
    print("missing confusion matrix fields", missing)
    sys.exit(1)
sys.exit(0)
PY
assert "Phase 6 validation payload includes aggregate confusion matrix and exemplars" "$?"
echo ""

echo "--- Test Group 3: Noise floor and holdout interpretation ---"
assert "references.md derives noise_floor from baseline_trials[]" \
  "$(grep -qF 'derive it from the Experiment 0 `baseline_trials[]` collection' "$REF_MD"; echo $?)"
assert "references.md defines holdout interpretation mode values" \
  "$(grep -qF '`directional_only` when `holdout_n < 10`, `decision_grade` when `holdout_n >= 10`' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 4: trust_gate artifact contract ---"
python3 - "$REF_MD" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text()
match = re.search(
    r"### session_close_holdout/variant_results\.json\n(.*?)\n---\n\n## Version Comparison Template",
    text,
    re.S,
)
if not match:
    print("missing session_close_holdout artifact section")
    sys.exit(1)
section = match.group(1)
required = [
    '"trust_gate": {',
    '"outcome":"review_required"',
    '"interpretation_mode":"directional_only"',
    '"hard_blockers": [',
    '"advisory_flags": [',
    '"false_pass_rate":',
    '"false_fail_rate":',
    '`block` > `review_required` > `promote`',
    '`holdout_below_baseline_plus_noise` triggers when `holdout_score < baseline_holdout_score`',
    '`within_noise_floor` triggers when `holdout_score` does not exceed `baseline_holdout_score + combined_score_noise_threshold`',
    'Healthy means `false_pass_rate <= 0.25` and `false_fail_rate <= 0.33`',
    '`false_pass_rate > 0.25 and <= 0.40` or `false_fail_rate > 0.33 and <= 0.50`',
    '`false_pass_rate > 0.40` or `false_fail_rate > 0.50` with `sample_count >= 6`',
    'Do not mirror `trust_gate` into `state.json.final_only_evaluation`',
]
missing = [item for item in required if item not in section]
if missing:
    print("missing trust_gate contract fields", missing)
    sys.exit(1)
sys.exit(0)
PY
assert "session_close_holdout artifact defines authoritative trust_gate contract" "$?"
echo ""

echo "--- Test Group 5: Gulf 2 Phase 2 contract alignment ---"
python3 - "$GULF2_MD" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text()

required = [
    "Multi-judge activation is `category + instability`, not category alone.",
    "`structural` evals remain single-judge.",
    "`task-completion` stays single-judge by default and escalates to panel mode only when `phase6_dev_fold_metrics` or human calibration shows instability.",
    "`quality` evals are eligible for panel review, but activate panel mode only when `phase6_dev_fold_metrics` or human calibration shows instability, or when the user explicitly forces it.",
    "`agreement_rule: unanimous`",
    "`references.md > Multi-Judge Verdict Schema`",
    "aggregate `confusion_matrix` plus `confusion_examples` on each `validation_results[]` row as the primary Phase 6 trust surface",
    "`phase6_dev_fold_metrics` plus `aggregated_tpr_tnr_summary` as the secondary stability diagnostic",
    "generate a confidence card showing the aggregate `confusion_matrix`, representative `confusion_examples`, TPR/TNR interpretation, and known blind spots",
    "Review `confusion_matrix` / `confusion_examples` first, then use `phase6_dev_fold_metrics` plus `aggregated_tpr_tnr_summary` to judge stability across folds.",
]

missing = [item for item in required if item not in text]
if missing:
    print("missing Gulf 2 contract phrases", missing)
    sys.exit(1)
sys.exit(0)
PY
assert "SKILL-gulf2.md locks Phase 5 instability routing and Phase 6 trust-surface wording" "$?"
echo ""

echo "--- Test Group 6: Gulf 3 Phase 3 contract alignment ---"
python3 - "$GULF3_MD" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text()

required = [
    "The root `noise_floor` summary remains derived from `baseline_trials[]`",
    "The queued task must explicitly preserve `selection_strategy = priority_order`, the ordered `selection_priority[]`, and a dev-only sample set",
    "do not let cadence-triggered human review surface `adversarial_holdout` examples or any holdout-only evidence path",
    "That queued task must preserve `selection_strategy = priority_order`, the ordered `selection_priority[]`, and dev-only surfaced samples",
    "Write `trust_gate` into that same artifact as the authoritative promotion surface for the selected candidate; do not duplicate `trust_gate` into `state.json.final_only_evaluation`.",
    "Label `trust_gate.holdout_assessment.interpretation_mode = directional_only` when `holdout_n < 10`, otherwise `decision_grade`.",
    "`trust_gate.outcome = promote` requires `holdout_score >= baseline_holdout_score + combined_score_noise_threshold`, zero hard blockers, and zero advisory flags.",
    "Set `trust_gate.outcome = block` when unresolved contributing disagreements remain, when an unapproved material judge remains in the selected candidate path",
    "When the selected candidate clears hard blockers but the holdout remains `directional_only`, the result stays within the noise floor, or calibration lands in `review_required` under the stored `false_pass_rate` / `false_fail_rate` thresholds, set `trust_gate.outcome = review_required`.",
    "This task still reviews dev-scored surfaced samples only: preserve `selection_strategy = priority_order`",
]

missing = [item for item in required if item not in text]
if missing:
    print("missing Gulf 3 contract phrases", missing)
    sys.exit(1)
sys.exit(0)
PY
assert "SKILL-gulf3.md locks Phase 7 dev-only routing and Session Close trust_gate semantics" "$?"
echo ""

echo "--- Test Group 7: Gulf 1 saturation guardrail ---"
assert "SKILL-gulf1.md adds advisory saturation prompt" \
  "$(grep -q 'Saturation check (after every 5th trace review' "$REPO_ROOT/autorefine/SKILL-gulf1.md"; echo $?)"
assert "SKILL-gulf1.md asks whether a new failure type appeared" \
  "$(grep -q 'new failure type appeared in the last 5 traces' "$REPO_ROOT/autorefine/SKILL-gulf1.md"; echo $?)"
assert "SKILL-gulf1.md keeps saturation advisory only" \
  "$(grep -q 'advisory saturation prompt, not a hard stop' "$REPO_ROOT/autorefine/SKILL-gulf1.md"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
