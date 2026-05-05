# Curator → AutoRefine Transfer Plan

*L3 of the Hermes Curator study. Maps each Curator technique to AutoRefine v3 (current) and v4 (locked design), categorizes as Have / Tighten / Adopt / Skip, and proposes integration points with effort estimates.*

*References:*
- *Curator study: `notes/2026-05-04-hermes-curator-study.md`*
- *v4 design: `dev/docs/design-autorefine-v4-skill-eval-platform.md` (2065 lines)*
- *v3 implementation: `autorefine/SKILL.md`, `autorefine/lib/`*

---

## TL;DR

Of the 15 Curator techniques + 2 study recommendations:

- **3 already covered** by AutoRefine — no action needed
- **5 partially covered** — TIGHTEN with Curator pattern (sharpen what exists)
- **6 real gaps to ADOPT** — concrete v4.0 or v4.1 work items
- **3 SKIP** — wrong fit, different problem space

The biggest single adoption: **a "consolidation pressure" Phase 1 audit dimension** that scores how class-level vs how narrow a skill is. This is a measurable property the Curator prompt treats as gospel and AutoRefine v4 has no equivalent for.

The biggest single tightening: **triple-source classification with hallucination detection on every Keep/Discard verdict**. AutoRefine v3 already has discard autopsy; Curator's pattern of (heuristic + LLM YAML + per-action declared intent) reconciliation, with explicit hallucination rejection when the umbrella doesn't exist, is a noticeable upgrade for the same code path.

---

## Verdict matrix

| # | Curator technique | AutoRefine status | Verdict | Priority |
|---|---|---|---|---|
| 1 | Two-phase eval (deterministic + LLM) | Mixed code+agent evals run together; no gating | 🔧 TIGHTEN | v4.1 |
| 2 | Triple-source classification with reconciliation | Discard autopsy exists; no triple-source / no hallucination check | 🔧 TIGHTEN | **v4.0** |
| 3 | Hallucination detection (post-run state diff) | Mutation loop trusts LLM claims without verification | 🆕 ADOPT | **v4.0** |
| 4 | Umbrella-vs-narrow as Phase 1 dimension | 5-pattern classification exists; no library-level consolidation pressure | 🆕 ADOPT | **v4.0** |
| 5 | Multi-signal activity (view+use+patch) | AutoRefine doesn't track skill usage telemetry | ⏭ SKIP | — |
| 6 | Pre-mutation snapshot (tar.gz, keep=5) | v4 has version registry as derived view; no formal snapshot CLI | 🆕 ADOPT | v4.1 |
| 7 | Reversible reversal | v4 already has non-destructive rollback (better than Curator) | ✅ HAVE | — |
| 8 | Cross-reference reconciliation (cron rewrite) | AutoRefine doesn't orchestrate, it evaluates | ⏭ SKIP | — |
| 9 | Reports per run (run.json + REPORT.md) | results.json + dashboard.html exist; no per-iteration human REPORT.md | 🆕 ADOPT | v4.0 |
| 10 | First-run deferral | No autonomous mode that needs deferral | ⏭ SKIP | — |
| 11 | Anchor on activity, fallback to created_at | Doesn't apply (no library-level grace logic) | ⏭ SKIP | — |
| 12 | Structured YAML required schema | results.json strictly schema'd | ✅ HAVE | — |
| 13 | Force intent declaration at action point | Discard autopsy has reason field, but post-hoc not at-action | 🔧 TIGHTEN | v4.0 |
| 14 | Dry-run banner in-band with prompt | No formal dry-run mode for mutation loop | 🆕 ADOPT | v4.1 |
| 15 | Tool-output truncation in reports (default ON) | reasoning_trace field can grow long; truncation policy unclear | 🔧 TIGHTEN | v4.0 (trivial) |
| A | "Consolidation pressure" Phase 1 audit dimension | Skill pattern classification exists (5 patterns); no library-level dim | 🆕 ADOPT | **v4.0** |
| B | Behavioral validation of merges (Curator gap that AutoRefine fills) | Already AutoRefine's core value prop | ✅ HAVE | — |

---

## ✅ HAVE — already covered

These three need no work; they're either already part of v3 or designed into v4.

### 7. Reversible reversal

Curator: snapshot-before-rollback to allow undoing a rollback.
AutoRefine v4 (Section 4c): "No destructive rollback: Later versions stay in results.json. Rollback creates a branch in the version tree."

