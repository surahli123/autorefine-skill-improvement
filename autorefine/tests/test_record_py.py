"""
autorefine/tests/test_record_py.py
-----------------------------------
Pytest tests for autorefine/scripts/record.py

Tests cover the recording pipeline directly — no live server is started.
We import the module's functions and call them with synthetic data.

ANALOGY: these are unit tests of the "transform" stage in a data pipeline.
We don't test the full pipeline end-to-end (that would require a network);
we test each transformation function in isolation with known inputs.

Test categories:
    1. Schema emission  — JSONL record has all required fields, correct types
    2. session_id stability — all records share the same SESSION_ID
    3. turn monotonicity — counter increments correctly
    4. Missing optional fields — skill_hint absent when --skill not set
    5. Error field — error= populated on upstream failure, turn still written
"""

from __future__ import annotations

import importlib
import io
import json
import os
import signal
import sys
import threading
import types
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# We import it fresh so we can patch module-level globals cleanly.
# ---------------------------------------------------------------------------

# Make autorefine/scripts importable regardless of working directory
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import record as rec  # noqa: E402  (import after sys.path patch)
from record import _URL_CRED_PATTERN, _scrub  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_globals(skill_hint: str | None = None) -> None:
    """Reset the module's mutable globals to a known state.

    This is the test equivalent of clearing experiment state between runs.
    We reset turn_counter and records_file so each test starts clean.
    """
    rec._turn_counter = 0
    rec._skill_hint = skill_hint
    # We'll inject a StringIO as the records file so we can inspect output
    # without touching the filesystem.


def _make_string_records_file() -> io.StringIO:
    """Return a StringIO buffer wired into rec._records_file."""
    buf = io.StringIO()
    rec._records_file = buf
    return buf


def _read_records(buf: io.StringIO) -> list[dict]:
    """Parse all JSONL lines from a StringIO buffer."""
    buf.seek(0)
    lines = [l.strip() for l in buf.readlines() if l.strip()]
    return [json.loads(l) for l in lines]


# ---------------------------------------------------------------------------
# 1. Schema emission tests
# ---------------------------------------------------------------------------

class TestSchemaEmission:
    """Verify that write_record() emits all required fields with correct types."""

    def setup_method(self) -> None:
        _reset_globals(skill_hint=None)
        self.buf = _make_string_records_file()

    def test_required_fields_present(self) -> None:
        """All six required fields from the Gulf 1 schema must be present."""
        rec.write_record(
            turn=1,
            messages=[{"role": "user", "content": "Hello"}],
            response_text="Hi there",
            tool_calls=[],
        )
        records = _read_records(self.buf)
        assert len(records) == 1
        r = records[0]

        # Required fields per references.md §Gulf 1 Trace Record Schema
        assert "session_id" in r, "session_id required"
        assert "turn" in r, "turn required"
        assert "timestamp" in r, "timestamp required"
        assert "messages" in r, "messages required"
        assert "response_text" in r, "response_text required"
        assert "tool_calls" in r, "tool_calls required"

    def test_field_types(self) -> None:
        """Each field must have the correct type."""
        rec.write_record(
            turn=1,
            messages=[{"role": "user", "content": "test"}],
            response_text="some text",
            tool_calls=[{"id": "tc1", "name": "bash", "arguments": {"cmd": "ls"}}],
            upstream_model="claude-opus-4-7",
        )
        records = _read_records(self.buf)
        r = records[0]

        # session_id: UUID string
        try:
            uuid.UUID(r["session_id"])
        except ValueError:
            raise AssertionError(f"session_id is not a valid UUID: {r['session_id']!r}")

        # turn: integer >= 1
        assert isinstance(r["turn"], int), f"turn must be int, got {type(r['turn'])}"
        assert r["turn"] >= 1

        # timestamp: ISO 8601 string ending in Z
        assert isinstance(r["timestamp"], str)
        assert r["timestamp"].endswith("Z"), \
            f"timestamp must end with Z (UTC), got {r['timestamp']!r}"
        # Basic structure check: YYYY-MM-DDTHH:MM:SS.mmmZ
        assert "T" in r["timestamp"]

        # messages: list of dicts
        assert isinstance(r["messages"], list)
        assert all(isinstance(m, dict) for m in r["messages"])

        # response_text: string
        assert isinstance(r["response_text"], str)

        # tool_calls: list of dicts with id/name/arguments
        assert isinstance(r["tool_calls"], list)
        for tc in r["tool_calls"]:
            assert "id" in tc
            assert "name" in tc
            assert "arguments" in tc
            assert isinstance(tc["arguments"], dict)

        # upstream_model: string when provided
        assert isinstance(r["upstream_model"], str)

    def test_messages_preserved_verbatim(self) -> None:
        """messages array must be preserved exactly as passed in."""
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
        ]
        rec.write_record(
            turn=1,
            messages=msgs,
            response_text="4",
            tool_calls=[],
        )
        records = _read_records(self.buf)
        assert records[0]["messages"] == msgs

    def test_tool_calls_structure(self) -> None:
        """tool_calls must be a list; empty list when no tools used."""
        rec.write_record(
            turn=1,
            messages=[],
            response_text="done",
            tool_calls=[],
        )
        records = _read_records(self.buf)
        assert records[0]["tool_calls"] == []

    def test_each_record_is_valid_json_line(self) -> None:
        """Each line written must be valid JSON (JSONL format)."""
        for i in range(3):
            rec._turn_counter = i  # manually set so turns are sequential
            rec.write_record(
                turn=i + 1,
                messages=[],
                response_text=f"response {i}",
                tool_calls=[],
            )
        self.buf.seek(0)
        lines = [l.strip() for l in self.buf.readlines() if l.strip()]
        assert len(lines) == 3
        for line in lines:
            parsed = json.loads(line)  # raises if invalid
            assert isinstance(parsed, dict)

    def test_response_text_newlines_round_trip(self) -> None:
        original = "line1\n```bash\nprintf 'x\\n'\n```\nline4\nliteral \\n marker"
        rec.write_record(
            turn=1,
            messages=[{"role": "user", "content": "serialize this"}],
            response_text=original,
            tool_calls=[],
        )
        records = _read_records(self.buf)
        assert len(records) == 1
        assert records[0]["response_text"] == original

    def test_response_text_multiline_round_trip(self) -> None:
        response_text = "line one\n```bash\nls -la\n```\nline two\n"
        rec.write_record(
            turn=1,
            messages=[{"role": "user", "content": "show me output"}],
            response_text=response_text,
            tool_calls=[],
        )
        records = _read_records(self.buf)
        assert records[0]["response_text"] == response_text


