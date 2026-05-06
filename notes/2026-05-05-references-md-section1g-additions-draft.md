# Staging — Section 1g additions to `autorefine/references.md`

**Date:** 2026-05-05
**Purpose:** Hold-area for the references.md content that lands in the parent PR (next-step #2) when PR #4 (`surahli123/autorefine-dev`) merges. Per Option D-modified placement decision (see `notes/2026-05-05-references-md-design-decision.md`).
**Target file:** `/Users/surahli/Documents/projects/skill-improvement/autorefine/references.md` (currently 6,079 lines).
**Estimated additions:** ~150 lines across 2 patches.
**Status:** DRAFT — content lifted from PR #4's locked Section 1g. Subject to revision based on PR #4 review feedback.

---

## Patch 1 — Update existing `## Phase 1 Design Audit Dimension Schema` (line 974)

### 1a. Append row 7 to canonical ordering table (line 980-987)

Add this row after the existing `scripts` row (currently row 6):

```
| 7 | `consolidation_pressure` | Consolidation Pressure | `ordinal_presence` | `present`, `partial`, `missing` | always scored except in Mini mode (skipped); `n/a` not allowed; library-context-dependent |
```

### 1b. Update prose immediately above the table (line 978)

Replace:

> Use this canonical ordering whenever a Phase 1 audit is represented structurally. Do not reorder dimensions ad hoc. `scripts` stays last because it is conditional; `description_quality` is part of the core audit set and must appear before any conditional script assessment.

With:

> Use this canonical ordering whenever a Phase 1 audit is represented structurally. Do not reorder dimensions ad hoc. `scripts` is conditional and `consolidation_pressure` is library-context-dependent — both are positioned after `description_quality` so the core single-skill audit set (rows 1-5) stays intact when either is skipped. `consolidation_pressure` is skipped only in Mini mode; it is never `n/a`.

### 1c. Update canonical structured payload example (line 998-1017)

Append `"consolidation_pressure"` to `dimension_order` array and add the corresponding entry to `dimensions` map. New shape:

```json
"dimension_order": [
  "gotchas",
  "voice",
  "progressive_disclosure",
  "anti_railroading",
  "description_quality",
  "scripts",
  "consolidation_pressure"
],
"dimensions": {
  "gotchas": {"score": "present", "score_type": "ordinal_presence_with_na"},
  "voice": {"score": "partial", "score_type": "ordinal_presence"},
  "progressive_disclosure": {"score": "missing", "score_type": "ordinal_presence"},
  "anti_railroading": {"score": "partial", "score_type": "ordinal_presence"},
  "description_quality": {"score": "present", "score_type": "ordinal_presence"},
  "scripts": {"score": "n/a", "score_type": "ordinal_presence_with_na"},
  "consolidation_pressure": {"score": "present", "score_type": "ordinal_presence"}
}
```

---

## Patch 2 — New section `## Consolidation Pressure Audit` (insert after line 1138, before `### Phase 1 Routing Fixture Run Result Schema`)

```markdown
## Consolidation Pressure Audit

Read when: Phase 1 active and the audit needs to score `consolidation_pressure` (the 7th audit dimension), or when Phase 7 mutation hypothesis generation needs to read `consolidation_candidates[]`.

This dimension scores library shape, not skill quality. A skill can score `present` on every other Phase 1 dimension and still score `missing` here — the question is whether the skill exists at the right umbrella level for a healthy library, not whether the artifact is well-executed. Mini mode skips this dimension; Standard runs it once; Deep runs it twice with reconciliation (see Deep Mode Reconciliation below).

### Library Context Manifest Schema

The audit reads a `library_context_manifest` describing the candidate skill's neighbors. The manifest is the only cross-skill input any Phase 1 dimension needs.

```yaml
library_context_manifest:
  fixture_set_id: <stable id of the library snapshot used for this audit>
  candidate_skill_id: <stable id of the skill under audit>
  candidate_skill_name: <human-readable name>
  candidate_pattern: <one of tool_wrapper | generator | reviewer | inversion | pipeline>
  library_size: <integer count of agent-created skills at audit time>
  built_after_mutation_id: <id of the most recent Phase 7 mutation observed when manifest was last built>
  prefix_clusters:
    - cluster_prefix: <shared first word or domain keyword>
      members: [<skill_name>, ...]
      cluster_size: <integer>
  adjacent_skills:
    - skill_name: <candidate's nearest neighbor by name distance>
      relevance_signal: <prefix_match | domain_match | semantic_match>
      candidate_belongs_under: <true | false | undetermined>
```

**Persistence and invalidation:** The manifest persists across Phase 1 audits within a campaign. It is invalidated only when Phase 7 emits a scope-changing mutation (`merge_into_umbrella`, `demote_to_references`, `demote_to_templates`, `demote_to_scripts`, `split_into_umbrella_plus_subsection`). Content-changing mutations do not invalidate. The `built_after_mutation_id` stamp is a stale-read safety net: if a downstream consumer detects the manifest's stamp predates a known scope-changing mutation that escaped the invalidation hook, force-rebuild before scoring. Persisted to `state.json.phase1_context.library_context_manifest`.

### Audit Prompt Template

Phase 1 invokes this prompt for each candidate skill (one invocation per skill, manifest reused across invocations within a campaign).

```
You are auditing one skill's library shape. Score whether this skill exists at the right umbrella level for a healthy skill library.

CANDIDATE SKILL:
- name: {{candidate_skill_name}}
- pattern: {{candidate_pattern}}
- SKILL.md body: {{skill_body}}

LIBRARY CONTEXT (from library_context_manifest):
- library size: {{library_size}}
- prefix clusters this candidate matches: {{matching_prefix_clusters}}
- adjacent skills (by name distance): {{adjacent_skills}}
- existing umbrella opportunities: {{existing_umbrellas}}

Score one of: present | partial | missing.

PRESENT: Skill is already at the right umbrella level. Name reads like a category, body uses labeled subsections that share a coherent shape, supporting files capture session-specific detail. No consolidation pressure.

PARTIAL: Skill has a focused workflow that could legitimately stand alone, but you can identify one or more existing skills (or an obvious latent umbrella) it would belong inside as a labeled subsection. Recommend consolidation candidates.

MISSING: Skill is bound to a one-session artifact. At least TWO of these are true:
  - Name contains a session artifact (PR#, codename, ticket id, error string, customer name, audit-/triage-/salvage-/diagnosis-/fix- prefix)
  - Body is narrow enough that a maintainer would write it as a subsection
  - The library already contains a skill this one would fit under
  - The skill's core workflow does not generalize beyond the originating session

EXCLUSIONS (do NOT score Missing when):
  - Pattern is `pipeline` with multi-stage state and explicit handoff artifacts (top-bound at Partial)
  - Skill is the only member of its domain in the library (no umbrella to merge into)
  - Skill is intentionally session-scoped per the campaign goal (e.g., regression scaffold for incident X)

OBSERVABLE SIGNALS (in priority order):
  1. Name specificity (session artifacts → strong evidence of Missing)
  2. Prefix-cluster membership (2+ siblings sharing first word → Partial or Missing)
  3. Body breadth (narrow workflow → pressure toward Partial or Missing)
  4. Body structure (umbrella shape vs subsection shape)
  5. Reusability boundary (generalizes vs bound to one situation)
  6. Existing umbrella opportunity (does library already have a parent skill?)

Respond with the structured audit output schema (see Audit Output Schema below).
Critique: 1. Signals observed: [list which observable signals fired with evidence] 2. Indicators check: [count required indicators present for Missing] 3. Exclusion check: [list any exclusions that fire] 4. Verdict link: [explain why signals + indicators + exclusions resolve to this score]
Result: present | partial | missing
```

**Pattern-aware base pressure (calibration prior, not a hard rule):**

| Pattern | Base pressure prior | Notes |
|---|---|---|
| `tool_wrapper` | high | Narrow tool scope encourages siblings; strong umbrella opportunities |
| `generator` | medium | Templates often cluster by domain |
| `reviewer` | medium | Checklist skills cluster by review type |
| `inversion` | low | Interview gates usually intentionally scoped |
| `pipeline` | lowest | Multi-stage workflows designed for their scope; top-bound at Partial |

Resolve `pattern_calibration_profile_id` from this table at the start of each invocation. Persist `applied_pattern`, `base_pressure_prior`, and `pattern_calibration_profile_id` in the audit output's `pattern_calibration` block.

### Audit Output Schema

The Phase 1 audit payload's `dimensions.consolidation_pressure` field carries:

```json
{
  "consolidation_pressure": {
    "score": "missing",
    "score_type": "ordinal_presence",
    "library_context_manifest_ref": "fixtures/library-context-2026-05-04.json",
    "library_size_at_audit": 12,
    "indicators_present": [
      "name_contains_session_artifact",
      "body_is_subsection_shape",
      "umbrella_skill_exists_in_library"
    ],
    "exclusions_present": [],
    "consolidation_candidates": [
      {
        "candidate_umbrella": "pr-triage-salvage",
        "candidate_umbrella_id": "pr_triage_salvage",
        "consolidation_mode": "merge_into_existing_umbrella",
        "confidence_rank": 1,
        "cluster_size_prior": 5,
        "evidence": "candidate workflow is one of N labeled subsections this umbrella already maintains",
        "mode_options": [
          "merge_into_existing_umbrella",
          "create_new_umbrella",
          "demote_to_references",
          "demote_to_templates",
          "demote_to_scripts"
        ]
      },
      {
        "candidate_umbrella": "codex-review-triage",
        "candidate_umbrella_id": "codex_review_triage",
        "consolidation_mode": "merge_into_existing_umbrella",
        "confidence_rank": 2,
        "cluster_size_prior": 4,
        "evidence": "candidate workflow could also fit under the codex-review-triage umbrella",
        "mode_options": ["merge_into_existing_umbrella"]
      }
    ],
    "consolidation_ambiguity_flag": true,
    "pattern_calibration": {
      "applied_pattern": "tool_wrapper",
      "base_pressure_prior": "high",
      "pattern_calibration_profile_id": "tool_wrapper_consolidation_default"
    }
  }
}
```

**Field semantics:**

- `consolidation_candidates[]` — ranked by `confidence_rank` (1 = highest). Mutation loop picks top-ranked by default. Ranking prior is `cluster_size_prior` (size of candidate umbrella's existing prefix cluster); ties break by closest name-distance to candidate.
- `consolidation_ambiguity_flag` — `true` when top two candidates' `cluster_size_prior` values are within 20% of each other. Discard autopsy and human-review paths use this flag to spot borderline scope decisions without scanning every candidate list.
- `library_size_at_audit` — library size at moment of audit. Downstream re-audit triggers compare it against current library size (see Boundary Cases below for the `first_in_library` rule).
- `first_in_library` — emit `true` (with `library_size_at_audit`) when library size < 3 peers. Re-audit forced when library grows past 3 peers (manifest invalidation hook handles this — no separate mechanism).
- `consolidation_mode` enum: `merge_into_existing_umbrella | create_new_umbrella | demote_to_references | demote_to_templates | demote_to_scripts | split_into_umbrella_plus_subsection`.

Persisted to `state.json.phase1_context.consolidation_pressure_audit` for downstream-phase access without reopening Phase 1 artifacts.

### Audit Summary Aggregator (Library-Scale Audits)

When Phase 1 audits multiple skills in the same run, the per-skill payloads are aggregated into a top-level `consolidation_pressure_audit_summary` block on the run's structured Phase 1 audit output. Analogous to `aggregated_tpr_tnr_summary` in the Cross-Validation section.

```json
{
  "consolidation_pressure_audit_summary": {
    "fixture_set_id": "library-snapshot-2026-05-04",
    "library_size_at_audit": 50,
    "library_context_manifest_ref": "state.json.phase1_context.library_context_manifest",
    "manifest_built_after_mutation_id": "phase7_iter_12_content_tighten_voice",
    "skills_audited_count": 50,
    "skills_skipped_mini_mode_count": 0,
    "score_distribution": {
      "present": 31,
      "partial": 12,
      "missing": 7
    },
    "consolidation_pressure_indicators": {
      "skills_with_session_artifact_names": 7,
      "skills_with_subsection_shaped_bodies": 9,
      "skills_with_existing_umbrella_in_library": 11,
      "skills_with_non_generalizing_workflow": 5
    },
    "consolidation_candidates_total": 19,
    "consolidation_candidates_by_mode": {
      "merge_into_existing_umbrella": 8,
      "create_new_umbrella": 9,
      "demote_to_references": 1,
      "demote_to_templates": 1,
      "demote_to_scripts": 0
    },
    "consolidation_ambiguity_flag_count": 3,
    "first_in_library_skipped_count": 0,
    "library_health_finding": null,
    "phase7_mutation_priority_hint": {
      "scope_changing_mutations_recommended": 7,
      "interleave_recommended": 12,
      "content_changing_only": 31
    }
  }
}
```

**Field semantics:**

- `library_health_finding` — non-null when boundary case "Library where every skill scores Missing" fires. Carries a structured library-restructure recommendation; otherwise `null`.
- `phase7_mutation_priority_hint` — translates score distribution into Phase 7 batch composition guidance: Missing → scope-changing-priority, Partial → interleave, Present → content-only.
- `consolidation_candidates_by_mode` — sums across all per-skill payloads. Counts target-umbrella mode, not skill count (one skill can contribute to multiple modes if its candidates list has mixed modes).
- `manifest_built_after_mutation_id` — provenance for the manifest used in this audit run. If multiple skills in the run hit different `built_after_mutation_id` values (manifest was rebuilt mid-run), the aggregator records the *latest* value and the per-skill rows are the source of truth for which manifest each skill was scored against.

### Mini Mode Behavior

Skip this dimension entirely. Audit output emits:

```
"consolidation_pressure": "skipped (Mini mode — insufficient library context to score)"
```

Mini mode is for Quick Start campaigns where library hygiene is explicitly out of scope. No soft-note charity scoring; no name-only fallback. If a cheap name-only artifact check is wanted later, add it as a separate Phase 0 lint dimension rather than half-implementing this dimension in Mini.

### Deep Mode Reconciliation

Run the audit twice with different scan strategies, then reconcile.

1. **Pass A — name-centric:** Score based on name specificity, prefix-cluster signals, and existing umbrellas (faster).
2. **Pass B — body-centric:** Score based on body breadth, structure shape, and reusability boundary (slower, more semantic).

Reconciliation rule (per the verdict-reconciler pattern in transfer plan #2):

| Pass A | Pass B | Final score |
|---|---|---|
| Present | Present | Present |
| Missing | Missing | Missing |
| Disagreement (any other combination) | | Partial — both passes' evidence captured for human review |

Deep mode TPR/TNR target: ≥ 0.92 on calibration fixtures. Standard mode target: ≥ 0.85. Partial cases are diagnostic-only — no TPR/TNR target by definition (Partial is the ambiguous middle).

### Calibration Fixtures

Bundled fixture set: `phase1-consolidation-pressure-v1`. 12 fixtures evenly distributed across the three score values (4 missing, 4 partial, 4 present). Manifest at `tests/fixtures/phase1-consolidation-pressure-v1/manifest.json`. Add fixtures to the set and re-run cross-validation if confidence intervals widen past the 0.10 high-variance threshold.

Fold assignment for cross-validation uses `stable_fold_key = <input_id>|<content_hash>`, where `input_id` is the `candidate_skill_id` from the fixture's `library_context_manifest`.

### Boundary Cases

- **First skill in a fresh library** (`library_size < 3`): score `present`, emit `first_in_library: true` with `library_size_at_audit`. Re-audit triggered automatically when library grows past 3 peers (manifest invalidation hook reused — no separate mechanism).
- **Pipeline-pattern skill with sibling pipelines:** Each pipeline owns its scope by design; do not flag Missing solely because pipeline siblings exist with shared name prefixes. Top-bound at Partial.
- **Skill explicitly scoped to a session by campaign goal:** Exclusion criterion fires; score `present` and emit a note that campaign scope-discipline is the authoritative scoring input.
- **Library where every skill scores Missing:** Library design is wrong, not every skill. Set `library_health_finding` non-null with a structured library-restructure recommendation; recommend out-of-band library restructuring before continuing per-skill mutations.
- **Candidate umbrella does not yet exist:** Score `partial`, emit `consolidation_mode: create_new_umbrella` so the mutation loop knows to create the umbrella first.
- **Two umbrellas with comparable cluster size** (top two `cluster_size_prior` values within 20%): emit `consolidation_ambiguity_flag: true`. Mutation loop still defaults to top-ranked candidate; flag is for traceability, not loop control.

### Phase 7 Integration Points

Three integration points downstream of the audit output:

1. **Mutation hypothesis generation (Phase 7 step 1):** Missing → prioritize scope-changing mutations (merge / demote / split) over content-changing mutations; pick `confidence_rank: 1` candidate by default. Partial → interleave scope-changing and content-changing mutations in the same Phase 7 batch; eval scores arbitrate. Ambiguity flag true → discard autopsy captures runner-up candidate's evidence so a content-mutation success on the top-ranked candidate can be re-evaluated against the runner-up before declaring the loop converged.
2. **Mutation intent declaration:** Every mutation API call carries a `mutation_type` enum that includes scope-changing values (`merge_into_umbrella`, `demote_to_references`, `demote_to_templates`, `demote_to_scripts`, `split_into_umbrella_plus_subsection`) alongside existing content-changing values. Scope-changing emits trigger the manifest invalidation hook.
3. **Discard autopsy taxonomy:** `wrong_target` reason distinguishes "wrong content target" (you tried to fix the gotchas section but the gotchas section was fine) from "wrong scope target" (you tightened the voice on a skill that should not exist standalone).

### Eval Interaction (Phase 7 Mutation Scoring)

When a scope-changing mutation is applied, the eval result for the *original* skill ID is marked `superseded_by: <umbrella_skill_id>` rather than `pass` or `fail`. Shared-input comparison preflight treats `superseded_by` as a valid intermediate state.
```

---

## Open questions for parent PR review

1. **Section number assignment.** The new section currently has no top-level section number (just `## Consolidation Pressure Audit`). Should it be numbered (e.g., `## Phase 1.7 Consolidation Pressure Audit`) to mirror the design doc's Section 1g? Existing references.md uses prose section headers, not numbered ones, so I matched that convention. Flag if you want the design-doc numbering preserved for traceability.

2. **Prompt template wording.** The audit prompt template above is one synthesis of Section 1g's score contract + observable signals + required indicators + exclusions. Section 1g doesn't contain a literal prompt block — this is a derivation. Worth a careful read pass before commit.

3. **Reconciliation table format.** Existing references.md uses prose for verdict reconciliation in some places and tables in others. I used a table for clarity; flag if prose is preferred.

4. **Cross-references that don't yet exist in references.md.** Patch 2 references "Section 2c", "Section 1d", "Section 1f", and "transfer plan #2" — these are design-doc section refs, not references.md anchors. Should I:
   - (a) leave the design-doc-style refs as-is (works only if references.md is read alongside the design doc),
   - (b) replace them with references.md-internal anchors (cleaner but loses design-doc traceability),
   - (c) hybrid — keep design-doc refs but add a "see also" line per cross-reference?

5. **Manifest YAML vs JSON.** Section 1g specifies the manifest in YAML (matching how skill frontmatter is YAML), but the audit output and aggregator are JSON. Mixed languages within one references.md section is unusual — flag if you want the manifest converted to JSON for consistency (or if you want the existing schema sections to stay JSON-only and the YAML manifest to live in a different file).

---

## Application checklist (when PR #4 merges and parent PR opens)

1. Apply Patch 1a, 1b, 1c to `autorefine/references.md` line 974-1063 region.
2. Apply Patch 2 by inserting the new section after the existing `### Phase 1 Routing Fixture Run Result Schema` subsection (line ~1138).
3. Verify `grep -c "consolidation_pressure" autorefine/references.md` returns ≥ 12 (table row, payload example, schema section, output example, aggregator example, boundary cases, Phase 7 integration, eval interaction — multiple hits expected).
4. Update Section 1g checklist items #8 and #9 in `notes/2026-05-04-proposal-v4-section-1g-consolidation-pressure.md` from BLOCKED to DONE.
5. Resolve open questions 1-5 above (with you) before commit. Flag any wording revisions back into this staging file before pushing.
