# Codex GPT-5.5 (pro/xhigh) — Bitter Lesson Harness Audit — 2026-07-06
# Dispatched via handoff-codex; run_id 0706-cx-02-bitter-lesson-audit
# Fable verification: BL-02/04/05/09/10/13 spot-checked against repo — ALL CONFIRMED (see session record)

# AutoRefine Bitter Lesson Audit

Read-only audit. I did not edit files, run tests, or touch git/gh state.

## 1. PRINCIPLES CHECKLIST

1. **Behavior evals beat prompt control.** Durable harness value should live in ground truth, fixtures, validators, metrics, and replayable artifacts, not in exact prose instructions.
2. **Invariants are allowed.** Keep isolation, holdout protection, irreversible-action gates, provenance, and audit trails. These are environment/safety constraints, not model micromanagement.
3. **Do not freeze wording.** A stronger model should pass by preserving or improving behavior, not by emitting old labels, old JSON fields, or old rationale phrasing.
4. **Let strategy improve with the model.** Routing, decomposition, mutation shape, and search topology should be chosen by the agent under constraints, not hardcoded as today’s best workflow.
5. **More compute should buy more quality.** The harness should scale through more candidates, more samples, wider search, repeated judging, parallel branches, and adaptive stopping.
6. **Thresholds should be calibrated, not magical.** Fixed constants are acceptable defaults only when backed by uncertainty estimates and overrideable budget/statistical policy.
7. **Schemas should replace hydration prose.** State recovery should be enforced by typed schemas/validators and generated docs, not long markdown litanies the model must remember.
8. **Holdout stays sacred.** Train/dev/test/holdout boundaries, final-only access, stable input IDs, and anti-leak checks are model-agnostic and should remain hard gates.
9. **Human knowledge can be evidence, not steering law.** Prior lessons, meta-learnings, and curated examples should be optional research/eval material unless behavior-level evidence proves transfer.
10. **Replay incidents at the behavior level.** Frozen historical failures are valuable eval assets; freezing the exact repair wording is the anti-pattern.

## 2. VIOLATION AUDIT

