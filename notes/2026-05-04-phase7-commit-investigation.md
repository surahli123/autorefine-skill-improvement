# 2026-05-04 — Phase 7 Status Ledger Commit Investigation

## TL;DR

**Do not commit yet.** Open PR #41 (`feature/phase7-status-ledger-v0.5`, your account, OPEN since 2026-05-03) already ships the canonical v0.5 work. The untracked Phase 7 files on the current branch (`codex/autorefine-architecture-review-fixes`) appear to be a **divergent copy** at different paths and different sizes. Committing would duplicate or fork the work — the same failure mode that caused the PR #31/#32 recovery in April.

---

## Evidence

### PR #41 — what's already done

Branch: `feature/phase7-status-ledger-v0.5` · Commit: `e9cdf64` · Status: OPEN

| File | Lines | State |
|---|---|---|
| `autorefine/scripts/render-phase7-status.py` | **479** | NEW |
| `autorefine/tests/test_render_phase7_status_py.py` | **622** (24 tests) | NEW |
| `autorefine/docs/troubleshooting.md` | 30 | NEW |
| `.gitignore` | +9 | MODIFIED |
| `CHANGELOG.md` | +1 | MODIFIED |

PR body explicitly says: rescoped from v1.x after 5 review cycles + 2 codex REVISE verdicts. v0.5 is **manual script only, no SKILL.md integration**. Locked design = `design_phase7_status_ledger_v0.5.md`. The earlier `design_phase7_status_ledger.md` is described as "archived".

### Current branch — what's untracked

Branch: `codex/autorefine-architecture-review-fixes`

| File | Lines | Notes |
|---|---|---|
| `autorefine/scripts/render-phase7-status.py` | **483** | 4 lines DIFFERENT from PR #41's 479 |
| `autorefine/tests/test_render_phase7_status_py.py` | **437** | **185 lines SMALLER** than PR #41's 622 — likely older / fewer tests |
| `docs/troubleshooting.md` | MODIFIED | **WRONG PATH** — PR #41 uses `autorefine/docs/troubleshooting.md` (new file). This branch modifies the repo-root `docs/troubleshooting.md` |
| `CHANGELOG.md` | MODIFIED | Adds a different bullet than PR #41's |
| `design_phase7_status_ledger.md` | 468 | NEW — not in PR #41 (PR calls it "archived") |
| `design_phase7_status_ledger_v0.5.md` | 269 | NEW — PR #41 says this is the locked design |
| `reviews/2026-05-02-phase7-status-ledger-*.md` | 3 files | Review history, not in PR #41 |

### Suspicious noise to NEVER commit

| File | Why exclude |
|---|---|
| `Restricted` | empty 0-byte file (Apr 21 leftover) |
| `reviewer_confirmation_gate` | empty 0-byte file (Apr 21 leftover) |
| `reviewer_confirmation_gate.status` | empty 0-byte file (Apr 21 leftover) |
| `dev/` | **entire nested checkout with its own `.git`** — looks like a worktree or a duplicate clone, not real WIP |

---

## The decision

The user must pick one path. Each has different cleanup work.

### Option A — PR #41 is canonical; abandon the local copy

What this means: PR #41's v0.5 work is the version you (with Claude in a prior session) reviewed 5 times and locked. The local untracked files are stale duplicates from before PR #41 was opened.

Steps:
1. Delete untracked: `render-phase7-status.py`, `test_render_phase7_status_py.py`, `Restricted`, `reviewer_confirmation_gate*`, `dev/` (if confirmed cruft).
2. Keep + commit only the **design markdown + reviews** (`design_phase7_status_ledger.md`, `design_phase7_status_ledger_v0.5.md`, `reviews/2026-05-02-*`) since those documents support PR #41 but aren't in it.
3. Revert CHANGELOG.md / docs/troubleshooting.md changes if they duplicate PR #41's bullets.

### Option B — Local is the next iteration on top of PR #41

What this means: You intentionally improved the script (483 vs 479 lines) and the design after PR #41 was opened.

Steps:
1. Check out `feature/phase7-status-ledger-v0.5`.
2. Cherry-pick or rebase the local changes onto it.
3. Push as updates to PR #41 (not a new branch).

### Option C — Local was an accidental fork (most likely failure mode)

What this means: Codex (or a parallel session) re-did Phase 7 work without seeing PR #41. The 4-line / 185-line size mismatches and the wrong `docs/` path support this.

