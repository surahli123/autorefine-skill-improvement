# Hermes Curator — Skill-Improvement Techniques Study

*Source: `NousResearch/hermes-agent` v0.12.0 (2026-04-30), MIT-licensed. Read the actual implementation, not just the marketing.*

---

## TL;DR

Hermes Curator is more sophisticated than its launch tweet suggests. The grading is single-LLM (no multi-judge / no holdout — the eval-before-prune critique still stands), but the **safety architecture** around the grading is exemplary: pre-mutation snapshots, three-way reconciliation between LLM YAML and tool-call evidence, hallucination detection, fail-closed cron-reference rewriting, and reversible rollbacks. Many of these patterns are directly portable to AutoRefine.

The single biggest learning: **Curator's framing of skill quality as "umbrella vs narrow" is itself a teachable evaluation dimension.** The prompt explicitly says *"a library of class-level instructions beats a pile of narrow skills"* and treats consolidation pressure as a first-class signal. AutoRefine v4 has 6+ audit dimensions but no equivalent. This is a gap.

---

## Architecture in one diagram

```
                       hermes curator (background)
                                  │
              ┌───────────────────┴───────────────────┐
              │           SCHEDULER                   │
              │  • interval_hours ≥ 7d                │
              │  • min_idle_hours ≥ 2h                │
              │  • not paused, enabled                │
              │  • first-run defers one full interval │
              └───────────────────┬───────────────────┘
                                  │
                       ┌──────────▼──────────┐
                       │ snapshot_skills()   │  ← tar.gz, keep=5
                       │ pre-mutation safety │
                       └──────────┬──────────┘
                                  │
        ┌─────────────────────────▼─────────────────────────┐
        │ Phase 1: apply_automatic_transitions() — PURE     │
        │  • active → stale  (30d unused)                   │
        │  • stale → archived (90d unused)                  │
        │  • stale → active  (used again)                   │
        │  • pinned, bundled, hub-installed: SKIP           │
        │  • activity = view + use + patch                  │
        └─────────────────────────┬─────────────────────────┘
                                  │
        ┌─────────────────────────▼─────────────────────────┐
        │ Phase 2: forked AIAgent — LLM consolidation pass  │
        │  • toolset scoped to skills + memory only         │
        │  • prompt: umbrella-building, not duplicate-find  │
        │  • required output: structured YAML +             │
        │    `absorbed_into` arg on every skill_manage(del) │
        └─────────────────────────┬─────────────────────────┘
                                  │
        ┌─────────────────────────▼─────────────────────────┐
        │ Triple-source reconciliation:                     │
        │   1. Heuristic (substring match in tool calls)    │
        │   2. LLM's structured YAML block                  │
        │   3. `absorbed_into=<X>` at delete time           │
        │  ── reconcile, prefer (3) > (2) > (1)             │
        │  ── reject (2) when umbrella doesn't exist        │
        │     (hallucination detection)                     │
        └─────────────────────────┬─────────────────────────┘
                                  │
                       ┌──────────▼──────────┐
                       │ Cron job rewriting  │  ← skill refs follow consolidations
                       │ Reports (run.json + │  ← machine + human formats
                       │   REPORT.md)        │
                       │ State save          │
                       └─────────────────────┘
```

---

## The trust architecture (better than I expected)