**This is a better mechanism than Curator's.** Curator stores actual tar.gz of skill state and restores by extract; AutoRefine treats versions as derived views over experiment records, so rollback is just "use this snapshot path as the new baseline." Branching is implicit; nothing needs to be undone because nothing was overwritten.

Action: none. The v4 mechanism is leaner and more correct for the version-as-derived-view model.

### 12. Structured YAML required schema

Curator: forced `consolidations:` and `prunings:` lists with required fields.
AutoRefine: results.json has strict schema (decision_breakdown, eval_results[], reasoning_trace, evidence[], supporting_items[], etc.) with v4 design enforcing required fields per Section 1a.

Action: none. v4 schemas are already as strict or stricter than Curator's.

### B. Behavioral validation of merges

This is the Curator gap that *makes* AutoRefine valuable, not a thing to adopt. AutoRefine v4's mutation loop already runs evals against fixtures to validate every Keep verdict. That's exactly what Curator can't do.

Action: keep this as the v4 public-positioning lead.

---

## 🔧 TIGHTEN — sharpen what already exists

### 2. Triple-source classification with reconciliation [PRIORITY: v4.0]

**Current state:** v3's Discard Autopsy classifies discards into wrong_target / wrong_params / content_ceiling / eval_drift / data_limitation (per project memory). v4 design Section 1a captures `evidence[]` and `supporting_items[]` linking judge verdicts to outputs.

**Curator's tighter pattern:**
1. Heuristic check (substring / structural verification of the claim)
2. LLM's structured YAML with reason
3. Per-action declared intent at the API call (e.g., `absorbed_into=<X>` argument on the destructive call itself)
4. Reconciler with explicit precedence: (3) > (2) > (1), with hallucination check on (2)

**Application to AutoRefine:**

Every Keep / Discard verdict for a mutation should have three independent signals:
1. **Heuristic** — did the dev-split eval scores actually move in the direction the verdict claims? Did the SKILL.md actually change in the way the verdict claims?
2. **LLM YAML** — what reason did the LLM give in its decision_breakdown?
3. **Per-action declared intent** — when the mutation was committed, what enum-tagged reason was attached? (e.g., a structured `mutation_type=add_section | tighten_voice | remove_redundancy | rewrite_structure` field at the moment of mutation, not in post-hoc analysis)

When all three agree → auto-confirm.
When (2) and (3) disagree → flag in discard autopsy.
When (2) names a fix that (1) can't verify → hallucination — fall back to (1) or default to discard.

**Integration point:** `autorefine/lib/` would need a `verdict_reconciler.py` module that takes the three signals and returns a structured reconciled verdict. Phase 7's keep/discard step would call it. Effort: **small (1-3 days)**. Schema changes to results.json: add `reconciliation_source` field per experiment. Reuses existing decision_breakdown infrastructure.

---

### 13. Force intent declaration at action point [PRIORITY: v4.0]

**Current state:** v3 has discard autopsy with reason fields. v4 design Section 4a's "completion_cadence" tracks experiment finalization with status (baseline / keep / discard).

**Curator's tighter pattern:** the `absorbed_into=<umbrella>` argument is required *on the skill_manage(action='delete') call itself*, not in a post-hoc summary. The model has to commit to intent at the moment of action.

**Application to AutoRefine:**

Every mutation API call (whatever drives the change to SKILL.md or its support files) should require a structured `mutation_intent` argument with at minimum:
- `mutation_type`: enum (add | remove | tighten | rewrite | reorder | restructure)
- `targeted_dimension`: which Phase 1 audit dimension this addresses
- `predicted_score_delta`: the LLM's prediction of how dev-split scores will move
- `predicted_dimension_delta`: same for the targeted dimension

Then:
- `predicted_score_delta` becomes a calibration signal across iterations (track LLM prediction accuracy over time)
- `predicted_dimension_delta` lets the reconciler check if the mutation actually moved the dimension it claimed to target
- The `mutation_type` enum prevents the LLM from hand-waving with "I improved it"

**Integration point:** Tie into the same reconciler from #2. The `mutation_intent` payload becomes the third signal. Effort: **trivial (<1 day)** — schema change + prompt amendment. Pairs naturally with #2.

---

