# Eval Before Prune

*A counter-position essay for AutoRefine vs Hermes Curator*

*Draft v0.1 — 2026-05-04*

---

## The pitch in one line

Hermes Curator prunes your skill library. AutoRefine evaluates it. The order matters.

---

## The Curator moment

Last week, @Teknium [shipped Hermes Curator](https://x.com/Teknium/status/2049717907664581067) to 2,241 likes and 169 retweets. The pitch: *"Hermes now keeps the skills your self-improvement loop creates."* Every seven days, an autonomous background agent grades the skills in your library, merges duplicates, prunes the ones that don't carry their weight. You wake up to a leaner agent.

It is a beautiful pattern. Agents accumulate skills the way a developer accumulates dotfiles — slowly, carelessly, and never maintained. Curator solves a real problem.

It also has a single critical assumption: **the grading is good enough to act on.**

That assumption is doing more work than the rest of the system combined.

## The receipt

Three days after launch, @BadTechBandit [posted](https://x.com/BadTechBandit/status/2050588782764671315) the post no shipping team wants to see:

> "Speaking of self healing, how does this differ from newly dropped 'curator' in hermes? It completely butcher all my custom skills"

One user, one anecdote, but the failure mode is structural. When an autonomous loop **deletes** based on its own grading, every false negative is destruction. There is no review queue. There is no pull request. The skill is gone, and "I'll just write it again" is the user's problem.

This is not a Curator-specific bug. It is the same shape as every silent-failure system in software: the system is right *most* of the time, the cost of being wrong is high, and there is no observability into the wrong cases.

## What Curator's grader is doing

Look at how Curator describes its own job: *grade, consolidate, prune.* Three verbs, one feedback loop, one judge. The judge is built into Hermes itself — there's no public eval set, no holdout, no validation that the grader's "this skill is dead weight" verdict actually matches a user's notion of usefulness.

This is fine when the consequence of the verdict is a notification ("hey, you might not need this skill anymore"). It is risky when the consequence is deletion.

In ML terms, Curator is operating on **TPR-only logic**. It's optimizing "find the dead skills." It doesn't measure TNR — *how often does the grader call a useful skill dead?* Without that number, you cannot tell @BadTechBandit's failure from @Kaylee_AI's success. Both are anecdotes. Neither is calibration.

## What "eval before prune" looks like

The fix isn't to ditch Curator. It's to put a more rigorous eval layer in front of it. Before any skill gets pruned:

1. **Multi-judge agreement.** Don't trust one grader. Run two or three judges with different prompts; only act when they agree.
2. **Adversarial holdout.** Hold out 15-20% of the skill's eval cases that the grader has never seen. A skill that scores well on the training distribution but fails on holdout is a skill the grader has overfit to.
3. **Baseline noise floor.** Run the eval on the same skill three times. If runs disagree by more than the noise floor, the verdict isn't trustworthy enough to delete on.
4. **Human spot-check calibration.** Periodically sample the grader's "delete" verdicts and have a human label them. Track grader-vs-human agreement over time. If agreement drops, pause the autonomous prune.

These aren't novel inventions. They're standard ML evaluation discipline that has not yet reached the agent-skill space because the space is too new.

## What AutoRefine adds

AutoRefine is not trying to replace Curator. It's the layer that makes Curator's verdicts trustworthy enough to act on.

- AutoRefine's **trust architecture** (multi-judge, adversarial holdout, baseline noise measurement, human spot-check) is exactly the discipline an autonomous prune step needs *before* it reaches into the user's skill library.
- AutoRefine's **mutation loop** doesn't just rate skills — it tries to *fix* them. A skill the grader wants to delete might be a skill that's one tweak away from useful. Curator can't tell the difference. AutoRefine can.
- AutoRefine's **version control layer** keeps a deletion-safe history. If a prune was wrong, you can roll back to a known-good version of any skill, with the eval scores attached.

The complementary stack:

```
Skill library
     │
     ▼
AutoRefine eval pass — multi-judge, holdout, noise floor
     │
     ├── score is high, agreement is tight   →  KEEP (Curator skips)
     ├── score is low, agreement is tight    →  AutoRefine mutation try
     │       │
     │       ├── mutation rescues the skill   → KEEP improved version
     │       └── mutation fails               → SAFE-PRUNE candidate (Curator can act)
     └── agreement is loose                   → FLAG FOR HUMAN, no autonomous action
```

The phrase that matters: **safe-prune candidate.** Curator should never act on a verdict the eval layer can't stand behind. AutoRefine produces the calibrated verdict.

## Why this is not a Curator critique

Curator is solving a problem nobody else solved. That deserves credit. The risk isn't that Curator is bad — it's that the field is racing toward "autonomous skill management" without a paired commitment to "rigorous skill evaluation," and one without the other is the same failure pattern the recommender-system world spent 15 years learning the hard way.

The lesson from that era: **closed-loop systems eat themselves without independent measurement.** A grader that decides what to keep, and then keeps only what it graded well, will quietly converge toward whatever the grader is biased toward. The skills that survive aren't the useful ones — they're the gradeable ones.

AutoRefine's whole bet is that skill evaluation needs to be a separate, more rigorous, slower-moving layer than skill creation or skill maintenance. Eval before prune. Eval before merge. Eval before deploy.

## What this means for the AutoRefine pitch

For users on Hermes Agent: AutoRefine is the eval layer Curator was missing. Run AutoRefine when you onboard a new skill. Run it again before you trust Curator's verdict on whether to prune it.

For users on Claude Code: AutoRefine is the same eval discipline, with a mutation loop on top, designed for the harness you're already using. Hermes-style skill churn is coming to your stack too. The discipline is portable. The implementation is harness-specific.

For everyone else: when an autonomous loop is about to delete something for you, the right question is not "does it work most of the time?" The right question is "what's the false-negative rate, and what does the rollback path look like?"

That question is the moat.

---

## Appendix: claims to verify before publishing

- [ ] Confirm Curator is actually deletion-based (vs "marked for deletion / quarantine"). The marketing language says "prune" — verify whether v0.12 implementation hard-deletes or soft-deletes.
- [ ] Pull @BadTechBandit's full thread to confirm the failure mode (was it deletion? consolidation? merge collision?).
- [ ] Verify Curator does NOT publish a public eval set or TPR/TNR numbers (the essay's claim relies on this — if they DO publish them, recalibrate the argument).
- [ ] Cross-check @Teknium's launch tweet for any mention of human-in-the-loop / review queue / undo. The essay assumes none exists.
- [ ] Check whether @pbakaus's [Impeccable 2.0 launch](https://x.com/pbakaus/status/2041999176683418064) (536♥, "data-driven skill rewrite, evals across 7 niches") is a closer competitor than skill-eval — separate research note.

## Appendix: distribution plan options

1. **README section** in AutoRefine v4 (low-effort, low-reach, but persistent)
2. **Twitter thread** quoting @Teknium's launch (medium-effort, medium-reach, depends on @Teknium engaging)
3. **Blog post** on personal site, then linked from Twitter (highest-effort, highest-credibility, gives a permalink to cite later)
4. **Reply on @BadTechBandit's tweet** with a link to the essay (lowest effort, opportunistic, signal to people already feeling the pain)

Pick after first review pass.

## Open authorial questions

1. **Is "eval before prune" the right slogan?** Alternatives: "calibrate before delete," "measure before merge," "don't grade what you can't validate." Test 3-4 framings on a friendly reader.
2. **How aggressive should the Curator critique be?** Current draft is gentle ("Curator is solving a real problem"). Could be sharper if positioning AutoRefine as the safety layer. Tradeoff: sharp critique gets more engagement, but @Teknium has 100k+ followers and a sharper version risks turning him into an active opponent rather than a quoted source.
3. **Should the essay include a concrete demo / runnable example?** Currently abstract. A 30-line script that scores three skills and shows agreement-vs-disagreement would make it land harder. But that's prototype work (option 2B), which we deferred.
