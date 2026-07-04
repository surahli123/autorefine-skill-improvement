#!/bin/bash
# AutoRefine Iteration Directory Test Suite
# Validates that the split AutoRefine prompt files and references.md are
# internally consistent for the filesystem-as-memory feature.
#
# These are PROMPT CONSISTENCY tests — they grep the prompt files, not
# runtime behavior. A failure means the docs are out of sync.

PASS=0
FAIL=0
TOTAL=0

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL_MD="$PROJECT_ROOT/autorefine/SKILL.md"
SKILL_GULF3_MD="$PROJECT_ROOT/autorefine/references/gulf3-generalization.md"
REF_MD="$PROJECT_ROOT/autorefine/references.md"

assert() {
  TOTAL=$((TOTAL + 1))
  local desc="$1"
  local result="$2"  # 0 = pass, non-zero = fail
  if [ "$result" -eq 0 ]; then
    PASS=$((PASS + 1))
    echo "  ✓ $desc"
  else
    FAIL=$((FAIL + 1))
    echo "  ✗ FAIL: $desc"
  fi
}

echo "=== Test Suite: AutoRefine Iteration Directory (filesystem-as-memory) ==="
echo ""

# Guard: both files must exist or the entire suite is invalid
if [ ! -f "$SKILL_MD" ]; then
  echo "FATAL: SKILL.md not found at $SKILL_MD"
  exit 2
fi
if [ ! -f "$SKILL_GULF3_MD" ]; then
  echo "FATAL: gulf3-generalization.md not found at $SKILL_GULF3_MD"
  exit 2
fi
if [ ! -f "$REF_MD" ]; then
  echo "FATAL: references.md not found at $REF_MD"
  exit 2
fi

# ---------------------------------------------------------------------------
# Test Group 1: Schema presence
# ---------------------------------------------------------------------------
echo "--- Test Group 1: Schema Presence ---"

# Test 1: Gulf 3 references the Iteration Directory Schema section
assert "Gulf 3 surface references 'references.md > Iteration Directory Schema'" \
  "$(grep -q 'references\.md > Iteration Directory Schema' "$SKILL_GULF3_MD"; echo $?)"

# Test 2: The referenced section actually exists in references.md
assert "references.md has '## Iteration Directory Schema' section" \
  "$(grep -q '^## Iteration Directory Schema' "$REF_MD"; echo $?)"

echo ""

# ---------------------------------------------------------------------------
# Test Group 2: File format completeness
# All 5 artifact files must be documented in references.md
# ---------------------------------------------------------------------------
echo "--- Test Group 2: File Format Completeness (5 artifacts) ---"

assert "references.md documents 'mutation.md' artifact" \
  "$(grep -q 'mutation\.md' "$REF_MD"; echo $?)"

assert "references.md documents 'skill_before.md' artifact" \
  "$(grep -q 'skill_before\.md' "$REF_MD"; echo $?)"

assert "references.md documents 'skill_after.md' artifact" \
  "$(grep -q 'skill_after\.md' "$REF_MD"; echo $?)"

assert "references.md documents 'eval_results.json' artifact" \
  "$(grep -q 'eval_results\.json' "$REF_MD"; echo $?)"

assert "references.md documents 'decision.md' artifact" \
  "$(grep -q 'decision\.md' "$REF_MD"; echo $?)"

echo ""

# ---------------------------------------------------------------------------
# Test Group 3: Directory creation
# ---------------------------------------------------------------------------
echo "--- Test Group 3: Directory Creation ---"

# runs/ must appear in the Initialize Workspace directory creation instruction
# SKILL.md line 72: "If workspace traces/, judges/, and runs/ subdirectories..."
assert "SKILL.md Initialize Workspace instruction mentions creating 'runs/' directory" \
  "$(grep -q "runs/" "$SKILL_MD"; echo $?)"

# Confirm it's in the Initialize Workspace section specifically
assert "SKILL.md 'runs/' creation is in Initialize Workspace context (with traces/ and judges/)" \
  "$(grep -q "traces/.*judges/.*runs/\|runs/.*subdirector" "$SKILL_MD"; echo $?)"

echo ""

# ---------------------------------------------------------------------------
# Test Group 4: Session-log entry type
# ---------------------------------------------------------------------------
echo "--- Test Group 4: Session-Log Entry Type ---"

