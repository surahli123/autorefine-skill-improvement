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
echo "  AutoRefine v4.2 Challenger Mode Schema Tests"
echo "================================================================"
echo ""

DESIGN_CONTENT="$(cat "$DESIGN_DOC")"
PLAN_CONTENT="$(cat "$PLAN_DOC")"
REFS_CONTENT="$(cat "$REFS_MD")"
GULF3_CONTENT="$(cat "$GULF3_MD")"

echo "--- docs/design-autorefine-v4.2-challenger-research-loop.md ---"
assert_contains "$DESIGN_CONTENT" '"challenger_mode": {' "Design doc defines challenger_mode example"
assert_contains "$DESIGN_CONTENT" '"lane_count": 3' "Design doc fixes lane count at 3"
assert_contains "$DESIGN_CONTENT" '"promotion_surface": "existing_trust_gate"' "Design doc routes promotion through existing trust surface"
assert_contains "$DESIGN_CONTENT" "isolated pseudo-parallel lanes" "Design doc locks isolated pseudo-parallel execution"
assert_contains "$DESIGN_CONTENT" "copy-on-write lane directory" "Design doc requires copy-on-write lane directories"
assert_contains "$DESIGN_CONTENT" "The first implementation may execute lanes sequentially for determinism and simpler resume behavior." "Design doc permits sequential execution for determinism"
assert_contains "$DESIGN_CONTENT" "runs/run_<timestamp>/iteration_<NNN>/challengers/lane_<lane_id>/" "Design doc defines per-lane artifact home"
assert_contains "$DESIGN_CONTENT" "runs/run_<timestamp>/iteration_<NNN>/challengers/shortlist.json" "Design doc defines shortlist artifact home"
assert_contains "$DESIGN_CONTENT" "Lane outputs are **candidate artifacts**, not first-class experiment versions." "Design doc keeps lane outputs below experiment lineage"
assert_contains "$DESIGN_CONTENT" "Only the shortlist winner may become a new immutable version artifact in \`skill-versions/\`." "Design doc promotes only shortlist winner into version lineage"
assert_contains "$DESIGN_CONTENT" "The first implementation slice does **not** add a new human gate between lane search and final holdout." "Design doc avoids a second human gate"
assert_contains "$DESIGN_CONTENT" "Shortlist selection is automatic and rule-based." "Design doc makes shortlist automatic"
assert_contains "$DESIGN_CONTENT" "lane_types = incremental_cleanup, simplification, from_scratch" "Design doc fixes lane types"
assert_contains "$DESIGN_CONTENT" "can consume \`research-intake.md\` and \`parsed_meta_learnings\`" "Design doc integrates research intake and parsed meta-learnings"
assert_contains "$DESIGN_CONTENT" "The lanes do **not** get separate holdout access" "Design doc forbids lane holdout access"
echo ""

echo "--- docs/plan-autorefine-v4.2-challenger-research-loop.md ---"
assert_contains "$PLAN_CONTENT" "\`challenger_mode\` is a Phase 7 candidate-generation feature, not a new trust or promotion system." "Plan keeps challenger mode scoped to candidate generation"
assert_contains "$PLAN_CONTENT" "The first implementation slice uses isolated copy-on-write lane directories and may execute lanes sequentially for deterministic resume behavior." "Plan locks copy-on-write sequential-friendly execution"
assert_contains "$PLAN_CONTENT" "Only the shortlist winner becomes the current experiment candidate and immutable version artifact; rejected lanes remain lane-local artifacts only." "Plan preserves shortlist winner lineage rule"
assert_contains "$PLAN_CONTENT" "Shortlist selection is automatic for v1 and feeds the existing experiment confirmation flow rather than adding a new human approval gate." "Plan keeps shortlist automatic and reuses existing confirmation"
assert_contains "$PLAN_CONTENT" "Task 0: Lock execution model, artifact homes, lineage rules, and shortlist approval model in docs/contracts" "Plan includes operational contract lock"
assert_contains "$PLAN_CONTENT" "per-lane artifact path is explicit" "Plan acceptance criteria require lane artifact path"
assert_contains "$PLAN_CONTENT" "shortlist artifact path is explicit" "Plan acceptance criteria require shortlist artifact path"
assert_contains "$PLAN_CONTENT" "only the shortlist winner becomes Experiment \`N\` and a version artifact" "Plan acceptance criteria require shortlist-winner lineage"
assert_contains "$PLAN_CONTENT" "lane count is fixed at 3 for the first version" "Plan keeps lane count bounded"
assert_contains "$PLAN_CONTENT" "lanes are described as copy-on-write lane artifacts, not shared-file edits" "Plan forbids shared-file lane edits"
assert_contains "$PLAN_CONTENT" "the instructions explicitly forbid holdout use during lane search" "Plan forbids mutation-time holdout use"
echo ""

echo "--- authoritative contract files ---"
assert_contains "$REFS_CONTENT" '"artifact_type": "challenger_mode_config"' "references define challenger_mode config schema"
assert_contains "$REFS_CONTENT" 'lane_01_incremental_cleanup' "references use numbered lane_01 id"
assert_contains "$REFS_CONTENT" 'lane_02_simplification' "references use numbered lane_02 id"
assert_contains "$REFS_CONTENT" 'lane_03_from_scratch' "references use numbered lane_03 id"
assert_contains "$REFS_CONTENT" '"selection_mode": "automatic"' "references keep shortlist automatic"
assert_contains "$REFS_CONTENT" '"holdout_access_during_lane_search": "forbidden"' "references forbid holdout in challenger config"
assert_contains "$GULF3_CONTENT" 'challengers/lane_01_incremental_cleanup/' "Gulf 3 uses numbered lane_01 directory"
assert_contains "$GULF3_CONTENT" 'challengers/lane_02_simplification/' "Gulf 3 uses numbered lane_02 directory"
assert_contains "$GULF3_CONTENT" 'challengers/lane_03_from_scratch/' "Gulf 3 uses numbered lane_03 directory"
assert_contains "$GULF3_CONTENT" 'The shortlist winner is the only lane output promoted into the canonical Experiment `N` candidate artifact' "Gulf 3 promotes only shortlist winner into experiment flow"
assert_contains "$GULF3_CONTENT" 'must not peek at holdout data' "Gulf 3 forbids holdout reads during lane search"
echo ""

echo "================================================================"
echo "  Results: $PASS_COUNT passed, $FAIL_COUNT failed"
echo "================================================================"
echo ""

[ "$FAIL_COUNT" -gt 0 ] && exit 1 || exit 0
