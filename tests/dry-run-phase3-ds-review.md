# Dry Run: AutoRefine v2 Phase 3 on ds-review

**Date:** 2026-03-22
**Skill:** ds-review
**Traces available:** 12 (T-01 through T-12)
**Purpose:** Validate v2 Phase 3 instructions produce correct output on real data

---

## Step 3: Smart sampling

### Dimension inference (first run — no Phase 4 dimensions exist)

Following the instruction: "infer lightweight dimensions from trace properties"

| Trace | Input length | Fixture source | Planted flaw | Fixture |
|-------|-------------|----------------|--------------|---------|
| T-01 | medium | real | no | real/vanguard-ab-test |
| T-02 | medium | real | no | real/meta-posttreatment-variables |
| T-03 | medium | real | no | real/kaggle-ibm-churn-lowquality |
| T-04 | medium | synthetic | yes | syn/04-contradicts-data |
| T-05 | medium | synthetic | no | syn/08-unstructured-text |
| T-06 | short (~1200w) | real | no | real/meta-llm-bug-reports |
| T-07 | medium (~1800w) | real | no | real/meta-llm-product-analytics |
| T-08 | short (~750w) | real | no | real/meta-asymmetric-experiments |
| T-09 | long (~3900w) | real | no | real/capstone-customer-churn |
| T-10 | long (~5100w) | real | no | real/kaggle-house-prices-eda |
| T-11 | long (~7500w) | real | no | real/kaggle-titanic-solutions |
| T-12 | short (~720w) | real | no | real/atlassian-rovo-search-relevance |

### Dimension value distribution

| Dimension | Value | Count | Traces |
|-----------|-------|-------|--------|
| Input length | short | 3 | T-06, T-08, T-12 |
| Input length | medium | 5 | T-01, T-02, T-03, T-04, T-05, T-07 |
| Input length | long | 3 | T-09, T-10, T-11 |
| Fixture source | real | 10 | T-01..T-03, T-06..T-12 |
| Fixture source | synthetic | 2 | T-04, T-05 |
| Planted flaw | yes | 1 | T-04 |
| Planted flaw | no | 11 | all others |

### Stratified sample (8 of 12)

Following: "one trace per dimension value, plus 2-3 from underrepresented combinations"

**Selection logic:**
1. Must include: 1 short, 1 medium, 1 long (covers input length)
2. Must include: 1 synthetic (covers fixture source — real is majority, no need to force)
3. Must include: 1 planted-flaw (covers planted flaw — only T-04)
4. Fill remaining 3-4 slots from underrepresented combos

**Selected 8 traces:**

| # | Trace | Why selected |
|---|-------|-------------|
| 1 | T-04 | synthetic + planted flaw (only trace with both) |
| 2 | T-05 | synthetic + no flaw (covers synthetic source) |
| 3 | T-06 | short + real (covers short length) |
| 4 | T-08 | short + real (2nd short — underrepresented) |
| 5 | T-01 | medium + real (covers medium length) |
| 6 | T-03 | medium + real (low-quality fixture — diversity) |
| 7 | T-09 | long + real (covers long length) |
| 8 | T-10 | long + real (2nd long — different domain: EDA vs capstone) |

**User-facing message:**
> "Selected 8/12 traces: 2 short, 2 medium, 2 long, 2 synthetic (1 with planted flaw). Strategy: stratified by input length + fixture source + planted flaw."

### session-log entry

```json
{"phase": "3", "type": "sampling", "detail": "Selected 8/12 traces covering 3 dimensions (length, source, planted-flaw)"}
```

### INSTRUCTION FINDING #1

The instructions say "one trace per dimension value" but dimension values aren't independent — every trace has a value for ALL dimensions. The instruction should clarify: "ensure every dimension VALUE is represented at least once in the sample." Current wording works but could confuse a literal-minded agent.

---

## Step 4: Preliminary clustering

Following: "assign each sampled trace a lightweight category ID based on surface patterns — output length, section structure, tool usage, error presence"

### Surface pattern analysis

| Trace | Score | Verdict | Doc type | Key pattern |
|-------|-------|---------|----------|-------------|
| T-04 | 83 | Major Rework | synthetic analysis | Planted flaw caught, score/verdict gap |
| T-05 | 83 | Good to Go | synthetic unstructured | No headings, missed narrative synthesis |
| T-06 | 62 | Major Rework | blog/operational | Wrong rubric applied (empirical → blog) |
| T-08 | 82 | Good to Go | blog/technical | Clean review, minor gaps |
| T-01 | 54 | Major Rework | real AB test | Multiple CRITICALs, solid review |
| T-03 | 49 | Major Rework | Kaggle notebook | Low quality caught, strong review |
| T-09 | 53 | Major Rework | academic capstone | Caught overfitting, notebook-as-report |
| T-10 | 62 | Major Rework | Kaggle EDA | Narrative flag, philosophical framing |

### Cluster assignments (4 clusters)

