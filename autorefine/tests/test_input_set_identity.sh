#!/bin/bash
# AutoRefine Input Set Identity Test Suite
# Locks the prompt contract for deterministic, stable input IDs.

PASS=0
FAIL=0
TOTAL=0

SKILL_MD="/Users/surahli/Documents/projects/skill-improvement/autorefine/SKILL.md"
GULF1_MD="/Users/surahli/Documents/projects/skill-improvement/autorefine/references/gulf1-comprehension.md"
GULF2_MD="/Users/surahli/Documents/projects/skill-improvement/autorefine/references/gulf2-specification.md"
GULF3_MD="/Users/surahli/Documents/projects/skill-improvement/autorefine/references/gulf3-generalization.md"
REF_MD="/Users/surahli/Documents/projects/skill-improvement/autorefine/references.md"

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

echo "=== Test Suite: AutoRefine Input Set Identity ==="
echo ""

if [ ! -f "$SKILL_MD" ] || [ ! -f "$GULF1_MD" ] || [ ! -f "$GULF2_MD" ] || [ ! -f "$GULF3_MD" ] || [ ! -f "$REF_MD" ]; then
  echo "FATAL: required prompt files are missing"
  exit 2
fi

PROMPT_CONTENT="$(cat "$SKILL_MD" "$GULF1_MD" "$GULF2_MD" "$GULF3_MD")"

echo "--- Test Group 1: Cross-References ---"
assert "prompt surfaces reference 'references.md > Input Set Identity Schema'" \
  "$(printf '%s' "$PROMPT_CONTENT" | grep -q 'references\.md > Input Set Identity Schema'; echo $?)"
assert "references.md defines '## Input Set Identity Schema'" \
  "$(grep -q '^## Input Set Identity Schema' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 2: Workspace Schema ---"
assert "references.md documents input-sets.json" \
  "$(grep -q '^### input-sets\.json' "$REF_MD"; echo $?)"
assert "input-sets.json schema includes set_id" \
  "$(grep -q '"set_id"' "$REF_MD"; echo $?)"
assert "input-sets.json schema includes input_id" \
  "$(grep -q '"input_id"' "$REF_MD"; echo $?)"
assert "input-sets.json schema includes canonical_hash" \
  "$(grep -q '"canonical_hash"' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 3: Deterministic Rules ---"
assert "references.md defines content_hash normalization" \
  "$(grep -q 'content_hash = sha256(normalized_input)' "$REF_MD"; echo $?)"
assert "references.md defines canonical_hash for the set" \
  "$(grep -q 'canonical_hash = sha256' "$REF_MD"; echo $?)"
assert "references.md defines stable set_id format" \
  "$(grep -q 'set_id = <kind>-<canonical_hash\[0:8\]>' "$REF_MD"; echo $?)"
assert "references.md forbids renumbering an existing set" \
  "$(grep -q 'Never renumber an existing set' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 4: Phase Wiring ---"
assert "Quick Start observation shows Input ID" \
  "$(printf '%s' "$PROMPT_CONTENT" | grep -q 'Input ID: \[input_id\]'; echo $?)"
assert "Quick Start scoring compares input_ids for overlap" \
  "$(printf '%s' "$PROMPT_CONTENT" | grep -q 'comparing `input_id`s'; echo $?)"
assert "Phase 3 registers fixtures in input-sets.json" \
  "$(printf '%s' "$PROMPT_CONTENT" | grep -q 'register it in `\[workspace\]/input-sets\.json`'; echo $?)"
assert "Phase 4 writes split membership by input_id" \
  "$(printf '%s' "$PROMPT_CONTENT" | grep -q 'exact `input_id` list for each split'; echo $?)"
assert "Phase 7 records input_set_id with experiment scoring" \
  "$(printf '%s' "$PROMPT_CONTENT" | grep -q 'Record the active `input_set_id`'; echo $?)"
assert "Phase 7 records exact input_set_ref with experiment scoring" \
  "$(printf '%s' "$PROMPT_CONTENT" | grep -q '`input_set_ref`'; echo $?)"
assert "Phase 7 records finalized-order input_ids with experiment scoring" \
  "$(printf '%s' "$PROMPT_CONTENT" | grep -q 'finalized-order `input_ids`'; echo $?)"
echo ""

echo "--- Test Group 5: Artifact Persistence ---"
assert "results.json schema includes input_set_id" \
  "$(grep -q '"input_set_id"' "$REF_MD"; echo $?)"
assert "results.json schema includes input_set_ref" \
  "$(grep -q '"input_set_ref"' "$REF_MD"; echo $?)"
assert "references.md defines input_set_ref format" \
  "$(grep -qF 'input-sets.json#<set_id>' "$REF_MD"; echo $?)"
assert "results.json schema includes input_ids" \
  "$(grep -q '"input_ids"' "$REF_MD"; echo $?)"
assert "Iteration eval_results.json schema includes input_set_id" \
  "$(grep -A10 '\*\*eval_results\.json\*\*' "$REF_MD" | grep -q '"input_set_id"'; echo $?)"
assert "Iteration eval_results.json schema includes input_set_ref" \
  "$(grep -A15 '\*\*eval_results\.json\*\*' "$REF_MD" | grep -q '"input_set_ref"'; echo $?)"
assert "Iteration eval_results.json schema includes input_ids" \
  "$(grep -A20 '\*\*eval_results\.json\*\*' "$REF_MD" | grep -q '"input_ids"'; echo $?)"
assert "session-log schema includes input_set_registered entry" \
  "$(grep -q 'input_set_registered' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 6: Version Comparison Alignment ---"
assert "references.md defines a Version Comparison Alignment section" \
  "$(grep -q '^## Version Comparison Alignment' "$REF_MD"; echo $?)"
assert "version comparison requires matching input_set_id before diffing" \
  "$(grep -q 'require the same `input_set_id`' "$REF_MD"; echo $?)"
assert "version comparison aligns Version N and N+1 by stable input_id" \
  "$(grep -q 'align Version N and Version N+1 by `input_id`' "$REF_MD"; echo $?)"
assert "version comparison marks mismatched comparisons as invalid-comparison" \
  "$(grep -q '`invalid-comparison`' "$REF_MD"; echo $?)"
assert "version comparison blocks normal comparison results on preflight failure" \
  "$(grep -q 'must not emit normal comparison results' "$REF_MD"; echo $?)"
assert "version comparison forbids list position or run order alignment" \
  "$(grep -q 'Do NOT align by list position, array order, or run order' "$REF_MD"; echo $?)"
assert "version comparison computes per-input deltas after input_id join" \
  "$(grep -q 'compute per-input diffs only after the `input_id` join succeeds' "$REF_MD"; echo $?)"
assert "SKILL.md points version comparison work to the alignment contract" \
  "$(grep -q 'references\.md > Version Comparison Alignment' "$SKILL_MD"; echo $?)"
assert "SKILL.md flags mismatched comparisons as invalid-comparison" \
  "$(grep -q '`invalid-comparison`' "$SKILL_MD"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
