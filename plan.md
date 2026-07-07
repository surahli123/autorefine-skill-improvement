# Implementation Plan: AutoRefine Domain Adapter Platform

## Status

Active follow-up plan.

The platform contract portions are already present in the current AutoRefine
runtime docs and tests. Treat this file as the remaining execution roadmap, not
as a proposal to invent the adapter model from scratch.

Derived from:
- [docs/brainstorm-skill-effectiveness-criteria.md](/Users/surahli/Documents/projects/skill-improvement/docs/brainstorm-skill-effectiveness-criteria.md)
- [docs/superpowers/plans/2026-04-15-skill-effectiveness-criteria.md](/Users/surahli/Documents/projects/skill-improvement/docs/superpowers/plans/2026-04-15-skill-effectiveness-criteria.md)
- repo research on SkillForge and darwin-skill
- Anthropic engineering article: [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)

## Overview

AutoRefine currently works best when an LLM judge is a good proxy for quality. That is strong enough for many code- and prose-adjacent skills, but weak for domains like search where the real objective is a domain metric such as ranking quality. The goal of this plan is to generalize AutoRefine by introducing a shared evaluation harness with pluggable domain adapters.

The core product shape is:

`universal floor + domain adapter + common trust loop`

This means AutoRefine keeps one shared pipeline for workspaces, contracts, holdouts, mutation, and trust, while each domain adapter defines the primary oracle that actually decides quality.

## Current Implementation Snapshot

Already implemented in the current repo:

- generic domain adapter contract in `autorefine/references.md`
- adapter state fields and checkpoint restore wiring in `autorefine/SKILL.md`
- adapter-aware Gulf 2 and Gulf 3 routing in `autorefine/references/gulf2-specification.md` and `autorefine/references/gulf3-generalization.md`
- run-scoped `experiment-contract.json` semantics
- search adapter contract vocabulary, including `search_retrieval_v1`, `doc_id`, `grade`, and `NDCG@5`

Still remaining:

- execute a real search adapter dogfood run with labeled golden data
- add or wire the first metric runner path that proves the adapter contract end-to-end
- update user-facing docs only after dogfood validates the shape

## Problem Statement

Current AutoRefine can optimize tasks where output quality is meaningfully judgeable by LLM-based evaluation. It does not yet have a first-class substrate for domain metrics. As a result:

- search skills cannot be improved on true retrieval quality
- extraction and classification skills cannot rely on exact task metrics
- workflow skills lack explicit completion or side-effect oracles
- creative and review-oriented skills are forced into the same scoring shape as factual tasks

The problem is not "we need one better universal evaluator." The problem is "we need one common harness that can host different primary evaluators safely."

## Goals

- Add a pluggable adapter interface for domain-specific evaluation.
- Preserve the existing AutoRefine trust model: holdout remains evaluation-only and human review remains authoritative for subjective domains.
- Make `search` the first reference adapter.
- Generalize next to `code`, `structured extraction/classification`, and `prose/review`.
- Keep current LLM-judge-only behavior as the fallback when no adapter exists.

## Non-Goals

- Building a domain-contextualized skill creator in this phase.
- Adding production-runtime A/B testing, online learning, or traffic instrumentation.
- Solving multi-skill interference or causal attribution across a full agent stack.
- Replacing human error analysis with full automation.

## Architecture Decisions

- **Shared platform, pluggable oracle.** AutoRefine owns the workflow, adapter owns the primary metric.
- **Primary metric decides quality.** Secondary LLM judges diagnose quality and guard regressions, but do not replace the adapter-specific oracle.
- **Holdout decides trust.** Promotion requires held-out evidence; dev gains alone are insufficient.
- **Universal floor stays cross-domain.** Activation quality, robustness, recovery, efficiency, and boundary discipline remain common checks across all skills.
- **Contract examples remain the common seed format.** Adapters consume the same contract and fixture pipeline, then add their own scoring logic.
- **Backwards compatibility matters.** If no adapter is configured, AutoRefine should degrade to the current LLM-judge path rather than failing closed.
- **Generator and evaluator stay separate.** The mutation actor should not be the final judge of its own work. AutoRefine should preserve an external evaluator surface for both objective and subjective adapters.
- **Use explicit experiment contracts.** Before a mutation cycle or bounded chunk of work, the system should define what success looks like in machine-readable form rather than letting the generator improvise the target mid-run.
- **Prefer file-based handoffs over conversational continuity.** Long-running adapter workflows should persist enough structured state to survive context resets or session changes cleanly.
- **Critical criteria can hard-fail.** For adapter-specific trust rules, any critical dimension below threshold should be able to fail the candidate even if aggregate scores look acceptable.

