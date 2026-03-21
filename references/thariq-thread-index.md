# Thariq (@trq212) — Complete Article Index

Claude Code Lead Engineer at Anthropic. Pinned thread from 2026-03-21.

## Articles (ordered by his thread)

| # | Title | Topic | URL | Relevance |
|---|-------|-------|-----|-----------|
| 1 | **Lessons from Building Claude Code: How We Use Skills** | Skill design, types, tips, distribution | [Full article saved](./thariq-skills-article.md) | **PRIMARY** — the definitive guide to skill design |
| 2 | **Lessons from Building Claude Code: Seeing Like an Agent** | Agent design philosophy | [Full article saved](./thariq-agent-building-article.md) | HIGH — agent architecture principles |
| 3 | Prompt Caching | Cost optimization for agent builders | x.com/trq212/status/2024574133011673516 | MEDIUM — relevant if building agents from scratch |
| 4 | Playgrounds | Visual iteration on ideas | x.com/trq212/status/2017024445244924382 | LOW — more for API users |
| 5 | Your Agent Should Use a File System | File-based state management | x.com/trq212/status/1970243253061783669 | HIGH — filesystem-context pattern |
| 6 | Bash Is All You Need | Bash tool for non-coding agents | x.com/trq212/status/1982869394482139206 | MEDIUM |
| 7 | Building Agents with the Claude Agent SDK | Agent SDK guide | claude.com/blog/building-agents-with-the-claude-agent-sdk | MEDIUM |

## Related Articles (External)

| Title | Author | Bookmarks | Saved |
|---|---|---|---|
| **5 Agent Skill Design Patterns Every ADK Developer Should Know** | @GoogleCloudTech | 8.9K | [Full article](./google-5-skill-design-patterns.md) |

The Google article covers 5 structural patterns for skill content design:
1. **Tool Wrapper** — on-demand library context (load references/ when keywords match)
2. **Generator** — enforced consistent output via templates in assets/
3. **Reviewer** — modular rubric in references/review-checklist.md, severity-scored
4. **Inversion** — agent interviews YOU before acting (gating instructions)
5. **Pipeline** — strict sequential workflow with diamond gate checkpoints

Key insight: "Patterns compose. A Pipeline can include a Reviewer step. A Generator can use Inversion to gather variables first."

## Community References (from replies)

- **PrimeLine evolving-lite:** github.com/primeline-ai/evolving-lite — "corrections become rules, experiences become memory, gotchas update automatically"
- **Lendtrain complete-pipeline:** github.com/lendtrain/complete-pipeline — one-shot build pipeline combining Thariq + Boris + Garry gstack
