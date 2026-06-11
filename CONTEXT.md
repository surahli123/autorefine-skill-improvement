# AutoRefine Context

AutoRefine improves skill workflows through staged Gulf review, adapter-aware evaluation, and campaign planning. This context names the domain concepts that should stay stable across architecture reviews, code changes, and handoffs.

## Language

**AutoRefine**:
The staged skill-improvement workflow that evaluates, mutates, and promotes skill changes through Gulf review and Phase 7 campaigns.
_Avoid_: optimizer, evaluator, skill runner

**Gulf Review**:
The staged review path that moves a workspace from comprehension through specification into generalization.
_Avoid_: gate sequence, approval process

**Gulf 1**:
The comprehension stage where a workspace establishes intent, failure modes, and human-reviewed understanding.
_Avoid_: first gate, understanding check

**Gulf 2**:
The specification stage where evaluation surfaces and judge expectations are approved.
_Avoid_: second gate, spec approval

**Gulf 3**:
The generalization stage where Phase 7 work is planned or run after required Gulf evidence is ready.
_Avoid_: final gate, execution stage

**Phase 7**:
The mutation and evaluation phase for improving a prepared skill workspace.
_Avoid_: optimization phase, campaign execution

**Campaign Readiness**:
The workspace state in which a campaign target can safely enter each Gulf stage.
_Avoid_: stage status, execution readiness, ready flag

**Campaign Planning**:
The report-building and work-packet planning layer that turns campaign manifests, targets, and readiness into scheduled Gulf work.
_Avoid_: campaign script logic, orchestration blob

**Campaign Target**:
A single skill or candidate workspace that the campaign planner can schedule through Gulf stages.
_Avoid_: job, task, unit of work

**Gate Pack**:
The preauthorized Gulf 1 and Gulf 2 artifact set used to make a workspace eligible for full Phase 7 planning.
_Avoid_: approval bundle, gate output

**Gate Pack Module**:
The library interface that prepares campaign and workspace Gate Pack artifacts without depending on the campaign CLI script.
_Avoid_: prepare script, dynamic campaign import

**Adapter State**:
The normalized view of a workspace's configured adapter id, domain-eval config, eval script, and golden set.
_Avoid_: config state, eval state

**Adapter Evidence**:
Confirmed domain-eval assets that bind an adapter id, metric config, eval script, and golden set to a workspace.
_Avoid_: eval config, metric files

**Candidate Evidence**:
Merged adapter evidence for a candidate workspace built from compatible source skill workspaces.
_Avoid_: combined evidence, merged eval files

**Candidate Workspace**:
A campaign workspace representing a combine or parametric-parent candidate derived from multiple source skills.
_Avoid_: merged workspace, generated workspace

**Single-Skill Workspace**:
A campaign workspace representing one source skill improved separately.
_Avoid_: original workspace, individual target

**Trust Gate**:
The Session Close holdout decision that authoritatively determines promote, review-required, or block.
_Avoid_: final score, promotion flag

**Golden Set**:
The adapter-specific labeled JSONL examples used by the primary domain metric.
_Avoid_: fixtures, examples, eval rows

**Gulf Trace Record**:
The JSONL capture of one proxied model turn, including scrubbed messages, response text, tool calls, optional model, and optional error.
_Avoid_: proxy log line, request dump

**Gulf Trace Recorder**:
The local HTTP proxy runtime that forwards provider traffic and writes Gulf Trace Records.
_Avoid_: parser module, trace schema

**Preference Signal**:
A normalized research-corpus payload that captures user style or mutation preferences inferred from override evidence.
_Avoid_: style note, preference row

**Override Scan**:
A mid-session scan of human overrides across experiment rows used to derive Preference Signals.
_Avoid_: feedback list, user edits summary

**Decision Contract**:
The machine-readable AutoRefine routing output used by validation and resume checks. It must be a single JSON object with `schema_version`, `scenario_family`, `required_action`, `phase`, `gulf_stage`, `allowed_reads`, `allowed_writes`, `prohibited_actions`, `evidence_required`, and `stop_reason`.
_Avoid_: routing blob, status JSON

**Decision Contract Quick Reference**:
The table in `autorefine/SKILL.md` that maps common validation/routing situations to exact Decision Contract fields.
_Avoid_: prompt patch, candidate cheat sheet

**Mutation Split Policy**:
The Phase 7 rule that blocks mutation-time access to `adversarial_holdout` and reserves holdout access for Session Close.
_Avoid_: holdout preference, eval split hint

## Relationships