| id | location | human knowledge encoded | why it inhibits stronger models | severity | disposition |
|---|---|---|---|---|---|
| BL-01 | `autorefine/SKILL.md:42-69`; `runs/.../p0_val.jsonl:1-12` | Eleven enumerated `scenario_family` / `required_action` / `phase` / `stop_reason` decisions. | Converts situational judgment into label matching; better models cannot choose a safer equivalent action unless it matches the frozen table. | BLOCKER-for-scaling | RESTRUCTURE |
| BL-02 | `docs/plans/...v3-plan.md:128-132`; `R4_VERDICT.md:3-14,16-24` | Darwin guard freezes Decision Contract and Phase 7 wording against an R4 Claude Sonnet snapshot. | Protects measured behavior, but makes one model’s routing sensitivity the contract. | BLOCKER-for-scaling | RESTRUCTURE |
| BL-03 | `autorefine/SKILL.md:71-98,200-221` | Quick/Standard/Deep plus fixed Gulf routing file map. | A stronger agent is forced through old phase topology instead of selecting the smallest sufficient eval/search path. | MAJOR | THIN |
| BL-04 | `gulf1-comprehension.md:283-293,314-330` | Exactly five skill patterns, exactly one primary pattern, six fixed audit dimensions, pattern-specific bypasses. | Forbids hybrid or novel classifications; locks eval design to a hand taxonomy. | MAJOR | THIN |
| BL-05 | `gulf2-specification.md:33-35`; `references.md:1467-1472` | Fixed “3 dimensions,” “30-40 total,” and train/dev/test/holdout percentages. | Sample size and split policy cannot adapt to task risk, budget, or model capability. | MAJOR | RESTRUCTURE |
| BL-06 | `autorefine/SKILL.md:111-147`; `references.md:14-90`; `test_run_context_recovery_contract.sh:1-18,48-82` | State hydration field litany duplicated across markdown and grep tests. | Makes correctness depend on prose recall; every new state field expands prompt burden. | MAJOR | RESTRUCTURE |
| BL-07 | `test_phase6_confound_hardening_contract.sh:1-8,49-72`; `test_phase7_edit_budget_contract.sh:10-12,43-96`; `test_input_set_identity.sh:1-4,37-122`; `test_trust_gate_contract.sh:1-4,33-52` | Grep-based prose tripwires locking exact strings. | Penalizes harmless wording improvements and can pass without runtime behavior. | MAJOR | RESTRUCTURE |
| BL-08 | `gulf1-comprehension.md:397-414,442-448,536-548`; `gulf2-specification.md:131-141`; `references.md:1531-1536,5975-5988` | Hand-tuned error-rate, TPR/TNR, sample-count, false-pass/false-fail bars. | Fixed constants replace adaptive statistical confidence and task-specific calibration. | MAJOR | RESTRUCTURE |
| BL-09 | `gulf3-generalization.md:56,61-77,174-223`; `references.md:26-27` | Default `max_edits=3`, one mutation per experiment, “textual learning-rate bound.” | Caps the size of useful rewrites; stronger models may need larger coherent changes. | MAJOR | THIN |
| BL-10 | `gulf3-generalization.md:58,112-124` | Challenger mode is exactly three lanes, one winner, fixed lane names. | Search topology is hardcoded instead of scaling with compute or uncertainty. | MAJOR | RESTRUCTURE |
| BL-11 | `references.md:3111-3192` | Research intake caps: 4 sources, 2 per kind, 12 patterns, 8 mutation leads; no auto-discovery. | Prevents compute-backed literature/tool search from improving candidate quality. | MAJOR | THIN |
| BL-12 | `gulf1-comprehension.md:321-330`; `references.md:71-83` | Pattern and strategy state become hard routing truth; missing/mismatch stops instead of allowing re-evaluation. | Stronger models cannot repair bad classification except by restarting old classifier. | MAJOR | RESTRUCTURE |
| BL-13 | `R4_VERDICT.md:3-14`; `docs/plans/...v3-plan.md:73-78`; `R4-T5/portability_prompt.txt:1` | Sonnet-specific repairs; systematic non-Claude regression gates deferred; cross-model spot-check is informational. | Harness quality is calibrated to one frontier model’s quirks. | BLOCKER-for-scaling | RESTRUCTURE |
| BL-14 | `gulf3-generalization.md:183-197,223-225,291` | Circuit breaker and closeout floors: 3 discards, >80%, 5pp, >15pp swing, `max(sample_count,5)`. | Encodes today’s intuition about plateau/noise rather than learned stopping policy. | MINOR/MAJOR | THIN |
| BL-15 | `gulf2-specification.md:133-139`; `test_judge_confound_replay.sh:1-12,53-104` | Confound incident handled partly by prose mandates. | The incident is real, but the durable part should be fixture replay and validator logic, not “Step 4b” wording. | MAJOR | RESTRUCTURE |
| BL-16 | `references.md:2657-2672`; `eval-search-metric.py:128-185,239-249` | Domain metric default thresholds and weight multiplier. | Primary oracles are right; fixed pass/concern weights should be calibrated from data. | MINOR | THIN |
| BL-17 | `autorefine/SKILL.md:145`; `gulf3-generalization.md:62,292`; `docs/plans/...v3-plan.md:286-300` | Curated meta-learnings steer mutation via `actionable_entry_ids`. | Stores what past humans discovered as future model steering law. | MAJOR | PARK/RESTRUCTURE |
| BL-18 | `campaign_planning.py:1-14`; `campaign_readiness.py:1-18`; `gate_pack.py:1-16`; `docs/plans/...v3-plan.md:271-284` | Campaign/gate-pack orchestration family. | Extra process scaffolding with public carrying cost; plan already marks it deletion-bound. | MINOR/MAJOR | DELETE |

### Per-item detail

**BL-01 — Decision Contract enumeration.** Observed: `SKILL.md` requires “exactly one JSON object” with fixed keys and enumerated values (`autorefine/SKILL.md:42-52`), then maps concrete situations to exact fields (`:58-69`). The frozen fixture output mirrors those exact labels (`p0_val.jsonl:1-12`). Inference: this is the clearest Bitter Lesson violation because it captures “how today’s model should decide” rather than the invariant outcome.

**BL-02 — Darwin guard.** Observed: v3 requires rerunning frozen R4 measurement for sensitive wording and stopping on any flip (`docs/plans/...v3-plan.md:128-132`). R4 says the repair was measured on “Claude Sonnet Agent” and fixed Sonnet variance by adding inline wording (`R4_VERDICT.md:3-14,22-24`). Honest tension: it is the best eval asset in the repo, but it is currently a wording freeze. Convert it to behavior-level replay.

