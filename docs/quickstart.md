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

## Adapter-aware runs

AutoRefine now supports an adapter-aware evaluation path for domains where an LLM judge is not a strong enough proxy for quality.

The lifecycle is:

1. **Suggested**: AutoRefine may suggest an adapter after pattern classification.
2. **Confirmed**: The adapter becomes active only if you explicitly confirm it.
3. **Configured**: AutoRefine writes or restores the adapter config under `[workspace]/domain-eval/`.
4. **Evaluated**: Phase 7 uses the adapter's primary oracle plus secondary judge diagnostics.

Current reference adapters:

- `search_retrieval_v1`
- `code_verification_v1`

If no adapter is confirmed, AutoRefine stays on the LLM-judge-only path.

## Best first run

If your skill has no evals yet, start with the standard flow. AutoRefine is strongest when it can build the failure taxonomy and judge surface before optimizing.

If your skill has a domain-specific metric already available, confirm the adapter when prompted so the mutation loop optimizes against that metric instead of prose quality alone.

## Read next

- [methodology.md](methodology.md)
- [trust-model.md](trust-model.md)
- [troubleshooting.md](troubleshooting.md)
