# AutoRefine References

Read when: user asks "why this order", "why can't I skip to autoresearch", or needs the v2.0 audit rubric.

---

## The Three Gulfs

Why the pipeline follows this order: Comprehension → Specification → Generalization.

### Gulf 1: Comprehension
**Gap:** What you think your skill does vs. what it actually does.
**How to close:** Manual error analysis. Read every output. No automation can close this.
**Must be closed first** — everything downstream depends on it.

### Gulf 2: Specification
**Gap:** What you want your skill to do vs. what your judges actually measure.
**Direct consequence of skipping comprehension.** If you haven't seen real failures, you can't write judges that measure what matters. You'll optimize against a fantasy.

### Gulf 3: Generalization
**Gap:** Test performance vs. real-world performance on unseen inputs.
**This is what AutoResearch addresses.** But only if the first two gulfs are already closed.

### Why You Can't Skip to AutoResearch

Three takes from practitioners who tried:

| Take | Approach | Result |
|------|----------|--------|
| 1 | Pointed AutoResearch at skill. Let it generate inputs, judges, everything. | Scores went up. Skill got worse. Optimized the wrong things. |
| 2 | Used structured input generation (dimensions, personas). Still no manual reading. | Better inputs. But judges still measuring imagined targets. |
| 3 | Read outputs manually. Built failure taxonomy. Wrote judges against observed failures. Then ran AutoResearch. | Actually improved the skill. |

> "If you are not willing to look at some data manually on a regular cadence you are wasting your time with evals." — Hamel Husain

---

## V2.0 Design Audit Rubric

Detailed checklist for Phase 1. Based on Thariq (Anthropic), Koylan (v2.0 rewrite), and Google (5 patterns).

### Dimension 1: Gotchas Section
- **Exists?** Look for a `## Gotchas` heading
- **Count:** Target 5-9 per skill. Under 5 = likely missing failure modes. Over 9 = probably too granular.
- **Quality check for each gotcha:**
  - Names a specific, non-obvious failure (not "be careful with X")
  - Explains WHY it happens (the mechanism)
  - States the CONSEQUENCE if ignored (what breaks)
  - Is experience-derived, not theoretical
- **Example of good gotcha:** "**Dashboard needs HTTP serving.** The dashboard.html fetches results.json via fetch(). Opening the file directly (file://) won't work because of browser CORS restrictions. Serve it: `python3 -m http.server 8080`."
- **Example of bad gotcha:** "Be careful with large files." (No mechanism, no consequence, generic)

### Dimension 2: Instructional Voice
- **Test:** Sample 5-10 directives. Count "Do X because Y" vs. "X is Y" format.
- **At Standard:** >80% instructional
- **Partial:** 40-80% instructional
- **Missing:** <40% instructional
- **Before:** "Causal forests estimate heterogeneous treatment effects"
- **After:** "Use causal forests when you need CATE estimates across segments because they handle high-dimensional covariates without pre-specifying interactions"

### Dimension 3: Progressive Disclosure
- **Folder structure:** Is the skill a folder (SKILL.md + references/) or a single file?
- **Reference tagging:** Do references have `Read when: [condition]` triggers?
- **Why it matters:** Agents load skill descriptions initially; full content only on activation. Flat reference lists invite loading everything, wasting context budget.

### Dimension 4: Composable Scripts (if applicable)
Only score if the skill has Python/JS scripts. Skip if none.
- **`__all__` exports** — prevents namespace pollution
- **Type hints on public signatures** — agents can reason about inputs/outputs
- **`Use when:` docstrings** — agents know when to call each function
- **`if __name__ == "__main__":` blocks** — runnable demos, not just importable code