| Mechanism | What it does | Where it lives |
|---|---|---|
| **Pre-run snapshot** | tar.gz of skills/ before every mutating pass; keep=5 rolling | `agent/curator_backup.py:209` |
| **Rollback is reversible** | Pre-rollback safety snapshot tagged `pre-rollback to <id>` before extract | `curator_backup.py:565` |
| **Cron reconciliation** | When a skill consolidates, cron jobs referencing it get rewritten to point to umbrella | `curator.py:976` |
| **Hallucination detection** | If LLM names umbrella `Y` but `Y` doesn't exist post-run → reject claim, fall back to heuristic | `curator.py:838` |
| **Triple-source classification** | Heuristic (substring) + YAML block + delete-time `absorbed_into` arg, with explicit reconciliation precedence | `curator.py:748-876` |
| **Pin protection (double)** | Pinned skills bypass curator AND `skill_manage` refuses writes — defense in depth | `curator.py:271` + tool layer |
| **First-run deferral** | First observed run seeds `last_run_at=now` → real run waits one full interval | `curator.py:226-241` |
| **Bundled/hub guard** | Only agent-created skills eligible; bundled/hub explicitly excluded from telemetry too | `curator.py:35` + `tools/skill_usage.py` |
| **Fail-soft snapshot** | Snapshot failure logs at debug, never blocks the run | `curator_backup.py:218` |
| **Atomic state writes** | `tempfile.mkstemp` + `os.replace` for `.curator_state` | `curator.py:96-114` |
| **Tool-call args truncation** | LLM tool-call args >400 chars truncated for reports — keeps reports readable | `curator.py:1636` |
| **Forked agent runtime inheritance** | Provider/model/creds propagate from parent — was a v0.11 bug fix (#16099) | `curator.py:1450-1493` |
| **Scoped toolset on fork** | Memory + skills only — no shell, no web (#16569) | curator init args |

This is mature production code. The Curator team has clearly been bitten by every failure mode — and the comments in the source explicitly cite past incidents as the rationale for each guard.

---

## The 15 techniques worth porting to AutoRefine

Ranked by transferability × value. Source line numbers in `agent/curator.py` unless noted.

### Tier 1 — adopt directly into AutoRefine v4

**1. Two-phase eval (deterministic first, LLM only for ambiguity)**
The cheap pure-function `apply_automatic_transitions()` handles obvious cases (90d unused → archive). LLM only runs for the ambiguous middle. AutoRefine v4's mutation loop is currently LLM-heavy throughout — adding a deterministic pre-pass (e.g., "did the mutation pass deterministic structural checks?") could cut iteration cost.

**2. Triple-source classification with reconciliation precedence**
Curator does NOT trust the LLM's structured summary blindly. It cross-checks with substring matching on tool calls AND requires the LLM to declare intent at the moment of the destructive action (`absorbed_into=<umbrella>` arg on every delete). Three signals, explicit precedence, hallucination detection when they disagree. This is the gold-standard pattern for grounding LLM verdicts. AutoRefine's mutation discard autopsy could adopt the same: heuristic + LLM YAML + per-action declared-intent triangulation.

**3. Hallucination detection via post-run state diff**
"If the LLM said 'I merged X into Y' but Y doesn't exist now → ignore that claim." Cheap deterministic check that catches a real LLM failure mode. AutoRefine should run this on every Phase 7 mutation: did the LLM claim it changed file X? Verify X actually changed.

**4. The umbrella-vs-narrow framing as an eval dimension**
The Curator prompt is essentially a 4,400-character treatise on skill library shape: *"a collection of hundreds of narrow skills where each captures one session's specific bug is a FAILURE of the library — not a feature."* This is a measurable property of a skill library. AutoRefine v4 has Phase 1 audit dimensions (anti-railroading, description quality, composability) but no "consolidation pressure" dimension. **Add one.**

**5. Multi-signal activity (view + use + patch), not just use**
Curator tracks `view_count`, `use_count`, and `patch_count` separately and combines them into `activity_count`. AutoRefine's "is this skill being used?" measurement should similarly multi-signal — a skill that's never invoked but heavily edited tells a different story than one that's invoked often.

### Tier 2 — adopt into AutoRefine when version-control layer ships

**6. Pre-mutation snapshot, fail-soft, keep=5 rolling**
AutoRefine v4's "Version Control Layer" (Section 4 of the design) needs a snapshot mechanism. Curator's pattern is the reference: tar.gz, deterministic id (UTC timestamp + counter), manifest.json with reason/size/file count, prune to keep=N, fail-soft (snapshot failure logs at debug, never blocks). Direct port.

**7. Reversible reversal**
Before any rollback extracts, take ANOTHER snapshot tagged `pre-rollback to <target>`. This means a mistaken rollback is one command away from being undone. AutoRefine version control should ship this from day one.

**8. Cross-reference reconciliation on consolidation**
When Curator merges skill X into umbrella Y, every cron job referencing X gets rewritten to reference Y. The mechanism is surgical (only the `skills`/`skill` fields, all other fields preserved as live state). AutoRefine equivalent: when a skill version supersedes another, eval contracts and downstream callers should auto-migrate. Pattern lives in `cron/jobs.py:rewrite_skill_refs()`.

**9. Reports per run in two formats**
Every Curator run writes `logs/curator/<timestamp>/run.json` (machine, full fidelity) AND `REPORT.md` (human, formatted). AutoRefine v4 has `results.json` and `dashboard.html` — but no one-page human summary per iteration. Add `REPORT.md` to each iteration dir.

### Tier 3 — pattern lessons (less direct, still useful)

**10. First-run deferral**
On first observation, seed `last_run_at=now` so the first real pass waits a full interval. Gives users a grace period to opt out. AutoRefine could adopt this for any autonomous loop step — phase transitions, mutation pass, etc.

**11. Anchor on activity, fallback to created_at**
Prevents new skills from instant-archiving themselves. The general pattern: **always have a sensible fallback for "never observed" cases** so the deterministic phase doesn't punish freshness.

**12. Structured YAML output with required schema**
Curator prompt requires a fenced ```yaml block with `consolidations:` and `prunings:` lists. AutoRefine evals already use structured outputs — but the *required* structure with explicit schema enforcement is worth checking. Look for fields you assume but don't enforce.

**13. Force intent declaration at the destructive action**
Every `skill_manage(action='delete')` call must include `absorbed_into=<umbrella>` or `absorbed_into=""`. The LLM has to commit to a reason at the moment it acts, not in a post-hoc summary. AutoRefine's mutation loop could similarly require: every Keep/Discard verdict carries an enum-tagged reason at the action point.

**14. Dry-run banner in-band with the prompt**
Curator's dry-run mode injects `CURATOR_DRY_RUN_BANNER` at the top of the prompt. The LLM knows it's in dry-run from the prompt itself, not from a hidden config flag. AutoRefine's evaluation prompts should similarly let the model know what mode it's in.

**15. Tool-output truncation in reports (default ON)**
Curator truncates tool-call arguments >400 chars in reports. Prevents giant `skill_manage create` calls from blowing up the report file. AutoRefine reports likely have the same risk; check that long judge reasoning is truncated when persisted to dashboards.

---

## What Curator does NOT do — eval-before-prune critique still stands

Despite the rich safety architecture, Curator's actual quality grading is single-judge:

| Discipline | Curator | AutoRefine v4 design |
|---|---|---|
| Multi-judge agreement | ❌ Single LLM does the consolidation pass | ✅ Multi-judge architecture in v4 design Section 2d |
| TPR/TNR validation of grader | ❌ No public eval set the grader is calibrated against | ✅ Phase 6 cross-validation + Phase 1f description quality eval |
| Adversarial holdout | ❌ Reviews the entire library at once; no held-out test | ✅ 18% holdout (v4 design Section "Holdout Split") |
| Baseline noise floor | ❌ No measurement that a re-run produces the same verdict | ✅ Section 2e: baseline noise measurement |
| Human spot-check feedback | ❌ Reports exist but no looped correction signal back to grader | ✅ Section 2f: checkpoint pause for human interaction batching |
| Skill *quality* eval | ❌ Inferred from name+content+activity (no behavioral measurement) | ✅ Mutation loop runs evals against fixtures |

**Translation:** Curator is excellent at *not breaking things while autonomously rearranging the library*, but it doesn't independently *measure* whether the rearrangement improves agent behavior. That's exactly the gap AutoRefine v4 is built for.

The eval-before-prune essay (`notes/2026-05-04-eval-before-prune-essay.md`) framing remains valid — but the essay's claim that "Curator has no public eval set or TPR/TNR numbers" is now verified, not assumed. Update the essay's "claims to verify" checklist.

---

## Three concrete recommendations for AutoRefine

### 1. Add a "consolidation pressure" audit dimension to Phase 1

The Curator prompt's umbrella-vs-narrow framing is a measurable skill property. A Phase 1 audit dimension could ask:

> "If this skill were placed into a library of similar skills, would a maintainer write it as N separate skills or as one with N labeled subsections? How many existing umbrella skills would it cleanly fit under as a section?"

Score: low (this skill is already an umbrella) → medium (could be a subsection of an existing skill) → high (this skill should not exist standalone).

This would catch the failure mode Curator is built to fight (skill sprawl) at design time, before it accumulates.

### 2. Adopt the triple-source classification reconciliation pattern in the mutation loop

For every Keep/Discard mutation verdict, require three independent signals:
1. **Heuristic check** — did the eval scores actually move in the direction the verdict claims?
2. **LLM structured output** — what reason did the LLM give in its verdict YAML?
3. **Per-action declared intent** — at the moment the mutation was applied, what tag did it carry?

When all three agree, auto-confirm the verdict. When they disagree, surface the disagreement to the discard autopsy. This catches LLM hallucination on "I improved X" claims.

### 3. Ship snapshots + reversible rollback as part of the v4 version control layer

The pattern is small (~700 LoC in Curator's case) and high-value. Specific design choices to copy:
- UTC ISO id with `-NN` suffix for same-second collisions
- `manifest.json` per snapshot with reason, size, counted file
- `keep=5` default, configurable
- Pre-rollback safety snapshot before extract
- Fail-soft (snapshot failure logs at debug, never blocks the workflow)
- Atomic top-level move via tempdir staging
- `.archive/` and telemetry sidecars included so rollback restores complete state

The point: v4's version control layer cannot ship without this. Otherwise an autonomous mutation loop on a skill the user cares about is one bug away from data loss.

---

## Open questions

1. **Does Curator's LLM consolidation pass have any test that verifies the merged umbrella skill actually works?** The prompt requires an `absorbed_into` declaration but I didn't find a behavioral eval that validates the merge produced a working skill. **(Worth a follow-up read of the test suite.)**

2. **What's the cost of a full Curator pass?** The prompt cap is `max_iterations=9999`. A pass that touches 50-100 skills via skill_manage could easily cost $1-5 per run. AutoRefine should compare its own per-run cost projection.

3. **How does Curator handle skills with multi-skill dependencies?** If skill A imports / references / chains into skill B, and Curator archives B, A breaks silently. The cron-reconciliation handles one specific dependency surface; what about other inter-skill links?

4. **Is the `agentskills.io` standard relevant?** The README mentions Curator works with that open standard. AutoRefine should check if there's a portable manifest format already defined that v4's eval contracts could conform to (per the Adam Wathan portability complaint from the earlier research).

---

## Verification checklist for the eval-before-prune essay

These claims should be updated based on this study:

- [x] **CONFIRMED:** Curator has no public eval set or TPR/TNR numbers — the LLM consolidation pass is single-judge, ungated.
- [x] **CONFIRMED:** Curator does not include human-in-the-loop / review queue / undo IN THE WORKFLOW — but it does ship rollback as a CLI command, which is an explicit non-autonomous undo. The essay should distinguish "no review queue between grading and action" (true) from "no undo at all" (false).
- [x] **PARTIALLY CONFIRMED:** Curator IS deletion-based at the directory level — but archival is into `.archive/` not `rm`, so the worst case is recoverable via `hermes curator restore <name>`. The essay should soften "deletion" to "archival" to be technically accurate, but the criticism stands because @BadTechBandit's failure mode (custom skills "butchered") is consolidation, not pruning, and consolidation IS lossy at the SKILL.md level even if the directory survives.
- [ ] **Still need to pull @BadTechBandit's full thread** to confirm the failure mode (consolidation lossiness vs archival vs merge collision).
