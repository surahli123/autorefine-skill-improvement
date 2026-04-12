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
echo "  AutoRefine v4.2 Session Close Research-Memory Schema Tests"
echo "================================================================"
echo ""

DESIGN_CONTENT="$(cat "$DESIGN_DOC")"
PLAN_CONTENT="$(cat "$PLAN_DOC")"
REFS_CONTENT="$(cat "$REFS_MD")"
GULF3_CONTENT="$(cat "$GULF3_MD")"

echo "--- docs/design-autorefine-v4.2-challenger-research-loop.md ---"
assert_contains "$DESIGN_CONTENT" "structured research-memory artifact that records lane outcomes, dead ends, and plateau-breaker performance." "Design doc introduces structured research-memory artifact"
assert_contains "$DESIGN_CONTENT" "runs/run_<timestamp>/session_close/research-memory.json" "Design doc defines research-memory artifact home"
assert_contains "$DESIGN_CONTENT" "Session Close should emit a structured research-memory artifact for the current run." "Design doc scopes research memory to Session Close"
assert_contains "$DESIGN_CONTENT" "This is not the same as top-level meta-learnings." "Design doc distinguishes research memory from meta-learnings"
assert_contains "$DESIGN_CONTENT" "which lane types were tried" "Design doc captures lane types tried"
assert_contains "$DESIGN_CONTENT" "which mutation families produced gains" "Design doc captures successful mutation families"
assert_contains "$DESIGN_CONTENT" "which ones repeatedly failed" "Design doc captures repeated failures"
assert_contains "$DESIGN_CONTENT" "whether the plateau-breaker helped" "Design doc captures plateau-breaker outcome"
assert_contains "$DESIGN_CONTENT" "whether dev gains survived final trust review" "Design doc captures final trust survival signal"
assert_contains "$DESIGN_CONTENT" "Promotion into curated cross-campaign learnings remains manual or separately gated." "Design doc forbids automatic promotion into curated learnings"
echo ""

echo "--- docs/plan-autorefine-v4.2-challenger-research-loop.md ---"
assert_contains "$PLAN_CONTENT" "Session Close gains a structured run-local research-memory artifact, but curated cross-campaign learnings remain separately governed." "Plan keeps research memory run-local and curated learnings separate"
assert_contains "$PLAN_CONTENT" "Task 2: Add research-memory artifact schema to \`autorefine/references.md\`" "Plan includes research-memory schema task"
assert_contains "$PLAN_CONTENT" "run-local research-memory schema exists" "Plan requires a run-local research-memory schema"
assert_contains "$PLAN_CONTENT" "artifact is clearly distinguished from curated meta-learnings" "Plan requires separation from curated meta-learnings"
assert_contains "$PLAN_CONTENT" "contract states that raw run memory is not auto-promoted into cross-campaign rules" "Plan forbids automatic promotion of run-local memory"
assert_contains "$PLAN_CONTENT" "Task 5: Add structured research-memory output to Session Close in \`autorefine/SKILL-gulf3.md\`" "Plan includes Session Close research-memory task"
assert_contains "$PLAN_CONTENT" "artifact includes lane outcomes, shortlist result, and plateau-breaker outcome" "Plan requires bounded research-memory contents"
assert_contains "$PLAN_CONTENT" "artifact does not replace the current learning summary; it complements it" "Plan preserves existing learning summary"
assert_contains "$PLAN_CONTENT" "Task 6: Define promotion boundary between run-local research memory and curated cross-campaign learnings" "Plan includes curation-boundary task"
echo ""

echo "--- authoritative contract files ---"
assert_contains "$REFS_CONTENT" '"artifact_type": "challenger_research_memory"' "references define research-memory artifact schema"
assert_contains "$REFS_CONTENT" '"activation_status": "skipped"' "references preserve skipped lane state in research memory"
assert_contains "$REFS_CONTENT" '"dev_gain_survived_final_trust_review": false' "references record whether dev gains survived final trust review"
assert_contains "$REFS_CONTENT" '"auto_promote_to_meta_learnings": false' "references forbid auto-promotion from research memory"
assert_contains "$GULF3_CONTENT" 'lane activation/skipped status' "Gulf 3 requires activation/skipped status in research memory"
assert_contains "$GULF3_CONTENT" "whether the selected candidate's dev gains survived the existing final trust review" "Gulf 3 requires trust-survival capture in research memory"
assert_contains "$GULF3_CONTENT" 'Do not auto-promote raw run-local research memory into curated cross-campaign meta-learnings' "Gulf 3 preserves curation boundary"
echo ""

echo "================================================================"
echo "  Results: $PASS_COUNT passed, $FAIL_COUNT failed"
echo "================================================================"
echo ""

[ "$FAIL_COUNT" -gt 0 ] && exit 1 || exit 0
