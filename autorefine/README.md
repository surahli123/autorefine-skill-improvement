# AutoRefine Bundle

This directory is the shipped AutoRefine bundle.

It is the path public plugin manifests and manual installs should point at.

## Install Into Claude Code

```bash
cp -r autorefine ~/.claude/skills/autorefine
```

After install, invoke it with:

```text
/autorefine /full/path/to/your-skill
```

The shipped shell also includes the Phase 1 design-audit dimensions, including anti-railroading and description quality, before Gulf 2 and Gulf 3 build on that state.

## Bundle Contents

- `SKILL.md` — the main action script
- `SKILL-gulf1.md` — Gulf 1: comprehension
- `SKILL-gulf2.md` — Gulf 2: specification and judge validation
- `SKILL-gulf3.md` — Gulf 3: mutation loop and session close
- `references.md` — templates, schemas, rubrics, and detail contracts
- `dashboard.html` — local run dashboard
- `validate-host.sh` — host capability check
- `hooks/` — bundle hooks
- `lib/` — runtime helper code used by the bundle
- `meta-learnings.md` — curated cross-campaign learning input

## What is not part of the shipped bundle

Repo-maintenance shell tests, internal plans, handovers, and research notes are intentionally kept outside this directory.

If you are looking for user-facing docs, start here:

- [`../README.md`](../README.md)
- [`../docs/quickstart.md`](../docs/quickstart.md)
- [`../docs/methodology.md`](../docs/methodology.md)
- [`../docs/trust-model.md`](../docs/trust-model.md)

## Notes

- Keep this directory installable as a self-contained skill bundle.
- Public plugin manifests should point to `./autorefine`.
- Internal engineering artifacts should live in the `dev` submodule, not here.