# ---------------------------------------------------------------------------
# 2. session_id stability
# ---------------------------------------------------------------------------

class TestSessionIdStability:
    """All records within one process must share the same session_id."""

    def setup_method(self) -> None:
        _reset_globals()
        self.buf = _make_string_records_file()

    def test_same_session_id_across_turns(self) -> None:
        """Multiple write_record() calls in one process → same session_id."""
        for i in range(5):
            rec.write_record(
                turn=i + 1,
                messages=[{"role": "user", "content": f"turn {i}"}],
                response_text=f"reply {i}",
                tool_calls=[],
            )
        records = _read_records(self.buf)
        assert len(records) == 5

        session_ids = {r["session_id"] for r in records}
        assert len(session_ids) == 1, \
            f"Expected 1 unique session_id, got {len(session_ids)}: {session_ids}"

        # Also verify it matches the module-level SESSION_ID constant
        assert records[0]["session_id"] == rec.SESSION_ID

    def test_session_id_is_valid_uuid(self) -> None:
        """SESSION_ID must be a valid UUIDv4."""
        uid = uuid.UUID(rec.SESSION_ID)
        assert uid.version == 4


# ---------------------------------------------------------------------------
# 3. turn monotonicity
# ---------------------------------------------------------------------------

class TestTurnMonotonicity:
    """_next_turn() must increment and write_record() must record correct values."""

    def setup_method(self) -> None:
        _reset_globals()
        self.buf = _make_string_records_file()

    def test_turn_counter_increments(self) -> None:
        """_next_turn() returns 1, 2, 3, ... on successive calls."""
        rec._turn_counter = 0
        turns = [rec._next_turn() for _ in range(5)]
        assert turns == [1, 2, 3, 4, 5], f"Expected [1..5], got {turns}"

    def test_turn_in_records_is_monotonic(self) -> None:
        """turns in written records are strictly increasing."""
        rec._turn_counter = 0
        for _ in range(4):
            t = rec._next_turn()
            rec.write_record(
                turn=t,
                messages=[],
                response_text="",
                tool_calls=[],
            )
        records = _read_records(self.buf)
        turns = [r["turn"] for r in records]
        assert turns == sorted(turns), f"turns not sorted: {turns}"
        assert turns[0] == 1, f"first turn should be 1, got {turns[0]}"
        assert turns == list(range(1, 5)), f"expected [1,2,3,4], got {turns}"

    def test_turn_counter_thread_safety(self) -> None:
        """Concurrent calls to _next_turn() must produce unique values."""
        import threading

        rec._turn_counter = 0
        results: list[int] = []
        lock = threading.Lock()

        def grab_turn() -> None:
            t = rec._next_turn()
            with lock:
                results.append(t)

        threads = [threading.Thread(target=grab_turn) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        assert len(set(results)) == 20, \
            f"Duplicate turn values from concurrent calls: {sorted(results)}"
        assert sorted(results) == list(range(1, 21))


# ---------------------------------------------------------------------------
# 4. Optional fields: skill_hint absent when --skill not set
# ---------------------------------------------------------------------------

class TestOptionalFields:
    """skill_hint must be OMITTED (not null) when no --skill was provided."""

    def setup_method(self) -> None:
        _reset_globals(skill_hint=None)  # no skill set
        self.buf = _make_string_records_file()

    def test_skill_hint_absent_when_no_skill(self) -> None:
        """skill_hint key must not appear in the record at all."""
        rec.write_record(
            turn=1,
            messages=[],
            response_text="hi",
            tool_calls=[],
        )
        records = _read_records(self.buf)
        r = records[0]
        assert "skill_hint" not in r, \
            f"skill_hint should be absent when no --skill set, got: {r.get('skill_hint')!r}"

    def test_skill_hint_absent_means_not_null(self) -> None:
        """Confirm we didn't set skill_hint to null/None — key must not exist."""
        rec.write_record(
            turn=1,
            messages=[],
            response_text="",
            tool_calls=[],
        )
        line = self.buf.getvalue().strip()
        parsed = json.loads(line)
        # The JSON should not have "skill_hint" at all — not even as null
        assert "skill_hint" not in parsed

    def test_skill_hint_present_when_set(self) -> None:
        """When skill_hint IS set, it must appear in the record."""
        rec._skill_hint = "/Users/alice/.claude/skills/react-debug/SKILL.md"
        rec.write_record(
            turn=1,
            messages=[],
            response_text="hi",
            tool_calls=[],
        )
        records = _read_records(self.buf)
        r = records[0]
        assert "skill_hint" in r
        assert r["skill_hint"] == "/Users/alice/.claude/skills/react-debug/SKILL.md"

    def test_upstream_model_absent_when_none(self) -> None:
        """upstream_model must not appear when not provided."""
        rec.write_record(
            turn=1,
            messages=[],
            response_text="hi",
            tool_calls=[],
            upstream_model=None,
        )
        records = _read_records(self.buf)
        assert "upstream_model" not in records[0]

    def test_error_absent_on_success(self) -> None:
        """error field must not appear on a successful turn."""
        rec.write_record(
            turn=1,
            messages=[],
            response_text="ok",
            tool_calls=[],
            error=None,
        )
        records = _read_records(self.buf)
        assert "error" not in records[0]


# ---------------------------------------------------------------------------
# 5. Error field: populated on upstream failure, turn still written
# ---------------------------------------------------------------------------

class TestErrorField:
    """When upstream call fails, error= is populated and turn IS written."""

    def setup_method(self) -> None:
        _reset_globals()
        self.buf = _make_string_records_file()

    def test_error_field_populated_on_failure(self) -> None:
        """error key must appear with a non-empty string when set."""
        rec.write_record(
            turn=1,
            messages=[{"role": "user", "content": "ping"}],
            response_text="",
            tool_calls=[],
            error="ConnectionError: upstream unreachable",
        )
        records = _read_records(self.buf)
        assert len(records) == 1, "Turn must be written even on upstream failure"
        r = records[0]
        assert "error" in r
        assert isinstance(r["error"], str)
        assert len(r["error"]) > 0

    def test_error_content_preserved(self) -> None:
        """Error string is stored verbatim."""
        err_msg = "HTTP 429: rate limit exceeded"
        rec.write_record(
            turn=1,
            messages=[],
            response_text="",
            tool_calls=[],
            error=err_msg,
        )
        records = _read_records(self.buf)
        assert records[0]["error"] == err_msg

    def test_turn_still_written_with_error(self) -> None:
        """Even with an error, turn/session_id/timestamp/messages are present."""
        rec.write_record(
            turn=3,
            messages=[{"role": "user", "content": "hello"}],
            response_text="",
            tool_calls=[],
            error="upstream timeout",
        )
        records = _read_records(self.buf)
        r = records[0]
        # Required fields must all be present even on error
        for field in ("session_id", "turn", "timestamp", "messages",
                      "response_text", "tool_calls"):
            assert field in r, f"{field!r} missing from error record"
        assert r["turn"] == 3
        assert r["error"] == "upstream timeout"

    def test_multiple_turns_some_with_errors(self) -> None:
        """Mixed success/error turns all get written; only error turns have error=."""
        rec._turn_counter = 0

        t1 = rec._next_turn()
        rec.write_record(turn=t1, messages=[], response_text="ok", tool_calls=[])

        t2 = rec._next_turn()
        rec.write_record(
            turn=t2, messages=[], response_text="", tool_calls=[],
            error="HTTP 500: server error",
        )

        t3 = rec._next_turn()
        rec.write_record(turn=t3, messages=[], response_text="back", tool_calls=[])

        records = _read_records(self.buf)
        assert len(records) == 3

        assert "error" not in records[0], "turn 1 should not have error"
        assert "error" in records[1], "turn 2 should have error"
        assert "error" not in records[2], "turn 3 should not have error"


# ---------------------------------------------------------------------------
# 6. Response parsing helpers (bonus: verify parsing logic is correct)
# ---------------------------------------------------------------------------

class TestResponseParsers:
    """Verify the response parsing helpers extract text + tool_calls correctly."""

    def test_parse_openai_non_streaming(self) -> None:
        """_parse_openai_response extracts content and tool_calls."""
        body = {
            "choices": [{
                "message": {
                    "content": "Hello world",
                    "tool_calls": [{
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "arguments": '{"cmd": "ls -la"}',
                        }
                    }]
                }
            }]
        }
        text, tcs = rec._parse_openai_response(body)
        assert text == "Hello world"
        assert len(tcs) == 1
        assert tcs[0]["id"] == "call_abc"
        assert tcs[0]["name"] == "bash"
        assert tcs[0]["arguments"] == {"cmd": "ls -la"}

    def test_parse_anthropic_non_streaming(self) -> None:
        """_parse_anthropic_response extracts text blocks and tool_use blocks."""
        body = {
            "content": [
                {"type": "text", "text": "I'll run that for you."},
                {
                    "type": "tool_use",
                    "id": "toolu_01",
                    "name": "computer",
                    "input": {"action": "screenshot"},
                },
            ]
        }
        text, tcs = rec._parse_anthropic_response(body)
        assert text == "I'll run that for you."
        assert len(tcs) == 1
        assert tcs[0]["id"] == "toolu_01"
        assert tcs[0]["name"] == "computer"
        assert tcs[0]["arguments"] == {"action": "screenshot"}

    def test_parse_openai_stream_accumulation(self) -> None:
        """_accumulate_openai_stream correctly joins text deltas."""
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            'data: [DONE]',
        ]
        text, tcs = rec._accumulate_openai_stream(lines)
        assert text == "Hello world"
        assert tcs == []

    def test_parse_openai_stream_no_content(self) -> None:
        """_accumulate_openai_stream returns empty string on no content deltas."""
        lines = [
            'data: {"choices":[{"delta":{}}]}',
            'data: [DONE]',
        ]
        text, tcs = rec._accumulate_openai_stream(lines)
        assert text == ""
        assert tcs == []

    def test_parse_openai_stream_tool_call_delta_accumulation(self) -> None:
        lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"bash","arguments":""}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"cmd\\":"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"ls\\"}"}}]}}]}',
            "data: [DONE]",
        ]
        text, tool_calls = rec._accumulate_openai_stream(lines)
        assert text == ""
        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "call_1"
        assert tool_calls[0]["name"] == "bash"
        assert tool_calls[0]["arguments"] == {"cmd": "ls"}

    def test_parse_openai_stream_tool_calls_across_multiple_deltas(self) -> None:
        lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"bash","arguments":"{\\"cmd\\": \\""}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"ls"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"}"}}]}}]}',
            "data: [DONE]",
        ]
        text, tool_calls = rec._accumulate_openai_stream(lines)
        assert text == ""
        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "call_1"
        assert tool_calls[0]["name"] == "bash"
        assert tool_calls[0]["arguments"] == {"cmd": "ls"}

    def test_parse_anthropic_stream_text_only(self) -> None:
        """_accumulate_anthropic_stream assembles text from content_block_delta events."""
        lines = [
            "event: content_block_start",
            'data: {"index":0,"content_block":{"type":"text","text":""}}',
            "",
            "event: content_block_delta",
            'data: {"index":0,"delta":{"type":"text_delta","text":"Hi "}}',
            "",
            "event: content_block_delta",
            'data: {"index":0,"delta":{"type":"text_delta","text":"there"}}',
            "",
            "event: content_block_stop",
            'data: {"index":0}',
        ]
        text, tcs = rec._accumulate_anthropic_stream(lines)
        assert text == "Hi there"
        assert tcs == []

    def test_now_iso_format(self) -> None:
        """_now_iso() must return a Z-terminated ISO 8601 string."""
        ts = rec._now_iso()
        assert ts.endswith("Z")
        assert "T" in ts
        # Must be parseable
        from datetime import datetime, timezone
        # Strip Z, parse as UTC
        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")
        assert dt is not None

    def test_sigint_does_not_race_with_inflight_write(self) -> None:
        """SIGINT cleanup must not close records file while a write holds _write_lock."""
        _reset_globals()
        rec._records_path = Path("/tmp/test-race.jsonl")
        rec._server_ref = None

        class BlockingFile:
            def __init__(self) -> None:
                self.closed = False
                self.write_started = threading.Event()
                self.allow_write = threading.Event()
                self.close_called = threading.Event()
                self.close_called_before_allow_write = threading.Event()
                self.lines: list[str] = []

            def write(self, data: str) -> int:
                self.write_started.set()
                self.allow_write.wait(timeout=2.0)
                if self.closed:
                    raise ValueError("I/O operation on closed file.")
                self.lines.append(data)
                return len(data)

            def flush(self) -> None:
                return None

            def close(self) -> None:
                if not self.allow_write.is_set():
                    self.close_called_before_allow_write.set()
                self.closed = True
                self.close_called.set()

        fake_file = BlockingFile()
        rec._records_file = fake_file

        writer_exc: list[BaseException] = []
        sigint_exc: list[BaseException] = []
        fixed_ts = "2026-04-21T18:34:56.123Z"

        def writer() -> None:
            try:
                rec.write_record(
                    turn=1,
                    messages=[{"role": "user", "content": "hi"}],
                    response_text="ok",
                    tool_calls=[],
                )
            except BaseException as exc:  # noqa: BLE001
                writer_exc.append(exc)

        def run_sigint() -> None:
            with patch.object(rec.sys, "exit", side_effect=SystemExit(0)):
                try:
                    rec._handle_sigint(signal.SIGINT, None)
                except SystemExit:
                    pass
                except BaseException as exc:  # noqa: BLE001
                    sigint_exc.append(exc)

        t_writer = threading.Thread(target=writer)
        with patch.object(rec, "_now_iso", return_value=fixed_ts):
            t_writer.start()
            assert fake_file.write_started.wait(timeout=2.0)

            t_sigint = threading.Thread(target=run_sigint)
            t_sigint.start()

            # Deterministic ordering: cleanup cannot close file before write releases lock.
            assert not fake_file.close_called.is_set()
            fake_file.allow_write.set()
            t_writer.join(timeout=2.0)
            t_sigint.join(timeout=2.0)

        assert not sigint_exc
        assert not writer_exc
        expected_line = json.dumps(
            {
                "session_id": rec.SESSION_ID,
                "turn": 1,
                "timestamp": fixed_ts,
                "messages": [{"role": "user", "content": "hi"}],
                "response_text": "ok",
                "tool_calls": [],
            },
            ensure_ascii=False,
        )
        assert fake_file.lines == [expected_line + "\n"], "write completed before close"
        assert fake_file.close_called.is_set(), "file was closed after the write finished"
        assert not fake_file.close_called_before_allow_write.is_set(), \
            "close was called before write was allowed to proceed"
        assert rec._records_file is None, "file handle nulled out"

    def test_openai_stream_chunk_boundary_preserves_content(self) -> None:
        """Chunk boundary splitting must not drop OpenAI SSE JSON content."""
        chunks = [
            b'data: {"choices":[{"delta":{"content":"Hel',
            b'lo"}}]}\n\n',
            b"data: [DONE]\n\n",
        ]
        lines: list[str] = []
        carry = ""
        for chunk in chunks:
            carry = rec._append_chunk_lines(lines, carry, chunk)
        if carry:
            lines.append(carry)
        text, tool_calls = rec._accumulate_openai_stream(lines)
        assert text == "Hello"
        assert tool_calls == []

    def test_anthropic_stream_chunk_boundary_preserves_text(self) -> None:
        """Chunk boundary splitting must not drop Anthropic SSE JSON content."""
        chunks = [
            b"event: content_block_start\n",
            b'data: {"index":0,"content_block":{"type":"text","text":""}}\n\n',
            b"event: content_block_delta\n",
            b'data: {"index":0,"delta":{"type":"text_delta","text":"Hel',
            b'lo"}}\n\n',
            b"event: content_block_stop\n",
            b'data: {"index":0}\n\n',
        ]
        lines: list[str] = []
        carry = ""
        for chunk in chunks:
            carry = rec._append_chunk_lines(lines, carry, chunk)
        if carry:
            lines.append(carry)
        text, tool_calls = rec._accumulate_anthropic_stream(lines)
        assert text == "Hello"
        assert tool_calls == []

    def test_anthropic_stream_tool_args_reassembled_across_chunks(self) -> None:
        """input_json_delta chunks must reconstruct a complete tool argument object."""
        chunks = [
            b"event: content_block_start\n",
            b'data: {"index":0,"content_block":{"type":"tool_use","id":"toolu_1","name":"bash"}}\n\n',
            b"event: content_block_delta\n",
            b'data: {"index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"command\\":\\"ec',
            b'ho\\""}}\n\n',
            b"event: content_block_delta\n",
            b'data: {"index":0,"delta":{"type":"input_json_delta","partial_json":",\\"args\\":{\\"x\\":1}}"}}\n\n',
            b"event: content_block_stop\n",
            b'data: {"index":0}\n\n',
        ]
        lines: list[str] = []
        carry = ""
        for chunk in chunks:
            carry = rec._append_chunk_lines(lines, carry, chunk)
        if carry:
            lines.append(carry)

        text, tool_calls = rec._accumulate_anthropic_stream(lines)
        assert text == ""
        assert len(tool_calls) == 1
        assert tool_calls[0]["id"] == "toolu_1"
        assert tool_calls[0]["name"] == "bash"
        assert tool_calls[0]["arguments"] == {"command": "echo", "args": {"x": 1}}

    def test_append_chunk_lines_flushes_overflowing_carry(self, capsys) -> None:
        """Carry buffer over 1MB with no newline must flush as a pseudo-line."""
        chunk = b"x" * (2 * 1024 * 1024)
        lines: list[str] = []
        carry = rec._append_chunk_lines(lines, "", chunk, turn=7)

        assert carry == ""
        assert len(carry.encode("utf-8", errors="replace")) <= rec.MAX_CARRY_BYTES
        assert len(lines) == 1
        assert len(lines[0]) == len(chunk)
        err = capsys.readouterr().err
        assert "carry-buffer overflow" in err
        assert "[turn 7]" in err