## Adapter Contract

Each adapter must define:

- `skill_family`
- `input_schema`
- `output_schema`
- `runner`
- `normalizer`
- `primary_metric`
- `secondary_metrics`
- `failure_taxonomy`
- `gold_source`
- `trust_rule`

### Minimal semantics

- **Runner** executes the skill on a test input.
- **Normalizer** converts the output into a stable scoring shape.
- **Primary metric** is the domain truth function.
- **Secondary metrics** are behavioral or presentation checks.
- **Failure taxonomy** explains why the run failed.
- **Gold source** describes what evidence the adapter needs: tests, labels, reference outputs, or human review.
- **Trust rule** defines how dev, holdout, and human review combine.

## Default Workspace Layout

Use one stable adapter surface under the existing workspace:

- `[workspace]/domain-eval/config.json` — adapter identity, trust rule, metric configuration, and artifact pointers
- `[workspace]/domain-eval/golden-set.jsonl` — optional labeled evaluation set when the domain requires one
- `[workspace]/domain-eval/fixtures/` — optional adapter-specific fixture material
- `[workspace]/domain-eval/metric.py` — optional metric implementation when a built-in metric is not enough

The shared pipeline should persist only the selected adapter identity and config path in `state.json`. Adapter-specific data stays inside `domain-eval/`.

## Resolved Decisions

- **Adapter resolution:** pattern classification may suggest an adapter, but activation requires explicit author confirmation. Suggestions are autocomplete, not autopilot.
- **Incomplete adapter data:** if an adapter is confirmed but required gold data is missing, AutoRefine must stop and ask the user to either provide the missing assets or explicitly downgrade to the fallback LLM-judge-only path. No silent downgrade.
- **Second adapter after search:** `code` is the second implementation. It uses a materially different primary oracle than search and is the best test that the abstraction is real.
- **Minimal search gold-set row:** each row should include `query`, `doc_id`, `grade`, and any stable ranking key needed for replay. Keep the first version minimal and ranking-oriented.
- **Long-running runs must be restart-safe:** adapter workflows should assume that compaction alone may be insufficient and must preserve state through explicit artifacts.
- **Campaign orchestrator implementation language:** implement V1 in Python because the current shipped AutoRefine helper surface is Python/pytest-first and this phase is still stabilizing manifest, graph, lock, and DRY-audit semantics. Rust remains attractive later for a polished standalone binary with stronger compile-time guarantees and safer concurrency primitives, but adopting it now would add a new build/test surface before the orchestration contract is proven. TypeScript/Node remains useful if the orchestrator later needs to live closer to skill-package or resolver tooling, but it would add another runtime style to the current Python-centered bundle.

## Initial Adapter Families

### 1. Search / Retrieval

Primary oracle:
- `NDCG@k`
- `Recall@k`
- `MRR` or `Success@k`

Secondary diagnostics:
- explanation quality
- clarity of clarifying questions
- scope discipline
- response formatting

Why first:
- this is the clearest gap raised by Search team feedback
- it is the hardest counterexample to the current LLM-judge-centric model
- it will force the right abstractions for output normalization and metric wiring

### 2. Code

Primary oracle:
- test pass rate
- static checks
- runtime contract checks where applicable

Secondary diagnostics:
- clarity
- overreach
- maintainability heuristics

### 3. Structured Extraction / Classification

Primary oracle:
- exact match
- accuracy
- precision / recall / F1
- calibration where relevant

Secondary diagnostics:
- explanation quality
- boundary handling

