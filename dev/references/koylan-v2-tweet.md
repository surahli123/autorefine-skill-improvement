# Source: Koylan v2.0 Skill Rewrite — Tweet + Synthesis

## Original Tweet
- **Author:** Muratcan Koylan (@koylanai)
- **Date:** 2026-03-18
- **URL:** https://x.com/koylanai/status/2034075011779109088
- **Context:** After reading Thariq's "Lessons from Building Claude Code: How We Use Skills"

## Key Quote

> Reading @trq212's "Lessons from Building Claude Code: How We Use Skills" made me rewrite my entire skills repository.
>
> Skills in the repo were "textbooks"; they taught Claude about context engineering. Anthropic and some other industry research suggest that the best skills are "toolboxes," they help Claude do things.
>
> The article also says the highest-signal content in any skill is the Gotchas section.

## What They Changed (v2.0)

1. Rewrote all 13 skills from descriptive ("X is Y") to hybrid instructional voice ("Do X because Y")
2. Added Gotchas sections to every skill (5-9 per skill, experience-derived, specific, actionable)
3. Made all 12 Python scripts composable: `__all__` exports, type hints, `"Use when:"` docstrings, `__main__` demo blocks
4. Added progressive disclosure triggers to all References (`"Read when: [specific condition]"`)
5. Updated the skill template so every future skill gets Gotchas by default

## Community Reactions (High-Signal)

- **@DatisAgent:** "Gotchas show you where the edges are. Most documentation shows the center of the target."
- **@superscribeio:** "The best skills read like post-mortems from someone who already broke the thing you are about to try"
- **@NathanielC85523:** "Toolboxes vs textbooks is the right framing... the instructional voice shift might help with the runtime-invocation step specifically"

## Reference Repo
- **URL:** https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering
- **Stars:** 14.1k
- **Skills:** 13 (context-fundamentals, context-degradation, context-compression, multi-agent-patterns, memory-systems, tool-design, filesystem-context, hosted-agents, context-optimization, evaluation, advanced-evaluation, project-development, bdi-mental-states)
- **Local clone:** installed to `~/.claude/skills/` (all 13 skills)
