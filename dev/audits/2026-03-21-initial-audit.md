# Skill Audit — 2026-03-21

## Methodology
Audited 10 most-used skills against v2.0 patterns from Agent Skills for Context Engineering repo.
Calibrated against `context-fundamentals/SKILL.md` as the reference standard.

## Results

| Skill | Gotchas | Voice | Progressive Disclosure | Scripts | Top Fix |
|---|---|---|---|---|---|
| **notebooklm** | PARTIAL | INSTRUCTIONAL | NO | NO | Add `Read when:` triggers; upgrade scripts |
| **eval-harness** | PARTIAL | MIXED | NO | N/A | Dedicated Gotchas section; fix voice |
| **agent-harness** | PARTIAL | INSTRUCTIONAL | NO | N/A | Dedicated Gotchas section |
| **backend-patterns** | NO | DESCRIPTIVE | NO | N/A | Full rewrite — weakest skill (0/4) |
| **verification-loop** | NO | INSTRUCTIONAL | NO | N/A | Add Gotchas section |
| **wrapup** | NO | INSTRUCTIONAL | NO | N/A | Add Gotchas section |
| **markitdown** | PARTIAL | INSTRUCTIONAL | NO | N/A | Reframe limitations as Gotchas |
| **security-review** | NO | MIXED | NO | N/A | Add Gotchas; fix voice |
| **autonomous-loops** | PARTIAL | INSTRUCTIONAL | NO | N/A | Reframe anti-patterns as Gotchas |
| **calibrate** | NO | INSTRUCTIONAL | NO | N/A | Add Gotchas section |

## Summary

| Dimension | At Standard | Partial | Missing |
|---|---|---|---|
| Gotchas | 0/10 | 5/10 | 5/10 |
| Voice | 6/10 instructional | 2/10 mixed | 1/10 descriptive |
| Progressive Disclosure | 0/10 | 0/10 | 10/10 |
| Composable Scripts | 0/1 applicable | 0 | 1 (notebooklm) |

## Top 5 Fixes (Priority Order)

1. **`backend-patterns`** — Full rewrite from descriptive to instructional. Score: 0/4.
2. **Add `## Gotchas` to all skills** — Zero have a dedicated section. Focus: verification-loop, wrapup, calibrate, security-review.
3. **Add `Read when:` triggers** — Universal gap across all 10 skills.
4. **Fix voice in `eval-harness` and `security-review`** — Both drift between instructional and textbook.
5. **Upgrade `notebooklm` scripts** — Only skill with Python; none composable.

## Fix Status

- [x] Fix 1: backend-patterns full rewrite (2026-03-21) — voice + 8 Gotchas + progressive disclosure
- [x] Fix 2: Gotchas for verification-loop (7), wrapup (6), calibrate (7), security-review (7) (2026-03-21)
- [x] Fix 3: Progressive disclosure triggers — notebooklm (7), autonomous-loops (6), agent-harness (7), markitdown (5), eval-harness (6) (2026-03-21)
- [x] Fix 4: Voice fix for eval-harness (6 passages) + 7 Gotchas (2026-03-21)
- [ ] Fix 5: notebooklm script composability — deferred to future session
