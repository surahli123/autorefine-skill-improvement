#!/bin/bash
# AutoRefine external reference collection contract test suite
# Locks the Phase 6.5 requirements for fetched source snapshots,
# citation metadata, retrieval timestamps, and raw artifact storage.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REFS_MD="$PROJECT_ROOT/autorefine/references.md"
GULF3_MD="$PROJECT_ROOT/autorefine/references/gulf3-generalization.md"
PUBLIC_DOC="$PROJECT_ROOT/dev/docs/archive/design-autorefine-v4-skill-eval-platform-public-root-snapshot.md"
DEV_DOC="$PROJECT_ROOT/dev/docs/design-autorefine-v4-skill-eval-platform.md"
SEED_FILE="$PROJECT_ROOT/dev/seeds/seed-autorefine-v4.yaml"

PASS_COUNT=0
FAIL_COUNT=0

pass_test() { PASS_COUNT=$((PASS_COUNT + 1)); echo "  PASS  $1"; }
fail_test() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "  FAIL  $1 (missing '$2')"; }
assert_contains() { printf '%s' "$1" | grep -qF -- "$2" && pass_test "$3" || fail_test "$3" "$2"; }

echo ""
echo "================================================================"
echo "  AutoRefine External Reference Collection Contract Tests"
echo "================================================================"
echo ""

REFS_CONTENT="$(cat "$REFS_MD")"
GULF3_CONTENT="$(cat "$GULF3_MD")"
PUBLIC_DOC_CONTENT="$(cat "$PUBLIC_DOC")"
DEV_DOC_CONTENT="$(cat "$DEV_DOC")"
SEED_CONTENT="$(cat "$SEED_FILE")"

REFS_RESEARCH_SECTION="$(sed -n '/CONTRACT-ANCHOR:research_intake_stage:start/,/CONTRACT-ANCHOR:research_intake_stage:end/p' "$REFS_MD")"
REFS_INTAKE_SECTION="$(sed -n '/CONTRACT-ANCHOR:research_intake_sections:start/,/CONTRACT-ANCHOR:research_intake_sections:end/p' "$REFS_MD")"
REFS_PROVENANCE_SECTION="$(sed -n '/CONTRACT-ANCHOR:corpus_provenance:start/,/CONTRACT-ANCHOR:corpus_provenance:end/p' "$REFS_MD")"

echo "--- autorefine/references.md ---"
assert_contains "$REFS_RESEARCH_SECTION" "### External Source Retrieval and Snapshot Requirements" "references define external retrieval and snapshot requirements"
assert_contains "$REFS_RESEARCH_SECTION" 'Fetch remote `best_practice`, `article`, and `repo` sources before extraction' "references require source fetch before extraction"
assert_contains "$REFS_RESEARCH_SECTION" "[workspace]/research-sources/<source_id>/" "references define a raw research source artifact directory"
assert_contains "$REFS_RESEARCH_SECTION" '`citation_metadata`' "references define citation metadata for accepted external sources"
assert_contains "$REFS_RESEARCH_SECTION" '`retrieval_started_at`' "references define retrieval_started_at"
assert_contains "$REFS_RESEARCH_SECTION" '`retrieval_completed_at`' "references define retrieval_completed_at"
assert_contains "$REFS_RESEARCH_SECTION" '`raw_artifact_ref`' "references define raw_artifact_ref for fetched source snapshots"
assert_contains "$REFS_PROVENANCE_SECTION" '`source_ref.citation_metadata.title`' "provenance requirements include citation title"
assert_contains "$REFS_PROVENANCE_SECTION" '`source_ref.citation_metadata.author_or_org`' "provenance requirements include citation author or organization"
assert_contains "$REFS_PROVENANCE_SECTION" '`source_ref.citation_metadata.published_at`' "provenance requirements include citation published_at"
assert_contains "$REFS_PROVENANCE_SECTION" '`traceability.raw_artifact_refs[]`' "provenance requirements include raw artifact traceability"
assert_contains "$REFS_INTAKE_SECTION" "## Source Snapshots" "research-intake template includes a source snapshots section"
assert_contains "$REFS_INTAKE_SECTION" "citation_title" "research-intake template persists citation_title"
assert_contains "$REFS_INTAKE_SECTION" "citation_author_or_org" "research-intake template persists citation_author_or_org"
assert_contains "$REFS_INTAKE_SECTION" "retrieval_started_at" "research-intake template persists retrieval_started_at"
assert_contains "$REFS_INTAKE_SECTION" "retrieval_completed_at" "research-intake template persists retrieval_completed_at"
assert_contains "$REFS_INTAKE_SECTION" "raw_artifact_ref" "research-intake template persists raw_artifact_ref"
echo ""

echo "--- autorefine/references/gulf3-generalization.md ---"
assert_contains "$GULF3_CONTENT" 'fetch the exact source content into `[workspace]/research-sources/<source_id>/` before extracting patterns' "Gulf 3 fetches exact source content into raw artifacts"
assert_contains "$GULF3_CONTENT" 'Persist citation metadata, retrieval timestamps, and `raw_artifact_ref`' "Gulf 3 persists citation metadata and artifact refs"
assert_contains "$GULF3_CONTENT" "If remote retrieval fails, reject that source explicitly instead of extracting from a partial fetch" "Gulf 3 rejects failed remote retrievals"
echo ""

echo "--- dev/docs/archive/design-autorefine-v4-skill-eval-platform-public-root-snapshot.md ---"
assert_contains "$PUBLIC_DOC_CONTENT" "Phase 6.5 must fetch the exact content for any remote best-practice/article/repo source before extraction" "public design doc requires remote fetch before extraction"
assert_contains "$PUBLIC_DOC_CONTENT" 'store the fetched snapshot under `[workspace]/research-sources/<source_id>/`' "public design doc stores fetched snapshots under research-sources"
assert_contains "$PUBLIC_DOC_CONTENT" "citation metadata, retrieval timestamps, and raw artifact references are part of the Phase 6.5 contract" "public design doc carries citation and artifact metadata"
echo ""

echo "--- dev/docs/design-autorefine-v4-skill-eval-platform.md ---"
assert_contains "$DEV_DOC_CONTENT" "Phase 6.5 must fetch the exact content for any remote best-practice/article/repo source before extraction" "dev design doc requires remote fetch before extraction"
assert_contains "$DEV_DOC_CONTENT" 'store the fetched snapshot under `[workspace]/research-sources/<source_id>/`' "dev design doc stores fetched snapshots under research-sources"
assert_contains "$DEV_DOC_CONTENT" "citation metadata, retrieval timestamps, and raw artifact references are part of the Phase 6.5 contract" "dev design doc carries citation and artifact metadata"
echo ""

echo "--- dev/seeds/seed-autorefine-v4.yaml ---"
assert_contains "$SEED_CONTENT" "External best-practice/article/repo research sources are fetched into raw snapshot artifacts with citation metadata and retrieval timestamps before pattern extraction" "seed requires external source fetch with citation and timestamps"
assert_contains "$SEED_CONTENT" "description: \"Fetched external source snapshot with citation metadata, retrieval timestamps, and raw artifact references for Phase 6.5 research intake\"" "seed ontology describes research source snapshots"
echo ""

echo "================================================================"
echo "  Results: $PASS_COUNT passed, $FAIL_COUNT failed"
echo "================================================================"
echo ""

[ "$FAIL_COUNT" -gt 0 ] && exit 1 || exit 0