### 1. Two-phase eval (deterministic-first gating) [PRIORITY: v4.1]

**Current state:** AutoRefine runs code-based and agent-as-judge evals together. Both are part of decision_breakdown. There's no "skip the LLM judges if the cheap structural check already says no."

**Curator's pattern:** apply_automatic_transitions() handles 90% of the easy cases (90d unused → archive) without touching the LLM. The LLM only runs for ambiguous middle cases.

**Application to AutoRefine:**

Add a fast deterministic pre-check before the agent-as-judge evals run. Examples:
- Did the SKILL.md actually change? If diff is empty, skip judge evals and return Discard.
- Did any Phase 1 audit dimension's structural marker (e.g., gotchas section presence) change for the worse? If yes, mark as likely-discard before judges run, and apply LLM-as-judge with this prior.
- For mutations that only touch references/templates/scripts (not SKILL.md body), skip dimensions that only target SKILL.md.

This is *not* about replacing judges — it's about skipping wasted judge calls when the answer is already clear.

**Integration point:** New `autorefine/lib/structural_pre_check.py` module called at the top of Phase 7 step 2c (eval scoring). Effort: **small (1-3 days)**. Cost savings probably 15-30% of LLM judge invocations on mutations that don't change SKILL.md body.

---

### 14. Dry-run banner in-band with prompt [PRIORITY: v4.1]

**Current state:** AutoRefine doesn't have a formal autonomous mode. v4 design has `dry_run` mentioned in passing but no equivalent of Curator's `CURATOR_DRY_RUN_BANNER`.

**Curator's pattern:** when running in dry-run, the banner is injected into the prompt itself so the LLM knows it's in dry-run from the prompt. Not a hidden config flag the LLM can't see.

**Application to AutoRefine:**

Less urgent because AutoRefine isn't autonomous in the way Curator is — every mutation requires a human-confirmed Keep gate. But IF a future v4.x ships an autonomous-loop mode (e.g., "run AutoRefine to convergence without checkpoints"), the dry-run pattern is the right way to scope it. Mark as a v4.1 design note.

**Integration point:** None until autonomous mode is on the roadmap. Effort: **trivial (<1 day)** to add when needed.

---

### 15. Tool-output truncation in reports (default ON) [PRIORITY: v4.0, trivial]

**Current state:** v4 design Section 1a's `reasoning_trace` field can hold full judge critiques. results.json could grow to MB scale on long campaigns. Curator caps tool-call args at 400 chars in reports.

**Application to AutoRefine:**

Add a TRUNCATION_LIMIT for `reasoning_trace`, `evidence[].excerpt`, and similar long-form fields when written to dashboard renders. Keep the full version in iteration directories' raw artifacts (where the disk-space cost is local), truncate when copying into roll-up files like results.json or dashboard.html.

**Integration point:** Adjust whatever serializer writes results.json + dashboard.html. Effort: **trivial (<1 hour)** — single TRUNCATION_LIMIT constant + a `_truncate()` helper.

---

## 🆕 ADOPT — real gaps with high value

### A. "Consolidation pressure" Phase 1 audit dimension [PRIORITY: v4.0]

**The biggest single learning from Curator.** Curator's prompt frames its entire job around this question:

> *"Would a human maintainer write this as N separate skills, or as one skill with N labeled subsections?"*

That's a measurable property of a skill, just like "anti-railroading" or "description quality." AutoRefine v4 currently has 5+ Phase 1 audit dimensions (per Section 1d-1f) but no library-level consolidation dimension.

**The dimension specification:**

```markdown
PHASE 1 AUDIT DIMENSION: Consolidation Pressure

Score: low (already a class-level umbrella)
       medium (could fit as a section under existing skills)
       high (this skill should not exist standalone)

Signals:
- Name specificity: contains a PR number, codename, or specific error string → high pressure
- Body breadth: SKILL.md addresses one narrow workflow → medium-high
- Body structure: many short labeled subsections vs one focused workflow → low (already an umbrella)
- Adjacency: are there 2+ skills in the library with the same name prefix or domain? → high pressure
- Reusability: does the skill's core workflow generalize, or is it bound to one situation? → drives score

Output: pressure_score in [0, 1] + identified umbrella candidate (if pressure >= 0.5)
```

