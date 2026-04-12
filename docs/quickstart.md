# Quickstart

## Install

```bash
git clone https://github.com/surahli123/autorefine-skill-improvement.git
cp -r autorefine-skill-improvement/autorefine ~/.claude/skills/autorefine
```

## Run

```text
/autorefine /full/path/to/your-skill
```

## What happens

1. AutoRefine creates a workspace.
2. It copies your skill into that workspace so your original skill stays untouched.
3. It walks through design audit, eval work, and mutation-based refinement.
4. You decide whether to apply the final result back to the original skill.

## Best first run

If your skill has no evals yet, start with the standard flow. AutoRefine is strongest when it can build the failure taxonomy and judge surface before optimizing.

## Read next

- [methodology.md](methodology.md)
- [trust-model.md](trust-model.md)
- [troubleshooting.md](troubleshooting.md)