### 4. Prose / Review

Primary oracle:
- contract-example success rate
- human confirmation

Secondary diagnostics:
- LLM-judge quality checks
- style and boundary discipline

## Dependency Graph

Adapter contract + workspace schema
-> phase routing + state persistence
-> scoring engine integration
-> search adapter reference implementation
-> adapter generalization to other families
-> dashboard + docs + rollout

## Task List

### Session Close: PR #37 Live Trace Capture

- [x] Review and merge useful parts from `/Users/surahli/.codex/worktrees/skill-improvement-v4-1-trust-alignment`
- [x] Run code review, TDD test review, security review, and architecture review using the requested skill workflow
- [x] Fix confirmed review findings in the Gulf 1 recorder/converter path
- [x] Open PR #37, mark it ready for review, resolve `main` merge conflicts, and verify GitHub reports `mergeStateStatus: CLEAN`
- [ ] After PR #37 merges, run one live recorder smoke test against a non-production local mock or explicitly approved API session before relying on real captured traces
- [ ] Decide whether the generated search-adapter helper files should be promoted into PR scope or kept for a separate dogfood branch

### Phase 1: Platform Contract

- [x] Task 1: Define the adapter specification in `references.md`
- [x] Task 2: Add adapter-related state and workspace paths to `state.json` schema
- [x] Task 3: Define fallback behavior for skills without adapters

### Checkpoint: Platform Contract

- [x] Adapter interface is explicit and minimal
- [x] No task-specific logic is hardcoded into the shared harness
- [x] Existing LLM-judge-only workflows still have a valid path

### Phase 2: Pipeline Integration

- [x] Task 4: Route Phase 0.5 / Phase 4 / Phase 5 / Phase 7 to read adapter configuration when present
- [x] Task 5: Separate primary-metric scoring from secondary judge scoring in Phase 7
- [x] Task 6: Update Session Close and trust reporting to surface adapter metrics distinctly from LLM-judge scores
- [x] Task 6b: Add explicit experiment-contract artifacts so mutation/evaluation loops agree on "done" before scoring

### Checkpoint: Pipeline Integration

- [x] The scoring breakdown can represent both adapter and judge components
- [x] Holdout remains evaluation-only
- [x] Promotion logic uses adapter-aware trust rules
- [x] Mutation and evaluation stages read the same explicit contract for the current run

### Phase 3: Search Adapter Reference Implementation

- [x] Task 7: Define a canonical search output contract with stable result identifiers
- [x] Task 8: Add a search metric runner using labeled ranked-result data
- [x] Task 8a: Add a deterministic synthetic silver-set builder for early search dogfood when no human golden set exists
- [ ] Task 9: Add search-specific failure taxonomy and reporting
  - [x] Emit per-query metric evidence, missing relevant `doc_id`s, and judge-vs-metric false-pass / false-fail diagnostics
  - [ ] Add explicit search failure-bucket classification (`missed_relevant_results`, `poor_ranking`, `irrelevant_top_results`, `over_filtering`, `explanation_mismatch`) to the metric report after the first reviewed dogfood dataset

### Checkpoint: Search Adapter

- [x] Search quality can be scored on a real ranking metric instead of LLM preference alone
- [x] LLM judges remain secondary diagnostics, not the primary gate
- [ ] Holdout evaluation reports both metric gain and behavioral regressions
  - [ ] Promote a reviewed subset of synthetic silver rows to `gold_reviewed` before treating it as holdout-grade data

### Phase 3b: Campaign Orchestrator V1

- [x] Task 9b: Add a Phase 7-only campaign manifest and planning runner for multiple prepared skill workspaces
  - [x] Manifest records `skill_id`, `skill_path`, `workspace_path`, `depends_on`, `cluster_id`, `phase7_command`, and `result_refs`
  - [x] Preflight rejects shared mutable paths, including duplicate skill paths, workspace paths, `state.json`, holdout refs, and result artifacts
  - [x] Scheduler runs independent skills in parallel, dependency-linked skills in topological order, and shared-cluster skills sequentially under one group lock
  - [x] DRY/adjacency audit classifies overlapping skills as report-only `merge_candidate` or `parametric_parent_candidate` instead of rewriting them automatically
  - [x] Gulf 1 / Gulf 2 / Gulf 3 analysis packets read skill content and produce report-only recommendations to combine skills, extract a parametric parent, improve separate skills, or keep skills separate
  - [x] Add `prepare-gulf-gate-pack.py` as an explicit advanced utility for adapter-backed deterministic Gulf 1 / Gulf 2 preauthorization; keep it outside the default campaign workflow until real workspace runs prove the flow

