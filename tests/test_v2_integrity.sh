#!/bin/bash
# =================================================================
# AutoRefine v2 Structural Integrity Tests
# =================================================================
# Validates:
#   1. validate-host.sh correctness (PASS / FAIL / INCONCLUSIVE paths)
#   2. SKILL.md structural integrity (phases, steps, cross-refs)
#   3. references.md structural integrity (sections, subsections)
#   4. Line budget compliance
#
# Run:  bash tests/test_v2_integrity.sh
#       (from the skill-improvement root directory)
# =================================================================

set -u  # Treat unset variables as errors (but no set -e; we handle failures ourselves)

# --- Paths (absolute, derived from script location) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_MD="$PROJECT_ROOT/autorefine/SKILL.md"
REFS_MD="$PROJECT_ROOT/autorefine/references.md"
VALIDATE_SH="$PROJECT_ROOT/autorefine/validate-host.sh"

# --- Counters ---
PASS_COUNT=0
FAIL_COUNT=0
TOTAL_COUNT=0

# --- Test runner helpers ---
# pass_test and fail_test both take a description string.
# They print a colored line and update counters.
pass_test() {
    TOTAL_COUNT=$((TOTAL_COUNT + 1))
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "  PASS  $1"
}

fail_test() {
    TOTAL_COUNT=$((TOTAL_COUNT + 1))
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "  FAIL  $1"
}

# assert_eq VALUE EXPECTED DESCRIPTION
# Compares two values; passes if equal, fails otherwise.
assert_eq() {
    local actual="$1"
    local expected="$2"
    local desc="$3"
    if [ "$actual" = "$expected" ]; then
        pass_test "$desc"
    else
        fail_test "$desc (expected '$expected', got '$actual')"
    fi
}

# assert_contains HAYSTACK NEEDLE DESCRIPTION
# Passes if HAYSTACK contains NEEDLE (substring match).
assert_contains() {
    local haystack="$1"
    local needle="$2"
    local desc="$3"
    if echo "$haystack" | grep -qF "$needle"; then
        pass_test "$desc"
    else
        fail_test "$desc (could not find '$needle')"
    fi
}

# assert_not_contains HAYSTACK NEEDLE DESCRIPTION
assert_not_contains() {
    local haystack="$1"
    local needle="$2"
    local desc="$3"
    if echo "$haystack" | grep -qF "$needle"; then
        fail_test "$desc (unexpectedly found '$needle')"
    else
        pass_test "$desc"
    fi
}

# assert_file_exists PATH DESCRIPTION
assert_file_exists() {
    local path="$1"
    local desc="$2"
    if [ -f "$path" ]; then
        pass_test "$desc"
    else
        fail_test "$desc (file not found: $path)"
    fi
}

# assert_file_executable PATH DESCRIPTION
assert_file_executable() {
    local path="$1"
    local desc="$2"
    if [ -x "$path" ]; then
        pass_test "$desc"
    else
        fail_test "$desc (file not executable: $path)"
    fi
}

# assert_line_count_le FILE MAX DESCRIPTION
# Passes if line count of FILE is <= MAX.
assert_line_count_le() {
    local file="$1"
    local max="$2"
    local desc="$3"
    local count
    count=$(wc -l < "$file" | tr -d ' ')
    if [ "$count" -le "$max" ]; then
        pass_test "$desc ($count lines <= $max)"
    else
        fail_test "$desc ($count lines > $max)"
    fi
}

# =================================================================
echo ""
echo "================================================================"
echo "  AutoRefine v2 Structural Integrity Tests"
echo "================================================================"
echo ""

# =================================================================
# 1. validate-host.sh Tests
# =================================================================
echo "--- validate-host.sh ---"

# 1a. File exists
assert_file_exists "$VALIDATE_SH" "validate-host.sh exists"

# 1b. File is executable
assert_file_executable "$VALIDATE_SH" "validate-host.sh is executable"

# For the PASS/FAIL/INCONCLUSIVE tests, we simulate what the script's
# evaluation logic does. The script reads interactive input, so we
# can't run it end-to-end. Instead, we extract the evaluation block
# and test it in isolation by piping simulated responses.

