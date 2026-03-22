# AutoRefine

**Karpathy's autoresearch + Hamel's Three Gulfs, applied to Claude Code skills.**

Iteratively improve any Claude Code skill — from zero evals to optimized and validated. Design audit, error analysis, and mutation-based optimization with a live Karpathy-style dashboard.

![AutoRefine Dashboard — ds-trace improving from 36.1% to 88.9% across 9 experiments](autorefine/assets/dashboard-ds-trace.png)

## Quick Start

```bash
# Clone and install
git clone https://github.com/surahli123/autorefine-skill-improvement.git
cp -r autorefine-skill-improvement/autorefine/ ~/.claude/skills/autorefine/

# Use it
/autorefine path/to/your-skill/
```

Works on **Claude Code** or any compatible coding agent with Read/Write/Bash tools.

**Strongly recommended:** Install [Hamel's evals-skills](https://github.com/hamelsmu/evals-skills) for the full pipeline (eval-audit, error-analysis, judge writing, judge validation).

## Why AutoRefine? (vs. Skill-Creator or Raw AutoResearch)

There are simpler tools. Here's why we built this one.

**Skill-Creator (Anthropic's default)** tests whether a skill triggers correctly and compares outputs via blind A/B. It's great for building skills from scratch and optimizing descriptions. But it doesn't tell you *why* your skill fails or *what* your evals should measure. If your evals are wrong, skill-creator optimizes against the wrong target — and you won't know until users complain.

**Raw AutoResearch (Karpathy-style)** runs a mutation loop: change the skill, test, keep or discard. Fast and effective — but it assumes you already have good evals. In practice, most skills have no evals, or evals that were brainstormed rather than grounded in observed failures. Optimizing against brainstormed evals is what Hamel calls "optimizing against a fantasy."

**AutoRefine closes the gap** by adding Hamel's Three Gulfs before the optimization loop:

1. **Gulf of Comprehension** — You read 20+ skill outputs yourself and build a failure taxonomy from what you actually see, not what you imagined. This is manual and irreplaceable.
2. **Gulf of Specification** — You write judges grounded in those observed failures, then validate them (TPR/TNR >90%). Now your evals measure what actually matters.
3. **Gulf of Generalization** — *Now* you run AutoResearch. The mutation loop optimizes against validated judges, not guesswork.

**The lesson we learned the hard way:** Our ds-review skill hit 100% on its initial evals — and an eval audit revealed the 100% was "likely an artifact of measuring a narrow slice of quality." The evals were too easy, not the skill too good. AutoRefine exists so you don't make the same mistake.

| Approach | Builds evals? | Grounds evals in observation? | Validates judges? | Optimizes? |
|----------|:---:|:---:|:---:|:---:|
| Skill-Creator | No (bring your own) | No | No | Yes (description + blind A/B) |
| Raw AutoResearch | No (bring your own) | No | No | Yes (mutation loop) |
| **AutoRefine** | **Yes (Phase 3)** | **Yes (error analysis)** | **Yes (Phase 6, v1.1)** | **Yes (Phase 7)** |

## Results

| Skill | Baseline | Final | Experiments | Keep Rate |
|-------|----------|-------|-------------|-----------|
| ds-trace | 36.1% | 88.9% | 9 | 100% |
| ds-review | 85.7% | 100% | 3 | 67% |

## What's Inside

```
autorefine/          <- Install this folder to ~/.claude/skills/autorefine/
├── SKILL.md         All instructions inline (orchestrator + phases + gotchas)
├── dashboard.html   Karpathy step graph + bar chart, auto-refreshes every 10s
├── references.md    Three Gulfs framework + v2.0 audit rubric (on demand)
└── README.md        Detailed documentation
```

See [`autorefine/README.md`](autorefine/README.md) for full documentation: pipeline details, dashboard features, requirements, and limitations.

## Credits & Inspiration

AutoRefine was inspired by and built upon:

- **[Ole Nurijanian's autoresearch-as-skill](https://x.com/nurijanian/status/2035257434365976671)** — The original repo that applied Karpathy's autoresearch to Claude Code skills. AutoRefine extends this with Hamel's Three Gulfs methodology, a design audit pipeline, and a Karpathy-style dashboard.
- **[Karpathy's autoresearch](https://github.com/karpathy/autoresearch)** — The mutation-test-keep/discard loop
- **[Hamel Husain's eval methodology](https://hamel.dev)** — The Three Gulfs framework (Comprehension → Specification → Generalization)
- **[Thariq Shubair's skill design patterns](https://www.anthropic.com)** — The v2.0 audit dimensions (Gotchas, instructional voice, progressive disclosure)

## Development

The `dev/` directory contains development artifacts (not needed for installation):

- `dev/principles/` — v2.0 skill design framework
- `dev/references/` — Source articles (Thariq, Koylan, Google patterns)
- `dev/audits/` — Historical skill audits
- `dev/docs/` — Design documents and session handovers

## License

MIT