# iteration_write entry type must exist in session-log schema in references.md
assert "references.md session-log schema includes 'iteration_write' entry type" \
  "$(grep -q 'iteration_write' "$REF_MD"; echo $?)"

# The entry type must include the required fields: experiment and path
assert "references.md 'iteration_write' entry has 'experiment' field" \
  "$(grep -A2 'iteration_write' "$REF_MD" | grep -q 'experiment'; echo $?)"

assert "references.md 'iteration_write' entry has 'path' field" \
  "$(grep -A2 'iteration_write' "$REF_MD" | grep -q 'path'; echo $?)"

echo ""

# ---------------------------------------------------------------------------
# Test Group 5: Timing consistency — keeps write at 2e, discards write at 2f
# ---------------------------------------------------------------------------
echo "--- Test Group 5: Timing Consistency (step 2e keeps, step 2f discards) ---"

# Step 2e: kept experiments write iteration artifacts
assert "Gulf 3 step 2e mentions writing iteration artifacts for kept experiments" \
  "$(grep -q 'write iteration artifacts.*iteration_' "$SKILL_GULF3_MD"; echo $?)"

# Step 2f: discarded experiments write iteration artifacts
assert "Gulf 3 step 2f mentions writing iteration artifacts for discarded experiments" \
  "$(grep -q 'Write iteration artifacts.*iteration_' "$SKILL_GULF3_MD"; echo $?)"

# references.md When to Write section confirms step 2e for keeps
assert "references.md 'When to Write' mentions 'step 2e' for kept experiments" \
  "$(grep -q 'step 2e' "$REF_MD"; echo $?)"

# references.md When to Write section confirms step 2f for discards
assert "references.md 'When to Write' mentions 'step 2f' for discarded experiments" \
  "$(grep -q 'step 2f' "$REF_MD"; echo $?)"

echo ""

# ---------------------------------------------------------------------------
# Test Group 6: Step 2a reads decision.md files
# ---------------------------------------------------------------------------
echo "--- Test Group 6: Step 2a Reads Prior Decisions ---"

assert "Gulf 3 step 2a references reading 'decision.md' files from prior iterations" \
  "$(grep -q 'decision\.md' "$SKILL_GULF3_MD"; echo $?)"

# Confirm it reads from the current run directory via state.json
assert "Gulf 3 step 2a reads decision.md from current_run_path (not wildcard glob)" \
  "$(grep -q 'decision\.md.*current_run_path' "$SKILL_GULF3_MD"; echo $?)"

echo ""

# ---------------------------------------------------------------------------
# Test Group 7: Baseline write + trial persistence contract
# ---------------------------------------------------------------------------
echo "--- Test Group 7: Baseline Write + Trial Persistence ---"

assert "Gulf 3 step 1 (baseline) references writing to 'iteration_000/'" \
  "$(grep -q 'iteration_000' "$SKILL_GULF3_MD"; echo $?)"

assert "Gulf 3 says 'Write baseline iteration artifacts' to iteration_000/" \
  "$(grep -q 'Write baseline iteration artifacts.*iteration_000\|iteration_000' "$SKILL_GULF3_MD"; echo $?)"

assert "Gulf 3 requires three unchanged-skill baseline invocations" \
  "$(grep -q 'Invoke the unchanged working-copy skill evaluation exactly three times' "$SKILL_GULF3_MD"; echo $?)"

assert "Gulf 3 persists each baseline run into baseline_trials[]" \
  "$(grep -q 'Persist each unchanged-skill baseline execution as a distinct record in `baseline_trials\[\]`' "$SKILL_GULF3_MD"; echo $?)"

assert "Gulf 3 requires stable baseline trial identifiers" \
  "$(grep -q 'stable `trial_id`' "$SKILL_GULF3_MD" && grep -q 'unique `trial_index`' "$SKILL_GULF3_MD"; echo $?)"

assert "Gulf 3 keeps rich per-trial baseline payload fields" \
  "$(grep -q '`run_index`, `timestamps`, `raw_outputs\[\]`, and `trial_metadata`' "$SKILL_GULF3_MD"; echo $?)"

# references.md must also document iteration_000 behavior
assert "references.md documents iteration_000 (baseline) directory" \
  "$(grep -q 'iteration_000' "$REF_MD"; echo $?)"

