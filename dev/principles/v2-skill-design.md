# v2.0 Skill Design Principles

## The Core Shift: Textbook → Toolbox

| Dimension | Textbook (v1) | Toolbox (v2) |
|---|---|---|
| Voice | "X is Y" (descriptive) | "Do X because Y" (instructional) |
| Failure guidance | None or buried | Dedicated **Gotchas** section (5-9 per skill) |
| Scripts | Reference code to read | Composable: `__all__`, type hints, `Use when:` docstrings |
| References | Flat list | **Progressive disclosure**: `Read when: [condition]` |
| Template | No standard for failure modes | Gotchas section required by default |

## The Four Audit Dimensions

### 1. Gotchas Section
- **What:** Dedicated `## Gotchas` section with numbered failure-mode warnings
- **Format:** Each gotcha names the non-obvious failure, explains why it happens, states the consequence
- **Target:** 5-9 gotchas per skill, experience-derived, specific, actionable
- **Why it matters:** "Highest-signal content in any skill" per Anthropic's internal guidance
- **Anti-pattern:** Burying failure modes in "Limitations" or "Troubleshooting" sections without the explicit framing

### 2. Instructional Voice
- **What:** Every directive includes a reason — "Do X because Y"
- **Before:** "Causal forests estimate heterogeneous treatment effects"
- **After:** "Use causal forests when you need CATE estimates across segments because they handle high-dimensional covariates without pre-specifying interactions"
- **Anti-pattern:** Philosophy paragraphs that describe without directing

### 3. Progressive Disclosure
- **What:** References tagged with activation conditions
- **Format:** `- [Resource Name](./path) — Read when: [specific condition]`
- **Why:** Agents load only skill names and descriptions initially; full content loads only when activated
- **Anti-pattern:** Flat reference lists that invite agents to load everything

### 4. Composable Scripts
- **What:** Scripts that agents can import and call, not just read
- **Requirements:**
  - `__all__` exports on each module
  - Type hints on all public function signatures
  - `"Use when:"` as first line of each public docstring
  - `if __name__ == "__main__":` demo blocks
- **Anti-pattern:** Scripts that auto-execute on import (side effects break composability)

## Skill Template (v2.0)

```markdown
---
name: skill-name
description: One-line trigger description — when to activate this skill
---

# Skill Name

## When to Use
[Explicit trigger conditions — not topic adjacency]

## Core Instructions
[Instructional voice: "Do X because Y" throughout]

## Gotchas
1. **[Failure name]** — [What breaks], because [why]. Consequence: [what happens if ignored].
2. ...
(Target: 5-9 per skill)

## References
- [Resource](./path) — Read when: [specific condition]
- [Resource](./path) — Read when: [specific condition]
```

## Continuous Improvement Loop

1. **Use the skill** in real work
2. **Notice failures** — what broke, what was confusing, what was missing
3. **Add Gotchas** — capture each failure as a numbered gotcha
4. **Refine voice** — convert any "X is Y" passages to "Do X because Y"
5. **Tag references** — add `Read when:` triggers as you discover when each reference is actually needed