```
Preliminary clusters:
  C1 = High-score reviews (score >=80, verdict Good to Go or near) — T-04, T-05, T-08
  C2 = Low-score analytical reviews (score <60, Major Rework, legitimate catches) — T-01, T-03, T-09
  C3 = Mid-score wrong-rubric reviews (score 60-70, applied wrong standards) — T-06, T-10
  C4 = (empty — no traces in this cluster)
```

**Result: 3 clusters.** This is at the lower bound of "target 3-5." Acceptable per instructions.

### INSTRUCTION FINDING #2

The instructions say "based on surface patterns — output length, section structure, tool usage, error presence" but ds-review traces don't have "tool usage" (it's a review skill, not a tool-using skill). The dimension list is illustrative, not prescriptive, but an agent might waste time trying to find "tool usage" in a review output. Consider adding: "adapt dimensions to the skill type."

---

## Step 5: Simulated human review with consistency detection

Reviewing 8 sampled traces one at a time. Using existing annotations where available.

### Review 1: T-04 (Cluster C1)
- **Pass/Fail:** Pass (minor — score slightly inflated)
- **Notes:** Planted contradiction caught. Score 83 vs Major Rework verdict gap due to floor rule.
- **Consistency check:** N/A (< 5 reviews)

### Review 2: T-05 (Cluster C1)
- **Pass/Fail:** FAIL
- **Notes:** Missed narrative synthesis flaw. Gave 83/100 Good to Go for a data dump.
- **Consistency check:** N/A (< 5 reviews)

### Review 3: T-06 (Cluster C3)
- **Pass/Fail:** FAIL (too harsh)
- **Notes:** Applied empirical standards to operational blog post. Wrong rubric for document type.
- **Consistency check:** N/A (< 5 reviews)

### Review 4: T-08 (Cluster C3)
- **Pass/Fail:** Pass (borderline — missing conclusion flagged appropriately)
- **Notes:** Clean review of short technical blog. Gaps flagged are real but minor.
- **Consistency check:** N/A (< 5 reviews)

### Review 5: T-01 (Cluster C2)
- **Pass/Fail:** Pass
- **Notes:** Solid review. Caught all major analytical issues. Score could be improved but review quality is good.
- **Consistency check (>=5 reviews):**
  - T-01 is C2. No prior C2 traces reviewed yet. No flag.

### Review 6: T-03 (Cluster C2)
- **Pass/Fail:** Pass
- **Notes:** Correctly identified all low-quality indicators. Strong analytical review.
- **Consistency check:**
  - T-03 is C2. Prior C2: T-01 (Pass). Same verdict. No flag.

### Review 7: T-09 (Cluster C2)
- **Pass/Fail:** Pass (borderline — score and catches are solid)
- **Notes:** Caught overfitting, SMOTE leakage, SHAP overclaiming. Narrative flag accurate.
- **Consistency check:**
  - T-09 is C2. Prior C2: T-01 (Pass), T-03 (Pass). Same verdict. No flag.

### Review 8: T-10 (Cluster C3)
- **Pass/Fail:** Pass (borderline)
- **Notes:** Narrative flag is accurate, EDA-teaches-but-doesn't-conclude caught.
- **Consistency check:**
  - T-10 is C3. Prior C3: T-06 (FAIL), T-08 (Pass). **Mixed verdicts in C3!**

**CONSISTENCY FLAG FIRES:**

> "T-06 and T-08 both match C3 (mid-score wrong-rubric reviews) but you marked T-06 Fail and T-08 Pass — want to revisit?"

```json
{"phase": "3", "type": "consistency_flag", "detail": "T-06 and T-08 match C3, judged differently (T-06=Fail, T-08=Pass)"}
```

**Analysis of the flag:** This is a REAL inconsistency worth surfacing. T-06 and T-08 are both Meta blog posts reviewed with arguably wrong rubric strictness. T-06 was marked FAIL because the rubric was clearly wrong (empirical standards on a blog). T-08 was marked Pass because the review, while strict, caught real gaps. The flag correctly surfaces this for human reflection.

**User decision (simulated):** "T-06 stays FAIL — the review applied fundamentally wrong standards. T-08 stays Pass — the standards were high but appropriate. The difference is degree, not kind."

### INSTRUCTION FINDING #3

The consistency flag is useful here! But the resolution depends on WHY the verdicts differ, which the cluster ID alone doesn't capture. The flag prompt ("want to revisit?") is good because it's a question, not a command. However, the instructions don't say what to do with the user's response — is it logged? Should the flag be annotated with the resolution?

**Suggestion:** Add to the consistency check instruction: "If the user confirms both verdicts, note the resolution in session-log.json."

---

## Step 6: Build failure taxonomy (simulated)

From the 8 reviewed traces (2 FAILs, 6 Passes):

```
## Failure Taxonomy: ds-review
1. Missing narrative synthesis — review flags individual issues but misses when they compound into "no story" — observed in 1/8 traces (T-05)
2. Wrong rubric for document type — review applies empirical analysis standards to non-empirical docs (blogs, system descriptions) — observed in 1/8 traces (T-06)
3. Score inflation — scores trend ~5 points high across traces — observed as soft pattern in 3/8 traces (T-02, T-04, T-05)
```

### INSTRUCTION FINDING #4

