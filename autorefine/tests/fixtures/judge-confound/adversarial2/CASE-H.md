# HANDOVER
**Branch:** parser/quotes | **Status:** Blocked
## Goal
Parse CSV fields that contain escaped quotes.
## Notes
Spent the afternoon on this. The naive regex-split approach choked on nested quotes — it raised `ValueError: unbalanced parenthesis` on the third test row — so I'm now leaning on the stdlib `csv` module, which handles quoting natively. Haven't wired it in yet.
## Current state
- Broken: `parse.py:22` still uses the regex.
## Resume instructions
1. Replace the regex with `csv.reader(..., quotechar='"')` -> the nested-quote row parses, no ValueError.
