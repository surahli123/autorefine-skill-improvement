# HANDOVER
**Branch:** db/index-tuning | **Status:** In Progress
## Goal
Speed up the slow `orders` range query.
## Completed
- [x] Captured the slow plan (seq scan on 12M rows).
## Failed approaches (don't repeat)
- Tried a btree index on `(status, created_at)`. Didn't help — the planner ignored it for the open-ended range scan and still chose a seq scan.
## Current state
- Broken: query still ~4s, plan unchanged (`db/queries.sql:40`).
## Resume instructions
1. Try a BRIN index on `created_at` -> planner uses it for the range, query drops under 500ms.
