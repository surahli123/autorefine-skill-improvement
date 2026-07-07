# Codex GPT-5.5 (pro/xhigh) — Sharpen v3 Plan U4-U9 — 2026-07-06
# Dispatched via handoff-codex; run_id 0706-cx-01-sharpen-v3-plan
# Fable verification: key claims spot-checked against repo (references.md:3026/3035, awk anchors, missing test_state_schema_legacy_read.sh, Darwin tooling paths, gulf3 plain-threshold wording) — ALL CONFIRMED

## 1. VERDICT

- U4 — READY-WITH-EDITS: executable now once the exact prose/test edits below are applied; live prose still has the `<20%` WADH drift and plain-threshold keep rule.
- U5 — NOT-READY: owner-gated human/paid screen; handoff says do not start without explicit owner go (`docs/handover-2026-07-06-autorefine-v3-fable-review-feedback.md:32`).
- U6 — READY-WITH-EDITS: pre-clear after U4 only; it must preserve U4’s new `decision_breakdown.margin` / noise-gate wording while removing the existing SKILL duplicate (`autorefine/SKILL.md:227-228`).
- U7 — READY-WITH-EDITS: scope is clear, but one planned file is absent: `autorefine/tests/test_state_schema_legacy_read.sh` was NOT FOUND.
- U8 — READY: target files exist, and active `SKILL.md` / references do not call `run-campaign.py` or `prepare-gulf-gate-pack.py`; only `plan.md:245,251` preserves history.
- U9 — READY: seed sources and loader exist; keep n=1 lessons `candidate`, not actionable, per `autorefine/meta-learnings.md:9-12` and loader actionability rules at `autorefine/lib/meta_learnings_loader.py:907-912`.

## 2. U4 EXECUTION PACKET

### a. Exact prose-edit list

1. `autorefine/references.md`

Current:
- `Gotchas` already uses `<30%`: `5. **High Phase 3 fail rates are healthy.** 60-100% fail = diverse fixtures + rigorous reviewer. <30% = too easy.` (`autorefine/references.md:3026`) — no edit.
- Stale text: `2. **Phase 3 fail rate <20%.** Fixtures too easy or reviewer too generous. Add harder inputs.` (`autorefine/references.md:3035`)

Replace line 3035 with:
```md
2. **Phase 3 fail rate <30%.** Treat this as a `headroom_advisory`, not an automated abort: fixtures too easy / reviewer too generous, or the target may be a genuinely strong target. When fewer than 10 human-reviewed traces support the rate, mark the reading `directional_only` and add harder inputs before trusting the fail-rate signal.
```

Current `decision_breakdown` example omits margin (`autorefine/references.md:1768-1795`) and field list stops at `threshold` / `proposed_decision` (`autorefine/references.md:1801-1804`).

Add to the JSON example after `"threshold": 0.8,`:
```json
  "margin": -0.034,
```

Add field prose after `threshold`:
```md
- `margin`: `combined_score - (threshold + noise_floor)`, where `noise_floor` is the existing root-level baseline-variance summary from `results.json`. A keep requires `combined_score >= threshold + noise_floor`; a kept result with `margin < 0.05` is labeled `borderline`.
```

Current scoring/explainer text names only `decision_breakdown.threshold` and plain keep threshold (`autorefine/references.md:4022-4025`, `4057-4059`, `4066`).

Replace with wording that includes:
```text
aggregate: `decision_breakdown.weighted_points`, `decision_breakdown.total_weight`, `decision_breakdown.combined_score`, `decision_breakdown.threshold`, `decision_breakdown.margin`
keep bar: threshold + noise_floor
margin: combined_score - (threshold + noise_floor)
proposed_decision: keep only when combined_score >= threshold + noise_floor; label kept results with margin < 0.05 as borderline
```

2. `autorefine/references/gulf1-comprehension.md`

