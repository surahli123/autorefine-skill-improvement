# Changelog

## Unreleased

- restructure the public repo so `autorefine/` is the clear shipped bundle
- rewrite the public `README.md` and `autorefine/README.md` around product-vs-bundle roles
- add curated public user docs under `docs/`
- move internal design, handover, research, seed, and asset artifacts into the `dev` submodule
- move repo-maintenance shell tests out of the shipped bundle into `dev/tests/`
- add `.claude-plugin/` and `.codex-plugin/` manifests plus a plugin-facing README
- normalize internal note and archive naming in `dev/` and add an internal consolidation sanity check
- fix the shipped bundle README so standalone installs point at live GitHub docs instead of missing repo-relative paths, then re-verify the merged `main` bundle from a fresh scratch `~/.claude/skills/autorefine` install
