---
name: autorefine
description: Iterate and improve any skill using eval-grounded autoresearch. Combines v2.0 design audit, Hamel's Three Gulfs eval methodology, and Karpathy-style mutation optimization. Use when you want to assess skill quality, build evals from scratch, run error analysis, or optimize a skill through experiments.
---

# AutoRefine

Guided skill improvement pipeline. Point at a skill: `/autorefine path/to/my-skill/`

## Preflight

### Step 0: Environment Check (MANDATORY — runs first, < 15 seconds)

Fast-fail checks. If ANY fail, STOP immediately with an actionable error message. Do NOT retry or explore alternatives silently.

1. **Target skill path.** If user provided a path, use it. If not, ask: "Which skill should I improve? Provide the full path to the skill directory."
2. **Target readable.** Run: `head -5 [skill-path]/SKILL.md`. If this fails → STOP: "I can't read your skill at [skill-path]. If you're in a sandboxed environment, copy your skill into my working directory first: `cp -r [skill-path] ./skill-under-test/` then re-invoke with `./skill-under-test/`"
3. **Workspace location.** Ask the user (ONE question, wait for answer):
   ```
   Where should I create the AutoRefine workspace?
     a) /tmp/autorefine-[skill-name]/  <- recommended (safe, no repo interference)
     b) Next to your skill: [skill-parent]/autorefine-[skill-name]/
     c) Custom path
   ```
   Default to (a) if user says "whatever" or "default." NEVER create the workspace without this confirmation.
4. **Workspace writable.** Run: `mkdir -p [chosen-workspace] && touch [chosen-workspace]/.preflight-test && rm [chosen-workspace]/.preflight-test`. If this fails → STOP: "I can't write to [chosen-workspace]. Try option (a) /tmp/ which is always writable, or specify a different path."
5. **Skill import.** Copy the entire skill directory into the workspace: `cp -r [skill-path]/ [chosen-workspace]/skill-under-test/`. All subsequent reads and writes operate ONLY on `[workspace]/skill-under-test/`, never on the original skill path. This protects the user's real skill from accidental modification.
6. **Persist paths.** Record in state.json: `original_skill_path: [skill-path]`, `workspace_path: [chosen-workspace]`. These are needed for Session Close (Apply Back gate) and session resume.

After Step 0 completes, print:
```
Preflight passed
  Target skill: [skill-path]/SKILL.md
  Workspace: [chosen-workspace]/
  Working copy: [chosen-workspace]/skill-under-test/SKILL.md
  Original path saved for apply-back: [skill-path]
  Original skill is UNTOUCHED until you approve changes.
```

### Step 1: Detect & Configure

