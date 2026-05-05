# Proposal: v4 Section 1g — Consolidation Pressure (Phase 1 — 7th audit dimension)

*Draft v0.1 — 2026-05-04. Candidate addition to `dev/docs/design-autorefine-v4-skill-eval-platform.md`. Style-matched to existing Sections 1e (Anti-Railroading) and 1f (Description Quality).*

*Background and rationale: `notes/2026-05-04-hermes-curator-study.md` (Tier-1 technique #4) and `notes/2026-05-04-curator-to-autorefine-transfer-plan.md` (item A).*

---

#### 1g. Consolidation Pressure (Phase 1 — 7th audit dimension)

**Source:** Hermes Curator prompt (NousResearch/hermes-agent v0.12.0, 2026-04-30) — *"the goal of the skill collection is a library of class-level instructions and experiential knowledge. A collection of hundreds of narrow skills where each one captures one session's specific bug is a failure of the library — not a feature."*

**Problem:** A skill can pass every existing Phase 1 dimension (Gotchas, Voice, Progressive Disclosure, Anti-Railroading, Description Quality, Scripts) and still be the *wrong shape* for a healthy library. Skills bound to a single PR number, codename, or error-string artifact accumulate over time and pollute the catalog with hundreds of narrow near-duplicates that bloat description scans, fragment tribal knowledge, and force every agent that depends on the library to do duplicate work to figure out which narrow skill applies.

Hermes Curator addresses this *after the fact* by archiving and merging skills on a 7-day cadence. AutoRefine should catch the sprawl pressure *at design time*, on the very next mutation loop, before the library accumulates a problem worth a Curator pass.

**Change:** Add a 7th audit dimension to Phase 1.

**Library-shape score contract (consolidation lens):**

| Score | Consolidation pressure criteria | Action implication |
|---|---|---|
| Present | Skill is already at the right umbrella level for its job. SKILL.md describes a class-level workflow with labeled subsections that share a coherent shape; supporting `references/`, `templates/`, or `scripts/` files capture session-specific detail. The skill name reads like a category, not a session artifact. | Keep as-is. No consolidation pressure. |
| Partial | Skill has a focused workflow that could legitimately stand alone, but the audit identifies one or more existing skills (or an obvious latent umbrella) that it would belong inside as a labeled subsection. | Recommend consolidation target before next mutation loop iteration. Ship a `consolidation_candidates[]` field in the audit output. |
| Missing | Skill is bound to a one-session artifact: name contains a PR number, codename, specific error string, customer name, ticket id, or a meta-tag like `audit-`, `triage-`, `salvage-`, `diagnosis-`, `fix-`. Body is narrow enough that a maintainer would write it as a subsection of an umbrella, not a standalone skill. | High pressure to consolidate. The mutation loop should treat this as evidence that the skill itself is the wrong shape — a Phase 7 mutation that "improves" a missing-pressure skill while leaving its scope intact is fixing the wrong thing. |

`consolidation_pressure` measures library shape, not skill quality. A skill can score Missing here while scoring Present on every other dimension — the issue is *that the skill exists as a standalone artifact at all*, not that the artifact is poorly executed.

**Cost:** Higher than other Phase 1 dimensions because it requires library-level context. Approximately 2-3 minutes per audit: the agent must scan the existing skill catalog for prefix clusters, evaluate the candidate skill's name specificity, and weigh the body against the umbrella-vs-narrow framing. For library-scale audits (>50 skills), this dimension dominates the Phase 1 cost budget. Mini mode skips this dimension; Standard runs it; Deep mode runs it twice with different scan strategies for a higher-confidence verdict.

**Observable signals (in priority order):**

1. **Name specificity** — does the skill name contain a session artifact (PR number, codename, error string, ticket id)? Strong evidence of Missing.
2. **Prefix-cluster membership** — are there 2+ existing skills sharing the candidate's first word or domain keyword? Strong evidence of Partial or Missing depending on cluster size.
3. **Body breadth** — does SKILL.md address one narrow workflow or a class of workflows? Narrow body = pressure toward Partial or Missing.
4. **Body structure** — many short labeled subsections (umbrella shape) vs one focused workflow (subsection shape)?
5. **Reusability boundary** — does the skill's core workflow generalize across users / contexts / sessions, or is it bound to one situation?
6. **Existing umbrella opportunity** — does the library already contain a skill that this one would naturally fit under as a labeled subsection?

**Required indicators for Missing (skill should not exist standalone):**

At least TWO of:
- Name contains a session artifact (PR#, codename, ticket id, error string, customer name)
- Body is narrow enough that a maintainer would write it as a subsection
- The library already contains a skill this one would fit under
- The skill's core workflow does not generalize beyond the originating session

**Exclusion criteria (do NOT score Missing when):**

- The skill is a `pipeline` pattern with multi-stage state and explicit handoff artifacts (per Section 1d). Pipelines need their own scope by design; consolidation pressure for a pipeline skill should top out at Partial.
- The skill is the only member of its domain in the library (no umbrella to merge into; no consolidation candidate to recommend).
- The skill is intentionally session-scoped per the campaign goal (e.g., a regression-test scaffold for a specific incident — explicitly out of scope for the library).

**Pattern interaction (per Section 1d):**

| Pattern (1d) | Consolidation pressure default | Notes |
|---|---|---|
| Tool Wrapper | High base pressure — narrow tool scope encourages many siblings (`hermes-config-*`, `gateway-*`) | Strong umbrella opportunities |
| Generator | Medium base pressure — templates can cluster by domain | Often consolidate under a domain umbrella with template subsections |
| Reviewer | Medium base pressure — checklist skills cluster by review type | Often consolidate by review category |
| Inversion | Low base pressure — interview gates are usually intentionally scoped | Rarely consolidates |
| Pipeline | Lowest base pressure — multi-stage workflows are designed for their scope | Consolidation top-bound at Partial |

This base-by-pattern is a calibration prior, not a hard rule. The audit should still examine name specificity and library context; pattern just shifts where the prior lands.

**Phase 1 dimension schema contract update:**

The canonical Phase 1 audit order becomes:

| Order | Canonical key | Score type | Allowed range |
|---|---|---|---|
| 1 | `gotchas` | `ordinal_presence_with_na` | `present`, `partial`, `missing`, `n/a` |
| 2 | `voice` | `ordinal_presence` | `present`, `partial`, `missing` |
| 3 | `progressive_disclosure` | `ordinal_presence` | `present`, `partial`, `missing` |
| 4 | `anti_railroading` | `ordinal_presence` | `present`, `partial`, `missing` |
| 5 | `description_quality` | `ordinal_presence` | `present`, `partial`, `missing` |
| 6 | `scripts` | `ordinal_presence_with_na` | `present`, `partial`, `missing`, `n/a` |
| **7** | **`consolidation_pressure`** | **`ordinal_presence`** | **`present`, `partial`, `missing`** |

`consolidation_pressure` is always scored and never `n/a`. Library-of-one (no other skills exist yet) is a real audit context — score `present` and note "first-skill-in-library; consolidation candidates not yet meaningful." Mini mode skips this dimension entirely (insufficient library context to score reliably).

**Library-context input contract:**

This dimension is the only Phase 1 dimension that needs cross-skill input. The audit needs a `library_context_manifest` describing the candidate's neighbors:

```yaml
library_context_manifest:
  fixture_set_id: <stable id of the library snapshot used for this audit>
  candidate_skill_id: <stable id of the skill under audit>
  candidate_skill_name: <human-readable name>
  candidate_pattern: <one of tool_wrapper | generator | reviewer | inversion | pipeline>
  library_size: <integer count of agent-created skills at audit time>
  prefix_clusters:
    - cluster_prefix: <shared first word or domain keyword>
      members: [<skill_name>, ...]
      cluster_size: <integer>
  adjacent_skills:
    - skill_name: <candidate's nearest neighbor by name distance>
      relevance_signal: <prefix_match | domain_match | semantic_match>
      candidate_belongs_under: <true | false | undetermined>
```

The fixture set is built once at Phase 1 entry and reused across all dimensions in the same run (cost-amortization).

**Audit output schema:**

The Phase 1 audit payload's `dimensions` field gains:

```json
{
  "consolidation_pressure": {
    "score": "missing",
    "score_type": "ordinal_presence",
    "library_context_manifest_ref": "fixtures/library-context-2026-05-04.json",
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
        "evidence": "candidate workflow is one of N labeled subsections this umbrella already maintains",
        "mode_options": [
          "merge_into_existing_umbrella",
          "create_new_umbrella",
          "demote_to_references",
          "demote_to_templates",
          "demote_to_scripts"
        ]
      }
    ],
    "pattern_calibration": {
      "applied_pattern": "tool_wrapper",
      "base_pressure_prior": "high",
      "pattern_calibration_profile_id": "tool_wrapper_consolidation_default"
    }
  }
}
```

The `consolidation_candidates[]` array drives downstream Phase 7 mutation behavior: when present and the candidate's score is Missing, the mutation loop should treat scope-changing mutations (merge into umbrella, demote to support file) as higher-priority than content-changing mutations (tighten voice, add gotchas section). When the candidate's score is Partial, the mutation loop should evaluate scope-changing mutations alongside content-changing ones rather than defaulting to content-changing.

**Calibration fixtures:**

A bundled fixture set `phase1-consolidation-pressure-v1` ships with v4 to anchor judge calibration. Each fixture captures a sketch skill with its library context and the expected score. Minimum 12 fixtures, evenly distributed:

| ID | Sketch | Pattern | Library context | Expected score |
|---|---|---|---|---|
| C1 | `pr-3142-codex-payload-fix` | reviewer | library has `pr-triage-salvage` umbrella + 4 sibling pr-NNNN skills | `missing` |
| C2 | `gateway-telegram-stale-stream-fix` | tool_wrapper | library has 6 `gateway-*` skills, no umbrella | `partial` |
| C3 | `ship` | pipeline | bundled umbrella with rich subsections | `present` |
| C4 | `audit-2026-04-pre-launch-checklist` | reviewer | one-off audit artifact, no library siblings | `missing` |
| C5 | `salvage-issue-15203-minimax-oauth` | tool_wrapper | library has 1 sibling `salvage-*` skill | `missing` |
| C6 | `humanizer` | generator | bundled, no obvious siblings | `present` |
| C7 | `vercel-deploy-precise` | tool_wrapper | bundled, named domain umbrella | `present` |
| C8 | `ollama-anthropic-config-tweaks` | tool_wrapper | library has `ollama-*` cluster of 3 + `anthropic-*` cluster of 4 | `partial` (ambiguous which umbrella) |
| C9 | `mcp-schema-defs-vs-definitions` | tool_wrapper | library has `mcp-*` cluster of 2 | `partial` |
| C10 | `competitor-analysis-anthropic-2026-q2` | reviewer | one competitor skill, no umbrella | `partial` |
| C11 | `python-shutdown-hook-debug-trace` | tool_wrapper | many `python-*` siblings, no umbrella, body is narrow | `missing` |
| C12 | `airtable` | tool_wrapper | bundled, named domain | `present` |

The fixture catalog should be expandable; new fixtures added when boundary cases surface in real campaigns.

**Calibration target:**

In Phase 6 cross-validation (Section 2c), the judge for `consolidation_pressure` should hit:
- TPR ≥ 0.85 on the fixture set's `missing` cases
- TNR ≥ 0.85 on the fixture set's `present` cases
- Partial cases are diagnostic only (no TPR/TNR target — partial is the ambiguous middle by definition)

**Mutation-loop integration (Phase 7):**

Three integration points in the existing Phase 7 step ordering:

1. **Mutation hypothesis generation (Phase 7 step 1):** When the candidate's `consolidation_pressure` is Missing, mutation hypotheses should prioritize scope-changing mutations (merge / demote / split) over content-changing mutations. The hypothesis generator reads `consolidation_candidates[]` from the Phase 1 audit output as candidate target umbrellas.

2. **Mutation intent declaration (per the transfer plan's #13):** Every mutation API call should carry a `mutation_type` enum that includes scope-changing values: `merge_into_umbrella`, `demote_to_references`, `demote_to_templates`, `demote_to_scripts`, `split_into_umbrella_plus_subsection`, alongside the existing content-changing values.

3. **Discard autopsy taxonomy (per v3 P1 status):** The `wrong_target` discard reason should distinguish between "wrong content target" and "wrong scope target" — the former is "you tried to fix the gotchas section but the gotchas section was fine," the latter is "you tightened the voice on a skill that should not exist standalone."

**Eval interaction (Phase 7 mutation scoring):**

When a scope-changing mutation is applied (e.g., the skill is demoted to a `references/` file under an umbrella), the eval result for the *original* skill ID should be marked `superseded_by: <umbrella_skill_id>` rather than `pass` or `fail`. The shared-input comparison preflight (per Section 4b) should treat `superseded_by` as a valid intermediate state rather than rejecting the comparison.

**Boundary cases:**

- **First skill in a fresh library:** Score `present` and note "first-skill-in-library." No consolidation candidates possible until library has 2+ peers.
- **Pipeline-pattern skill with sibling pipelines:** Each pipeline owns its scope by design; do not flag Missing solely because pipeline siblings exist with shared name prefixes.
- **Skill explicitly scoped to a session by campaign goal:** When the campaign declares the skill is intentionally session-scoped (e.g., a regression scaffold for incident X), exclusion criterion fires; score the skill `present` and emit a note that the campaign's scope-discipline is the authoritative scoring input.
- **Library where every skill scores Missing:** This is a signal the *library design* is wrong, not that every individual skill is wrong. Flag it as a library-level finding in the run report and recommend an out-of-band library restructuring pass before continuing per-skill mutations.
- **Candidate umbrella does not yet exist:** When the audit identifies that "skill X belongs as a section under umbrella Y" but Y is not yet a real skill, score Partial (umbrella opportunity exists but hasn't materialized) and emit `consolidation_mode: create_new_umbrella` in the candidates list so the mutation loop knows to create Y first.

**Cost accounting:**

For a Standard-mode audit on a 50-skill library:

- One library-context-manifest construction: ~30 seconds (one read of all 50 SKILL.md frontmatters)
- One per-skill consolidation pressure audit: ~2 minutes (LLM evaluates name + body + library context)
- Total: ~30s amortized + 2 minutes per skill

For a single-skill audit, the manifest construction is the dominant cost. For a campaign that audits a library of N skills, the manifest is built once and reused.

**Mini mode behavior:**

Skip this dimension entirely. Note in the audit output: `consolidation_pressure: skipped (Mini mode — insufficient library context to score)`. Mini mode is for Quick Start campaigns where library hygiene is out of scope.

**Deep mode behavior:**

Run the audit twice with different scan strategies:

1. **Pass A — name-centric:** Score based on name specificity, prefix-cluster signals, and existing umbrellas (faster).
2. **Pass B — body-centric:** Score based on body breadth, structure shape, and reusability boundary (slower, more semantic).

Then reconcile (per the verdict-reconciler pattern from transfer plan #2):
- Both Present → Present
- Both Missing → Missing
- Disagreement → Partial, with both passes' evidence captured for human review

Deep mode TPR/TNR target: ≥ 0.92 on calibration fixtures.

**State and serialization:**

The dimension's score travels as a regular ordinal-presence score in the existing Phase 1 audit payload (per Section 1f's schema contract). The `consolidation_candidates[]` array, `library_context_manifest_ref`, and `pattern_calibration` block live nested under the `consolidation_pressure` key inside the audit payload. Persisted to `state.json.phase1_context.consolidation_pressure_audit` so downstream phases can read the candidates list without reopening Phase 1 artifacts.

When Phase 7 emits a structured `phase7_mutation_to_test_launch` payload (per Section 2e), it must include `consolidation_pressure_audit_ref` so the test phase can reopen the consolidation candidates list during mutation result interpretation.

---

## Resolutions (2026-05-04 — merged into locked v4 design)

All 5 open questions resolved by user on 2026-05-04. Section 1g merged into `dev/docs/design-autorefine-v4-skill-eval-platform.md` between Sections 1f and 2. This file is preserved as the historical RFC; the locked design is the authoritative version going forward.

| # | Question | Decision | Notes |
|---|---|---|---|
| 1 | Mini mode behavior | **(A) Skip cleanly** | Audit payload emits `skipped (Mini mode — insufficient library context)`. Mini's contract is "library hygiene out of scope" — keep it clean. |
| 2 | Phase 7 ranking for Partial cases | **(B) Interleave scope + content mutations** | Eval scores arbitrate. Falls back to pattern-conditional ordering only if Phase 7 cost balloons in real campaigns. |
| 3 | Multiple umbrella candidates | **(B) Allow multiple, ranked** | Each candidate carries `confidence_rank`. Emit top-level `consolidation_ambiguity_flag: true` when top two candidates' priors are within 20% of each other. |
| 4 | Library-of-one subtlety | **(A) Score Present + first-in-library note** | Add `library_size_at_audit: <int>` field. Force re-audit when library grows from <3 peers to ≥3 peers (numeric trigger, reuses the Q5 invalidation hook). |
| 5 | Manifest persistence | **(C) Persist with mutation-driven invalidation** | Persist by default. Invalidate on any Phase 7 emit whose `mutation_type` is in the scope-changing enum. Stamp manifest with `built_after_mutation_id: <id>` as a stale-read safety net. |

**Cross-cutting note:** Q4 and Q5 share infrastructure. The manifest invalidation hook from Q5 is the same mechanism that triggers Q4's re-audit when library size crosses 3 peers. Build once, pay for both.

---

## Implementation checklist

Before this section can be merged into the locked v4 design:

- [x] Resolve open questions 1-5 above (2026-05-04 — see "Resolutions" section above)
- [ ] Add the calibration fixture set `phase1-consolidation-pressure-v1` with the 12 sketch fixtures
- [ ] Update Section 1f's dimension order table to include order=7 for `consolidation_pressure`
- [ ] Update Section 2c (Cross-Validation for Evals) to define the cross-validation strategy for this dimension
- [ ] Update Section 7 (or wherever Mini/Standard/Deep mode definitions live) to document this dimension's mode behavior
- [ ] Confirm that Section 1d (Skill Pattern Classification) and this section don't conflict on pattern-aware scoring — the `pattern_calibration_profile_id` keys should not collide
- [ ] Update the Phase 1 cost projections in v4 design Section "Cost & Time" (if such a section exists) to include this dimension's amortized + per-skill cost
- [ ] Add this dimension to the Phase 1 prompt template in `references.md`
- [ ] Spec the `library_context_manifest` schema in `references.md` as a reusable contract (other dimensions may want to read it later)
- [ ] Define the structured Phase 1 audit output's top-level `consolidation_pressure_audit_summary` aggregator field shape (similar to `aggregated_tpr_tnr_summary` in Section 2c)

---

## Why ship this in v4.0 and not v4.1

Three reasons:

1. **It's load-bearing for the public positioning.** The eval-before-prune essay (`notes/2026-05-04-eval-before-prune-essay.md`) leans on AutoRefine measuring library health, not just per-skill quality. Without this dimension, that claim is aspirational rather than backed.

2. **It changes mutation hypothesis ordering.** Skipping this dimension means Phase 7 mutations may "polish" skills that should not exist at all. Catching that at design time is much cheaper than discovering it after a 20-iteration mutation loop.

3. **The cost is amortized.** The library-context manifest is a one-time cost per Phase 1 entry. Other future dimensions (composability, cross-skill coupling) will reuse it. Building the manifest infrastructure once for this dimension pays for the next two.

The risk is mode-behavior calibration: Mini mode skipping this dimension cleanly is an explicit non-answer, and Standard mode's 2-3-minute-per-skill cost is substantial. Profile against existing dimensions (especially `description_quality`'s production routing replay) before declaring 2-3 minutes acceptable.