Current:
```md
Generate `gate-report-gulf-1.md` with: sample stats, fail rate, categories, consistency flags, proposed evals. Append to session-log.json: `{"phase":"gate_1","type":"gate_decision","detail":"APPROVED"}` (or REJECTED). **Override logging:** if user removes evals or rejects categories, also append: `{"phase":"gate_1","type":"override","detail":"Removed E4","reason":"..."}`
```
(`autorefine/references/gulf1-comprehension.md:556-557`)

Replace with:
```md
Generate `gate-report-gulf-1.md` with: sample stats, fail rate, categories, consistency flags, proposed evals, and a `headroom_advisory` block. If Phase 3 fail rate is <30%, `headroom_advisory` must present both readings: fixtures too easy / reviewer too generous, and genuinely strong target. This is advisory only, never an automated abort. Store `interpretation_mode: directional_only` when `traces_reviewed < 10`; otherwise store `interpretation_mode: decision_grade`. Append to session-log.json: `{"phase":"gate_1","type":"gate_decision","detail":"APPROVED"}` (or REJECTED). **Override logging:** if user removes evals or rejects categories, also append: `{"phase":"gate_1","type":"override","detail":"Removed E4","reason":"..."}`
```

3. `autorefine/references/gulf3-generalization.md`

Current baseline establishes root `noise_floor` from `baseline_trials[]` (`autorefine/references/gulf3-generalization.md:60`), but keep/discard still uses plain threshold wording (`autorefine/references/gulf3-generalization.md:151,170-171,225-227`).

Replace the relevant scoring/verdict sentences with:
```md
The keep/discard rule is noise-gated: a candidate may be proposed as keep only when `combined_score >= threshold + noise_floor`, where `noise_floor` is the existing root-level Experiment 0 baseline-variance summary. Store `decision_breakdown.margin = combined_score - (threshold + noise_floor)` in the same scoring pass. Label any kept recommendation with `margin < 0.05` as borderline in the user-facing explainer and `decision_explanation`.
```

Do not edit `autorefine/SKILL.md` in U4. Its duplicated Phase 7 quick-reference lines are a U6 cleanup target (`autorefine/SKILL.md:227-228`; v3 plan U6 at `docs/plans/2026-07-04-001-fix-autorefine-public-trust-hardening-v3-plan.md:243-245`).

### b. New test file TDD sequence

Create `autorefine/tests/test_gulf1_headroom_advisory_contract.sh`, then run it before prose edits and expect RED; rerun after edits and expect GREEN.

Exact assertions:
```bash
#!/bin/bash
PASS=0; FAIL=0; TOTAL=0
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF="$ROOT/autorefine/references.md"
GULF1="$ROOT/autorefine/references/gulf1-comprehension.md"
GULF3="$ROOT/autorefine/references/gulf3-generalization.md"

assert_contains() { TOTAL=$((TOTAL+1)); printf '%s' "$1" | grep -qF "$2"; r=$?; [ "$r" -eq 0 ] && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "FAIL: $3"; }; }
assert_not_contains() { TOTAL=$((TOTAL+1)); printf '%s' "$1" | grep -qF "$2"; r=$?; [ "$r" -ne 0 ] && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "FAIL: $3"; }; }

WADH="$(awk '/^## When AutoRefine Doesn.t Help/{f=1} /^---$/{if(f){print; exit}} f{print}' "$REF")"
G1_EXIT="$(awk '/^### Gate: Gulf 1 Exit/{f=1} /^---$/{if(f){print; exit}} f{print}' "$GULF1")"
G3="$(awk '/^## Phase 7: AutoResearch Loop/{f=1} /^## Session Close/{f=0} f{print}' "$GULF3")"
DB="$(awk '/^### decision_breakdown fields/{f=1} /^### decision_explanation fields/{f=0} f{print}' "$REF")"
EXPLAINER="$(awk '/^## Aggregation Explainer Template/{f=1} /^---$/{if(f){print; exit}} f{print}' "$REF")"

assert_contains "$WADH" "Phase 3 fail rate <30%" "When AutoRefine Doesn't Help uses <30%"
assert_not_contains "$WADH" "Phase 3 fail rate <20%" "No stale <20% WADH threshold"
assert_contains "$G1_EXIT" "headroom_advisory" "Gulf 1 Exit writes headroom_advisory"
assert_contains "$G1_EXIT" "directional_only" "Gulf 1 Exit marks n<10 directional_only"
assert_contains "$G1_EXIT" "fixtures too easy" "Gulf 1 advisory names easy-fixture reading"
assert_contains "$G1_EXIT" "genuinely strong target" "Gulf 1 advisory names strong-target reading"
assert_contains "$G3" "combined_score >= threshold + noise_floor" "Gulf 3 keep rule is noise-gated"
assert_contains "$G3" "decision_breakdown.margin" "Gulf 3 stores decision_breakdown.margin"
assert_contains "$G3" "margin < 0.05" "Gulf 3 labels borderline margin"
assert_contains "$DB" '"margin"' "references.md decision_breakdown schema includes margin"
assert_contains "$EXPLAINER" "threshold + noise_floor" "Aggregation Explainer shows noise-gated keep bar"

echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
exit "$FAIL"
```