### Checkpoint: Campaign Orchestrator

- [x] V1 is report/planning-first and does not execute Phase 7 commands by default
- [x] Coupled skills are not treated as parallel-safe until shared mutable surfaces are removed
- [x] Language choice is documented: Python for V1 contract stabilization, Rust or TypeScript only after the workflow proves useful
- [x] Campaign output includes human-gated Gulf work orders instead of claiming automatic Gulf completion

### Phase 4: Generalize to Other Families

- [ ] Task 10: Add `code` adapter support using tests and static checks as the primary oracle
- [ ] Task 11: Add `structured extraction/classification` adapter support
- [ ] Task 12: Add `prose/review` adapter support with human-confirmed contract-based trust rules

### Checkpoint: Generalization

- [ ] Four adapter families work under one common protocol
- [ ] No adapter requires bespoke phase logic outside the defined interface
- [ ] The fallback path remains simpler than the adapter path for unsupported skills

### Phase 5: UX, Docs, and Dogfooding

- [ ] Task 13: Update dashboard to distinguish adapter metrics, secondary judges, and final trust
- [ ] Task 14: Update `quickstart.md`, `methodology.md`, and `trust-model.md` to explain the adapter model
- [ ] Task 15: Dogfood the platform on one search skill and one non-search skill to validate abstraction quality

### Checkpoint: Complete

- [ ] Adapter model is documented
- [ ] Search adapter is proven on real domain data
- [ ] At least one non-search adapter validates the generalization
- [ ] Trust reporting stays understandable to users

## Task Details

## Task 1: Define Adapter Specification

**Description:** Add a dedicated adapter spec to `autorefine/references.md` that defines the required fields, lifecycle hooks, and scoring semantics for all domain-specific evaluators.

**Acceptance criteria:**
- [ ] The spec defines required fields for runner, normalizer, primary metric, secondary metrics, gold source, and trust rule
- [ ] The spec explains fallback behavior when no adapter is available
- [ ] The spec is generic enough to support search, code, extraction, and prose without domain-specific branching

**Verification:**
- [ ] Manual read for clarity and completeness
- [ ] Cross-check all later plan tasks against the same field names

**Dependencies:** None

**Files likely touched:**
- `autorefine/references.md`

**Estimated scope:** Small

## Task 2: Add Adapter State + Workspace Paths

**Description:** Extend workspace schemas so the pipeline can persist adapter identity, config paths, gold-source references, and trust settings without inventing per-domain ad hoc state.

**Acceptance criteria:**
- [ ] `state.json` schema includes adapter selection and config references
- [ ] Workspace layout has a stable adapter/config location
- [ ] Resume flows can restore adapter state without recomputing it

**Verification:**
- [ ] Schema fields are referenced consistently across all instructions
- [ ] Resume and checkpoint instructions mention adapter state explicitly

**Dependencies:** Task 1

**Files likely touched:**
- `autorefine/SKILL.md`
- `autorefine/references.md`

**Estimated scope:** Small

## Task 4: Phase Routing + Scoring Separation

**Description:** Update pipeline routing so adapter-aware skills invoke primary-metric logic at the right stages while preserving existing judge-writing and trust surfaces.

**Acceptance criteria:**
- [ ] Phase 5 can emit adapter-aware evaluation logic
- [ ] Phase 7 stores primary-metric and secondary-judge components separately
- [ ] Session Close reports adapter outcomes distinctly from judge outcomes
- [ ] The mutation actor cannot self-certify promotion without the external evaluator path

