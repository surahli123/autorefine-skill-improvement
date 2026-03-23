#!/bin/bash
# =================================================================
# AutoRefine v2.1 Structural Integrity Tests
# =================================================================
# Validates SKILL.md (action script) and references.md (detail library)
# after the v2.1 streamline restructure.
#
# Run:  bash tests/test_v2_integrity.sh
# =================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_MD="$PROJECT_ROOT/autorefine/SKILL.md"
REFS_MD="$PROJECT_ROOT/autorefine/references.md"
VALIDATE_SH="$PROJECT_ROOT/autorefine/validate-host.sh"

PASS_COUNT=0
FAIL_COUNT=0
TOTAL_COUNT=0

pass_test() { TOTAL_COUNT=$((TOTAL_COUNT + 1)); PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail_test() { TOTAL_COUNT=$((TOTAL_COUNT + 1)); FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1"; }
assert_eq() { [ "$1" = "$2" ] && pass_test "$3" || fail_test "$3 (expected '$2', got '$1')"; }
assert_contains() { echo "$1" | grep -qF "$2" && pass_test "$3" || fail_test "$3 (missing '$2')"; }
assert_not_contains() { echo "$1" | grep -qF "$2" && fail_test "$3 (found '$2')" || pass_test "$3"; }
assert_file_exists() { [ -f "$1" ] && pass_test "$2" || fail_test "$2 (not found: $1)"; }
assert_file_executable() { [ -x "$1" ] && pass_test "$2" || fail_test "$2 (not executable: $1)"; }
assert_line_count_le() { local c=$(wc -l < "$1" | tr -d ' '); [ "$c" -le "$2" ] && pass_test "$3 ($c lines <= $2)" || fail_test "$3 ($c lines > $2)"; }

echo ""
echo "================================================================"
echo "  AutoRefine v2.1 Structural Integrity Tests"
echo "================================================================"
echo ""

# =================================================================
# 1. validate-host.sh
# =================================================================
echo "--- validate-host.sh ---"
assert_file_exists "$VALIDATE_SH" "validate-host.sh exists"
assert_file_executable "$VALIDATE_SH" "validate-host.sh is executable"

run_eval_logic() {
    local MARKER="AUTOREFINE_RW_PROBE_c4f9e2"
    local HAS_VISIBLE=$(echo "$1" | grep -c "MARKER_VISIBLE_OK" || true)
    local HAS_HIDDEN=$(echo "$1" | grep -c "$MARKER" || true)
    if [ "$HAS_VISIBLE" -gt 0 ] && [ "$HAS_HIDDEN" -eq 0 ]; then echo "PASS"
    elif [ "$HAS_VISIBLE" -gt 0 ] && [ "$HAS_HIDDEN" -gt 0 ]; then echo "FAIL"
    elif [ "$HAS_VISIBLE" -eq 0 ]; then echo "INCONCLUSIVE"; fi
}
assert_eq "$(run_eval_logic 'MARKER_VISIBLE_OK')" "PASS" "PASS path works"
assert_eq "$(run_eval_logic 'MARKER_VISIBLE_OK AUTOREFINE_RW_PROBE_c4f9e2')" "FAIL" "FAIL path works"
assert_eq "$(run_eval_logic 'nothing')" "INCONCLUSIVE" "INCONCLUSIVE path works"
echo ""

# =================================================================
# 2. SKILL.md structure (action script)
# =================================================================
echo "--- SKILL.md action script ---"
SKILL_CONTENT=$(cat "$SKILL_MD")

# 2a. All 7 phases present
assert_contains "$SKILL_CONTENT" "## Phase 1: Design Audit" "Phase 1 present"
assert_contains "$SKILL_CONTENT" "## Phase 2: Eval Audit" "Phase 2 present"
assert_contains "$SKILL_CONTENT" "## Phase 3: Error Analysis" "Phase 3 present"
assert_contains "$SKILL_CONTENT" "## Phase 4: Expand Inputs" "Phase 4 present"
assert_contains "$SKILL_CONTENT" "## Phase 5: Write Judges" "Phase 5 present"
assert_contains "$SKILL_CONTENT" "## Phase 6: Validate Judges" "Phase 6 present"
assert_contains "$SKILL_CONTENT" "## Phase 7: AutoResearch Loop" "Phase 7 present"

# 2b. Both gates present with override logging
GULF1_GATE=$(sed -n '/Gulf 1 Exit/,/^---/p' "$SKILL_MD")
assert_contains "$GULF1_GATE" "Override logging" "Gulf 1 gate has override logging"
assert_contains "$GULF1_GATE" "STOP" "Gulf 1 gate stops for approval"

GULF2_GATE=$(sed -n '/Gulf 2 Exit/,/^---/p' "$SKILL_MD")
assert_contains "$GULF2_GATE" "Override logging" "Gulf 2 gate has override logging"
assert_contains "$GULF2_GATE" "STOP" "Gulf 2 gate stops for approval"

# 2c. v2 features present
assert_contains "$SKILL_CONTENT" "Smart sampling" "Smart sampling in Phase 3"
assert_contains "$SKILL_CONTENT" "Preliminary clustering" "Preliminary clustering in Phase 3"
assert_contains "$SKILL_CONTENT" "Consistency check" "Consistency detection in Phase 3"
assert_contains "$SKILL_CONTENT" "session-log.json" "session-log.json referenced"

# 2d. v2.1 features present
assert_contains "$SKILL_CONTENT" "pipeline depth" "Pipeline tiering in Preflight"
assert_contains "$SKILL_CONTENT" "Quick" "Quick tier option"
assert_contains "$SKILL_CONTENT" "Standard" "Standard tier option"
assert_contains "$SKILL_CONTENT" "Deep" "Deep tier option"
assert_contains "$SKILL_CONTENT" "Confidence-weighted scoring" "Feature 3: confidence scoring"
assert_contains "$SKILL_CONTENT" "Judge gap detection" "Feature 4: judge gaps"
assert_contains "$SKILL_CONTENT" "## Loop-Back Prompt" "Feature 5: loop-back"
assert_contains "$SKILL_CONTENT" "## Session Close" "Feature 2: session close"

# 2e. Philosophy briefing in pipeline status
PIPELINE_STATUS=$(sed -n '/^## Pipeline Status/,/^---/p' "$SKILL_MD")
assert_contains "$PIPELINE_STATUS" "builds the scorer" "Philosophy briefing present"

# 2f. Skip-to-loop in Preflight
PREFLIGHT=$(sed -n '/^## Preflight/,/^## /p' "$SKILL_MD")
assert_contains "$PREFLIGHT" "approved" "Skip-to-loop detects approved gates"

# 2g. References pointers (SKILL.md delegates to references.md)
assert_contains "$SKILL_CONTENT" "references.md" "SKILL.md references references.md"
REF_POINTERS=$(grep -c 'references.md' "$SKILL_MD")
if [ "$REF_POINTERS" -ge 5 ]; then
    pass_test "SKILL.md has $REF_POINTERS references.md pointers (>=5 expected)"
else
    fail_test "SKILL.md has only $REF_POINTERS references.md pointers (need >=5)"
fi

# 2h. Gotchas section (condensed, with pointer to full list)
GOTCHAS=$(sed -n '/^## Gotchas/,/^---/p' "$SKILL_MD")
assert_contains "$GOTCHAS" "session-log.json" "Gotchas mention session-log"
assert_contains "$GOTCHAS" "Gulf 1" "Gotchas mention Gulf 1"
echo ""

# =================================================================
# 3. references.md (detail library)
# =================================================================
echo "--- references.md detail library ---"
REFS_CONTENT=$(cat "$REFS_MD")

# 3a. All moved sections present
assert_contains "$REFS_CONTENT" "## Workspace Schemas" "Workspace Schemas section"
assert_contains "$REFS_CONTENT" "## The Three Gulfs" "Three Gulfs section"
assert_contains "$REFS_CONTENT" "## V2.0 Design Audit Rubric" "Design Audit Rubric section"
assert_contains "$REFS_CONTENT" "## Eval Audit Categories" "Eval Audit Categories section"
assert_contains "$REFS_CONTENT" "## Smart Sampling Methodology" "Smart Sampling section"
assert_contains "$REFS_CONTENT" "## Eval Suite Template" "Eval Suite Template section"
assert_contains "$REFS_CONTENT" "## Judge Prompt Template" "Judge Prompt Template section"
assert_contains "$REFS_CONTENT" "## TPR/TNR Reference" "TPR/TNR Reference section"
assert_contains "$REFS_CONTENT" "## Results & Changelog Schemas" "Results Schemas section"
assert_contains "$REFS_CONTENT" "## Gotchas" "Full Gotchas section"
assert_contains "$REFS_CONTENT" "## Hamel Integration Details" "Hamel Integration section"

# 3b. Schemas in references (moved from SKILL.md)
assert_contains "$REFS_CONTENT" "schema_version" "state.json schema has schema_version"
assert_contains "$REFS_CONTENT" "loop_iteration" "state.json schema has loop_iteration"
assert_contains "$REFS_CONTENT" "locked_judges" "state.json schema has locked_judges"
assert_contains "$REFS_CONTENT" "session-log.json" "session-log schema present"

# 3c. Session-log entry types documented
assert_contains "$REFS_CONTENT" "judge_gap" "Judge gap entry type documented"
assert_contains "$REFS_CONTENT" "override" "Override entry type documented"

# 3d. Read when: tags present on key sections
assert_contains "$REFS_CONTENT" "Read when:" "Read when: tags present"
echo ""

# =================================================================
# 4. Line budget
# =================================================================
echo "--- Line budget ---"
assert_line_count_le "$SKILL_MD" 250 "SKILL.md within action script budget"
assert_line_count_le "$REFS_MD" 320 "references.md within detail budget"
echo ""

# =================================================================
echo "================================================================"
echo "  Results: $PASS_COUNT passed, $FAIL_COUNT failed, $TOTAL_COUNT total"
echo "================================================================"
echo ""
[ "$FAIL_COUNT" -gt 0 ] && exit 1 || exit 0