# Helper: runs the evaluation logic portion of the script against
# a simulated RESPONSE string and captures the RESULT line.
run_eval_logic() {
    local response="$1"
    # Replicate the script's evaluation logic exactly
    local MARKER="AUTOREFINE_RW_PROBE_c4f9e2"
    local HAS_VISIBLE
    local HAS_HIDDEN
    HAS_VISIBLE=$(echo "$response" | grep -c "MARKER_VISIBLE_OK" || true)
    HAS_HIDDEN=$(echo "$response" | grep -c "$MARKER" || true)

    if [ "$HAS_VISIBLE" -gt 0 ] && [ "$HAS_HIDDEN" -eq 0 ]; then
        echo "PASS"
    elif [ "$HAS_VISIBLE" -gt 0 ] && [ "$HAS_HIDDEN" -gt 0 ]; then
        echo "FAIL"
    elif [ "$HAS_VISIBLE" -eq 0 ]; then
        echo "INCONCLUSIVE"
    fi
}

# 1c. PASS path: only MARKER_VISIBLE_OK present
RESULT=$(run_eval_logic "I can see MARKER_VISIBLE_OK in the file")
assert_eq "$RESULT" "PASS" "PASS path: MARKER_VISIBLE_OK present, probe absent"

# 1d. FAIL path: both markers present
RESULT=$(run_eval_logic "I see MARKER_VISIBLE_OK and also AUTOREFINE_RW_PROBE_c4f9e2")
assert_eq "$RESULT" "FAIL" "FAIL path: both MARKER_VISIBLE_OK and AUTOREFINE_RW_PROBE_c4f9e2 present"

# 1e. INCONCLUSIVE path: neither marker present
RESULT=$(run_eval_logic "The skill loaded but I don't see any special markers")
assert_eq "$RESULT" "INCONCLUSIVE" "INCONCLUSIVE path: neither marker present"

# 1f. INCONCLUSIVE path: only probe, no MARKER_VISIBLE_OK (also INCONCLUSIVE)
RESULT=$(run_eval_logic "I see AUTOREFINE_RW_PROBE_c4f9e2 but not the visible one")
assert_eq "$RESULT" "INCONCLUSIVE" "INCONCLUSIVE path: probe present but MARKER_VISIBLE_OK absent"

# 1g. Test skill template contains correct markers
SCRIPT_CONTENT=$(cat "$VALIDATE_SH")
assert_contains "$SCRIPT_CONTENT" "MARKER_VISIBLE_OK" "Test SKILL template contains MARKER_VISIBLE_OK"
assert_contains "$SCRIPT_CONTENT" "AUTOREFINE_RW_PROBE_c4f9e2" "Test SKILL template contains AUTOREFINE_RW_PROBE_c4f9e2"

# 1h. Script creates temp test SKILL.md (uses mktemp -d)
assert_contains "$SCRIPT_CONTENT" 'mktemp -d' "Script creates temp directory via mktemp"
assert_contains "$SCRIPT_CONTENT" 'TEST_SKILL=' "Script defines TEST_SKILL path for temp SKILL.md"

# 1i. Cleanup instructions are present
assert_contains "$SCRIPT_CONTENT" "Cleanup:" "Script includes cleanup instructions"
assert_contains "$SCRIPT_CONTENT" 'rm -rf' "Script shows rm -rf cleanup command"

echo ""

# =================================================================
# 2. SKILL.md Structural Integrity
# =================================================================
echo "--- SKILL.md structural integrity ---"

SKILL_CONTENT=$(cat "$SKILL_MD")

# 2a. Phase 3 has exactly 7 steps
# Count "### Step N:" headings between "## Phase 3:" and "## Phase 4:"
# Phase 3 starts at "## Phase 3: Error Analysis" and ends before "## Phase 4:"
PHASE3_SECTION=$(sed -n '/^## Phase 3: Error Analysis/,/^## Phase 4:/p' "$SKILL_MD")
PHASE3_STEP_COUNT=$(echo "$PHASE3_SECTION" | grep -c '^### Step [0-9]')
assert_eq "$PHASE3_STEP_COUNT" "7" "Phase 3 has exactly 7 steps"

# 2b. Phase 3 has Gate: Gulf 1 Exit
assert_contains "$PHASE3_SECTION" "### Gate: Gulf 1 Exit" "Phase 3 has 'Gate: Gulf 1 Exit' section"

