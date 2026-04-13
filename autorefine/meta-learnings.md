# AutoRefine Meta-Learnings

Manually curated cross-campaign rules for improving `SKILL.md`-based agents.

Read this file at Phase 7 startup alongside `preferences.md` and `research-intake.md`. Promote entries here only after human review. This file is for reusable rules, not raw session notes.

## Curation Rules

- Manual promotion only. Do not auto-append from Session Close without explicit human approval.
- One entry per reusable rule.
- Every entry must state where it applies and where it does not.
- Every entry must cite concrete supporting evidence. Prefer at least two supporting cases before marking an entry `active`.
- Use `superseded` or `rejected` instead of deleting old entries so weak agents can see why a rule stopped being trusted.
- Cross-skill transfer happens through reusable rules and patterns only. Do not claim direct score comparability across different skills.

## Entry Template

### ML-<YYYY-MM-DD>-<NNN> | <short title>
- entry_type: `meta_learning_rule`
- status: `candidate | active | superseded | rejected`
- learning: <one-sentence reusable insight>
- applicability_conditions:
  - skill_patterns: [`tool_wrapper`, `generator`, `reviewer`, `inversion`, `pipeline`]
  - agent_targets: [`claude_code`, `rovodev`, `any_skill_md`]
  - scenario_targets: [`individual`, `production`]
  - scope_type: `skill_lineage | pattern_family | ecosystem`
  - scope_ref: <skill id, pattern id, or `any_skill_md`>
  - skill_metadata_keywords: [<optional metadata phrases from skill id/title/summary/tags/path>]
  - objective_keywords: [<optional campaign-objective phrases that must match this run>]
  - when_to_apply: <observable conditions that should be true before using this rule>
  - do_not_apply_when: <known exclusions or counter-signals>
- supporting_evidence:
  - case_id: <campaign or version-comparison id>
    source_kind: `prior_campaign | reference_skill | meta_learning | best_practice`
    source_ref: <path, artifact ref, or URL>
    evidence_locator: <experiment, heading, section, lines, or comparison artifact>
    excerpt_or_metric: <short quote, score delta, or metric>
    why_it_supports: <one-sentence causal link between evidence and the learning>
- confidence: `high | medium | low`
- promotion_basis: <why this insight graduated from a local session learning to a cross-campaign rule>
- precedence: `high | medium | low`
- review_status: `pending | approved | superseded`
- supporting_case_ids: [<case-study ids>]
- derived_from_entry_ids: [<research corpus ids>]
- last_reviewed_at: <ISO timestamp>

## Blank Entry

### ML-<YYYY-MM-DD>-<NNN> | <title>
- entry_type: `meta_learning_rule`
- status: `candidate`
- learning:
- applicability_conditions:
  - skill_patterns: []
  - agent_targets: []
  - scenario_targets: []
  - scope_type:
  - scope_ref:
  - skill_metadata_keywords: []
  - objective_keywords: []
  - when_to_apply:
  - do_not_apply_when:
- supporting_evidence:
  - case_id:
    source_kind:
    source_ref:
    evidence_locator:
    excerpt_or_metric:
    why_it_supports:
- confidence:
- promotion_basis:
- precedence:
- review_status: `pending`
- supporting_case_ids: []
- derived_from_entry_ids: []
- last_reviewed_at:
