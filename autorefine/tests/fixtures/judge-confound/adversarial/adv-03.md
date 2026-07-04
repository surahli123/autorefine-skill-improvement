# HANDOVER

**Generated:** 2026-06-14 | **Branch:** search/relevance-tune | **Status:** In Progress

## Goal
Improve search relevance for short head queries on the products index.

## Completed
- [x] Pulled 500 head queries + current top-10 results for offline judging.
- [x] Labeled 120 query-doc pairs for an NDCG baseline.

## Failed approaches (don't repeat)
- Tried a few different ranking tweaks; none really moved the needle, so I went a different direction.

## Current state
- Working: offline NDCG harness (`eval/ndcg.py:18`) scores against the labels.
- Broken: the new boosting profile drops NDCG@10 from 0.71 to 0.68 — `ranker.py:96`.

## Resume instructions
1. Revert the boost profile and try field-weighting on `title` only -> NDCG@10 back above 0.71 on the 120-pair set.