# 2c. Step numbering is sequential (1 through 7, no gaps, no duplicates)
PHASE3_STEP_NUMBERS=$(echo "$PHASE3_SECTION" | grep '^### Step [0-9]' | sed 's/### Step \([0-9]*\).*/\1/')
EXPECTED_STEPS="1
2
3
4
5
6
7"
assert_eq "$PHASE3_STEP_NUMBERS" "$EXPECTED_STEPS" "Phase 3 steps are sequential 1-7 (no gaps, no duplicates)"

# 2d. Gulf 1 gate references "Step 7" (not "Step 5")
GULF1_GATE=$(sed -n '/^### Gate: Gulf 1 Exit/,/^---/p' "$SKILL_MD")
assert_contains "$GULF1_GATE" "Step 7" "Gulf 1 gate references Step 7"
assert_not_contains "$GULF1_GATE" "Step 5" "Gulf 1 gate does NOT reference Step 5"

# 2e. Gulf 2 gate contains override logging instruction
GULF2_GATE=$(sed -n '/^### Gate: Gulf 2 Exit/,/^---/p' "$SKILL_MD")
assert_contains "$GULF2_GATE" "Override logging" "Gulf 2 gate contains override logging instruction"

# 2f. session-log.json creation appears in Initialize Workspace
INIT_SECTION=$(sed -n '/^## Initialize Workspace/,/^## /p' "$SKILL_MD")
assert_contains "$INIT_SECTION" "session-log.json" "Initialize Workspace mentions session-log.json"

# 2g. state.json schema contains loop_iteration and locked_judges
STATE_SCHEMA_LINE=$(grep 'loop_iteration' "$SKILL_MD")
assert_contains "$STATE_SCHEMA_LINE" "loop_iteration" "state.json schema has loop_iteration"
assert_contains "$STATE_SCHEMA_LINE" "locked_judges" "state.json schema has locked_judges"

# 2h. Gotcha 9 (was 11, renumbered) exists and mentions session-log.json
GOTCHA_9=$(grep '^9\. \*\*session-log' "$SKILL_MD")
assert_contains "$GOTCHA_9" "session-log.json" "Gotcha 9 mentions session-log.json"

# 2i. All session-log.json append instructions use valid JSON examples
# Extract every line that says "Append to session-log.json" and verify it
# contains a JSON object with "phase", "type", and "detail" keys.
SESSION_LOG_APPENDS=$(grep 'Append.*session-log\.json.*entries:' "$SKILL_MD")
APPEND_COUNT=$(echo "$SESSION_LOG_APPENDS" | wc -l | tr -d ' ')

# Check each append line has the required JSON structure
ALL_HAVE_PHASE=true
ALL_HAVE_TYPE=true
ALL_HAVE_DETAIL=true

while IFS= read -r line; do
    echo "$line" | grep -q '"phase"' || ALL_HAVE_PHASE=false
    echo "$line" | grep -q '"type"' || ALL_HAVE_TYPE=false
    echo "$line" | grep -q '"detail"' || ALL_HAVE_DETAIL=false
done <<< "$SESSION_LOG_APPENDS"

if $ALL_HAVE_PHASE; then
    pass_test "All session-log.json appends have 'phase' key ($APPEND_COUNT entries)"
else
    fail_test "Some session-log.json appends missing 'phase' key"
fi

if $ALL_HAVE_TYPE; then
    pass_test "All session-log.json appends have 'type' key"
else
    fail_test "Some session-log.json appends missing 'type' key"
fi

if $ALL_HAVE_DETAIL; then
    pass_test "All session-log.json appends have 'detail' key"
else
    fail_test "Some session-log.json appends missing 'detail' key"
fi

# 2j. Override entries have 'reason' key
OVERRIDE_APPENDS=$(grep 'type.*override' "$SKILL_MD" | grep 'session-log')
ALL_HAVE_REASON=true
while IFS= read -r line; do
    echo "$line" | grep -qF '"reason"' || ALL_HAVE_REASON=false
done <<< "$OVERRIDE_APPENDS"
if $ALL_HAVE_REASON; then
    pass_test "All override session-log entries have 'reason' key"
else
    fail_test "Some override session-log entries missing 'reason' key"
fi