class TestMainStartup:
    @pytest.mark.parametrize(
        ("skill_arg", "expected_slug"),
        [
            (".md", "unclassified"),
            (".SKILL.md", "skill"),
            ("a.md", "unclassified"),
            ("ab.md", "ab"),
            ("---symbols---.md", "symbols"),
        ],
    )
    def test_derive_skill_slug_edge_cases(self, skill_arg: str, expected_slug: str) -> None:
        assert rec._derive_skill_slug(skill_arg) == expected_slug

    def test_records_path_scoped_by_skill_slug_and_file_mode(self, tmp_path) -> None:
        _reset_globals()
        rec._records_file = None
        rec._records_path = None
        rec._skill_hint = None

        records_dir = tmp_path / "records"
        skill_path = tmp_path / "My Skill.md"
        skill_path.write_text("# test skill\n", encoding="utf-8")

        class FakeServer:
            def __init__(self, addr, handler_cls, bind_and_activate=False) -> None:
                self.addr = addr

            def server_bind(self) -> None:
                return None

            def server_activate(self) -> None:
                return None

            def serve_forever(self) -> None:
                return None

        argv = [
            "record.py",
            "--skill",
            str(skill_path),
            "--port",
            "8877",
            "--records-dir",
            str(records_dir),
        ]

        old_argv = sys.argv[:]
        sys.argv = argv
        try:
            with (
                patch.object(rec, "ThreadedHTTPServer", FakeServer),
                patch.object(rec.signal, "signal", lambda *args, **kwargs: None),
                patch.object(rec, "_print_banner", lambda *args, **kwargs: None),
            ):
                rec.main()
        finally:
            sys.argv = old_argv

        assert rec._records_path is not None
        expected_path = records_dir / "my-skill" / f"{rec.SESSION_ID}.jsonl"
        assert rec._records_path == expected_path
        assert rec._records_path.exists()
        mode = os.stat(rec._records_path).st_mode & 0o777
        assert mode == 0o600

        if rec._records_file is not None:
            rec._records_file.close()
            rec._records_file = None


