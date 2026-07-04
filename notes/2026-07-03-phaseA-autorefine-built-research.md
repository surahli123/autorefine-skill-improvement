# Phase A — What has been built/improved for AutoRefine (research synthesis, 2026-07-03)

Method: inline research (Sonnet subagents hit the session limit at spawn time; reset since).
Sources: CHANGELOG.md, autorefine/SKILL.md (full read), references.md heading map, luban audit
(`reviews/2026-06-14-luban-audit-autorefine.md`), core-value RESULT.md, pitfalls-r2/r3, TODOS.md, MEMORY.

## 1. The shipped bundle (`autorefine/`)

| Piece | Size | Role | Health signal |
|---|---|---|---|
| SKILL.md | 260 lines (dense) | Router: Preflight → Decision Contract → Init/Resume → Gulf routing → Phase 7 → Gotchas | Visible duplication: Phase 7 evidence rules stated twice (L227-231 AND L255-260); hydration paragraphs ~300 words each (luban P1) |
| references.md | 6,106 lines, ~150 sections | Schemas, templates, rubrics, methodology | Luban P1: overload; unknown fraction has no inbound pointer |
| references/gulf1,2,3.md | 565 / 146 / 466 lines | Per-phase procedures (progressive disclosure) | gulf3 flagged 99KB by luban (long lines) |
| lib/ | 21 Python modules | adapters, campaign planning, meta-learnings loader, preference signals, research corpus, extractors, shared text | Several built for lanes now closed (see §3) |
| scripts/ | 8 CLIs | record.py + records-to-gulf1.py (trace capture), build-search-silver / eval-search-metric / eval-search-family-regression (search adapter), run-campaign.py + prepare-gulf-gate-pack.py (campaign orchestrator), render-phase7-status.py | Search + campaign families: no evidence of use in any run since built (2026-04) |
| tests/ | 21 .sh contract + 13 .py (202 cases) | Prose-contract + unit coverage | .sh tests NEVER gated by CI until cut-1 (PR #61, OPEN); 6 had homedir paths (public leak since 04-21) |
| meta-learnings.md | 76 lines | Cross-campaign learning store | EMPTY of real entries — 5 rounds + 2 dogfoods of lessons live in runs/pitfalls-*.md instead (luban "空跑") |
| dashboard.html | Chart.js, renders | Results visualization | Never surfaced in any README |

## 2. Capability timeline (built → status)

- **2026-04:** repo restructure (public bundle vs dev submodule); trace recorder (record.py proxy + converter, Phase 0.5 Option D); SkillClaw frontmatter compat; **campaign orchestrator** (run-campaign.py, gate-pack) — *no subsequent run uses it*; **search adapter family** (silver builder, NDCG/recall runner, family-regression gate) — *no subsequent run uses it*.
- **2026-05:** architecture simplification; edit budget (Phase 7 regularizer, contract-tested); Run Context Recovery consolidation (4 hydration variants → 1 canonical list); v3 P1 (Discard Autopsy + Derived Registry); references.md decoupling via CONTRACT-ANCHOR sentinels (split itself DEFERRED, ADR-0001); lib shared primitives (PR #48).
- **2026-06 (Darwin/SkillOpt lane, R1–R5):** Decision Contract table + v1/v2 eval suites + seed manifests (PR #51-53); AMB-2 + AMB-1 wording repairs applied back (PR #54, #55) — the ONLY optimization the loop ever applied to its own bundle; robust eval 24/24; R5 pilots saturate → **lane CLOSED** (bundle headroom exhausted on 3 surfaces).
- **2026-06-13/14:** ds-writer dogfood → **NEGATIVE**; core-value C-run → **mechanism PROVEN end-to-end** (blind mutation agent discovered+removed injected defect; holdout 3/3 vs 0/3) but **value headroom-bound**; luban audit 74/100 → cut-1 (PR #61 OPEN); cuts 2-4 unexecuted (dev-test CI routing, references.md split, fill meta-learnings).

## 3. Evidence table — what the experiments say about "usable to improve OTHER skills"

| Evidence | Verdict | Implication |
|---|---|---|
| R1 (v1 evals) | baseline 18/18 — saturated | Eval sets saturate on capable models; calibration gate essential |
| R2 (96 variants, dual metric) | blocked_eval_headroom | Fairness-difficulty circularity is structural (pitfall #2) |
| R3/R4 (wording repairs) | 2 real ambiguities fixed, robust 24/24 | Loop CAN fix measured defects; additive > subtractive wording (pitfall r3 #2) |
| R5a/b pilots | 0% drift / 6/6 pass — saturate | Bundle robust on decision-JSON, traces, real execution |
| ds-writer dogfood | NEGATIVE (−0.71 vs control) | Optimizing a strong baseline lowers composite (Goodhart-adjacent) |
| Core-value C-run | KEEP; holdout 3/3 vs 0/3 | Mechanism works; but soft test (obvious reversible defect) |
| **Converged finding** | **value is HEADROOM-BOUND** | 3 data points: loop is sound; measurable value on capable executors requires a target skill with genuine headroom (rare) or a weaker executor (direction C — separate project) |

## 4. Candidates for dead weight / risk (input to Phase B audit — unverified hypotheses)

1. Campaign orchestrator family (run-campaign.py, prepare-gulf-gate-pack.py, lib/campaign_*.py, gate_pack.py) — built 04-24, never used in any recorded run.
2. Search adapter family (3 scripts + search_family_regression.py + adapter schema sections) — built for a search-skill use case that never materialized.
3. Meta-learnings machinery (meta_learnings_loader.py + 4 big schema sections at references.md:3512-3865 + SKILL.md bootstrap paragraph) — mechanism shipped, store empty, never consumed.
4. Research intake stage (research_corpus.py + references.md:3098-3511) — usage unverified.
5. Challenger mode (references.md:4799-5243) — usage unverified.
6. SKILL.md duplicated Phase 7 evidence text (L227-231 vs L255-260) + triple-stated hydration rules.
7. references.md sections with no inbound pointer (needs mechanical scan).
8. Known eval-validity gaps: J1-type rubric gap (no-failure case), saturation trap for strong baselines, adapter integrity assumptions.
9. Open TODOs: cross-model portability gate (armed), fresh adversarial holdout (rescoped/dormant), luban cuts 2-4.
