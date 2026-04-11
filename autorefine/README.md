# AutoRefine

**Karpathy's autoresearch + Hamel's Three Gulfs, applied to Claude Code skills.**

A guided pipeline for iteratively improving any skill — from zero evals to optimized and validated. Point it at a skill, and it walks you through design audit, error analysis, and mutation-based optimization with a live dashboard.

## Why AutoRefine? (vs. Skill-Creator or Raw AutoResearch)

There are simpler tools. Here's why we built this one.

**Skill-Creator (Anthropic's default)** builds assertion-based evals, reviews transcripts after running the skill, and optimizes descriptions via iterative refinement with train/test splits. It's great for building skills from scratch and tuning trigger accuracy. But its eval grounding is partial — assertions are drafted post-run, not from a systematic failure taxonomy. And judge validation is qualitative (graders critique weak assertions) rather than quantitative (no TPR/TNR calibration).

**Raw AutoResearch (Karpathy-style)** runs a mutation loop: change the skill, test, keep or discard. Fast and effective — but it assumes you already have good evals. In practice, most skills have no evals, or evals that were brainstormed rather than grounded in observed failures.

**AutoRefine closes the gap** by adding Hamel's Three Gulfs before the optimization loop:

1. **Gulf of Comprehension** — You read 20+ skill outputs yourself and build a failure taxonomy from what you actually see, not what you imagined. This is manual and irreplaceable.
2. **Gulf of Specification** — You write judges grounded in those observed failures, then validate them (TPR/TNR >90%). Now your evals measure what actually matters.
3. **Gulf of Generalization** — *Now* you run AutoResearch. The mutation loop optimizes against validated judges, not guesswork.

| Approach | Builds evals? | Grounds in observation? | Validates judges? | Optimizes? |
|----------|:---:|:---:|:---:|:---:|
| Skill-Creator | Yes (assertion-based) | Partial (post-run transcript review) | Partial (qualitative, no TPR/TNR) | Yes (description tuning + feedback loop) |
| Raw AutoResearch | No (bring your own) | No | No | Yes (mutation loop) |
| **AutoRefine** | **Yes (Phase 3 taxonomy)** | **Yes (human error analysis)** | **Yes (Phase 6 TPR/TNR)** | **Yes (Phase 7 mutation loop)** |

The real differentiator is **rigor**, not capability. Skill-creator builds evals and observes outputs, but doesn't formalize failures into a taxonomy or calibrate judges quantitatively. AutoRefine's advantage is the structured pipeline with human gates — so you know your evals measure what actually matters before you optimize against them.

## Results

We used autorefine on two of our own skills:

| Skill | Baseline | Final | Experiments | Key mutation |
|-------|----------|-------|-------------|--------------|
| ds-review | 85.7% | 100% | 3 | Location precision rule — banned vague references like "entire document" |
| ds-trace | 60% | 100% | 3 | Tool diversity rule + substantive "what went wrong" requirement |

## Install

```bash
git clone https://github.com/surahli123/autorefine-skill-improvement.git
cp -r autorefine-skill-improvement/autorefine/ ~/.claude/skills/autorefine/
```

Or copy the 4 core files directly to `~/.claude/skills/autorefine/`:
- `SKILL.md` — action script (what the agent follows)
- `references.md` — detail library (templates, schemas, rubrics)
- `dashboard.html` — live results dashboard
- `validate-host.sh` — one-time host capability test

## Usage

```
/autorefine path/to/your-skill/
```

The agent detects your progress and picks up where you left off. First run scaffolds a workspace with dashboard, results tracking, and eval templates.

### Pipeline Depth

Choose your depth at the start:

| Tier | Phases | Time | When to use |
|------|--------|------|-------------|
| **Quick** | 1 + 7 | ~15 min | Skills with existing evals or known failure modes |
| **Standard** | 1-7 | ~60-90 min | Skills needing eval methodology from scratch |
| **Deep** | 1-7 + expanded fixtures | ~2 hrs | Critical skills requiring statistical rigor |

Quick requires an existing approved workspace (both gates passed, populated judges). If you haven't run Standard yet, start there.

## What It Does

Three gulfs to cross, in order:

```
Gulf 1: Comprehension — What does this skill actually do?
  Phase 1: Design Audit        Score against v2.0 patterns (Gotchas, voice, disclosure, anti-railroading, description quality)
  Phase 2: Eval Audit           Assess existing evals or document their absence
  Phase 3: Error Analysis       YOU read 20+ outputs and build a failure taxonomy
  >>> Human Gate <<<             Approve taxonomy before proceeding

Gulf 2: Specification — Do our judges measure what matters?
  Phase 4: Expand Inputs        Dimension-based fixture generation + train/dev/test split
  Phase 5: Write Judges         Code-based evals first, LLM judges for subjective criteria
  Phase 6: Validate Judges      TPR/TNR calibration on dev split, final measurement on test
  >>> Human Gate <<<             Approve judges before autoresearch

Gulf 3: Generalization — Does it work on unseen inputs?
  Phase 7: AutoResearch Loop    Mutate -> test -> user confirms -> keep/discard
```

Phase 3 (error analysis) is human-in-the-loop by design. You cannot automate comprehension.

## Features

### Core (v2.1)
- **Pipeline tiering** — Quick/Standard/Deep depth selection at Preflight
- **Feedback spine** — `session-log.json` tracks sampling decisions, gate approvals, overrides, and judge gaps across every phase
- **Confidence-weighted scoring** — Phase 7 weights each eval by its judge's validated TPR/TNR. Code evals = 1.0, agent evals = (TPR+TNR)/2
- **Judge gap detection** — When you override a Phase 7 verdict, it's logged as a judge blind spot
- **Loop-back prompt** — If you override 2+ verdicts, autorefine offers to loop back to Phase 5 to fix the judges, then re-run Phase 7
- **Session Close** — Synthesizes session-log into a 3-5 bullet learning summary, persisted to your agent's memory system
- **Action script architecture** — SKILL.md is pure instructions. Templates, schemas, and rationale live in references.md, loaded on demand

### Quick Start (v2.2)
- **Context-aware routing** — Detects workspace state and routes to the right entry point (new, returning with bootstrap evals, returning with validated evals)
- **Bootstrap eval generator** — Auto-generates lightweight evals from Phase 1 findings + observed failures
- **Mini Phase 7** — 2-3 targeted mutations with simplified scoring (directional, not validated)

### Harness Engineering (v2.3)
- **Preflight workspace isolation** — Skill copied to workspace, original untouched until apply-back
- **Judge confidence cards** — TPR/TNR with interpretation, evidence table, asymmetry warning (>20pt gap)
- **Mutation regression check** — Per-eval breakdown, compares against prior kept experiments
- **Gotcha detection precision** — 3-stage (taxonomy + static evidence + smoke probe)
- **Checkpoint/resume** — Save and resume across session boundaries

### AutoKaggle Patterns (v3)
- **Discard autopsy** — 3-way classification (`wrong_target | wrong_params | wrong_type`) after each Phase 7 discard, directing the next hypothesis
- **Derived mutation registry** — Computes `sections_explored`, `mutation_types`, `diversity_score` from results.json on demand
- **Circuit breaker** — Stops after 3 consecutive discards with diagnosis (content ceiling vs strategy review)
- **Filesystem-as-memory** — Per-experiment iteration directories (`runs/run_<timestamp>/iteration_<NNN>/`) with 5 artifact files surviving context compaction

## The Dashboard

Each autorefine run produces a live dashboard with:

- **Score Progression** — bar chart showing each experiment's pass rate
- **Improvement Staircase** — Karpathy-style scatter + step graph showing the running best score climbing over experiments
- **Expandable experiment details** — click any row to see what changed (type, location, code snippet)
- **Per-eval breakdown** — pass rates for each binary eval

Serve it: `cd autoresearch-<skill>/ && python3 -m http.server 8080`

## Architecture

| File | Lines | Role |
|------|-------|------|
| `SKILL.md` | ~460 | **Action script** — every line is an instruction the agent follows |
| `references.md` | ~1020 | **Detail library** — templates, schemas, formulas, rubrics. Read on demand via `references.md > Section` pointers |
| `dashboard.html` | — | Chart.js dashboard with Karpathy step graph, auto-refreshes every 10s |
| `validate-host.sh` | — | Tests whether your agent supports `Read when:` progressive disclosure |

The agent loads the action script (~460 lines). When it needs a template or formula, the script tells it exactly which section of references.md to read.

## Requirements

- **Claude Code** or any compatible coding agent with Read/Write/Bash tools
- Works on agents with limited tool sets — no TaskCreate, Agent, or Skill tool required
- **Optional enhancement:** Install [Hamel's evals-skills](https://github.com/hamelsmu/evals-skills) for deeper eval auditing and judge writing

## Limitations

- **Small fixture counts yield directional TPR/TNR.** With 30-40 fixtures (~15 dev), judge validation is signal, not proof. For rigorous validation, generate 100+ fixtures per Hamel's methodology.
- **Dashboard requires internet** for Chart.js CDN. If your network blocks CDN access, download `chart.umd.min.js` locally.
- **No concurrent sessions.** Don't run two autorefine sessions on the same skill — state.json has no locking.

## License

MIT
