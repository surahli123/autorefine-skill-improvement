# Handover: Skill-Improver v1.0

## Project
- **Name:** Skill Improvement
- **Path:** `/Users/surahli/Documents/projects/skill-improvement/`
- **Branch:** `feature/skill-improver-v1` (commit `49fcdd2`)

## Last Session Summary
Built the **skill-improver meta-skill** — a standalone, portable tool for iteratively improving any Claude Code skill using eval-grounded autoresearch. Brainstormed 3 approaches, settled on a Karpathy-simple 3-file architecture after the user pushed back on a 10+ file design. Added Hamel's eval-skill integration and a Karpathy step graph dashboard with expandable experiment details.

## Current State

### What's Working
- **SKILL.md** (282 lines) — Orchestrator + Phases 1, 2, 3, 7 inline. Hamel integration blocks for eval-audit, error-analysis, generate-synthetic-data, and skill-creator subagents (grader/comparator/analyzer). Phases 4-6 stubbed with methodology summary.
- **dashboard.html** (322 lines) — Two charts: bar chart (score per experiment) + Karpathy step graph (scatter + staircase line showing running best). Expandable experiment rows showing change type/location/snippet. Auto-refresh every 10s via Chart.js.
- **references.md** (71 lines) — Three Gulfs framework + v2.0 design audit rubric. Loaded on demand.
- **Phase 1 quick test passed** — Ran design audit against notebooklm skill, correctly scored Partial on all 4 dimensions.

### Key Constraints
- Must work on user's in-house coding agent (~late 2025 Claude Code): Read/Write/Bash/Grep/Glob only, general-purpose subagents, no auto-triggering
- Core methodology inline (works without Hamel's skills). Hamel's evals-skills enhance when available.
- Developed in skill-improvement repo, deployed to `~/.claude/skills/skill-improver/`

## Next Steps (Priority Order)

1. **Full end-to-end test on ds-trace** — Run Phases 1-3 on `ds-productivity-agents/skills/ds-trace/` (user's own skill). ds-trace is more deterministic than ds-review (structured output, binary evals) — better for validating skill-improver itself. Existing `autoresearch-ds-trace/` artifacts provide ground truth. Phase 2 should match the existing eval findings. Phase 3 is the real test: run ds-trace on 20+ inputs and have user review outputs.

2. **Add Phases 4-6 to SKILL.md (v1.1)** — ~90 lines covering Gulf 2 (Expand Inputs, Write Judges, Validate Judges). Stubs already exist with Hamel skill integration notes. Estimated: ~410 lines total, still under 500.

3. **Deploy to ~/.claude/skills/skill-improver/** — Copy the 3 files, test from a different project directory. Confirm it works standalone.

4. **Merge feature branch to main** — After testing is complete.

5. **Formal evals (v2)** — Use skill-creator's eval framework to build evals for skill-improver itself (meta!). Only after manual testing validates the workflow.

## Key Decisions Made

- **3-file architecture** over 10+ file runbook stack — Karpathy-simple: SKILL.md (all instructions), dashboard.html (viz), references.md (on-demand context)
- **Core inline, Hamel optional** — Works without external dependencies. Hamel's skills enhance when detected.
- **Main-context first** — Critical thinking in main agent, subagents only for simple parallel tasks (in-house agent constraint)
- **results.json extended** with `changes` array per experiment — stores type/location/snippet for dashboard expandable details
- **Karpathy step graph** uses Chart.js scatter + `stepped: 'before'` line (not matplotlib like Karpathy's original)

## Relevant Files to Read First
1. `skill-improver/SKILL.md` — The complete skill
2. `skill-improver/dashboard.html` — Dashboard with step graph
3. `skill-improver/references.md` — On-demand reference
4. `principles/v2-skill-design.md` — The audit rubric source
5. `~/.claude/projects/-Users-surahli/memory/project_skill_improver.md` — Project memory
6. `~/.claude/projects/-Users-surahli/memory/feedback_inhouse_agent_capabilities.md` — In-house agent constraints
