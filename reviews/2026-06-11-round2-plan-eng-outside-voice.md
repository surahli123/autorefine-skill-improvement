# Outside Voice (Codex) — Round 2 plan challenge — 2026-06-11

Invoked by /plan-eng-review Outside Voice step. codex exec, read-only, reasoning=high.
VERIFIED_AGAINST: main @ 4134705 @ 2026-06-11T18:00Z (post eng-review D1-D8 edits)

## CODEX SAYS (verbatim, 14 findings)

1. The plan still has a benchmark-validity problem. It calibrates v2 on `val+test`, then later uses the same v2 test as a regression guard. That makes "test" no longer an untouched test. You need a never-looked-at holdout or stop calling it test.
2. The circularity defense is weak. Fable authors items/oracles, Sonnet verifies them, Sonnet is also the target/scorer channel. That mainly proves Claude-family agreement about Claude-authored interpretations, not objective correctness.
3. The answerability panel batching undercuts independence. Six items per verifier means the verifier can infer category mappings across the batch. For a 30-item benchmark, saving calls is not worth contaminating the fairness check.
4. The calibration loop can sculpt the dataset to the baseline. "Iterate <=3 until 25-45% failure" is benchmark tuning against the exact model channel being measured. The plan needs a frozen authoring rule before scoring, or separate calibration-only items.
5. Workflow runtime is sequenced too late. W0 proves major assumptions about `agent()`, schemas, background execution, kill/resume, args, and null behavior, but T6 comes after v2 data authoring/calibration/PR. Probe the runtime before spending the dataset work.
6. The validator reuse claim is false as written. Current `validate_seed_splits.py` only audits `provider_visible` prompt text against its own oracle; it does not scan workflow script text or arbitrary workspace surfaces. (validate_seed_splits.py:4, :128)
7. The comparator needs more than `--pass-label`. Current `score_decisions.py` skips missing-oracle decisions and denominates by submitted decisions, not expected item set. Missing outputs can distort aggregates instead of failing closed. (score_decisions.py:91, :107)
8. `blocked_budget` is overloaded. Null agent death, schema failure, retries exhausted, and real budget exhaustion are different failure classes. Collapsing them hides runtime reliability problems as budget behavior.
9. "Zero turn boundaries by construction" is overstated. Background execution removes chat nudges, not runtime stalls, quota expiry, session death, journal corruption, or same-session resume limits. The claim should be "no user turn boundary if W0 proves it under comparable duration."
10. The metric target is too small for n=12 val. `+>=2 items` can be noise, especially after channel variance and calibrated difficulty. The plan cites dual-baseline variance but does not define a decision rule if variance is >=2.
11. The plan optimizes against Sonnet while explicitly parking portability. That is strategically questionable for an AutoRefine bundle whose apply-back risk is Claude-specific phrasing. The parent plan already calls this out as a parked risk (2026-06-10 design doc line 58); Round 2 spends heavily before checking whether the metric matters outside Claude.
12. The v2 derivability rule is too narrow. "Oracle fields derivable from shipped `SKILL.md` text" can turn the eval into contract-text lookup. AutoRefine is a shipped bundle, not only `SKILL.md`; memory from this repo also says the target surface is bundle-first.
13. Cap-counting semantics are inconsistent. The plan says every `agent()` call is wrapped, but W-C expects cap=1 and "zero post-gate calls." If Gate is an agent, count it. If Gate is script-only, stop saying "Gate: agent runs `prelaunch_data_gate.py`."
14. The plan has stale state embedded. Preconditions say PR #52 is open, implementation tasks say merged/done. That is a small sign, but in this lane stale status text has already caused bad handoffs.

## Disk arbitration (protocol step 3, against HEAD 4134705)
- Claim 6: TRUE — leak check (5a/5b) scans non-train PROMPTS vs own oracle only; no script/workspace scan exists yet. Plan's "validators reused" wording overstated; D2 edit phrased extension as existing capability.
- Claim 7: TRUE — load_jsonl skips missing-oracle ids with stderr WARNING and continues; aggregates denominate by len(submitted decisions). Fail-open confirmed.
- Claim 13: PARTIAL — "zero post-gate calls" in plan refers to the BUDGET gate (R1 wording), not the data Gate; but the counted-call enumeration ambiguity is real (Gate stage IS an agent call and counts).
- Claim 14: TRUE — P1 says "(OPEN at plan time)" while T1 was edited to "(DONE 2026-06-11)".
