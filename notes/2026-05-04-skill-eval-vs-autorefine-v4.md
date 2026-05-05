# 2026-05-04 — skill-eval (Federico Mete) vs AutoRefine v4 — Competitive Read

## TL;DR

**Not a competitive threat to AutoRefine v4. Different scope by an order of magnitude.** skill-eval is a focused npm utility for "did this skill help, yes/no?" point-in-time A/B testing on Gemini CLI. AutoRefine v4 is an improvement platform that audits, evaluates with multi-judge rigor, and runs a mutation loop to generate better skills. The verbal pitches sound similar ("rigorous measurement of skill helpfulness") but the architecture, scope, and target users differ.

**However:** AutoRefine v4 should steal 3-4 small things from skill-eval and explicitly NOT lead its own positioning with overlap-territory language.

---

## Sources

### skill-eval

| Field | Value |
|---|---|
| Repo | `github.com/fede0089/skill-eval` (resolves from t.co shortlink) |
| Author | Federico Mete (Sr Software Eng. Manager @ pedidosya, ex-Mercadolibre, Argentina) |
| Created | 2026-04-18 · last push 2026-04-25 (no activity since launch) |
| Language | TypeScript |
| License | MIT |
| Size | ~5,324 KB |
| Adoption | 2 stars · 0 forks · 0 issues |
| Distribution | `npm install -g @fede0089/skill-eval` (or `npx`) |
| Launch tweet | 59 views, 0 likes, 0 RTs (Apr 25, Spanish) |
| Author profile | 177 followers, 179 lifetime tweets |

### Origin announcement (Apr 25, full text translated from Spanish)

> "I published skill-eval, a tool to validate whether a skill really improves an agent's behavior. Because one thing is for a skill to 'work' in a demo... very different is knowing, with evidence, whether it:
> - **activates consistently**
> - **improves results**
> - **or adds more noise, cost, and context than needed**
>
> skill-eval runs local evals, compares baseline vs with-skill, supports multiple trials, and generates HTML reports with metrics and token usage.
>
> For now it's for Gemini CLI."

### Replies of note (signal of reception)

- @fmontes (133♥, the well-followed author of *"un buen SKILL.md no se escribe, se borra"*): replied "Niceee!!! gracias por compartir." — friendly but not a co-sign on the tool itself
- @charliesbot · @addyosmani thread (May 5, 63♥): federicomete pitched skill-eval as a "more serious way to measure" — the parent thread was about LLM shortcut-taking. No deeper engagement.

---

## The README at a glance

```
                  eval prompt
                       │
               ┌───────▼───────┐
               │   skill-eval  │
               └───────┬───────┘
                       │
           ┌───────────┴───────────┐
      ─ with skill ─          ─ baseline ─
      ┌──────┴──────┐         ┌─────┴──────┐
    agent 1      agent 2   agent 3      agent 4
      │              │         │             │
    judge          judge     judge         judge
      └──────┬──────┘         └──────┬──────┘
             └──────────┬────────────┘
                        │
                     pass@k
```

Two commands, both with `--workspace --skill --agents N --trials K --timeout`:
- `skill-eval trigger` — only checks if the skill dispatched (no judge, no baseline)
- `skill-eval functional` — runs N parallel agents (some with skill, some baseline), LLM judge grades each transcript against `expectations`, output is **pass@k**

Eval format (JSON):

```json
{
  "skill_name": "my-skill",
  "evals": [
    { "id": 1, "prompt": "...", "expectations": "..." }
  ]
}
```

Skill directory layout: `SKILL.md` + `evals/*.json` + optional `evals/config/<runner>/settings.json` per-agent runner config.

Default agent backend: `gemini-cli`. The `[agent]` positional arg suggests it's extensible but the README only documents Gemini.

---

## Direct comparison

| Dimension | skill-eval | AutoRefine v4 |
|---|---|---|
| **Job-to-be-done** | "Did this skill help?" — point-in-time A/B | "How do I make this skill better?" — iterative improvement loop |
| **Output** | pass@k report (HTML + token usage) | Improved skill version + version comparison + dashboard |
| **Architecture** | Single tool, npm package, ~5MB TS | 5-layer platform, 21 components, 2065-line design doc, Python on top of v3 7-phase pipeline |
| **Eval rigor** | Single LLM judge; pass@k over baseline | TPR/TNR validation, multi-judge agreement, adversarial holdout, baseline noise measurement |
| **Skill audit** | None (skill is a black box) | 6+ audit dimensions: anti-railroading, description quality, composability, pattern classification (Tool Wrapper / Generator / Reviewer / Inversion / Pipeline) |
| **Skill mutation** | None | 7-phase mutation loop with discard autopsy + circuit breakers + derived registry |
| **Version model** | None — point-in-time only | Version registry, keep-mutation lineage, comparison view, rollback |
| **Research / learning** | None | External pattern study + cross-campaign meta-learnings |
| **Trust architecture** | None — single judge can game | Trust gate, human spot-check calibration, cross-validation, multi-judge agreement |
| **Multi-harness** | Gemini CLI default; `[agent]` arg theoretically extensible (no docs) | Claude Code primary, RovoDev planned |
| **Distribution** | `npm install -g` | Local repo + workspace skill |
| **Adoption** | 2 ⭐, 0 likes on launch | Pre-release |