class TestProxySecurity:
    def test_passthrough_rejects_disallowed_path(self) -> None:
        handler = rec.ProxyHandler.__new__(rec.ProxyHandler)
        handler.path = "/internal/secrets"
        handler.command = "GET"
        handler.headers = {}
        handler.wfile = io.BytesIO()

        state: dict[str, list] = {"status": [], "headers": []}

        def fake_send_response(code: int) -> None:
            state["status"].append(code)

        def fake_send_header(name: str, value: str) -> None:
            state["headers"].append((name, value))

        handler.send_response = fake_send_response
        handler.send_header = fake_send_header
        handler.end_headers = lambda: None

        class FakeResponse:
            status_code = 200
            headers = {"Content-Type": "application/json"}
            content = b'{"ok":true}'

        class FakeClient:
            def __init__(self, timeout: float) -> None:
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def request(self, method: str, url: str, headers=None, content=None):
                return FakeResponse()

        with patch.object(rec.httpx, "Client", FakeClient):
            handler._handle_passthrough()

        body = handler.wfile.getvalue().decode("utf-8", errors="replace")
        assert state["status"] == [403]
        assert "path not allowed" in body

    def test_non_streaming_error_body_scrubs_credentials(self) -> None:
        _reset_globals()
        buf = _make_string_records_file()
        handler = rec.ProxyHandler.__new__(rec.ProxyHandler)
        handler._send_response_to_client = lambda status, headers, body: None
        handler.send_response = lambda code: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.wfile = io.BytesIO()
        handler.headers = {}
        handler.command = "POST"
        handler.path = "/v1/chat/completions"

        raw_body = b'{"model":"gpt-test","messages":[]}'
        bad_body = b"token sk-abc123def456789 and Bearer xyz987"

        class FakeResponse:
            status_code = 401
            headers = {"Content-Type": "application/json"}
            content = bad_body

            def json(self):
                return {}

        class FakeClient:
            def __init__(self, timeout: float) -> None:
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def post(self, upstream_url: str, headers=None, content=None):
                return FakeResponse()

        with patch.object(rec.httpx, "Client", FakeClient):
            handler._handle_non_streaming(
                upstream_url="https://api.openai.com/v1/chat/completions",
                forward_headers={},
                raw_body=raw_body,
                turn=9,
                messages=[],
                upstream_model="gpt-test",
                path="/v1/chat/completions",
            )

        records = _read_records(buf)
        assert len(records) == 1
        error_field = records[0]["error"]
        assert error_field.count("[REDACTED]") == 2
        assert "sk-abc123def456789" not in error_field
        assert "Bearer xyz987" not in error_field

    def test_scrub_and_url_credential_pattern_cases(self) -> None:
        assert _scrub("no credentials here") == "no credentials here"

        api_key_only = "?api_key=sk-abc123"
        assert _URL_CRED_PATTERN.search(api_key_only)
        assert _scrub(api_key_only) == "?api_key=[REDACTED]"

        assert (
            _scrub("https://example.com?api_key=xxx&token=yyy&other=z")
            == "https://example.com?api_key=[REDACTED]&token=[REDACTED]&other=z"
        )
        assert _scrub("sk-abc123def456789") == "[REDACTED]"
        assert _scrub("Bearer tok-xyz") == "[REDACTED]"
        assert _scrub("Bearer sk-xxx ?api_key=yyy") == "[REDACTED] ?api_key=[REDACTED]"
        assert _scrub("?API_KEY=zzz") == "?API_KEY=[REDACTED]"
        assert _scrub("?token=abc") == "?token=[REDACTED]"

    def test_recorded_post_exception_scrubs_url_api_key_in_record_and_response(self) -> None:
        _reset_globals()
        buf = _make_string_records_file()
        handler = rec.ProxyHandler.__new__(rec.ProxyHandler)
        handler.path = "/v1/chat/completions"
        handler.command = "POST"
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler._build_upstream_url = lambda path: "https://api.openai.com" + path
        handler._forward_headers = lambda: {}
        handler._read_body = lambda: b'{"model":"gpt-test","messages":[{"role":"user","content":"hi"}]}'
        handler._handle_non_streaming = (
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("gateway failed ?api_key=sk-abc123def456789")
            )
        )

        handler._handle_recorded_post("/v1/chat/completions")

        records = _read_records(buf)
        assert len(records) == 1
        error_field = records[0]["error"]
        response_body = handler.wfile.getvalue().decode("utf-8", errors="replace")
        assert "api_key=[REDACTED]" in error_field
        assert "api_key=[REDACTED]" in response_body
        assert "sk-abc123def456789" not in error_field
        assert "sk-abc123def456789" not in response_body

    def test_send_response_drops_stale_body_metadata_headers(self) -> None:
        handler = rec.ProxyHandler.__new__(rec.ProxyHandler)
        sent_headers: dict[str, str] = {}
        handler.send_response = lambda code: None
        handler.send_header = lambda name, value: sent_headers.setdefault(name, value)
        handler.end_headers = lambda: None
        handler.wfile = io.BytesIO()

        handler._send_response_to_client(
            200,
            {
                "Content-Type": "application/json",
                "Content-Length": "999",
                "Content-Encoding": "gzip",
                "Transfer-Encoding": "chunked",
                "Connection": "keep-alive",
            },
            b'{"ok":true}',
        )

        assert sent_headers == {"Content-Type": "application/json"}
        assert handler.wfile.getvalue() == b'{"ok":true}'

    def test_recorded_post_exception_scrubs_bearer_in_record_and_response(self) -> None:
        _reset_globals()
        buf = _make_string_records_file()
        handler = rec.ProxyHandler.__new__(rec.ProxyHandler)
        handler.path = "/v1/chat/completions"
        handler.command = "POST"
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler._build_upstream_url = lambda path: "https://api.openai.com" + path
        handler._forward_headers = lambda: {}
        handler._read_body = lambda: b'{"model":"gpt-test","messages":[{"role":"user","content":"hi"}]}'
        handler._handle_non_streaming = (
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("gateway failed Bearer tok-xyz")
            )
        )

        handler._handle_recorded_post("/v1/chat/completions")

        records = _read_records(buf)
        assert len(records) == 1
        error_field = records[0]["error"]
        response_body = handler.wfile.getvalue().decode("utf-8", errors="replace")
        assert "[REDACTED]" in error_field
        assert "[REDACTED]" in response_body
        assert "tok-xyz" not in error_field
        assert "tok-xyz" not in response_body
        assert "RuntimeError: gateway failed [REDACTED]" in error_field
        assert "\"error\": \"upstream failure: RuntimeError: gateway failed [REDACTED]\"" in response_body
        assert "Bearer tok-xyz" not in error_field
        assert "Bearer tok-xyz" not in response_body

    def test_passthrough_exception_scrubs_bearer_in_error_response(self) -> None:
        handler = rec.ProxyHandler.__new__(rec.ProxyHandler)
        handler.path = "/v1/models"
        handler.command = "GET"
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler._read_body = lambda: b""

        class FakeClient:
            def __init__(self, timeout: float) -> None:
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def request(self, method: str, url: str, headers=None, content=None):
                raise RuntimeError("passthrough failed Bearer tok-xyz")

        with patch.object(rec.httpx, "Client", FakeClient):
            handler._handle_passthrough()

        response_body = handler.wfile.getvalue().decode("utf-8", errors="replace")
        assert "[REDACTED]" in response_body
        assert "tok-xyz" not in response_body
        assert "\"error\": \"upstream failure: passthrough failed [REDACTED]\"" in response_body
        assert "Bearer tok-xyz" not in response_body


