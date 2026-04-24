#!/bin/bash
# AutoRefine Research Intake contract test suite
# Locks the Phase 6.5 contract across the canonical reference,
# Gulf 3 execution surface, and mirrored v4 design docs.

PASS=0
FAIL=0
TOTAL=0

ROOT="/Users/surahli/Documents/projects/skill-improvement"
REF_MD="$ROOT/autorefine/references.md"
GULF3="$ROOT/autorefine/references/gulf3-generalization.md"
PUBLIC_DOC="$ROOT/dev/docs/archive/design-autorefine-v4-skill-eval-platform-public-root-snapshot.md"
DEV_DOC="$ROOT/dev/docs/design-autorefine-v4-skill-eval-platform.md"
SEED="$ROOT/dev/seeds/seed-autorefine-v4.yaml"

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

echo "=== Test Suite: AutoRefine Research Intake Contract ==="
echo ""

for file in "$REF_MD" "$GULF3" "$PUBLIC_DOC" "$DEV_DOC" "$SEED"; do
  if [ ! -f "$file" ]; then
    echo "FATAL: required file missing: $file"
    exit 2
  fi
done

echo "--- Test Group 1: Canonical Reference Contract ---"
assert "references define a dedicated Research Intake Stage Contract section" \
  "$(grep -q '^## Research Intake Stage Contract' "$REF_MD"; echo $?)"
assert "references define Inputs for Research Intake" \
  "$(grep -q '^### Inputs' "$REF_MD"; echo $?)"
assert "references define Responsibilities for Research Intake" \
  "$(grep -q '^### Responsibilities' "$REF_MD"; echo $?)"
assert "references define Outputs for Research Intake" \
  "$(grep -q '^### Outputs' "$REF_MD"; echo $?)"
assert "references define Validation rules for Research Intake" \
  "$(grep -q '^### Validation rules' "$REF_MD"; echo $?)"
assert "references define Failure / Error Handling for Research Intake" \
  "$(grep -q '^### Failure / Error Handling' "$REF_MD"; echo $?)"
assert "references define a Research Intake Configuration Schema section" \
  "$(grep -q '^### Research Intake Configuration Schema' "$REF_MD"; echo $?)"
assert "references persist the research_intake state ledger" \
  "$(grep -q '`research_intake`: null, or' "$REF_MD"; echo $?)"
assert "references persist the research_intake_path pointer" \
  "$(grep -q '`research_intake_path`: null, or' "$REF_MD"; echo $?)"
assert "references define session-log entry for research_intake_started" \
  "$(grep -q 'research_intake_started' "$REF_MD"; echo $?)"
assert "references define session-log entry for research_intake_completed" \
  "$(grep -q 'research_intake_completed' "$REF_MD"; echo $?)"
assert "references require at least one evidence-backed extracted pattern" \
  "$(grep -q 'Accept the stage only when at least one source yields at least one evidence-backed extracted pattern' "$REF_MD"; echo $?)"
assert "references define same-skill targeting in the default config" \
  "$(grep -q 'improvement_scope: same_skill_only' "$REF_MD"; echo $?)"
assert "references define default source selection caps" \
  "$(grep -q 'max_total_sources: 4' "$REF_MD"; echo $?)"
assert "references define default retrieval caps" \
  "$(grep -q 'max_mutation_leads: 8' "$REF_MD"; echo $?)"
assert "references define override precedence for research intake config" \
  "$(grep -q 'base defaults -> pattern defaults -> `research_intake_overrides` -> per-source `analysis_goal`' "$REF_MD"; echo $?)"
assert "references require a Resolved Config section in research-intake.md" \
  "$(grep -q '^## Resolved Config' "$REF_MD"; echo $?)"
assert "references define invalid research intake config as a blocking error" \
  "$(grep -q 'invalid_research_intake_config' "$REF_MD"; echo $?)"
assert "references define corpus provenance and attribution requirements" \
  "$(grep -q '^### Corpus Provenance and Attribution Requirements' "$REF_MD"; echo $?)"
assert "references require retrieval_context in the shared corpus schema" \
  "$(grep -q '`retrieval_context`' "$REF_MD"; echo $?)"
assert "references require source_timestamps in the shared corpus schema" \
  "$(grep -q '`source_timestamps`' "$REF_MD"; echo $?)"
assert "references require traceability in the shared corpus schema" \
  "$(grep -q '`traceability`' "$REF_MD"; echo $?)"
assert "references require canonical_location and retrieved_at in accepted sources" \
  "$(grep -q 'canonical_location: <normalized-path-or-url> | analysis_goal: <goal> | retrieved_at: <ISO timestamp>' "$REF_MD"; echo $?)"
assert "references block failed research intake from flowing into Phase 7" \
  "$(grep -q 'Phase 7 may read `research-intake.md` only when `state.json.research_intake.status` is `completed` or `partial`' "$REF_MD"; echo $?)"
assert "references forbid Research Intake from reading adversarial_holdout" \
  "$(grep -q 'Research Intake must never read `adversarial_holdout`' "$REF_MD"; echo $?)"
assert "per-phase state fields include Phase 6.5 research intake" \
  "$(grep -q '| 6.5 | `research_intake.status`' "$REF_MD"; echo $?)"
echo ""

echo "--- Test Group 2: Gulf 3 Wiring ---"
assert "Gulf 3 defines Phase 6.5 Research Intake" \
  "$(grep -q '^## Phase 6.5: Research Intake (optional)' "$GULF3"; echo $?)"