Steps:
1. Diff `e9cdf64` files against the local untracked versions.
2. Decide which is canonical (probably PR #41 — has more tests, design lock, codex REVISE history).
3. Delete the local copies.

---

## Recommendation

**Option C → consolidate to A.** The 622-vs-437 test count strongly suggests the local copy is older, not newer — PR #41's test file added more coverage. Same with the wrong `docs/` path: PR #41 deliberately put the doc inside `autorefine/docs/` to scope it; modifying repo-root `docs/troubleshooting.md` looks like a regression of that decision.

Safe next step: **diff the two scripts**, confirm PR #41 supersedes, then delete the local untracked Phase 7 implementation files and commit ONLY the design + reviews (which add value PR #41 doesn't have).

---

## Twitter Skills Research — Full Pull

### federicomete `skill-eval` thread (the closest peer to AutoRefine)

> "Awesome feature! I'll give it a try. Btw, I built skill-eval for a skill related problem: having a more rigorous way to measure whether a..."
> — @federicomete, May 04 20:47, 0♥

(Pulled via `twitter -c tweet 2051403267326816331` — only the federicomete tweet + the JackWoth98 parent returned. No deeper replies in thread. Need a follow-up search on @federicomete's profile to find the skill-eval announcement post itself.)

### JackWoth98 — Gemini CLI auto-skill harvesting (parent of federicomete reply)

> "Automatically create Agent Skills from past sessions. Gemini CLI can now comb through past session data and suggest new skills based on..."
> — @JackWoth98, May 04 19:09, **207♥, 24 RT**

Directly relevant to AutoRefine's "harvest skills from traces" angle — Gemini shipped a competing pattern.

### Hermes Agent v0.12 "Curator" — autonomous skill-library maintenance (the headline pattern)

This is the most relevant cluster. Multiple authors converge on the same primitive: **a background agent that grades, merges, and prunes the skill library on a schedule.**

| Author | Likes | Snippet |
|---|---|---|
| @SmelterLabsai | 1 | "v0.12.0 is the Curator release. The headline feature is an autonomous background agent that grades..." |
| @Kaylee_AI_ | 0 | "Curator runs every 7 days to grade, consolidate, and prune your skill library automatically" |
| @JulianGoldieSEO | 27 | "Hermes just learned to maintain itself overnight while you sleep" |
| @kaisiqqqqq | 1 | "Keep your skill list from ballooning: run Hermes Curator (or let it do its weekly pass) to automatically prune/consolidate..." |
| @omkar_builds | 0 | "Autonomous Curator runs every 7 days, grades your skills, merges duplicates" |
| @NexusDailyAI | 2 | "Nous Research dropped Hermes AI Agent V0.12 'The Curator', featuring autonomous memory pruning" |
| @BadTechBandit | 0 | "Curator completely butchered all my custom skills" — counterpoint |

**Pattern signature:** weekly cadence + grade + consolidate + prune.

**Why this matters for AutoRefine:** Hermes Curator is solving the *post-creation* lifecycle (skill library hygiene). AutoRefine targets the *creation/eval* loop. Adjacent, complementary problems. The fact that Curator already shipped suggests:
- Skill-library pruning is not AutoRefine's wedge — leave to Curator.
- Skill-eval / skill-creation IS still open — federicomete's skill-eval is the only public peer found.
- Counterpoint from @BadTechBandit (Curator broke custom skills) suggests autonomous pruning without strong evals is risky — direct opening for AutoRefine's rigor angle.

### Adam Wathan — `.agents/` portability rant (engagement leader)

> "Claude Code not supporting `.agents/` for skills and stuff is annoyingly hostile 🫠"
> — @adamwathan, May 05 02:00, **410♥, 8 RT**

Reply thread (sampled):
- @qudnesa: "everything else supports .claude/skills, so it just makes sense to distribute them as that, definitely hostile"
- @ITangoI: "Claude Code not supporting .agents for skills is very not Effective Altruism of them"
- @koomai (8♥): "Do I need a Connector or Capabilities? Where do skills fit? Naming is bad."
- @_watzon: "even .claude doesn't work for skills half the time anymore. Claude Code is shit software"
- @mylifcc: "pinning agents + skills + hooks all under .claude/ is deliberate — first-party UX over cross-tool portability"
- @jig_corp: "Not supporting .agents/ for skills in Claude Code feels weirdly hostile"

**Theme:** the skill-distribution layer is not standardized. AutoRefine's eval format choice should anticipate this — eval contracts / skill manifests should NOT lock to one harness's directory layout.

### Higgsfield CLI + Marketing Skills (largest engagement)

> "Meet Higgsfield CLI + Marketing Skills... CLI keeps agent spend lean, Skills keep creative output high quality"
> — @higgsfield, May 04 16:59, **1545♥, 178 RT**

Productized "skills as a creative quality layer" — orthogonal to AutoRefine but signals the skills-as-product framing.

### NVIDIA — internal agent skills

> "Internally at NVIDIA, we use cuOpt based agentic workflows with agent skills to optimize our supply chains"
> — @NVIDIAAI, May 04 22:30, **131♥, 22 RT**

Enterprise validation that agent skills is a real production pattern.

### sharbel — top GitHub growth this month

> "Fastest growing GitHub repos this month: 1. NousResearch/hermes-agent (+108.1K stars), 2. forrestchang/..."
> — @sharbel, May 04 06:49, **121♥, 12 RT**

NousResearch/hermes-agent +108K stars in one month is a tell — the skills-as-modular-agent pattern has consumer-grade traction now.

### shopify integration

> "Shopify released a dedicated 'Hermes Agent skill' for Nous Research's open-source AI agent framework"
> — @WesRoth, May 04 11:00, **71♥, 4 RT**

Vendors are publishing skills as integration points — confirms the "skill = SDK" framing.

---

## Synthesis for AutoRefine positioning

| Public skill-tool | Layer | Gap AutoRefine could own |
|---|---|---|
| Hermes Curator | post-creation library hygiene (prune/merge) | doesn't evaluate skill quality before pruning |
| Gemini CLI auto-harvest | extracts skills from past sessions | no rigor on whether harvested skills actually help |
| Higgsfield Skills | curated creative bundle | no eval framework, just human-curated |
| Adam Wathan's portability complaint | distribution format | format is unstandardized — AutoRefine's manifest can be the bridge |
| federicomete skill-eval | "rigorous measurement of skill helpfulness" | direct competitor — investigate further |

**Action:** find federicomete's original skill-eval announcement post (today's was a reply only). That's the closest public peer to AutoRefine and the one to study.