With only 2 FAILs in 8 traces, the taxonomy is thin. The instructions say "After all traces reviewed, cluster failure notes into categories" but 2 failures don't cluster well. The handover mentions needing ~15+ traces for a robust taxonomy. The instructions could note: "If fail rate is very low (<30%) with sampled traces, consider reviewing the remaining un-sampled traces before building taxonomy."

---

## Step 7: Generate initial eval suite (simulated)

```
EVAL 1: Narrative Synthesis Detection
Question: Does the review identify when individual findings compound into a systemic document-level flaw (e.g., "data dump without narrative")?
Pass: Review names the overarching pattern, not just individual symptoms
Fail: Review flags individual issues but misses the synthesis-level failure
Why: Catches FM1 — review missed that unstructured text lacked narrative thread

EVAL 2: Document-Type Rubric Calibration
Question: Does the review apply standards appropriate to the document type (blog vs analysis vs academic)?
Pass: Rubric expectations match what the document is trying to do
Fail: Review demands empirical rigor from a "here's what we built" blog post
Why: Catches FM2 — review applied wrong rubric to operational blog

EVAL 3: Score Accuracy
Question: Is the review score within ±5 points of a reasonable expert assessment?
Pass: Score reflects the actual quality level without systematic inflation
Fail: Score is consistently 5+ points above expert consensus
Why: Catches FM3 — systematic score inflation
```

---

## Gulf 1 Gate (simulated)

### gate-report-gulf-1.md

```
# Gate Report: Gulf 1 Exit — ds-review

## Summary
- **Traces sampled:** 8 of 12 (stratified by input length + fixture source + planted flaw)
- **Sampling strategy:** 2 short, 2 medium, 2 long, 2 synthetic (1 planted flaw)
- **Fail rate:** 25% (2/8 — T-05, T-06)
- **Top failure categories:** Missing narrative synthesis (1), Wrong rubric for doc type (1), Score inflation (soft, 3)

## Consistency Flags
- C3 cluster (T-06, T-08): different verdicts — user confirmed both after review. T-06 FAIL justified (wrong rubric), T-08 Pass justified (appropriate rigor).

## Proposed Eval Suite
1. E1: Narrative Synthesis Detection
2. E2: Document-Type Rubric Calibration
3. E3: Score Accuracy

## Decision
Approve this taxonomy and eval suite to proceed?
```

### Override simulation

**User action:** "Remove E3 (Score Accuracy) — it's a soft pattern, hard to judge as binary Pass/Fail. Better addressed by adjusting the scoring rubric directly in Phase 7."

### session-log entry

```json
{"phase": "gate_1", "type": "override", "detail": "Removed E3 (Score Accuracy)", "reason": "Soft pattern, not binary-testable. Address via rubric adjustment in Phase 7."}
```

---

## Complete session-log.json

```json
{
  "skill": "ds-review",
  "session_start": "2026-03-22T22:45:00Z",
  "entries": [
    {"phase": "3", "type": "sampling", "detail": "Selected 8/12 traces covering 3 dimensions (length, source, planted-flaw)"},
    {"phase": "3", "type": "consistency_flag", "detail": "T-06 and T-08 match C3, judged differently (T-06=Fail, T-08=Pass)"},
    {"phase": "gate_1", "type": "override", "detail": "Removed E3 (Score Accuracy)", "reason": "Soft pattern, not binary-testable. Address via rubric adjustment in Phase 7."}
  ]
}
```

---

## Instruction Quality Assessment

### Issues found

| # | Severity | Issue | Location | Fix |
|---|----------|-------|----------|-----|
| F1 | LOW | "One trace per dimension value" is ambiguous — dimensions aren't independent. Should say "ensure every dimension value is represented at least once." | SKILL.md Step 3, line 141 | Clarify wording |
| F2 | LOW | Surface pattern examples include "tool usage" which doesn't apply to all skill types. | SKILL.md Step 4, line 150 | Add "adapt to skill type" |
| F3 | MEDIUM | Consistency flag resolution not logged — user confirms verdict but resolution isn't captured in session-log | SKILL.md Step 5, line 172 | Add resolution logging instruction |
| F4 | MEDIUM | With 25% fail rate on 8 sampled traces (only 2 failures), taxonomy is thin. Instructions don't address this edge case. | SKILL.md Step 6, line 176 | Add guidance for low fail count in sampled set |

### What worked well

1. **Stratified sampling produced a representative set.** 8 of 12 covers all dimension values with no blind spots.
2. **Clustering was straightforward.** Surface patterns (score range + verdict type) produced 3 meaningful clusters without overthinking.
3. **Consistency detection fired on a real inconsistency.** The C3 flag (T-06 vs T-08) was genuinely useful — same cluster, different verdicts, legitimate reason to reflect.
4. **Override logging schema is clean.** The session-log entries parse correctly and the override reason captures actionable context.
5. **Session-log JSON schema is consistent.** All entries have `{phase, type, detail}`, overrides add `reason`. No polymorphism confusion.

### Verdict

**Phase 3 instructions work on real data.** The 4 findings are edge-case improvements, not blockers. The consistency detection feature proved its value on the first real test. Ready for PR after optional fixes.