- **AutoRefine** uses **Gulf Review** to prepare a workspace for **Phase 7**.
- **Gulf Review** proceeds through **Gulf 1**, **Gulf 2**, and **Gulf 3**.
- A **Campaign Target** is either a **Single-Skill Workspace** or a **Candidate Workspace**.
- **Adapter State** normalizes the configured **Adapter Evidence** for a workspace.
- **Adapter Evidence** can produce one **Gate Pack**.
- **Candidate Evidence** is produced only from compatible source **Adapter Evidence**.
- A **Gate Pack** contributes to **Campaign Readiness** for Gulf 3.
- **Campaign Readiness** is consumed by the campaign planner when scheduling targets.
- **Campaign Readiness** covers Gulf 1, Gulf 2, and Gulf 3 together.
- **Campaign Readiness** is reported as one aggregate object with per-Gulf entries.
- **Campaign Readiness** reuses the Gulf stage status words `ready`, `blocked`, `needs_human_gate`, and `complete`; only `overall_status` is derived.
- **Campaign Readiness** derives `overall_status` by blocker-first precedence: `blocked`, then `needs_human_gate`, then `ready`, then `complete`.
- Each **Campaign Readiness** per-Gulf entry carries `blocked_by`, `next_action`, and `trust_level` so callers do not recompute why a stage has its status.
- Each **Campaign Readiness** per-Gulf entry also carries the raw `gate` object used by campaign rendering.
- The read-only **Campaign Readiness** Module lives at `autorefine/lib/campaign_readiness.py`.
- The first **Campaign Readiness** implementation slice includes both the Module and the campaign planner caller refactor.
- **Campaign Readiness** uses typed dataclasses internally and exposes dictionary conversion for campaign planner compatibility.
- **Campaign Readiness** is assessed from the existing campaign target dictionary via `assess_campaign_readiness(target)`.
- **Campaign Readiness** reads workspace state and trust-gate files itself; callers pass only the campaign target.
- The first **Campaign Readiness** implementation slice preserves current campaign planner behavior before adding stricter readiness checks.
- **Campaign Readiness** parity means preserving the current Gulf stage dictionaries exactly.
- **Campaign Readiness** owns the Gulf expected-output constants; campaign scripts may import them from the Module.
- **Campaign Readiness** parity tests use representative cases instead of old/new helper comparison.
- `run-campaign.py` treats **Campaign Readiness** as the source of truth and converts the aggregate object back into the legacy `target["stages"]` dictionaries for planner output.
- **Campaign Planning** lives in `autorefine/lib/campaign_planning.py`; `run-campaign.py` is the CLI and HTML-rendering adapter.
- **Gate Pack Module** lives in `autorefine/lib/gate_pack.py`; `prepare-gulf-gate-pack.py` is the CLI adapter.
- **Gate Pack Module** consumes **Campaign Planning** through a library import, not by dynamically importing `run-campaign.py`.
- A **Trust Gate** can complete or block **Campaign Readiness** regardless of earlier Gulf evidence.
- A **Golden Set** belongs to **Adapter Evidence** and is interpreted through the adapter id.
- **Gulf Trace Recorder** lives in `autorefine/scripts/record.py` and owns HTTP forwarding, provider routing, locks, and file writes.
- **Gulf Trace Record** construction, scrubbing, provider response parsing, streaming accumulation, and chunk-line buffering live in `autorefine/lib/gulf_trace_record.py`.
- `record.py` keeps compatibility wrappers for the old helper names while delegating trace logic to the **Gulf Trace Record** Module.
- **Preference Signal** constants, normalization, Override Scan payload building, and candidate derivation live in `autorefine/lib/preference_signals.py`.
- `research_corpus.py` remains the facade for normalized corpus assembly and re-exports the **Preference Signal** API.
- `style_preferences_loader.py` uses **Preference Signal** normalization directly instead of importing private `research_corpus.py` internals.
- **Decision Contract** output is guided by the **Decision Contract Quick Reference** in `autorefine/SKILL.md`.
- **Decision Contract Quick Reference** lives inside `## Preflight`, after Step 0 and before Step 1, so line-sensitive preflight placeholder sentinels continue to pass.
- **Decision Contract** checkpoint resume uses `gulf_stage: none` when a valid checkpoint has non-empty `next_action` and integrity checks pass; do not derive Gulf stage from the resumed experiment before making that decision.
- **Mutation Split Policy** takes precedence over apply-back scope when one request both asks for holdout access and mentions copying a candidate back to the original skill.

## Recent Session Fixes

