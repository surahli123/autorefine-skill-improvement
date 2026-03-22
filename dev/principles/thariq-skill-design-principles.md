# Thariq's Skill Design Principles (Synthesized)

Source: "Lessons from Building Claude Code: How We Use Skills" (2026-03-17, 42.5K bookmarks)

## The 9 Skill Categories

Every skill should fit cleanly into ONE of these. If it straddles several, it's probably too broad.

1. **Library & API Reference** — How to use a library/CLI/SDK. Include gotchas and reference code snippets.
2. **Product Verification** — How to test/verify code works. Pair with external tools (Playwright, tmux). "Worth having an engineer spend a week making verification skills excellent."
3. **Data Fetching & Analysis** — Connect to data/monitoring stacks. Include credentials, dashboard IDs, common workflows.
4. **Business Process & Team Automation** — Automate repetitive workflows. Save results in log files for consistency across runs.
5. **Code Scaffolding & Templates** — Generate framework boilerplate. Useful when scaffolding has natural language requirements.
6. **Code Quality & Review** — Enforce org code quality. Can run deterministically via hooks or GitHub Actions.
7. **CI/CD & Deployment** — Fetch, push, deploy code. May reference other skills for data collection.
8. **Runbooks** — Symptom → investigation → structured report. Multi-tool investigation workflows.
9. **Infrastructure Operations** — Routine maintenance with destructive-action guardrails.

## The 10 Skill-Writing Tips

### 1. Don't State the Obvious
Focus on information that pushes Claude out of its normal thinking. Claude already knows how to code — teach it what's specific to YOUR codebase/org.

### 2. Build a Gotchas Section
> "The highest-signal content in any skill is the Gotchas section."

Build from common failure points. Update over time as new failures are discovered.

### 3. Use the File System & Progressive Disclosure
A skill is a FOLDER, not just a markdown file. Use the whole filesystem as context engineering:
- `references/api.md` — detailed function signatures
- `assets/template.md` — output templates to copy
- `scripts/` — composable code
- `examples/` — canonical examples

Tell Claude what files exist and it will read them at the right time.

### 4. Avoid Railroading Claude
Be careful of overly specific instructions. Give Claude the information it needs but flexibility to adapt. Skills are reusable — overspecificity breaks edge cases.

### 5. Think Through the Setup
Skills may need user configuration. Pattern: store setup info in `config.json` in the skill directory. If not configured, agent asks the user. Use `AskUserQuestion` for structured choices.

### 6. The Description Field Is For the Model
> "The description field is not a summary — it's a description of when to trigger."

Claude scans descriptions at session start to decide which skills are relevant. Write descriptions as trigger conditions, not summaries.

### 7. Memory & Storing Data
Skills can include memory by storing data within them:
- Simple: append-only text log or JSON files
- Complex: SQLite database
- Example: standup-post skill keeps `standups.log` so next run shows what changed

Store in `${CLAUDE_PLUGIN_DATA}` for persistence across upgrades.

### 8. Store Scripts & Generate Code
> "One of the most powerful tools you can give Claude is code."

Give Claude composable helper functions so it can spend turns on composition and decision-making rather than reconstructing boilerplate. Claude generates scripts on the fly to compose these functions.

### 9. On-Demand Hooks
Skills can register hooks that activate only when the skill is called and last for the session. Use for opinionated hooks that are too aggressive for always-on:
- `/careful` — blocks rm -rf, DROP TABLE, force-push
- `/freeze` — blocks Edit/Write outside a directory

### 10. Distribution: Repo vs Marketplace
- Small teams: check skills into `./.claude/skills` in the repo
- At scale: internal plugin marketplace with organic curation
- Skills gain traction → owner moves to marketplace
- Warning: easy to create bad/redundant skills, so curate before release

## Key Meta-Insights

- "Most of ours began as a few lines and a single gotcha, and got better because people kept adding to them as Claude hit new edge cases."
- Skills are folders, not files — think of the filesystem as progressive disclosure
- The description is a trigger condition, not documentation
- Verification skills are worth disproportionate investment
- Skills that compose with other skills multiply their value
