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
| **Quick** | Context-aware | ~15-30 min | Adapts based on workspace state (see below) |
| **Standard** | 1-7 | ~60-90 min | Skills needing eval methodology from scratch |
| **Deep** | 1-7 + expanded fixtures | ~2 hrs | Critical skills requiring statistical rigor |

Quick is context-aware — it adapts based on your workspace state:
- **First time (Quick Start, ~30 min):** Design audit → read 5 outputs → generate bootstrap evals → run 2-3 mutations. You see your skill improve with honest "directional" labeling. Everything carries forward into Standard.
- **Returning with bootstrap evals (~15 min):** More mutations with your existing evals. Results still directional until you run Standard to validate.
- **Returning with validated evals (~15 min):** Full confidence mutations with calibrated scoring.

## What It Does

Three gulfs to cross, in order:

```
Gulf 1: Comprehension — What does this skill actually do?
  Phase 1: Design Audit        Score against v2.0 patterns (Gotchas, voice, disclosure)
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

## v2.2 Features (NEW)

- **Quick Start** — First-time path that shows value in ~30 min. Design audit → read 5 outputs → bootstrap evals → targeted mutations. Honestly labeled as "directional." Everything carries forward into Standard.
- **Context-aware Quick tier** — Automatically detects workspace state and routes to the right path (first-timer vs. returning with bootstrap vs. returning with validated evals)
- **Bootstrap eval generator** — Converts Phase 1 audit findings + observed failures into lightweight evals using a simplified zero-shot judge template
- **Fresh scoring corpus** — Mini Phase 7 generates separate inputs for mutation scoring to prevent overfitting on the traces you just reviewed

## v2.1 Features

- **Pipeline tiering** — Quick/Standard/Deep depth selection at Preflight
- **Feedback spine** — `session-log.json` tracks sampling decisions, gate approvals, overrides, and judge gaps across every phase
- **Confidence-weighted scoring** — Phase 7 weights each eval by its judge's validated TPR/TNR. Code evals = 1.0, agent evals = (TPR+TNR)/2
- **Judge gap detection** — When you override a Phase 7 verdict, it's logged as a judge blind spot
- **Loop-back prompt** — If you override 2+ verdicts, autorefine offers to loop back to Phase 5 to fix the judges, then re-run Phase 7
- **Session Close** — Synthesizes session-log into a 3-5 bullet learning summary, persisted to your agent's memory system
- **Action script architecture** — SKILL.md (220 lines) is pure instructions. Templates, schemas, and rationale live in references.md (370 lines), loaded on demand

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
| `SKILL.md` | 220 | **Action script** — every line is an instruction the agent follows |
| `references.md` | 370 | **Detail library** — templates, schemas, formulas, rubrics. Read on demand via `references.md > Section` pointers |
| `dashboard.html` | — | Chart.js dashboard with Karpathy step graph, auto-refreshes every 10s |
| `validate-host.sh` | — | Tests whether your agent supports `Read when:` progressive disclosure |

The agent loads only the 220-line action script. When it needs a template or formula, the script tells it exactly which section of references.md to read.

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