assert "references.md results schema includes baseline_trials[]" \
  "$(grep -q '"baseline_trials"' "$REF_MD"; echo $?)"

assert "references.md iteration schema includes stable baseline trial identifiers" \
  "$(grep -q '"trial_index": 2,' "$REF_MD" && grep -q '"trial_id": "baseline-trial-001"' "$REF_MD"; echo $?)"

assert "references.md iteration schema keeps raw_outputs and trial_metadata on baseline trials" \
  "$(grep -q '"raw_outputs"' "$REF_MD" && grep -q '"trial_metadata"' "$REF_MD"; echo $?)"

echo ""

# ---------------------------------------------------------------------------
# Test Group 8: Run directory creation at Phase 7 start
# ---------------------------------------------------------------------------
echo "--- Test Group 8: Run Directory Creation ---"

assert "Gulf 3 mentions creating 'run_<timestamp>' directory at Phase 7 start" \
  "$(grep -q 'run_<timestamp>' "$SKILL_GULF3_MD"; echo $?)"

assert "Gulf 3 specifies timestamp format 'YYYY-MM-DDTHH-MM-SS'" \
  "$(grep -q 'YYYY-MM-DDTHH-MM-SS' "$SKILL_GULF3_MD"; echo $?)"

# references.md must also document the timestamp format
assert "references.md specifies 'YYYY-MM-DDTHH-MM-SS' timestamp format for run directories" \
  "$(grep -q 'YYYY-MM-DDTHH-MM-SS' "$REF_MD"; echo $?)"

echo ""

# ---------------------------------------------------------------------------
# Test Group 9: Cross-reference — When to Write mentions both step 2e and 2f
# ---------------------------------------------------------------------------
echo "--- Test Group 9: Cross-Reference Completeness ---"

# The When to Write section in references.md must cover all 3 timing cases
assert "references.md 'When to Write' covers baseline (Experiment 0)" \
  "$(grep -A10 'When to Write' "$REF_MD" | grep -q 'Experiment 0\|baseline'; echo $?)"

assert "references.md 'When to Write' covers kept experiments" \
  "$(grep -A10 'When to Write' "$REF_MD" | grep -q '[Kk]ept'; echo $?)"

assert "references.md 'When to Write' covers discarded experiments" \
  "$(grep -A10 'When to Write' "$REF_MD" | grep -q '[Dd]iscard'; echo $?)"

echo ""

# ---------------------------------------------------------------------------
# Test Group 10: No orphan references — every section referenced from SKILL.md
# with "references.md > [section]" must exist in references.md
# ---------------------------------------------------------------------------
echo "--- Test Group 10: No Orphan Section References ---"

# Extract all "references.md > X" references from SKILL.md + Gulf 3,
# then check each exists.
# We strip trailing backtick/paren/period to get the clean section name.
MISSING=0
while IFS= read -r ref; do
  # Skip empty lines
  [ -z "$ref" ] && continue

  # For compound refs like "Section > Subsection", check the leaf name (after last >)
  # For simple refs like "Section", check the full name.
  # Both must resolve to a ## or ### heading in references.md.
  leaf=$(echo "$ref" | awk -F' > ' '{print $NF}' | sed 's/[[:space:]]*$//')
  top=$(echo "$ref" | awk -F' > ' '{print $1}' | sed 's/[[:space:]]*$//')

  # A reference resolves if EITHER:
  #   (a) the full top-level name matches a ## heading, OR
  #   (b) the leaf name matches any ## or ### heading
  if ! grep -q "^## $top" "$REF_MD" 2>/dev/null && \
     ! grep -q "^## $leaf\|^### $leaf" "$REF_MD" 2>/dev/null; then
    echo "    ✗ Orphan ref: 'references.md > $ref' — section not found in references.md"
    MISSING=$((MISSING + 1))
  fi
done < <(cat "$SKILL_MD" "$SKILL_GULF3_MD" \
          | grep -o 'references\.md > [^`)*\.]*' \
          | sed 's/references\.md > //' \
          | sed 's/[[:space:]]*$//' \
          | sort -u)

assert "All 'references.md > [section]' cross-references from SKILL.md + Gulf 3 resolve to existing sections (0 orphans)" \
  "$MISSING"

echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
