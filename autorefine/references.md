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

---

## Hamel Integration Details

Read when: `hamel_available` is true in state.json, or user asks about Hamel's eval skills integration.

### Phase 2: eval-audit
If `hamel_available` is true in state.json, invoke the `eval-audit` skill for deeper analysis. It runs the same 6 diagnostics above but with richer heuristics: flags class imbalance in metrics, detects stale analyses, and recommends specific next skills.

**How to invoke:** Provide the eval artifacts (eval-suite.md, results files, fixture paths) as context. The skill produces a structured findings report with problem title, status, explanation, and recommended fix for each diagnostic.

### Phase 3: error-analysis
If `hamel_available` is true, invoke the `error-analysis` skill to structure the review process. Adaptations for skills vs. LLM pipelines:
- Hamel's skill expects ~100 production traces → use 20-25 fixture outputs instead
- Hamel's skill uses LLM-assisted clustering after ~30 traces → use manual clustering (our trace count is smaller)
- Hamel's skill recommends random/stratified/outlier sampling → use fixture diversity instead (we control inputs)
- The core protocol is the same: read every output → judge Pass/Fail → capture root cause (not explanation) → cluster into 5-10 categories → compute failure rates

### Phase 3: generate-synthetic-data
If `hamel_available` is true, use the `generate-synthetic-data` skill to prepare diverse fixtures in Step 1. It generates inputs via dimension-based tuples:
1. Define 3 failure-prone dimensions (e.g., Document Type × Quality Level × Domain)
2. Draft 20 tuples with user feedback
3. LLM generates more tuples, user validates
4. Convert tuples to natural language test inputs
This produces more systematically diverse fixtures than ad hoc generation.

### Phase 4: generate-synthetic-data
If available, use `generate-synthetic-data` for systematic tuple generation. Adaptations for skills:
- Hamel targets ~100 traces → use 30-40 for skills (attention + token pragmatism)
- Hamel's Step 6 says "run through full pipeline" → for session-spanning skills, generate synthetic output fixtures instead (same adaptation as Phase 3)

### Phase 5: write-judge-prompt
If available, invoke `write-judge-prompt` for richer judge prompt engineering. Adaptations: Hamel assumes external API calls → use agent-as-judge instead (the coding agent evaluates inline).

### Phase 6: validate-evaluator
If available, invoke `validate-evaluator` for deeper calibration. Adaptations for skills:
- Hamel targets ~100 labeled examples → use 30-40 for skills
- Hamel recommends Rogan-Gladen correction → skip for skills (not enough data for meaningful correction)
- Hamel recommends bootstrap CI → skip for skills (same reason)
- The core protocol applies: dev iteration → test once → report TPR/TNR

### Phase 7: skill-creator subagents
If skill-creator is available, use its specialized subagents to strengthen the loop:

**Grader** — After each experiment run, dispatch the grader subagent with the eval expectations and skill output. It returns structured pass/fail verdicts with evidence, verifies claims from the output, AND critiques the evals themselves (flags assertions that would pass bad outputs). Provide: expectations list, output files, transcript.

**Comparator** — For rigorous A/B testing between the baseline and mutated skill, dispatch the comparator with both outputs (blinded — it doesn't know which is which). It scores on content + structure rubrics and picks a winner. Use when score deltas are small and you need confidence the mutation actually helped.

**Analyzer** — After the comparator picks a winner, dispatch the analyzer with both skills + transcripts. It explains WHY the winner won and produces prioritized improvement suggestions. Use to inform your next mutation hypothesis.

---

## Smart Sampling Methodology

Read when: Phase 3 active, or user asks about sampling strategy.

### Why 8-10 traces, not all 20+

Full review of all traces provides maximum coverage but creates HITL friction that blocks adoption. 8-10 traces with stratified sampling captures dimension coverage while keeping the review under 30 minutes. The consistency detection mechanism catches cases where the reduced sample introduces contradictory judgments.

### Why lightweight dimensions before Phase 4

Phase 4 defines formal, failure-oriented dimensions (e.g., Session Length x Domain Type x Error Density). But on a first run, Phase 4 hasn't executed yet. The lightweight dimensions in Step 3 (input length, fixture source, planted flaw) are observable without any prior analysis. They're weaker than Phase 4 dimensions but sufficient for first-pass stratification. On re-runs, Phase 4 dimensions automatically take over.

### When to override consistency flags

Not every flag requires changing a verdict. Same-cluster traces can legitimately get different verdicts if one is borderline — e.g., two "short output" traces where one is concise-but-complete and the other is truncated. The flag's purpose is to prompt reflection, not enforce consistency. If the user confirms both verdicts after reviewing, move on.