**Why it matters:**
- Catches sprawl at design time, before Curator-style cleanup is needed
- Surfaces "this should be a subsection of X" suggestions during AutoRefine's audit pass, not after the library has 100 skills
- Gives AutoRefine a positioning advantage — the eval includes library-level health, not just per-skill quality

**Integration point:** New audit dimension in v4 design Section 1g (or insert as Section 1d.1 since it relates to pattern classification). Phase 1 prompt extension. Effort: **small (1-3 days)** for the dimension definition + scoring rubric + prompt + 5-10 calibration fixtures. Pairs well with Section 1d's pattern classification — high consolidation pressure may suggest the skill should be merged into an existing pattern's umbrella.

---

### 3. Hallucination detection via post-run state diff [PRIORITY: v4.0]

**Current state:** AutoRefine's mutation loop currently trusts LLM claims about what was changed. Discard autopsy is reactive — it's about why a verdict was wrong, not whether the LLM lied about what it did.

**Curator's pattern:** if the LLM says "I merged X into Y" but Y doesn't exist post-run, the heuristic ignores the claim and falls back to substring evidence in tool calls.

**Application to AutoRefine:**

For every mutation the LLM applies:
1. The LLM declares (in mutation_intent — see #13): "I changed `<file_path>` to `<change_type>`"
2. After the mutation is applied, a deterministic post-mutation check runs: did `<file_path>` actually change in a way consistent with `<change_type>`?
3. If the LLM claims `add_section` but no new heading appeared in the diff → flag as hallucination, downgrade verdict to discard, log to discard autopsy.

This is *cheap* and catches a real failure mode (LLM says "I added a gotchas section" but actually just whitespace-changed an existing line).

**Integration point:** New module `autorefine/lib/mutation_verification.py` called between mutation apply and Phase 7 scoring. Effort: **small (1-3 days)**. Schema additions: results.json gains `mutation_verification: {claimed: ..., actual: ..., status: verified | hallucination | partial}`.

---

### 9. Reports per run (run.json + REPORT.md) [PRIORITY: v4.0]

**Current state:** AutoRefine has `results.json` (machine-readable, full campaign) + `dashboard.html` (visualization). No per-iteration / per-experiment human-readable summary.

**Curator's pattern:** every run writes both `run.json` and `REPORT.md` to a timestamped directory.

**Application to AutoRefine:**

Each Phase 7 iteration directory already exists (`runs/<run_id>/iteration_NNN/`). Add a `REPORT.md` per iteration with:
- One-line outcome (Kept | Discarded with reason)
- Score table (eval-by-eval with deltas vs baseline + previous iteration)
- Mutation summary (what changed, in plain English, from the LLM)
- Discard autopsy (if applicable)
- Pointer to the raw artifacts in the same directory

Lets users grep / read campaign history without parsing JSON or opening the dashboard.

**Integration point:** New `autorefine/lib/iteration_reporter.py` module + Phase 7 hook to write REPORT.md after each finalized iteration. Effort: **small (1-3 days)** — straightforward markdown rendering from existing data.

---

### 6. Pre-mutation snapshot CLI surface [PRIORITY: v4.1]

**Current state:** v4 design Section 4 (Version Control) treats versions as derived views over results.json. This is good for non-destructive history. But there's no explicit `autorefine snapshot` / `autorefine rollback` CLI.

**Curator's pattern:** explicit `hermes curator backup` (manual snapshot with reason), `hermes curator rollback --list` (see snapshots), `hermes curator rollback --id <ts>` (restore specific). Fail-soft, keep=5 rolling.

**Application to AutoRefine:**

While the version-as-derived-view model handles most rollback needs, having a CLI surface for explicit "I want to checkpoint here before the next campaign" makes adoption easier. Particularly valuable for:
- Pre-experiment safety checkpoints when running long Phase 7 campaigns
- Manual user-initiated rollbacks ("I changed my mind about v3, go back to v2")
- Disaster recovery if results.json itself is corrupted

**Integration point:** New `autorefine/scripts/checkpoint.py` + CLI subcommands. Could pattern after Curator's `curator_backup.py` directly (it's MIT-licensed). Effort: **medium (1 week)** — CLI surface, manifest format, prune logic, list rendering.

---

### 4. "Consolidation pressure" — see entry A above

(Same item as A; numbering is just a cross-reference for the matrix.)

---

## ⏭ SKIP — wrong fit

