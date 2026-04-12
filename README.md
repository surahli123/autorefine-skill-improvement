# AutoRefine

**Karpathy's autoresearch + Hamel's Three Gulfs, applied to Claude Code skills.**

AutoRefine is a guided workflow for improving a `SKILL.md` file from vague instructions to eval-grounded, trust-checked, iterative optimization. It is designed for skill authors who want more than prompt tweaking: it adds human error analysis, judge validation, and a disciplined mutation loop before claiming a skill got better.

## Why this exists

Most skill iteration tools are strong at fast optimization but weak at proving that the optimization is real.

AutoRefine's core idea is simple:

1. **Comprehend** what the skill actually does wrong by reading outputs.
2. **Specify** judges grounded in those observed failures and validate them.
3. **Generalize** only after the eval surface is trustworthy.

That turns “prompt iteration” into a more reliable research loop.

## Install

Clone the repo and copy the shipped bundle into your Claude Code skills directory:

```bash
git clone https://github.com/surahli123/autorefine-skill-improvement.git
cp -r autorefine-skill-improvement/autorefine ~/.claude/skills/autorefine
```

If you want the bundle-level file breakdown, see [autorefine/README.md](autorefine/README.md).

The repo also includes `.claude-plugin/` and `.codex-plugin/` metadata for plugin/discovery surfaces. Both plugin manifests mirror the same public package identity and point at the shipped runtime bundle under `./autorefine`.

## Usage

```text
/autorefine /full/path/to/your-skill
```

AutoRefine creates a workspace, copies your target skill into it, and then guides you through the full refinement pipeline.

## What you should read next

- [docs/quickstart.md](docs/quickstart.md) for the fastest first run
- [docs/methodology.md](docs/methodology.md) for the Three Gulfs and mutation loop
- [docs/trust-model.md](docs/trust-model.md) for how judge trust and final promotion work
- [docs/faq.md](docs/faq.md) for common questions
- [docs/troubleshooting.md](docs/troubleshooting.md) for runtime/setup issues

## What is shipped

The installable runtime lives under [`autorefine/`](autorefine/). That bundle contains:

- `SKILL.md`
- `SKILL-gulf1.md`
- `SKILL-gulf2.md`
- `SKILL-gulf3.md`
- `references.md`
- `dashboard.html`
- `validate-host.sh`

Repo-maintenance tests and internal design material are intentionally kept outside the shipped bundle.

## Public vs internal repo surface

This public repo is user-facing:

- `autorefine/` is the shipped bundle
- `docs/` is curated user documentation

Internal engineering material lives in the `dev` submodule and is not part of the public install surface.

## License

MIT