---

## Verdict: NOT a competitive threat

Three reasons:

1. **Scope mismatch.** skill-eval answers a yes/no question. AutoRefine v4 answers "now make it better." The mutation loop is the moat.
2. **Adoption is essentially zero.** 2 stars after 2 weeks. 59 views on launch tweet. The author is a strong solo eng manager but not building a community around it.
3. **Different harnesses.** Gemini CLI vs Claude Code. Even if scope overlapped, the user populations don't.

The verbal pitch overlap ("rigorous measurement of skill helpfulness") is real but maps to different products. Same way "rigorous measurement of code quality" describes both linters AND CI-driven mutation testing — they're both real, both legitimate, and they don't compete.

---

## What AutoRefine v4 should steal

### 1. The three-axis pitch (replace "5 layers, 21 components" in marketing)

skill-eval pitches: "Does the skill **activate consistently / improve results / not add noise**?" That's a tighter top-of-funnel hook than AutoRefine v4's architecture-first framing. Use as a README intro / one-liner.

**Concrete suggestion:** Add to AutoRefine v4 README front matter:

> AutoRefine answers three questions about your skill:
> 1. Does it activate when it should — and only when it should?
> 2. Does it improve the agent's results vs the unassisted baseline?
> 3. Does it earn its keep on cost and context, or just add noise?
>
> Then it doesn't stop at the answer — it makes the skill better.

### 2. The trigger vs functional split (first-class activation eval)

skill-eval's `trigger` command is just "did the skill fire?" — no judge, no baseline. AutoRefine v4 bundles activation into description-quality + anti-railroading dimensions. Worth considering a **first-class activation-rate metric** that's exposed independently of the weighted composite, so a user can see "this skill fires 95% of the time it should and 8% when it shouldn't" without parsing the audit dimensions.

### 3. pass@k as an output primitive (alongside weighted score)

skill-eval reports **pass@k** (pass rate over k trials). AutoRefine v4 uses confidence-weighted scoring. pass@k is:
- well-known (HumanEval, etc.)
- naturally captures non-determinism
- easier to explain to users than weighted aggregation

**Concrete suggestion:** v4 dashboard should show pass@k alongside the weighted score. Pure presentation change, no new computation — the data is already in `eval_results[]` × trial count.

### 4. Headless agent CLI orchestration as a validation path

skill-eval drives `gemini` headlessly via shell, in parallel. AutoRefine v4's eval execution is more abstract — it relies on subagent dispatch within Claude Code rather than driving the CLI process itself. **Open question:** can v4 also run headless real-CLI evals end-to-end (Claude Code or RovoDev as a subprocess) for ground-truth validation, the way skill-eval does for Gemini? If not, v4's evals are always one level removed from "does this skill actually help when a fresh Claude Code process runs it." Worth checking the implementation.

---

## What AutoRefine should NOT copy

- **npm distribution** — v4 is intentionally local-first / repo-bundled
- **Single LLM judge** — multi-judge + cross-validation is a v4 differentiator; reverting is a regression
- **Single A/B (skill on vs off)** — v4 needs N-version comparison; the version layer is core
- **Black-box skill treatment** — v4's audit dimensions (pattern classification, anti-railroading, composability) are differentiators

---

## Positioning recommendation

When AutoRefine v4 ships publicly:

1. **Acknowledge skill-eval as a respected predecessor** that solves the *measurement* question for Gemini CLI users. Don't pretend it doesn't exist.
2. **Lead with the mutation loop**, not the eval architecture. The thing skill-eval cannot do is the moat: *"AutoRefine doesn't just tell you if your skill is good — it makes it better."*
3. **Use the three-axis pitch** for the top-of-README hook, then transition to the improvement loop as the differentiator.
4. **Stay specific about Claude Code** as the primary harness. Don't fight on Gemini territory.

---

## Threat reassessment trigger

The above verdict assumes skill-eval stays a solo project. **Re-check if any of these happen:**

- Federico Mete posts a Claude Code adapter for skill-eval (would close the harness gap)
- skill-eval's star count crosses 100 (signals the framing is catching on)
- Anthropic, Google, or a major dev tool features skill-eval in docs/blog
- A second open-source skill-eval competitor emerges with a mutation loop (would compress AutoRefine's moat)

Otherwise, no need to react further.

---

## What this unblocks

This research closes the "is skill-eval competitive with AutoRefine v4?" question with a clear NO. Direction 2 (counter-position vs Hermes Curator) can proceed without re-litigating the v4 design.

The 4 stealable patterns above (three-axis pitch, trigger/functional split, pass@k, headless CLI orchestration) are small enough to fold into v4 implementation without changing the locked design — they're presentation/framing changes plus one open question on real-CLI eval execution.
