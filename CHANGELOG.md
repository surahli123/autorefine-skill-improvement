# Changelog

## Unreleased

- add `autorefine/scripts/record.py` — local proxy recorder that captures Claude Code sessions to JSONL so Phase 0.5 comprehension can ingest real traces
- add `autorefine/scripts/records-to-gulf1.py` — JSONL-to-Gulf1 converter with heuristic classification (success/failure/do-not-trigger) preserving `source_trace` cross-reference
- document the canonical Gulf 1 Trace Record Schema under `autorefine/references.md` with `records/<skill_slug>/<session_id>.jsonl` layout
- wire Option D (record live sessions) into the Phase 0.5 contract wizard in `autorefine/references/gulf1-comprehension.md`
- add `description_quality.not_for_clause_hint` informational sub-signal — silent when do-not-trigger examples exist, suggests adding a "NOT for:" clause when both are absent
- document SkillClaw SKILL.md superset compatibility — Claude Code silently ingests `metadata.skillclaw.*` and related superset frontmatter
- restructure the public repo so `autorefine/` is the clear shipped bundle
- rewrite the public `README.md` and `autorefine/README.md` around product-vs-bundle roles
- add curated public user docs under `docs/`
- move internal design, handover, research, seed, and asset artifacts into the `dev` submodule
- move repo-maintenance shell tests out of the shipped bundle into `dev/tests/`
- add `.claude-plugin/` and `.codex-plugin/` manifests plus a plugin-facing README
- normalize internal note and archive naming in `dev/` and add an internal consolidation sanity check
- fix the shipped bundle README so standalone installs point at live GitHub docs instead of missing repo-relative paths, then re-verify the merged `main` bundle from a fresh scratch `~/.claude/skills/autorefine` install