Expected RED before prose edits: failures on stale `<20%`, missing `headroom_advisory`, missing `directional_only`, missing both readings, missing `threshold + noise_floor`, missing `decision_breakdown.margin`, missing `margin < 0.05`, missing schema margin. Expected GREEN after all listed edits.

### c. Darwin guard command packet

R4 root exists with `after_receipt.json`, `controls/`, `decisions/`, `scores/`; no decision-generation runner was found under `runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/`. Fallback is frozen-decision rescoring using `runs/seed-data-v2/tools/score_decisions.py` and `aggregate_robust.py`.

```bash
mkdir -p /tmp/autorefine-u4-darwin-guard
for i in 0 1 2 3 4; do
  python3 runs/seed-data-v2/tools/score_decisions.py \
    --val runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/decisions/p${i}_val.jsonl \
    --test runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/decisions/p${i}_test.jsonl \
    --oracles runs/seed-data-v2/scorer_only/scorer_oracles.jsonl \
    --pass-label r4_p${i} \
    --output /tmp/autorefine-u4-darwin-guard/pass_p${i}.json
done

python3 runs/seed-data-v2/tools/aggregate_robust.py \
  --pass-output /tmp/autorefine-u4-darwin-guard/pass_p0.json \
  --pass-output /tmp/autorefine-u4-darwin-guard/pass_p1.json \
  --pass-output /tmp/autorefine-u4-darwin-guard/pass_p2.json \
  --pass-output /tmp/autorefine-u4-darwin-guard/pass_p3.json \
  --pass-output /tmp/autorefine-u4-darwin-guard/pass_p4.json \
  --oracles runs/seed-data-v2/scorer_only/scorer_oracles.jsonl \
  --pass-label r4 \
  --output /tmp/autorefine-u4-darwin-guard/robust_scores.json

python3 runs/seed-data-v2/tools/score_decisions.py \
  --val runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/decisions/v1_val.jsonl \
  --test runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/decisions/v1_test.jsonl \
  --oracles runs/seed-data/scorer_only/scorer_oracles.jsonl \
  --pass-label v1_r4 \
  --output /tmp/autorefine-u4-darwin-guard/v1_scores.json

python3 runs/seed-data-v2/tools/score_decisions.py --val runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/controls/self_val.jsonl --test runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/controls/self_test.jsonl --oracles runs/seed-data-v2/scorer_only/scorer_oracles.jsonl --pass-label control_self --output /tmp/autorefine-u4-darwin-guard/control_self.json
python3 runs/seed-data-v2/tools/score_decisions.py --val runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/controls/corrupt_val.jsonl --test runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/controls/corrupt_test.jsonl --oracles runs/seed-data-v2/scorer_only/scorer_oracles.jsonl --pass-label control_corrupt --output /tmp/autorefine-u4-darwin-guard/control_corrupt.json
```