class TestStartup:
    def test_main_uses_skill_slug_subdir_and_private_file_mode(self, tmp_path, monkeypatch) -> None:
        skill_path = tmp_path / "Gulf 1.Trace Recorder.md"
        skill_path.write_text("# skill", encoding="utf-8")
        records_dir = tmp_path / "records"

        class FakeServer:
            def __init__(self, addr, handler, bind_and_activate=False) -> None:
                self.addr = addr
                self.handler = handler
                self.bind_and_activate = bind_and_activate

            def server_bind(self) -> None:
                return None

            def server_activate(self) -> None:
                return None

            def serve_forever(self) -> None:
                return None

        monkeypatch.setattr(rec, "ThreadedHTTPServer", FakeServer)
        monkeypatch.setattr(rec.signal, "signal", lambda *args, **kwargs: None)
        monkeypatch.setattr(rec, "_print_banner", lambda *args, **kwargs: None)
        monkeypatch.setattr(rec, "SESSION_ID", "session-test-001")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com")

        old_argv = sys.argv[:]
        sys.argv = [
            "record.py",
            "--skill",
            str(skill_path),
            "--port",
            "8877",
            "--records-dir",
            str(records_dir),
        ]
        try:
            rec.main()
        finally:
            sys.argv = old_argv
            if rec._records_file is not None:
                rec._records_file.close()
                rec._records_file = None

        expected_path = records_dir / "gulf-1-trace-recorder" / "session-test-001.jsonl"
        assert rec._records_path == expected_path
        assert expected_path.exists()
        assert (os.stat(expected_path).st_mode & 0o777) == 0o600
