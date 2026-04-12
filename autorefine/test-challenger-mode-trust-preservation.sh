#!/bin/bash

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DESIGN_DOC="$REPO_ROOT/docs/design-autorefine-v4.2-challenger-research-loop.md"
PLAN_DOC="$REPO_ROOT/docs/plan-autorefine-v4.2-challenger-research-loop.md"
REFS_MD="$REPO_ROOT/autorefine/references.md"
GULF3_MD="$REPO_ROOT/autorefine/SKILL-gulf3.md"

PASS_COUNT=0
FAIL_COUNT=0

pass_test() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail_test() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1 (missing '$2')"; }
assert_contains() { echo "$1" | grep -qF "$2" && pass_test "$3" || fail_test "$3" "$2"; }

echo ""
echo "================================================================"
echo "  AutoRefine v4.2 Challenger Trust-Preservation Tests"
echo "================================================================"
echo ""

DESIGN_CONTENT="$(cat "$DESIGN_DOC")"
PLAN_CONTENT="$(cat "$PLAN_DOC")"
REFS_CONTENT="$(cat "$REFS_MD")"
GULF3_CONTENT="$(cat "$GULF3_MD")"
HOLDOUT_SECTION="$(sed -n '/^### session_close_holdout\/variant_results.json/,/^---$/p' "$REFS_MD")"

echo "--- v4.2 design/plan trust-preservation wording ---"
assert_contains "$DESIGN_CONTENT" "The initial implementation should stay additive to the current docs/contracts and avoid reopening \`trust_gate\`, holdout routing, or Phase 6 trust semantics." "Design doc keeps v4.1 trust semantics closed"
assert_contains "$DESIGN_CONTENT" "\`trust_gate\` is authoritative only in \`session_close_holdout/variant_results.json\`." "Design doc keeps trust_gate authoritative only in holdout artifact"
assert_contains "$DESIGN_CONTENT" "Treat holdout as evaluation-only." "Design doc preserves holdout as evaluation-only"
assert_contains "$DESIGN_CONTENT" "Duplicate \`trust_gate\` into top-level state" "Design doc explicitly forbids top-level trust_gate duplication"
assert_contains "$DESIGN_CONTENT" "Any change to final outcomes: \`promote\`, \`review_required\`, \`block\`" "Design doc protects final outcome vocabulary"
assert_contains "$DESIGN_CONTENT" "Final promotion still happens only in Session Close through the existing holdout + \`trust_gate\` path." "Design doc preserves final promotion path"
assert_contains "$DESIGN_CONTENT" "Cross-run triggers based on prior final holdout outcomes are deferred until a later slice." "Design doc defers cross-run trust-path triggers"
assert_contains "$PLAN_CONTENT" "\`trust_gate\` remains authoritative only in \`session_close_holdout/variant_results.json\`." "Plan preserves trust_gate authority location"
assert_contains "$PLAN_CONTENT" "holdout remains evaluation-only and unavailable to challenger lanes." "Plan keeps holdout unavailable to challenger lanes"
assert_contains "$PLAN_CONTENT" "final promotion must continue to flow through the existing final holdout artifact and \`trust_gate\`" "Plan preserves existing final promotion flow"
assert_contains "$PLAN_CONTENT" "The final promotion path still flows through the existing holdout + \`trust_gate\`" "Plan checkpoint preserves final promotion path"
assert_contains "$PLAN_CONTENT" "trust-preservation test exists" "Plan requires a trust-preservation test"
echo ""

echo "--- existing v4.1 trust invariants still present in core contracts ---"
assert_contains "$HOLDOUT_SECTION" '"trust_gate": {' "references still define trust_gate in final holdout artifact"
assert_contains "$HOLDOUT_SECTION" '"outcome":"review_required"' "references still include review_required outcome"
assert_contains "$HOLDOUT_SECTION" '"interpretation_mode":"directional_only"' "references still include directional_only interpretation"
assert_contains "$HOLDOUT_SECTION" 'Do not mirror `trust_gate` into `state.json.final_only_evaluation`' "references still forbid trust_gate duplication into state"
assert_contains "$HOLDOUT_SECTION" '`block` > `review_required` > `promote`' "references still lock trust_gate precedence"
printf '%s\n' "$REFS_CONTENT" | grep -qF -- '- `trust_gate.noise_assessment.noise_source`: always `baseline_trials` for v4.1.' \
  && pass_test "references still derive trust noise from baseline_trials" \
  || fail_test "references still derive trust noise from baseline_trials" '- `trust_gate.noise_assessment.noise_source`: always `baseline_trials` for v4.1.'
assert_contains "$GULF3_CONTENT" 'Write `trust_gate` into that same artifact as the authoritative promotion surface for the selected candidate; do not duplicate `trust_gate` into `state.json.final_only_evaluation`.' "Gulf 3 still keeps trust_gate artifact-only"
assert_contains "$GULF3_CONTENT" 'Label `trust_gate.holdout_assessment.interpretation_mode = directional_only` when `holdout_n < 10`, otherwise `decision_grade`.' "Gulf 3 still preserves holdout interpretation split"
assert_contains "$GULF3_CONTENT" 'Treat it as evaluation-only: do not reopen Phase 5/6/7 refinement from these examples inside the same run.' "Gulf 3 still keeps holdout evaluation-only"
echo ""

echo "================================================================"
echo "  Results: $PASS_COUNT passed, $FAIL_COUNT failed"
echo "================================================================"
echo ""

[ "$FAIL_COUNT" -gt 0 ] && exit 1 || exit 0