**Verification:**
- [ ] Manual review of phase routing paths
- [ ] Schema and dashboard fields align with stored scoring payloads

**Dependencies:** Tasks 1-3

**Files likely touched:**
- `autorefine/SKILL.md`
- `autorefine/references/gulf2-specification.md`
- `autorefine/references/gulf3-generalization.md`
- `autorefine/dashboard.html`

**Estimated scope:** Medium

## Task 6b: Add Experiment-Contract Artifacts

**Description:** Introduce a lightweight contract artifact for each bounded mutation/evaluation run so the generator and evaluator operate against the same explicit definition of success.

**Acceptance criteria:**
- [ ] Each run has a machine-readable contract that names the target behavior, scoring surface, and fail conditions
- [ ] Mutation and evaluation stages consume the same contract artifact
- [ ] Resume/checkpoint flows restore the active contract without reconstructing it from chat history

**Verification:**
- [ ] Manual review confirms the contract contains the required fields
- [ ] Checkpoint instructions reference the contract artifact explicitly

**Dependencies:** Tasks 1-6

**Files likely touched:**
- `autorefine/SKILL.md`
- `autorefine/references.md`
- `autorefine/references/gulf3-generalization.md`

**Estimated scope:** Small

## Task 7: Search Adapter Reference Implementation

**Description:** Implement the first concrete adapter for search/retrieval so AutoRefine can optimize real search quality instead of only output phrasing.

**Acceptance criteria:**
- [ ] Search outputs normalize into a ranked-result schema with stable identifiers
- [ ] A held-out labeled set can compute ranking metrics
- [ ] Search adapter results appear in Phase 7 and Session Close reporting

**Verification:**
- [ ] Search metric improves or regresses numerically on a controlled fixture set
- [ ] LLM judges do not override a failing primary search metric
- [ ] Holdout reporting is preserved

**Dependencies:** Tasks 1-6

**Files likely touched:**
- `autorefine/references.md`
- `autorefine/references/gulf2-specification.md`
- `autorefine/references/gulf3-generalization.md`
- `autorefine/dashboard.html`

**Estimated scope:** Medium

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Over-abstracting before a real adapter exists | High | Treat `search` as the reference implementation and only generalize what survives that build |
| LLM judges overpower true domain metrics | High | Make adapter primary metric the quality gate and relegate judges to diagnostics + regression checks |
| Adapter sprawl creates custom phase logic everywhere | High | Keep the interface minimal and require all adapters to fit the same lifecycle hooks |
| Users do not have gold data for many domains | Medium | Keep adapter support optional and preserve the current fallback path |
| Metric gaming on dev split | High | Preserve heldout evaluation-only policy and human review before promotion |
| Dashboard/reporting becomes too complex | Medium | Render adapter score, judge score, and trust gate as separate explicit surfaces |

## Open Questions

- Which fields beyond `query`, `doc_id`, and `grade` are necessary in the first search gold set to support replay without overfitting the schema?
- Should the first built-in adapter metrics live entirely in instruction logic, or should AutoRefine standardize on `metric.py` as the default execution surface?

## Recommended Execution Order

1. Keep the stale prompt-consistency tests aligned with the current `autorefine/references/gulf*.md` layout.
2. Build the first real `search_retrieval_v1` dogfood fixture set with stable `query`, `doc_id`, and `grade` labels.
3. Add the smallest metric runner path needed to compute `NDCG@5` and `recall@5` from the golden set.
4. Run one end-to-end adapter-aware Phase 7 / Session Close dry run and inspect whether primary metrics remain separate from secondary judges.
5. Generalize only after `search` proves the abstraction.

## Success Criteria

- Search team can use AutoRefine to optimize search skills on real search-quality metrics.
- Non-search skills still work without requiring domain adapters.
- AutoRefine preserves its current trust-first philosophy while becoming more domain-capable.
- The adapter model is simple enough that adding a second domain feels incremental rather than architectural.

## 2026-07-06 U8 Removal Decision

- Deleted the campaign/gate-pack orchestrator family from the public AutoRefine bundle per owner decision Q2a; recovery remains available through git history.