- Reframed the Darwin 2.0 + SkillOpt lane as direct evaluation/improvement of the shipped `autorefine/` bundle, not a design-borrowing exercise; `dev/` remains internal experiment/governance material.
- Proved provider connectivity early with a tiny OpenRouter/Qwen smoke (`qwen/qwen3.6-flash`, HTTP `200`, `total_tokens=140`) while preserving the no-secret-printing boundary.
- Ran the first isolated `/tmp` SkillOpt/Darwin experiment; it produced only a narrow copied-`SKILL.md` `High-Risk Action Blacklist` candidate, so apply-back was rejected as too weak.
- Hardened R2 around a structured **Decision Contract** target with split `scenario_prompts.jsonl` and scorer-only `scenario_oracles.jsonl`, deterministic cost preflight, secret scan, and a new decision-contract runner instead of the older prose scorer.
- Ran R2 V4/V5/V5b in `/tmp`: V4 reached `target_validated_ready_for_v5`, while V5/V5b improved broad operational means but produced zero exact primary-oracle improvements, ending at `paused_rethink`.
- Added the supervised decision-contract successor spec after the R2 V4/V5/V5b SkillOpt route produced broad semantic gains but no exact-primary hard-field improvement.
- Established strict split boundaries for supervised decision-contract learning: train-only labels, scorer-only validation/test/adversarial labels, answer-free non-train provider prompts, and fail-closed split-contract checks.
- Ran interface calibration where `interface_enum_table_plus_json_skeleton` stopped at `blocked_weak_target` (`0/4` exact primary), then `few_shot_train_format` reached `target_validated_ready_for_candidate` (`1/4` exact primary, `0.425` family-weighted mean).
- Recovered the subsequent candidate-generation outcome as `candidate_generated_no_test_improvement`: exact-primary stayed `0 -> 0` while family-weighted mean improved `0.0 -> 0.21`, so the lane pivoted away from repeating direct `SKILL.md` candidate generation.
- Created the target-redesign handover and launch contract to focus future work on exact hard fields: `scenario_family`, `required_action`, `phase`, `gulf_stage`, and `stop_reason`.
- Completed the private `/tmp` target-redesign/final-candidate run at `/tmp/autorefine-darwin-skillopt-fresh-candidate-20260609-205445`, ultimately validating a Decision Contract Quick Reference approach under Codex-only gates.
- Added replicated robustness/final-gate validation after overfit concerns: frozen Codex split `16/16`, dev robustness `18/18` x3, regression final gate `24/24` x3, and final gate v2 `16/16` x3.
- Added `autorefine/SKILL.md > Preflight > Decision Contract Quick Reference` as a table, not as the literal `/tmp` candidate bullet block, after review-gated integration.
- Preserved exact Decision Contract values for preflight, workspace initialization, checkpoint resume, contract integrity, adapter integrity, Gulf sequencing, phase routing, mutation split policy, mutation scope guard, Session Close, and ambient learning.
- Moved the Decision Contract Quick Reference inside `## Preflight` after Step 0 because putting it above Preflight broke the line-sensitive `[chosen-workspace]` placeholder sentinel in `autorefine/tests/test_preflight.sh`.
- Verified the integrated repo `autorefine/SKILL.md` with `bash autorefine/tests/test_preflight.sh` (`59/59`), `bash autorefine/tests/test_contract_anchor_integrity.sh` (`29/29`), and Codex repo-integration eval (`frozen 16/16` twice, `final_gate_v2 16/16` twice).
- Preserved the OpenRouter/Qwen boundary: user approval was recorded, but runtime policy denied exporting private workspace-derived skill content and benchmark prompts; current validation is Codex-only plus robustness/final gates.

