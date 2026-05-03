# Changelog

## Unreleased

- add `autorefine/scripts/render-phase7-status.py` — manual debugging tool that renders a Phase 7 status snapshot from `state.json` + run-dir artifacts to `[workspace]/phase7-status.md`. Pure stdlib; user invokes manually when they get lost mid-run.
- add `autorefine/lib/search_family_regression.py` and `autorefine/scripts/eval-search-family-regression.py` — pure-function library + thin CLI wrapper for per-query-family regression detection on `search_retrieval_v1` paired predictions, reusing the existing `score_predictions` scorer; emits `search_family_regression_v1` JSON with `pass`/`block`/`invalid` status, blocking-family detail, and stable exit codes 0/1/2
- extend the Phase 7 step 2c regression-check contract in `autorefine/references/gulf3-generalization.md` with a search-adapter family-regression sub-step that calls the new gate when `selected_adapter_id = "search_retrieval_v1"`, preserving the existing experiment-0/1 skip rule
- harden the Gulf 1 trace recorder and converter after code-review, TDD, security, and architecture review: HTTP/1.1 streaming, `/v1`-safe upstream joins, auth-header passthrough routing, official HTTPS upstream allowlist, default credential-like scrubbing, basename skill hints, stricter converter validation, and fail-closed output writes with explicit `--force`
- open PR #37 (`fix/autorefine-broken-tests`) for the live-trace capture path, mark it ready for review, resolve the `main` merge conflict, and confirm GitHub reports the PR as mergeable and clean with CI passing
- add `autorefine/scripts/build-search-silver.py` — deterministic synthetic silver-set builder for `search_retrieval_v1` that turns a frozen corpus into `query`/`doc_id`/`grade` rows with query-family split metadata and human-review status
- add `autorefine/scripts/eval-search-metric.py` — dependency-free `NDCG@k` / `recall@k` metric runner for ranked `doc_id` predictions, with per-query evidence and false-pass / false-fail diagnostics
- add Python regression coverage for the search silver-set builder and metric runner, including a live generator-to-scorer integration path and report-count guard for grade-0 hard negatives
- add `autorefine/scripts/run-campaign.py` — Phase 7-only campaign manifest validator, dependency/cluster scheduler, report-only skill adjacency/DRY audit, human-gated Gulf work packets, and plan-only top-level `execution_plan` reporting for prepared AutoRefine workspaces
- add `autorefine/scripts/prepare-gulf-gate-pack.py` — explicit advanced utility for adapter-backed deterministic Gulf 1 / Gulf 2 preauthorization without changing the default plan-only campaign workflow
- document the campaign orchestrator language tradeoff in `plan.md`: Python for V1 contract stabilization, with Rust or TypeScript deferred until the workflow proves useful
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
