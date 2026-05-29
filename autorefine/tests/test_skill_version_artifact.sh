#!/bin/bash
# AutoRefine Skill Version Artifact Contract Test Suite
# Locks the prompt/schema/design contract for immutable versioned skill artifacts.

set -euo pipefail

cd "$(dirname "$0")/.."

PASS=0
FAIL=0
TOTAL=0

SKILL_MD="SKILL.md"
SKILL_GULF3_MD="references/gulf3-generalization.md"
REF_MD="references.md"
DESIGN_DOC="../dev/docs/archive/design-autorefine-v4-skill-eval-platform-public-root-snapshot.md"
DEV_DESIGN_DOC="../dev/docs/design-autorefine-v4-skill-eval-platform.md"

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

echo "=== Test Suite: AutoRefine Skill Version Artifact ==="
echo ""

if [ ! -f "$SKILL_MD" ] || [ ! -f "$SKILL_GULF3_MD" ] || [ ! -f "$REF_MD" ] || [ ! -f "$DESIGN_DOC" ] || [ ! -f "$DEV_DESIGN_DOC" ]; then
  echo "FATAL: required prompt or design files are missing"
  exit 2
fi

echo "--- Test Group 1: Cross-References ---"
assert "Gulf 3 references 'references.md > Skill Version Artifact Schema'" \
  "$(grep -q 'references\.md > Skill Version Artifact Schema' "$SKILL_GULF3_MD"; echo $?)"
assert "references.md defines '## Skill Version Artifact Schema'" \
  "$(grep -q '^## Skill Version Artifact Schema' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 2: Workspace + Storage Contract ---"
assert "SKILL.md initialize workspace creates skill-versions/ directory" \
  "$(grep -q 'skill-versions/' "$SKILL_MD"; echo $?)"
assert "Gulf 3 writes immutable version artifacts under skill-versions/<version_id>/SKILL.md" \
  "$(grep -q 'skill-versions/<version_id>/SKILL.md' "$SKILL_GULF3_MD"; echo $?)"
assert "references.md defines version artifact manifest as artifact_type skill_version_artifact" \
  "$(grep -q '"artifact_type": "skill_version_artifact"' "$REF_MD"; echo $?)"
assert "references.md version artifact schema includes version_id" \
  "$(grep -q '"version_id"' "$REF_MD"; echo $?)"
assert "references.md version artifact schema includes parent_version_id" \
  "$(grep -q '"parent_version_id"' "$REF_MD"; echo $?)"
assert "references.md version artifact schema includes snapshot_path" \
  "$(grep -q '"snapshot_path"' "$REF_MD"; echo $?)"
assert "references.md version artifact schema includes version.json" \
  "$(grep -q '### version\.json' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 3: Mutation Wiring ---"
MUTATION_ARTIFACT_SECTION="$(sed -n '/CONTRACT-ANCHOR:mutation_candidate_revision:start/,/CONTRACT-ANCHOR:mutation_candidate_revision:end/p' "$REF_MD")"
assert "Mutation Candidate Revision Artifact includes version_artifact field" \
  "$(echo "$MUTATION_ARTIFACT_SECTION" | grep -q '`version_artifact`'; echo $?)"
assert "Gulf 3 carries version_artifact into mutation.md" \
  "$(grep -q 'carry the resulting `version_artifact` object unchanged into `mutation.md`' "$SKILL_GULF3_MD"; echo $?)"
assert "Gulf 3 carries version_artifact into eval_results.json" \
  "$(grep -q 'carry the resulting `version_artifact` object unchanged into .*`eval_results.json`' "$SKILL_GULF3_MD"; echo $?)"
assert "Gulf 3 carries baseline version_artifact into results.json.experiments[0]" \
  "$(grep -q 'results\.json\.experiments\[0\]' "$SKILL_GULF3_MD"; echo $?)"
echo ""

echo "--- Test Group 4: Derived Registry + Diff ---"
VERSION_REGISTRY_SECTION="$(sed -n '/CONTRACT-ANCHOR:version_registry:start/,/CONTRACT-ANCHOR:version_registry:end/p' "$REF_MD")"
assert "Version Registry Schema exposes version_id" \
  "$(echo "$VERSION_REGISTRY_SECTION" | grep -q '"version_id"'; echo $?)"
assert "Version Registry Schema carries version_artifact through unchanged" \
  "$(grep -q 'Carry the stored `version_artifact` object through unchanged' "$REF_MD"; echo $?)"
assert "Skill diff prefers version_artifact.snapshot_path" \
  "$(grep -q 'Prefer the immutable `version_artifact.snapshot_path`' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 5: Design Docs ---"
assert "main design doc mentions immutable skill-versions archive" \
  "$(grep -q 'immutable `skill-versions/<version_id>/` archive' "$DESIGN_DOC"; echo $?)"
assert "dev design doc mentions immutable skill-versions archive" \
  "$(grep -q 'immutable `skill-versions/<version_id>/` archive' "$DEV_DESIGN_DOC"; echo $?)"
assert "main design doc rollback prefers version_artifact.snapshot_path" \
  "$(grep -q 'version_artifact.snapshot_path' "$DESIGN_DOC"; echo $?)"
assert "dev design doc rollback prefers version_artifact.snapshot_path" \
  "$(grep -q 'version_artifact.snapshot_path' "$DEV_DESIGN_DOC"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
