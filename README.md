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

Works on **Claude Code** or any compatible coding agent with Read/Write/Bash tools. No advanced tools required.

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