1. **Detect enhancements.** Search for Hamel's `eval-audit` and `error-analysis` skills. If found, note in state.json. These enhance but are NOT required.
2. **Report tier:** Full (Hamel's detected) or Basic (core methodology only).
3. **Choose pipeline depth:**
   - **Quick** — Context-aware. Routes based on workspace state (~15-30 min). See routing below.
   - **Standard** — Full pipeline (Phases 1-7). For skills needing eval methodology from scratch. ~60-90 min.
   - **Deep** — Standard + expanded fixture set (30+ fixtures). For critical skills requiring statistical rigor.

   **Quick tier routing (3 states):**
   ```
   State 1: No workspace exists
     -> Quick Start path (~30 min)
     -> "First time? Let's find what your skill actually does wrong."
   State 1b: Workspace exists with schema_version 2 (legacy v2.1), no quick_start field
     -> Standard/Deep only (legacy workspace -- Quick Start not available)
     -> "This workspace was created before Quick Start. Use Standard or Deep."
   State 2: quick_start.completed = true, both gates still "pending"
     -> Quick Returning (~15 min): Run Phase 1 (design audit), then skip to Phase 7 in Mini mode. Show directional warning at start.
     -> Steps: (1) Run Phase 1 as normal. (2) Skip Phases 2-6. (3) Run Phase 7 -- it auto-detects Mini mode from state. (4) Run Session Close.
     -> "Your evals haven't been validated -- results are still directional."
   State 3: Both gulf_1 and gulf_2 = "approved" in state.json
     -> Quick Returning (~15 min): Run Phase 1 (design audit), then skip to Phase 7 in Full mode.
     -> Steps: (1) Run Phase 1 as normal. (2) Skip Phases 2-6. (3) Run Phase 7 -- it auto-detects Full mode from state. (4) Run Session Close.
   ```

   If workspace has approved gates: offer Quick as default. If quick_start_complete: offer Quick with directional note. Otherwise default to Standard (offer Quick Start as faster alternative).

## Initialize Workspace

**Workspace path** was confirmed in Preflight Step 0. The workspace is at `[workspace]/` and the working copy of the skill is at `[workspace]/skill-under-test/`. (After Preflight, `[workspace]` = the path chosen in Step 0.3 and persisted in `state.json.workspace_path`.)

If workspace `traces/`, `judges/`, `runs/`, and `skill-versions/` subdirectories don't exist: create them. Generate these files (see `references.md > Workspace Schemas` for exact formats):
- `state.json` — pipeline state (schema_version:4 for new workspaces — see `references.md > Workspace Schemas`)
- `results.json` — experiment results for dashboard
- `results.tsv` — append-only experiment log
- `session-log.json` — per-session audit trail
- `changelog.md`, `eval-suite.md`, `error-analysis-traces.md` — empty, formatted in later phases
- Copy `dashboard.html` from this skill's directory, replace `{{SKILL_NAME}}`

If workspace exists **with** `state.json`: read it, deserialize any persisted `phase1_context` (including `selected_skill_pattern` and `selected_eval_strategy_id`) plus any persisted `mutation_stage_split_access_policy`, `iteration_state`, `mid_session_preference_signals`, and `mid_session_preference_signals_path` into the loaded run context, then normalize the active-loop `style_preferences` payload using `references.md > Style Preferences Payload` before printing pipeline status.

**Step A: Checkpoint recovery (runs FIRST on resume).**
If `state.json.checkpoint` is not null and has `next_action`, enter resume mode — read all files in `checkpoint.files_to_read_on_resume` (skip any missing files and note which were missing), deserialize `state.json.phase1_context`, `state.json.mutation_stage_split_access_policy`, `state.json.iteration_state`, `state.json.mid_session_preference_signals`, and `state.json.mid_session_preference_signals_path` into the loaded run context before routing the resume path, then rebuild the normalized `style_preferences` payload from `references.md > Style Preferences Payload`, and print "Resuming from checkpoint: {next_action}". Restore `phase1_context.selected_skill_pattern` and `phase1_context.selected_eval_strategy_id` unchanged so later phases can read the chosen pattern + resolved downstream strategy from the loaded context rather than recomputing them. If the restored run-context pattern and `state.json.skill_pattern` mismatch, stop and rerun Phase 1 Step 0 instead of continuing. If the restored `selected_eval_strategy_id` is missing or no longer maps back to the restored pattern through `references.md > Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector`, stop and rerun strategy selection before continuing. If split-scoped Phase 7 work is active and the restored `mutation_stage_split_access_policy` is missing, read the same policy from `fixtures-manifest.md` or a stored Phase 4 `evaluation_metadata.config.mutation_stage_split_access_policy` snapshot, hydrate the loaded run context, and stop if the sources disagree. If `iteration_state` is present, treat it as the authoritative Phase 7 handoff record for whether the active `run_id` is in eval, mutate, test, or session_close; continue automatic progression from the persisted `next_action` until terminal success (`phase_status = "completed"`) or terminal failure (`phase_status = "blocked"`) without requiring manual phase handoff. Do not infer boundaries from directory scans while the persisted runner state is available. Then clear the checkpoint (set to null) while preserving every other serialized state field, including `phase1_context`, `mutation_stage_split_access_policy`, `iteration_state`, `mid_session_preference_signals`, and `mid_session_preference_signals_path`. See `references.md > Checkpoint Schema > Resume Detection`. Rotate `session-log.json` (rename to `session-log-<session_start, colons->dashes>.json`, create fresh). If `session-log.json` missing (pre-v2 workspace), create it. Legacy workspaces (schema_version 2 or 3) are read-compatible — checkpoint fields default to null. If checkpoint has `next_action` pointing to a Phase 7 experiment, **skip ambient learning entirely** (workspace copy must match the in-progress experiment state) and proceed from `next_action`.

**Pattern-aware downstream entry:** When routing into any downstream phase or stage after Phase 1, initialize pattern-aware logic from the loaded `state.json.phase1_context.selected_skill_pattern`. Then restore `state.json.phase1_context.selected_eval_strategy_id` into that same loaded run context and treat the pair as the active downstream routing state for the current run. If the active context does not already hold them, read the same canonical IDs from the top-level `selected_skill_pattern` and `selected_eval_strategy_id` fields emitted in `design-audit.md`, hydrate the loaded run context, and continue. If the active context does not already hold it, read the same canonical ID from the top-level `selected_skill_pattern` field emitted in `design-audit.md`, hydrate the loaded run context, and continue. If only the pattern is available, resolve the missing strategy through `references.md > Skill Pattern Eval Strategy > Pattern-to-Evaluation-Strategy Selector` before continuing. After hydrating `selected_eval_strategy_id`, immediately open the matching row in `references.md > Skill Pattern Eval Strategy > Strategy Definitions` and route all downstream eval work through that strategy bundle. The selected strategy is the execution path for Quick Start bootstrap evals, Phase 2 eval audit, Phase 3/4 failure clustering and fixture expansion, Phase 5/6 judge design, and Phase 7 mutation analysis; do not fall back to the generic downstream path while a valid selector is present. Do not trigger Phase 1 pattern classification again during downstream phase/stage initialization; rerun Phase 1 Step 0 only if the persisted pattern is missing or inconsistent with `state.json.skill_pattern`.

**Split-aware downstream entry:** When routing into Phase 7 or Session Close after Phase 4, initialize split-aware logic from the loaded `state.json.mutation_stage_split_access_policy`. If the active context does not already hold it, read the exact policy from `fixtures-manifest.md` or a stored Phase 4 `evaluation_metadata.config.mutation_stage_split_access_policy` snapshot, hydrate the loaded run context, and stop if those sources disagree. Treat the restored object as the active gate for any downstream step that may read split-scoped datasets, per-input outputs, or version-comparison joins. Canonicalize any caller-provided split token before the gate check; if the raw token, an alias, or a delegated resolution path lands on `adversarial_holdout`, reject the read. Once active, route every Phase 7 split-scoped read through `references.md > Restricted Mutation-Stage Dataset Access Path` instead of reopening fixtures, scored inputs, or comparison payloads directly from the mutation loop. Resolve intermediate scoring splits through that accessor and the active policy only; do not branch on raw split IDs or bypass the accessor to recover the dev corpus. If `requested_operation = mutation_scoring` resolves to `adversarial_holdout`, explicitly deny the request and fail closed before reopening any stored dev corpus. The final-only evaluation stage is not part of this Phase 7 read path: do not trigger holdout validation while the mutation loop is still iterating. Trigger it only once after the loop reaches a terminal exit for the active `state.json.current_run_path`. At Session Close, reuse the existing variant-evaluation interface to score the completed version lineage on the holdout split instead of inventing a second holdout-only scorer. Do not start a Phase 7 dataset read until that policy is active.

**Meta-learnings bootstrap context:** If the session may enter Phase 7 or Session Close, bootstrap the meta-learnings context into the loaded run context before any mutation steering or resume-time cross-campaign reasoning. Resolve `state.json.meta_learnings_path` (or the default AutoRefine skill-directory copy), normalize the current target context (`skill_pattern`, `agent_target`, `scenario_target`, `scope_type`, `scope_ref`), then hydrate `{meta_learnings_path, target_context, parsed_meta_learnings}` using `references.md > Campaign Bootstrap Meta-Learnings Context`. Rebuild this object on every start/resume instead of persisting parsed entries in `state.json`. When a run output or report payload is serialized, preserve the same bootstrap envelope's reporting fields — `curator_source`, `curator_version`, `transfer_parameters`, and `transfer_traceability` — unchanged so downstream filters and exports can replay the same curation lineage.

**Style-preferences payload:** If the session may continue iterating inside Phase 7 or Session Close, rebuild the normalized `style_preferences` payload from `state.json.mid_session_preference_signals` plus `state.json.mid_session_preference_signals_path` using `references.md > Style Preferences Payload`, then keep that envelope in the loaded run context across eval, mutate, test, and session_close. Mid-loop stages should read `style_preferences.active_signals` as the machine-readable preference set and `style_preferences.resolved_preferences_path` only when they need the human-readable `[workspace]/preferences.md` wording; do not rescan raw override sources once the hydrated payload is available.

**Step B: Ambient learning (runs AFTER checkpoint recovery, only if NOT resuming mid-Phase-7).**

Guard: `state.json.original_skill_path` must exist and be readable. If unreadable (sandbox, deleted), skip ambient learning silently and continue.

1. Run `diff [original-skill-path]/SKILL.md [workspace]/skill-under-test/SKILL.md`. If the `diff` command fails (sandbox restriction), skip ambient learning and continue.
2. If no diff → skill unchanged. Continue.
3. If diff exists → size gate:
   - **Small diff (<=20 lines changed):** likely preference signal. Proceed to step 4.
   - **Large diff (>20 lines, <=50% of file):** warn: "Large diff detected (N lines). Treat as preference signal or new baseline?" If user says baseline → skip to step 5.
   - **Rewrite (>50% of file):** skip rule extraction. Log `{"type":"ambient_learning","skipped":true,"reason":"full_rewrite","diff_size":N}`. Go to step 5.
4. **Extract preference rules.** Show the diff to the user. Ask: "Should I learn from these edits? (y/n)". If yes, extract rules using this format:
   ```
   RULE: [one-sentence preference]
   EVIDENCE: [quote removed text] -> [quote added text] (max 2 lines each)
   CONFIDENCE: high (clear intent) | medium (inferred) | low (ambiguous)
   ```
   Only auto-log `high` and `medium` rules. Present `low` rules for user confirmation. Distinguish preference edits from bug fixes (if the user fixed a typo or corrected a factual error, that's a fix, not a preference — skip it). Log to `[workspace]/preferences.md` (separate from `learnings.md` used by Session Close) and session-log: `{"type":"ambient_learning","rules_extracted":N,"diff_size":N}`.
5. **Sync workspace copy.** Always update: `cp [original-skill-path]/SKILL.md [workspace]/skill-under-test/SKILL.md`. This ensures the next mutation cycle starts from the user's current version.

If workspace exists **without** `state.json`: back up the workspace to `[workspace]-prev/` and create a fresh workspace at `[workspace]/`.

## Pipeline Status

Print at every session start:
```
AutoRefine: <name>
================================================================
Quick Start                        [STATUS]
Gulf 1: Comprehension
  Phase 1: Design Audit          [STATUS]
  Phase 2: Eval Audit             [STATUS]
  Phase 3: Error Analysis         [STATUS]  [N/M traces]
  >>> Gate: Approve taxonomy      [STATUS] <<<
Gulf 2: Specification
  Phase 4: Expand Inputs           [STATUS]  [N fixtures]
  Phase 5: Write Judges            [STATUS]  [N code / N judge]
  Phase 6: Validate Judges         [STATUS]  [TPR/TNR]
  >>> Gate: Approve judges         [STATUS] <<<
Gulf 3: Generalization
  Phase 7: AutoResearch Loop      [STATUS]  [best score]
================================================================
> Gulf 1 builds the scorer. Gulf 3 uses the scorer.
> Skip Gulf 1 and you optimize against a fantasy.
```
STATUS values: `not started`, `in progress`, `complete`, `skipped`. Read from `state.json.phases`.

---

## Gulf Routing

After Initialize Workspace and Pipeline Status, read the appropriate gulf file based on pipeline state. **Only read the gulf file relevant to the current phase. Do NOT preload all gulf files.**

| Current Phase | Read | Contains |
|---------------|------|----------|
| Quick Start, Phase 1-3 | `SKILL-gulf1.md` | Quick Start Path, Phase 1 (Design Audit + Pattern Classification), Phase 2 (Eval Audit), Phase 3 (Error Analysis), Gulf 1 Gate |
| Phase 4-6 | `SKILL-gulf2.md` | Phase 4 (Expand Inputs), Phase 5 (Write Judges + Eval Category Tags), Phase 6 (Validate Judges), Gulf 2 Gate |
| Phase 7, Session Close | `SKILL-gulf3.md` | Phase 7 (AutoResearch Loop + Verdict Explanation Cards + Aggregation Explainer + Version Registry), Loop-Back Prompt, Session Close (+ Version Comparison) |

**Routing rules:**
- Starting fresh or resuming in Phases 1-3 → read `SKILL-gulf1.md`
- Gulf 1 gate approved, entering Phases 4-6 → read `SKILL-gulf2.md`
- Gulf 2 gate approved (or Quick Start returning) → read `SKILL-gulf3.md`
- **Quick Start returning (State 2 or 3):** read `SKILL-gulf1.md` for Phase 1, then read `SKILL-gulf3.md` for Phase 7 + Session Close (two-file read)
- Loop-back from Phase 7 to Phase 5 → re-read `SKILL-gulf2.md`

---

## Gotchas

Critical rules (full list in `references.md > Gotchas`):

1. **Don't skip Gulf 1.** A 100% score on narrow evals is an artifact, not evidence.
2. **Error analysis cannot be automated.** Phase 3 requires the human to read outputs.
3. **session-log.json is best-effort.** If corrupted or missing, recreate and continue. Never blocks.
4. **Never run two sessions on same skill.** state.json has no locking.
5. **"Invoke" means "read and follow."** Not all agents support direct skill invocation.
6. **Quick Start is a preview, not validation.** Bootstrap evals are directional, not calibrated.
7. **Critical state lives in files, not conversation.** Auto-compact at ~85% context erases conversation history.
8. **Never write to the original skill path during the pipeline.** All work on `[workspace]/skill-under-test/`.
9. **Sandbox environments block cross-directory access.** Use `/tmp/` as workspace workaround.
10. **Agent-as-judge evals should not see mutation reasoning.** Tier 1 (subagent) = real isolation. Tier 2 (behavioral) = heuristic only.
11. **Workspace location must be confirmed, never assumed.** Never create without asking.

---

## References

`references.md` — Templates, schemas, methodology rationale, detailed rubrics, gotchas.
Read `references.md > Version Comparison Alignment` before surfacing version diffs or any per-input comparison payload.
Version diffs must run the comparison preflight first, require the exact same set of stable `input_id`s, surface `missing_from_left`, `missing_from_right`, `extra_in_left`, or `extra_in_right` on mismatch, mark that state as `invalid-comparison`, and must not emit normal comparison results when preflight fails.
After the preflight passes, surface the per-input comparison payload together with a shared-input outcome summary that reports trusted `improved` / `regressed` counts plus `unreliable` and `unchanged` counts across the joined `input_id` set.
Read `references.md > Judge Verdict Evidence Schema` when Phase 7 stores verdicts: preserve a structured `evidence` array with required `kind, source, locator` fields for input excerpts, output excerpts, metrics, or artifact references.
Phase 7 evidence storage uses a structured `evidence` array. Required fields: `kind, source, locator`. Supported evidence types: input excerpts, output excerpts, metrics, or artifact references.
Read `references.md > Discard Autopsy Heuristics` when Phase 7 discards an experiment so the discard autopsy classification is written back to `results.json`.