**BL-03 to BL-05 — Fixed pipeline and taxonomy.** Observed: Quick/Standard/Deep routes, fixed Gulf routing, exactly one pattern, fixed phase sequence, and fixed split ratios are all explicit (`SKILL.md:71-98,200-221`; `gulf1:283-293`; `gulf2:33-35`). Inference: keep the phase names as documentation if useful, but the controller should choose work from uncertainty, evidence gaps, and budget.

**BL-06 and BL-07 — Prose as runtime contract.** Observed: state recovery is a long field list in `SKILL.md` and `references.md`, and tests assert those strings exist (`SKILL.md:111-147`; `references.md:14-90`; `test_run_context...:16-18`). Several tests explicitly say they are prose/schema assertions and not runtime proof (`test_phase7_edit_budget...:10-12`). Inference: this is expensive to carry and blocks wording simplification.

**BL-08, BL-14, BL-16 — Magic constants.** Observed: activation thresholds, token/tool caps, TPR/TNR targets, trust-gate thresholds, and domain metric defaults are numeric constants (`gulf1:397-414,442-448`; `references.md:1531-1536,5975-5988,2657-2672`). Inference: defaults are fine, but the pass/fail policy should compute uncertainty and adapt to sample size/task risk.

**BL-09 and BL-10 — Compute caps.** Observed: Phase 7 defaults to `max_edits=3`, hypothesizes “ONE change,” and permits exactly three challenger lanes (`gulf3:56,61-77,58`). Inference: this prevents the Sutton-friendly path where more compute becomes more search and better candidates. Keep edit budgets as a user-settable regularizer, not as the default architecture.

**BL-11 and BL-17 — Human-curated knowledge as steering.** Observed: Research Intake is capped and explicit-curation only (`references.md:3153-3165,3181-3192`), and meta-learnings can steer mutation via parsed/actionable entries (`SKILL.md:145`; `gulf3:62`). Inference: treat these as optional evidence corpora; only promote them to steering if behavior evals prove transfer.

## 3. WHAT TO KEEP

- **Workspace copy protection.** Preflight copies into `[workspace]/skill-under-test/` and says all later writes avoid the original (`autorefine/SKILL.md:16-28`). Session Close has an explicit apply-back gate (`gulf3-generalization.md:288`). Keep.
- **Holdout isolation.** Phase 4 creates `adversarial_holdout` hidden until Session Close and blocks overlap (`gulf2-specification.md:35`). Session Close explicitly separates final-only holdout evaluation from mutation scoring (`gulf3-generalization.md:271,290`). Keep as hard invariant.
- **Stable input identity.** `Input Set Identity Schema` hashes inputs, reuses IDs, and forbids renumbering (`references.md:566-596`); version comparison hard-fails mismatched corpora (`references.md:626-648`). Keep.
- **Final trust artifact.** The final holdout runner uses a dedicated artifact and keeps trust promotion out of top-level state (`references.md:5820-5844,5974-5992`). Keep, but calibrate thresholds.
- **Deterministic/domain evals.** Search metric scoring computes NDCG/recall with per-query evidence (`eval-search-metric.py:1-14,128-205`). The pure regression library declares no filesystem I/O/state mutation (`search_family_regression.py:1-13`). Keep.
- **Confound fixture replay.** The shortcut-judge incident is real and captured in data-shape fixtures without an LLM call (`test_judge_confound_replay.sh:1-12,53-104`). Keep the fixture package; replace prose locks around it.
- **Human gates.** Gulf 2 waits for approval (`gulf2-specification.md:143-148`), Phase 7 exposes user verdict overrides (`gulf3-generalization.md:227`), and apply-back asks before touching originals (`gulf3:288`). Keep.
- **Primary-oracle adapters.** Search adapters require ranked `doc_id` identity and prevent explanation prose from replacing task success (`gulf2-specification.md:45-64,105-107`). Keep the oracle boundary.

## 4. UPGRADE PLAN

**Target end-state architecture**

- `autorefine/SKILL.md` becomes a thin launcher: preflight, workspace isolation, budget knobs, invariant summary, and pointers to executable validators/controllers.
- `references.md` stops being the controller. Split it into generated schema docs, rationale docs, and archived historical notes.
- Decision Contract becomes an invariant policy API: situations are test fixtures; pass condition is safe/valid behavior, not exact `scenario_family` wording.
- Darwin guard becomes “Darwin behavior eval”: keep frozen R4 fixtures, but accept any output that preserves safety, phase boundary, holdout protection, and required evidence.
- Prose-tripwire tests become behavior/property tests. Grep tests can remain only as docs-lint for anchors that are generated from schemas.
- Phase 7 becomes adaptive search: given budget, run N candidate strategies in parallel, score on dev, estimate noise, widen/narrow search, then holdout only at final close.

