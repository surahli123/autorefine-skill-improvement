# HANDOVER
**Branch:** cache/redis | **Status:** Blocked
## Completed
- [x] Stood up the Redis instance; the app connects.
## Failed approaches (don't repeat)
- Tried caching the full user object; serialization blew the 512KB value limit. Error: `OOM command not allowed`.
## Current state
- Broken: writes >512KB fail (`cache.py:55`).
## Resume instructions
1. Cache only the user id + a thin projection.