assert "Gulf 3 points to the canonical Research Intake Stage Contract" \
  "$(grep -q 'Read `references.md > Research Intake Stage Contract` before doing any Phase 6.5 work' "$GULF3"; echo $?)"
assert "Gulf 3 resolves research_intake_config before validation" \
  "$(grep -q 'Resolve `research_intake_config` from the base defaults' "$GULF3"; echo $?)"
assert "Gulf 3 carries default source-selection controls" \
  "$(grep -q '4 total sources by default, 2 per source kind by default' "$GULF3"; echo $?)"
assert "Gulf 3 carries default retrieval limits" \
  "$(grep -q '12 total extracted patterns and 8 mutation leads' "$GULF3"; echo $?)"
assert "Gulf 3 persists state.json.research_intake fields" \
  "$(grep -q 'state.json.research_intake = {status, target_skill_path, target_domain, requested_sources, accepted_sources, rejected_sources, completed_at, error_code}' "$GULF3"; echo $?)"
assert "Gulf 3 blocks invalid config overrides" \
  "$(grep -q 'error_code = \"invalid_research_intake_config\"' "$GULF3"; echo $?)"
assert "Gulf 3 blocks Phase 7 when research intake failed" \
  "$(grep -q 'If the status is `"failed"`, stop before Phase 7' "$GULF3"; echo $?)"
assert "Gulf 3 only reads research-intake.md for completed or partial status" \
  "$(grep -q 'read it next only when `state.json.research_intake.status` is `completed` or `partial`' "$GULF3"; echo $?)"
assert "Gulf 3 forbids cross-skill routing and holdout access in Research Intake" \
  "$(grep -q 'Never use Research Intake to compare different skills as routing candidates, and never read `adversarial_holdout`' "$GULF3"; echo $?)"
echo ""

echo "--- Test Group 3: Design Doc Mirrors ---"
assert "public design doc defines the canonical Phase 6.5 contract" \
  "$(grep -q '\*\*Canonical Phase 6.5 contract:\*\*' "$PUBLIC_DOC"; echo $?)"
assert "public design doc includes resolved research intake config defaults" \
  "$(grep -q 'Phase 6.5 must resolve one `research_intake_config` before reading sources' "$PUBLIC_DOC"; echo $?)"
assert "public design doc includes override precedence for research intake" \
  "$(grep -q '`base_defaults -> pattern_defaults -> research_intake_overrides -> per-source analysis_goal`' "$PUBLIC_DOC"; echo $?)"
assert "public design doc includes research_intake state object" \
  "$(grep -q '| `.research_intake` | object/null | Phase 6.5 ledger:' "$PUBLIC_DOC"; echo $?)"
assert "public design doc explains failed research intake is blocking" \
  "$(grep -q 'Phase 7 must stop instead of claiming the run is research-informed' "$PUBLIC_DOC"; echo $?)"
assert "public design doc defines provenance as required for research corpus entries" \
  "$(grep -q 'Provenance is required, not optional' "$PUBLIC_DOC"; echo $?)"
assert "public design doc includes retrieval_context and traceability in the shared envelope" \
  "$(grep -q '`source_ref`, `retrieval_context`, `captured_at`, `captured_by`, `source_timestamps`' "$PUBLIC_DOC"; echo $?)"
assert "public design doc forbids cross-skill routing and holdout access" \
  "$(grep -q 'Research Intake is for same-skill improvement only' "$PUBLIC_DOC"; echo $?)"
assert "dev design doc defines the canonical Phase 6.5 contract" \
  "$(grep -q '\*\*Canonical Phase 6.5 contract:\*\*' "$DEV_DOC"; echo $?)"
assert "dev design doc includes resolved research intake config defaults" \
  "$(grep -q 'Phase 6.5 must resolve one `research_intake_config` before reading sources' "$DEV_DOC"; echo $?)"
assert "dev design doc includes override precedence for research intake" \
  "$(grep -q '`base_defaults -> pattern_defaults -> research_intake_overrides -> per-source analysis_goal`' "$DEV_DOC"; echo $?)"
assert "dev design doc includes research_intake state object" \
  "$(grep -q '| `.research_intake` | object/null | Phase 6.5 ledger:' "$DEV_DOC"; echo $?)"
assert "dev design doc explains failed research intake is blocking" \
  "$(grep -q 'Phase 7 must stop instead of claiming the run is research-informed' "$DEV_DOC"; echo $?)"
assert "dev design doc defines provenance as required for research corpus entries" \
  "$(grep -q 'Provenance is required, not optional' "$DEV_DOC"; echo $?)"
assert "dev design doc includes retrieval_context and traceability in the shared envelope" \
  "$(grep -q '`source_ref`, `retrieval_context`, `captured_at`, `captured_by`, `source_timestamps`' "$DEV_DOC"; echo $?)"
assert "dev design doc forbids cross-skill routing and holdout access" \
  "$(grep -q 'Research Intake is for same-skill improvement only' "$DEV_DOC"; echo $?)"
echo ""

echo "--- Test Group 4: Seed Contract ---"
assert "seed requires provenance metadata for every normalized research corpus entry" \
  "$(grep -q 'Every normalized research corpus entry includes required provenance and source attribution metadata' "$SEED"; echo $?)"
assert "seed defines the research_provenance ontology object" \
  "$(grep -q 'name: research_provenance' "$SEED"; echo $?)"
echo ""

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $FAIL
