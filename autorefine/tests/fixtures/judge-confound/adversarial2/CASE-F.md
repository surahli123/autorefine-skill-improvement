# HANDOVER
**Branch:** feat/healthcheck | **Status:** Done
## Goal
Add a /health endpoint returning build SHA + uptime.
## Completed
- [x] Added the endpoint (`server.py:88`), returns `{sha, uptime_s}`.
- [x] Added a smoke test; passes.
## Failed approaches (don't repeat)
- None — the first approach worked on the first try.
## Current state
- Working: endpoint live, smoke test green.
## Resume instructions
1. Optionally add it to the uptime dashboard -> /health scraped every 30s.