- Added a read-only **Adapter State** validation module with typed normalized return objects.
- Routed **Gate Pack** preparation through normalized **Adapter Evidence** instead of duplicating config parsing.
- Made strict **Adapter Evidence** validation block missing adapter ids, mismatched state/config adapter ids, unreadable paths, malformed golden rows, and missing required domain-eval fields.
- Made **Candidate Evidence** block incompatible eval script content or scoring config before writing a **Candidate Workspace**.
- Cleared stale adapter state refs before revalidating freshly materialized **Candidate Evidence**.
- Made the gate-pack CLI executable and covered the direct path-style invocation in tests.
- Locked the next **Campaign Readiness** design direction as read-only first: it should report readiness, blocks, and trust state for all Gulf stages without repairing state or artifacts.
- Locked the **Campaign Readiness** return shape as one aggregate object with per-Gulf entries.
- Locked **Campaign Readiness** status vocabulary to the existing per-Gulf stage words, plus derived `overall_status`.
- Locked `overall_status` derivation to blocker-first precedence: `blocked` > `needs_human_gate` > `ready` > `complete`.
- Locked per-Gulf **Campaign Readiness** entries to include `blocked_by`, `next_action`, and `trust_level`.
- Locked per-Gulf **Campaign Readiness** entries to include the raw `gate` object.
- Locked the read-only **Campaign Readiness** Module location to `autorefine/lib/campaign_readiness.py`.
- Locked the first implementation slice to include the `run-campaign.py` caller refactor, so the Module passes the deletion test.
- Locked **Campaign Readiness** implementation shape to typed dataclasses internally, with dict conversion for `run-campaign.py`.
- Locked the public **Campaign Readiness** Interface to accept the existing campaign target dict via `assess_campaign_readiness(target)`.
- Locked `assess_campaign_readiness(target)` to read workspace state and trust-gate files itself.
- Locked the first **Campaign Readiness** implementation slice to parity-first extraction.
- Locked parity surface to preserve current Gulf stage dictionaries exactly.
- Locked Gulf expected-output constants ownership to `campaign_readiness.py`.
- Locked **Campaign Readiness** parity test shape to representative cases.
- Added the read-only **Campaign Readiness** module with typed `CampaignReadiness` and `CampaignReadinessStage` dataclasses.
- Moved Gulf expected-output constants and workspace/trust-gate readiness reads out of `run-campaign.py`.
- Refactored `run-campaign.py` so `build_target_stage_plan` delegates to `assess_campaign_readiness(target).to_stage_dicts()`.
- Covered representative **Campaign Readiness** parity cases: initial no-state planning, quick-start mini Gulf 3, trusted Gulf 3 completion, and invalid `state.json` blocking.
- Extracted **Campaign Planning** from `run-campaign.py` into `autorefine/lib/campaign_planning.py`.
- Kept `run-campaign.py` as the CLI and HTML-rendering adapter while preserving the existing campaign orchestrator tests.
- Extracted **Gate Pack Module** behavior into `autorefine/lib/gate_pack.py`.
- Removed the dynamic `run-campaign.py` import dependency from Gate Pack preparation.
- Preserved strict **Adapter Evidence** and **Candidate Evidence** validation while moving Gate Pack preparation behind a library interface.
- Extracted **Gulf Trace Record** logic into `autorefine/lib/gulf_trace_record.py`.
- Kept `record.py` as the **Gulf Trace Recorder** runtime adapter with compatibility wrappers for existing helper names and tests.
- Added direct **Gulf Trace Record** tests for record construction, scrubbing, provider parsing, stream reconstruction, and chunk overflow flushing.
- Extracted **Preference Signal** constants, normalizers, Override Scan builder, and candidate derivation into `autorefine/lib/preference_signals.py`.
- Kept `research_corpus.py` as the public facade for **Preference Signal** constants and builders.
- Removed `style_preferences_loader.py`'s dependency on private `research_corpus.py` internals.
- Added direct **Preference Signal** tests for builder normalization, candidate derivation, fewer-than-two override handling, invalid section-focus validation, and facade compatibility.
- Restored direct **Gate Pack Module** parity so `prepare_campaign_gate_pack(manifest)` prepares both **Single-Skill Workspace** and **Candidate Workspace** targets without requiring the CLI adapter.
- Made **Adapter State** fall back from a stale `adapter_config_path` to a valid `domain_eval_config_path` while preserving both refs in the normalized result.
- Restored compatibility facades for legacy `run-campaign.py` readiness helpers and `prepare-gulf-gate-pack.py` JSONL counting.
- Promoted **Preference Signal** normalization to the public `normalize_preference_signal_payload` API while keeping the private alias as a temporary compatibility shim.
- Added direct `run-campaign.py --manifest` subprocess coverage for the CLI import-path refactor.

## Example dialogue

> **Dev:** "Does this target have **Campaign Readiness** for Gulf 3?"
> **Domain expert:** "Only if the **Gate Pack** is backed by valid **Adapter Evidence** and the final trust gate has not already blocked it."

## Flagged ambiguities

- "ready" was used to mean both artifact existence and safe campaign progression; resolved: use **Campaign Readiness** for safe progression.
- "config" was used for both raw JSON files and normalized workspace state; resolved: use **Adapter State** for the normalized view and **Adapter Evidence** for confirmed domain-eval assets.
- "candidate" can mean a planned campaign target or a materialized workspace; resolved: use **Campaign Target** for the schedulable unit and **Candidate Workspace** for the on-disk workspace.