### 5. Multi-signal activity (view + use + patch)

This is library-hygiene telemetry, which is Curator's job. AutoRefine evaluates skill *quality*, not *frequency of use*. Different problem space. If AutoRefine ever ships a "skill library hygiene" module separate from its mutation loop, revisit. Otherwise: skip.

### 8. Cross-reference reconciliation (cron rewrite)

AutoRefine doesn't orchestrate skills (Hermes does). When Hermes consolidates skill X into umbrella Y, cron jobs that reference X break. AutoRefine has no equivalent downstream-reference surface. Skip.

### 10. First-run deferral

Only relevant if AutoRefine adds an autonomous loop that runs on a schedule without explicit invocation. Current model is human-invoked per campaign. Skip until that changes.

### 11. Anchor on activity, fallback to created_at

Same as #5 — applies to library-level grace logic, which AutoRefine doesn't have. Skip.

---

## Recommended implementation order

If you ship one batch in v4.0 and one batch in v4.1:

### v4.0 batch (high-leverage, mostly small)

1. **Consolidation pressure Phase 1 dimension** (A) — small (1-3 days), highest single value
2. **Triple-source classification with reconciliation** (#2) — small (1-3 days), pairs with #13
3. **Force intent declaration at action point** (#13) — trivial (<1 day), pairs with #2
4. **Hallucination detection via post-run state diff** (#3) — small (1-3 days), pairs with #13
5. **Reports per run (REPORT.md per iteration)** (#9) — small (1-3 days)
6. **Tool-output truncation** (#15) — trivial (<1 hour)

**Total v4.0 batch:** ~2-3 weeks. All six are additive — they don't change v4's locked architecture, just sharpen it.

### v4.1 batch (more invasive, more design work)

7. **Two-phase eval gating** (#1) — small (1-3 days), but needs profiling first to verify cost-savings claim
8. **Pre-mutation snapshot CLI surface** (#6) — medium (1 week), only worth shipping if users start asking for it
9. **Dry-run banner pattern** (#14) — trivial when needed, but only matters if v4.x adds an autonomous mode

---

## What this transfer plan does NOT change

- The locked v4.0 design (5 layers, 21 components) stays intact
- The 7-phase pipeline stays intact
- The version-as-derived-view model stays (it's better than Curator's tarball model for AutoRefine's use case)
- The trust architecture (multi-judge, holdout, baseline noise) stays — these are AutoRefine's differentiators that Curator doesn't have

What gets *added* is:
- One audit dimension (consolidation pressure)
- One module (verdict reconciler)
- One module (mutation verification)
- One file format (REPORT.md per iteration)
- One enum + struct (mutation_intent at action point)
- One truncation policy

---

## Open questions

1. **Should the consolidation pressure dimension be optional or mandatory?** Mandatory feels right for v4.0 — it's a load-bearing piece of the "skills are a library, not a pile" framing. But it costs ~2 minutes per Phase 1 audit. Profile against existing dimensions before deciding.

2. **Is the "predicted_score_delta" calibration loop worth the complexity?** Tracking LLM prediction accuracy over time is valuable for reasoning about when to trust the model's verdicts. But it adds an analysis surface that doesn't exist today. Ship the field in mutation_intent, but defer the calibration analysis until v4.1+.

3. **Should AutoRefine's reconciler also expose a CLI?** Curator's reconciler is internal — only the report shows the verdict. AutoRefine could expose `autorefine verdict <experiment_id>` to dump the three-source breakdown. Useful for debugging when a Keep/Discard outcome surprises the user. Trivial extra cost. Ship in v4.0.

4. **Do we want AutoRefine to learn from Curator's `agentskills.io` open standard?** Curator works with the agentskills.io manifest format. AutoRefine's eval contract format is currently bespoke. Worth a separate session to evaluate whether conforming to (or contributing to) the open standard would unlock cross-harness portability.

---

## What's next

This file ends the L3 transfer plan. Two natural follow-ups:

1. **Discuss & prioritize** — pick which v4.0 items (1-6) to actually adopt; deprioritize / defer the rest.
2. **Spec the highest-priority item** — most likely the consolidation pressure dimension, since it's the largest single design addition. Convert to a Section 1g design doc that slots into the v4 design, with calibration fixtures and scoring rubric.

Either step takes ~1 hour. Stop here for now and let the user choose.