Pass bar: robust v2 `12/12` val + `12/12` test, v1 `8/8` val + `10/10` test, self-control `12/12` + `12/12`, corrupt-control `0/12` + `0/12`. Existing receipt records the same bars (`runs/20260613T045832Z-r4-amb1-strengthen/R4-T4/after_receipt.json` exact strings: `"12/12"`, `"8/8"`, `"10/10"`, `"controls": "4/4 PASS"`).

### d. Branch/PR checklist

Current local evidence: branch `main`, `HEAD == origin/main == 6d83d820dde07d790429376153ff62a47c469403`, remote `https://github.com/surahli123/autorefine-skill-improvement.git`, dirty `CONTEXT.md`, `dev`, and untracked notes/reviews.

Executor checklist:
- Start fresh from `origin/main`: `git switch -c fix/autorefine-u4-headroom-noise-gate origin/main`.
- Before edits: record `git status --short`, `git remote -v`, `git rev-parse HEAD`, `git rev-parse origin/main`.
- Stage only:
  - `autorefine/references.md`
  - `autorefine/references/gulf1-comprehension.md`
  - `autorefine/references/gulf3-generalization.md`
  - `autorefine/tests/test_gulf1_headroom_advisory_contract.sh`
- Never stage `dev`; verify with `git diff --cached --name-only` and `git status --short`.
- PR body must include staged-file list, RED/GREEN TDD evidence, public shell sweep, pytest, Darwin guard packet, and explicit “`dev` not staged.”

## 3. PLAN GAPS

- U1-U3 remain written as implementation units in v3, but handoffs say they are already shipped via PR #61/#63; do not replay them (`docs/handover-2026-07-06-autorefine-v3-fable-review-feedback.md:13-16`, `docs/handover-2026-07-04-u3-confound-hardening-shipped.md:9-15`).
- U4 says reconcile both Gotchas and WADH, but Gotchas is already `<30%`; only WADH is stale (`autorefine/references.md:3026,3035`; plan says reconcile at `docs/plans/2026-07-04-001-fix-autorefine-public-trust-hardening-v3-plan.md:211`).
- U4 plan does not list `autorefine/SKILL.md`, yet SKILL’s Phase 7 quick reference still has duplicated threshold-only `decision_breakdown` prose (`autorefine/SKILL.md:227-228`); leave this to U6 or U4 scope widens.
- U7 lists `autorefine/tests/test_state_schema_legacy_read.sh`, but current repo output is `NOT FOUND autorefine/tests/test_state_schema_legacy_read.sh`; executor should treat it as absent, not blocked.
- Darwin guard plan says rerun rooted at R4-T4 (`docs/plans/2026-07-04-001-fix-autorefine-public-trust-hardening-v3-plan.md:128-132`), but R4-T4 contains artifacts/decisions, not the original live decision runner; use frozen rescoring unless that runner is recovered.

## 4. U6-U9 SHARPENING NOTES

- U6: Ambiguity is whether to delete or reword U4’s new margin/noise text during duplicate cleanup; resolution: preserve all U4 `threshold + noise_floor` and `decision_breakdown.margin` wording, then remove only the pre-existing duplicate SKILL lines.
- U7: Ambiguity is the missing `test_state_schema_legacy_read.sh`; resolution: drop that file from the edit target and add the public legacy-read coverage as a new public test if still required.
- U8: Ambiguity is whether `plan.md` historical campaign references block deletion; resolution: no, verify active SKILL/reference consumers only, then record the deletion decision in `plan.md`.
- U9: Ambiguity is whether seeded lessons become active; resolution: n=1 lessons stay `candidate`, and only entries with sufficient support plus approved review may become actionable.

## 5. OPEN RISKS

1. Darwin guard fallback rescoring does not regenerate LLM decisions, so it may miss drift that only appears during live decision generation.
2. U4 edits touch long single-line Gulf 3 prose; a mechanical patch can easily miss one plain-threshold sentence.
3. U6 can accidentally erase U4’s new margin/noise wording if run from the old cleanup checklist.
4. U7 has a missing planned file and private-`dev` test split risk; executor must keep parent `dev` unstaged.
5. U5 remains owner-gated and must not mutate protected source skills.