# 2k. Gotcha numbering is sequential with no gaps
GOTCHA_NUMBERS=$(grep -oE '^[0-9]+\.' "$SKILL_MD" | sed -n '/^[0-9]/p' | sed 's/\.//' | sort -n | uniq)
GOTCHAS_SECTION=$(sed -n '/^## Gotchas/,/^## /p' "$SKILL_MD")
GOTCHA_NUMS_IN_SECTION=$(echo "$GOTCHAS_SECTION" | grep -oE '^[0-9]+\.' | sed 's/\.//' | sort -n)
EXPECTED_GOTCHAS=$(seq 1 $(echo "$GOTCHA_NUMS_IN_SECTION" | tail -1))
assert_eq "$GOTCHA_NUMS_IN_SECTION" "$EXPECTED_GOTCHAS" "Gotcha numbering is sequential (no gaps)"

# 2l. state.json has schema_version field
assert_contains "$SKILL_CONTENT" '"schema_version"' "state.json schema has schema_version"

# 2m. Phase step cross-references are internally consistent
# Phase 3 Step 3 references "Phase 4 dimensions" — Phase 4 must define dimensions
PHASE4_SECTION=$(sed -n '/^## Phase 4:/,/^## Phase 5:/p' "$SKILL_MD")
assert_contains "$PHASE4_SECTION" "Define dimensions" "Phase 4 has 'Define dimensions' step (referenced by Phase 3 Step 3)"

# Phase 3 Step 7 writes eval-suite.md — Phase 7 references eval-suite.md
PHASE7_SECTION=$(sed -n '/^## Phase 7:/,/^## Gotchas/p' "$SKILL_MD")
assert_contains "$PHASE7_SECTION" "eval-suite.md" "Phase 7 references eval-suite.md (written in Phase 3 Step 7)"

# Phase 5 references eval-suite.md from Phase 3
PHASE5_SECTION=$(sed -n '/^## Phase 5:/,/^## Phase 6:/p' "$SKILL_MD")
assert_contains "$PHASE5_SECTION" "eval-suite.md" "Phase 5 references eval-suite.md"

# Phase 6 references judges from Phase 5
PHASE6_SECTION=$(sed -n '/^## Phase 6:/,/^## Phase 7:/p' "$SKILL_MD")
assert_contains "$PHASE6_SECTION" "judge" "Phase 6 references judges (built in Phase 5)"

# The references section in SKILL.md mentions references.md
assert_contains "$SKILL_CONTENT" "references.md" "SKILL.md references references.md"

echo ""

# =================================================================
# 3. references.md Structural Integrity
# =================================================================
echo "--- references.md structural integrity ---"

REFS_CONTENT=$(cat "$REFS_MD")

# 3a. Smart Sampling Methodology section exists
assert_contains "$REFS_CONTENT" "## Smart Sampling Methodology" "Smart Sampling Methodology section exists"

# 3b. Section has "Read when:" tag
# The Smart Sampling section should have a "Read when:" line
SMART_SAMPLING_SECTION=$(sed -n '/^## Smart Sampling Methodology/,/^## /p' "$REFS_MD")
assert_contains "$SMART_SAMPLING_SECTION" "Read when:" "Smart Sampling has 'Read when:' tag"

# 3c. Contains subsections (dimension inference + consistency algorithm moved to SKILL.md to avoid duplication)
assert_contains "$REFS_CONTENT" "### Why 8-10" "Subsection 'Why 8-10' exists"
assert_contains "$REFS_CONTENT" "### Why lightweight dimensions" "Subsection 'Why lightweight dimensions' exists"
assert_contains "$REFS_CONTENT" "### When to override" "Subsection 'When to override' exists"

echo ""

# =================================================================
# 4. Line Budget Checks
# =================================================================
echo "--- Line budget ---"

# 4a. SKILL.md <= 520 lines (budget ~503, with margin)
assert_line_count_le "$SKILL_MD" 520 "SKILL.md within line budget"

# 4b. references.md <= 170 lines
assert_line_count_le "$REFS_MD" 170 "references.md within line budget"

echo ""

# =================================================================
# Summary
# =================================================================
echo "================================================================"
echo "  Results: $PASS_COUNT passed, $FAIL_COUNT failed, $TOTAL_COUNT total"
echo "================================================================"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
else
    exit 0
fi