**Migration order**

1. **Classify contracts.** Mark every rule as `invariant`, `default_policy`, `historical_rationale`, or `deprecated`. Only `invariant` remains blocking.
2. **Convert Darwin first.** Reuse R4 fixtures as behavior oracles. Preserve old exact-match scores as a report column, not as the pass condition.
3. **Extract schemas.** Move `state.json`, `iteration_state`, `edit_budget`, split policies, trust gates, and mutation artifacts into JSON Schema/Python validators. Generate docs from those.
4. **Replace grep tests.** For each prose tripwire, write one executable validator or fixture replay. Keep the confound replay; remove the requirement that exact phrases like `Step 4b` survive.
5. **Thin the routing.** Replace Quick/Standard/Deep fixed flows with a controller that asks: what evidence is missing, what budget exists, what invariant gates apply?
6. **Make search scale.** Generalize challenger lanes from exactly three to budgeted candidate generation. Let “from scratch,” simplification, deletion, and targeted edits compete under the same eval.
7. **Calibrate thresholds.** Replace `<30%`, `0.05`, `95/95`, false-pass bars, and edit counts with defaults plus confidence intervals/noise estimates.
8. **Cross-model replay.** Run behavior evals across Claude/current frontier/open alternatives. A model-specific failure becomes a compatibility note, not the global wording contract.
9. **Retire campaign/meta steering.** Delete campaign family as planned. Recast meta-learnings as optional research corpus until transfer is proven.

**Regression verification**

- Frozen R4 fixtures still replay, but pass by invariant outcome.
- Holdout access tests remain hard-fail.
- Stable input identity and version-comparison tests remain strict.
- Search adapter metric fixtures remain deterministic.
- Public shell/pytest coverage should prove runtime behavior, not only markdown wording.

## 5. RECONCILIATION WITH v3 PLAN

| unit | verdict | Bitter Lesson read |
|---|---|---|
| U4 Headroom Advisory + Noise Gate | PROCEED-MODIFIED | Good direction: exposes low headroom/noise (`docs/plans/...v3-plan.md:205-220`). Modify: do not hard-freeze `<30%`, `threshold + noise_floor`, or `0.05` as prose constants; implement adaptive/statistical behavior tests. |
| U5 Scratch-Only Headroom Screen | PROCEED-MODIFIED | Scratch-only source protection is correct (`:222-236`). Modify: fixed candidate pool, 8-10 fixtures, and 30% graduation should be a preregistered screen default, not a reusable law. |
| U6 Slop and Orphan Cleanup | PROCEED-MODIFIED | Deletion-biased cleanup aligns with the end-state (`:238-253`). Modify: use this as the first thinning pass; Darwin should run as behavior replay, not wording freeze. |
| U7 Public Test Residuals | PROCEED | Moves toward honest eval surfaces by removing false-green/private public tests (`:255-269`). |
| U8 Campaign Family Deletion | PROCEED | Directly deletes orchestration scaffolding with no live consumer (`:271-284`). Strong Bitter Lesson alignment. |
| U9 Meta-Learnings Seed | PARK | As written, it adds curated human discoveries as future steering (`:286-300`). Revive only as optional evidence corpus with candidate labels and behavior-proven transfer. |

## 6. TOP 10

1. Decision Contract exact JSON enumeration: highest scaling blocker; converts judgment into label replay.
2. Darwin guard as wording/model-snapshot freeze: best eval asset, worst coupling.
3. Prose-tripwire tests: freeze markdown instead of proving behavior.
4. Fixed Phase 0.5-7 controller: old workflow topology outranks model judgment.
5. One-mutation/edit-budget default: caps coherent stronger-model rewrites.
6. Exact three-lane challenger mode: search is bounded by human taxonomy, not compute.
7. State hydration litany: prompt memory substitutes for schema validation.
8. Hand-tuned thresholds: constants replace uncertainty-aware calibration.
9. Single-pattern classifier and downstream strategy lock: forbids better/hybrid task representations.
10. Meta-learnings as automatic steering: turns past human discoveries into future constraints.

