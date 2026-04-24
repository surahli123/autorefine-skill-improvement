#!/usr/bin/env python3
"""
records-to-gulf1.py — JSONL trace → Gulf 1 Phase 0.5 Option D converter.

Think of this like an ETL pipeline:
  Extract  → read raw session trace records (JSONL from record.py)
  Transform → classify each turn + reshape into a Phase 0.5 contract example row
  Load      → write output JSONL that Phase 0.5 Option D can ingest directly

Input schema: references.md § "Gulf 1 Trace Record Schema"
Output schema: references.md § "Contract Example Schema"
  (Success Example Row / Failure Example Row / Do-Not-Trigger Example Row)

Usage:
  python autorefine/scripts/records-to-gulf1.py \
    --input records/            # dir of .jsonl files, or a single .jsonl file
    --output gulf1-candidates.jsonl \
    --classify auto             # auto | interactive | none   (default: auto)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ─── Required fields every input record MUST have ───────────────────────────
REQUIRED_FIELDS = ["session_id", "turn", "timestamp", "messages", "response_text", "tool_calls"]

# ─── Optional fields — missing = treat as absent, not an error ───────────────
OPTIONAL_FIELDS = ["skill_hint", "upstream_model", "error"]

# ─── Valid classification labels ─────────────────────────────────────────────
VALID_CLASSES = {"success", "failure", "do-not-trigger", "unclassified"}


# ─── Validation ──────────────────────────────────────────────────────────────

def validate_record(record: dict, filepath: str, lineno: int) -> None:
    """
    Fail loudly if any required field is absent.
    Analogous to a schema check at the top of an ETL pipeline — better to
    blow up early with a clear message than to produce silently wrong output.
    """
    for field in REQUIRED_FIELDS:
        if field not in record:
            # Include exact file path + line number so the user can fix it fast.
            raise ValueError(
                f"[{filepath}:{lineno}] Missing required field '{field}'. "
                f"Every record must have: {', '.join(REQUIRED_FIELDS)}"
            )

    if not isinstance(record["session_id"], str) or not record["session_id"].strip():
        raise ValueError(
            f"[{filepath}:{lineno}] Field 'session_id' must be a non-empty string."
        )

    if (
        not isinstance(record["turn"], int)
        or isinstance(record["turn"], bool)
        or record["turn"] < 1
    ):
        raise ValueError(
            f"[{filepath}:{lineno}] Field 'turn' must be a positive integer."
        )

    if not isinstance(record["timestamp"], str) or not record["timestamp"].strip():
        raise ValueError(
            f"[{filepath}:{lineno}] Field 'timestamp' must be a non-empty string."
        )

    # tool_calls and messages must be lists (not strings, not null).
    for list_field in ("messages", "tool_calls"):
        if not isinstance(record[list_field], list):
            raise ValueError(
                f"[{filepath}:{lineno}] Field '{list_field}' must be a JSON array, "
                f"got {type(record[list_field]).__name__!r}."
            )

    if not isinstance(record["response_text"], str):
        raise ValueError(
            f"[{filepath}:{lineno}] Field 'response_text' must be a string, "
            f"got {type(record['response_text']).__name__!r}."
        )


# ─── Auto-classification heuristics ─────────────────────────────────────────

def classify_auto(record: dict) -> tuple[str, str, str]:
    """
    Apply three heuristic rules (in priority order) to guess whether a turn is
    a success, failure, or do-not-trigger example.

    Think of these like business rules in a labeling function (Snorkel-style):
    - Rule 1 (highest signal): explicit error field → failure
    - Rule 2 (medium signal): blank response + no tool calls → skill declined
    - Rule 3 (fallback): everything else → success candidate

    Returns (classification, confidence, reason).
    """
    error = record.get("error")          # optional field
    response_text = record["response_text"]
    tool_calls = record["tool_calls"]

    # Rule 1: upstream call errored — clear failure signal.
    if error:
        return (
            "failure",
            "high",
            f"'error' field present: {error!r}",
        )

    # Rule 2: empty response AND no tool calls → skill likely declined or DNT.
    if not response_text.strip() and not tool_calls:
        return (
            "do-not-trigger",
            "medium",
            "response_text is empty and tool_calls is empty — skill likely declined",
        )

    # Rule 3: non-empty response without explicit success evidence.
    return (
        "success",
        "low",
        "non_empty_response_but_no_success_criteria_matched",
    )


# ─── Interactive classification ──────────────────────────────────────────────

def classify_interactive(
    record: dict,
    filepath: str,
    lineno: int,
) -> tuple[str | None, str | None, str | None]:
    """
    Prompt the user to label each turn.  Good for a first-pass review when
    you want human judgment on ambiguous turns.
    """
    # Show a compact summary so the user knows what they're labeling.
    preview = record["response_text"][:120].replace("\n", " ")
    tool_names = [t.get("name", "?") for t in record["tool_calls"]]

    print(f"\n--- Turn {record['turn']} | session {record['session_id'][:8]}... | {filepath}:{lineno}")
    print(f"    Response preview: {preview!r}")
    print(f"    Tool calls: {tool_names or '(none)'}")
    if record.get("error"):
        print(f"    ERROR: {record['error']}")

    while True:
        raw = input("  [s]uccess / [f]ailure / [d]o-not-trigger / [k]skip? ").strip().lower()
        if raw == "s":
            return ("success", "high", "User-labeled: success")
        if raw == "f":
            return ("failure", "high", "User-labeled: failure")
        if raw == "d":
            return ("do-not-trigger", "high", "User-labeled: do-not-trigger")
        if raw == "k":
            return (None, None, None)   # caller will skip this turn
        print("  Please enter s, f, d, or k.")


# ─── Output row construction ─────────────────────────────────────────────────

def build_output_row(
    record: dict,
    idx: dict,           # {"success": N, "failure": N, "do-not-trigger": N}
    classification: str,
    confidence: str,
    reason: str,
) -> dict:
    """
    Reshape a raw trace record into a Gulf 1 Phase 0.5 contract example row.

    The output schema mirrors references.md § "Contract Example Schema":
      - success     → Success Example Row shape
      - failure     → Failure Example Row shape
      - do-not-trigger → Do-Not-Trigger Example Row shape
      - unclassified → bare record with classification metadata

    Extra fields added by this converter (not in base schema):
      source_trace            — cross-reference back to original session + turn
      classification          — which bucket this row landed in
      classification_confidence — low/medium/high (auto mode only)
      classification_reason   — human-readable explanation of the heuristic
      skill_hint              — forwarded from the trace if present
    """

    # Cross-reference: lets Phase 0.5 / the user trace back any row to the
    # exact line in the original JSONL file. Like a foreign key in a DB.
    source_trace = {
        "session_id": record["session_id"],
        "turn": record["turn"],
    }

    # Derive a user-visible input string from the LAST user message in the
    # messages array (most recent user turn = most informative context).
    last_user_msg = ""
    for msg in reversed(record["messages"]):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            # content may be a string or a list of content blocks (Anthropic format).
            if isinstance(content, str):
                last_user_msg = content
            elif isinstance(content, list):
                # Extract text from {"type": "text", "text": "..."} blocks.
                parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                last_user_msg = " ".join(parts)
            break

    # Shared metadata appended to every row regardless of classification.
    meta = {
        "source_trace": source_trace,
        "classification": classification,
        "classification_confidence": confidence,
        "classification_reason": reason,
    }

    # Forward skill_hint if the recorder included it — useful for Phase 0.5
    # to know which skill this example is associated with.
    if record.get("skill_hint"):
        meta["skill_hint"] = record["skill_hint"]

    # ── Build the shape matching the classification bucket ──────────────────
    if classification == "success":
        n = idx["success"] + 1
        row = {
            "id": f"success-{n}",
            "input": last_user_msg or "(no user message found in turn)",
            "output_shape": {
                # Description seeded from actual output — Phase 0.5 wizard will
                # ask the author to refine this before confirming the contract.
                "description": (
                    f"Skill produced a response of {len(record['response_text'])} chars"
                    + (f" and {len(record['tool_calls'])} tool call(s)" if record["tool_calls"] else "")
                    + ". (Auto-seeded — author should refine this description.)"
                ),
                "schema": None,   # Phase 0.5 wizard generates schema; null until then
            },
            "actual_output": record["response_text"],
            **meta,
        }
        idx["success"] += 1

    elif classification == "failure":
        n = idx["failure"] + 1
        row = {
            "id": f"failure-{n}",
            "input": last_user_msg or "(no user message found in turn)",
            "output_shape": {
                "description": "What correct output would have looked like — author must fill this in.",
                "schema": None,
            },
            "actual_output": record["response_text"] or f"(error: {record.get('error', 'unknown')})",
            "failure_reason": (
                record.get("error")
                or "Auto-classified as failure — author must document the failure reason."
            ),
            **meta,
        }
        idx["failure"] += 1

    elif classification == "do-not-trigger":
        n = idx["do-not-trigger"] + 1
        row = {
            "id": f"dnt-{n}",
            "input": last_user_msg or "(no user message found in turn)",
            # Default expected_behavior is "decline" for empty-response turns.
            "expected_behavior": "decline",
            **meta,
        }
        idx["do-not-trigger"] += 1

    else:
        # "unclassified" — pass through raw, let Phase 0.5 handle downstream.
        row = {
            "id": f"unclassified-{idx.get('unclassified', 0) + 1}",
            "input": last_user_msg or "(no user message found in turn)",
            "actual_output": record["response_text"],
            **meta,
        }
        idx["unclassified"] = idx.get("unclassified", 0) + 1

    return row


# ─── File discovery ───────────────────────────────────────────────────────────

def collect_input_files(input_path: str) -> list[Path]:
    """
    Accept either a single .jsonl file or a directory.
    Directory → prefer two-level layout (*/*.jsonl), fallback to flat (*.jsonl),
    sorted for determinism.

    Like a Spark read that handles both file and directory paths.
    """
    p = Path(input_path)
    if not p.exists():
        print(f"ERROR: --input path does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    if p.is_file():
        if p.suffix != ".jsonl":
            print(f"WARNING: --input file does not have .jsonl extension: {p}", file=sys.stderr)
        return [p]

    if p.is_dir():
        files = sorted(set(p.glob("*/*.jsonl")) | set(p.glob("*.jsonl")))
        if not files:
            print(f"ERROR: No .jsonl files found in directory: {input_path}", file=sys.stderr)
            sys.exit(1)
        return files

    print(f"ERROR: --input is neither a file nor a directory: {input_path}", file=sys.stderr)
    sys.exit(1)


# ─── Main pipeline ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Convert AutoRefine session trace records (JSONL) into "
            "Gulf 1 Phase 0.5 Option D input rows."
        )
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to a single .jsonl file or a directory of .jsonl files."
    )
    parser.add_argument(
        "--output", required=True,
        help="Destination .jsonl file for converted Phase 0.5 candidate rows."
    )
    parser.add_argument(
        "--classify",
        choices=["auto", "interactive", "none"],
        default="auto",
        help=(
            "Classification strategy: "
            "'auto' (heuristics), "
            "'interactive' (stdin prompts per turn), "
            "'none' (emit unclassified rows)."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing non-symlink output file.",
    )
    args = parser.parse_args()

    input_files = collect_input_files(args.input)
    out_path = Path(args.output)
    out_resolved = out_path.resolve()
    if any(input_file.resolve() == out_resolved for input_file in input_files):
        print(
            f"ERROR: --output must not match an input file: {out_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Counters for the final summary line.
    total_turns = 0
    total_files = len(input_files)
    skipped_turns = 0
    bucket_counts = {"success": 0, "failure": 0, "do-not-trigger": 0, "unclassified": 0}

    # Per-bucket index for id generation (success-1, failure-2, etc.)
    idx = {"success": 0, "failure": 0, "do-not-trigger": 0, "unclassified": 0}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.is_symlink():
        print(f"ERROR: refusing to write through symlink: {out_path}", file=sys.stderr)
        sys.exit(1)
    if out_path.exists() and not args.force:
        print(
            f"ERROR: refusing to overwrite existing output file without --force: {out_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    open_flags = os.O_WRONLY | os.O_CREAT
    open_flags |= os.O_TRUNC if args.force else os.O_EXCL
    fd = os.open(str(out_path), open_flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out_fh:

        for filepath in input_files:
            with filepath.open("r", encoding="utf-8") as in_fh:
                for lineno, raw_line in enumerate(in_fh, start=1):
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue  # skip blank lines (trailing newlines, etc.)

                    # ── Parse JSON ─────────────────────────────────────────
                    try:
                        record = json.loads(raw_line)
                    except json.JSONDecodeError as exc:
                        print(
                            f"ERROR: [{filepath}:{lineno}] Invalid JSON: {exc}",
                            file=sys.stderr,
                        )
                        sys.exit(1)

                    # ── Validate required fields ───────────────────────────
                    try:
                        validate_record(record, str(filepath), lineno)
                    except ValueError as exc:
                        print(f"ERROR: {exc}", file=sys.stderr)
                        sys.exit(1)

                    total_turns += 1

                    # ── Classify ───────────────────────────────────────────
                    if args.classify == "auto":
                        classification, confidence, reason = classify_auto(record)

                    elif args.classify == "interactive":
                        classification, confidence, reason = classify_interactive(
                            record, str(filepath), lineno
                        )
                        if classification is None:
                            # User pressed 'k' to skip this turn.
                            skipped_turns += 1
                            continue

                    else:  # none
                        classification = "unclassified"
                        confidence = None
                        reason = "Classification deferred — --classify none mode."

                    # ── Build output row ───────────────────────────────────
                    row = build_output_row(record, idx, classification, confidence, reason)

                    # ── Write one JSONL line ───────────────────────────────
                    out_fh.write(json.dumps(row, ensure_ascii=False) + "\n")

                    bucket_counts[classification] = bucket_counts.get(classification, 0) + 1

    # ─── Summary ─────────────────────────────────────────────────────────────
    print(
        f"Converted {total_turns} turns from {total_files} file(s) → {args.output}"
    )
    if skipped_turns:
        print(f"  Skipped (user): {skipped_turns}")
    if args.classify in ("auto", "interactive"):
        for label in ("success", "failure", "do-not-trigger", "unclassified"):
            count = bucket_counts.get(label, 0)
            if count:
                print(f"  {label}: {count}")


if __name__ == "__main__":
    main()
