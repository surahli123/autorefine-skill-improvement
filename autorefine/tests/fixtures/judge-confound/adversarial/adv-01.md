# HANDOVER

**Generated:** 2026-06-14 | **Branch:** ci/cache-deps | **Status:** In Progress

## Goal
Add dependency caching to CI so builds stop re-downloading packages every run.

## Completed
- [x] Measured baseline: each CI run spends ~3m40s in `npm ci` cold.
- [x] Confirmed the lockfile is committed and stable across the last 20 commits.
- [x] Picked actions/cache@v4 keyed on the lockfile hash.

## Current state
- Working: the cache step is wired into `.github/workflows/ci.yml:31`, uploads on success.
- Broken: nothing broken yet; the cache just hasn't been validated on a cold runner.

## Resume instructions
1. Push a trivial commit, watch two consecutive runs -> second restores the cache and `npm ci` drops from ~3m40s to <30s.
2. Add a cache-miss fallback -> on a lockfile change the run still succeeds (cold install), no red build.

## Setup / env
- No new secrets; uses the default GITHUB_TOKEN.

## Warnings / gotchas
- Cache key must include the OS — a macOS cache restored on ubuntu corrupts node-gyp builds.
