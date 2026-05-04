from __future__ import annotations

import io

from autorefine.lib.gulf_trace_record import (
    append_chunk_lines,
    build_trace_record,
    parse_openai_response,
    accumulate_openai_stream,
    scrub,
)


def test_build_trace_record_scrubs_payloads_and_omits_empty_optional_fields() -> None:
    record = build_trace_record(
        session_id="session-1",
        turn=2,
        timestamp="2026-04-21T18:34:56.123Z",
        messages=[{"role": "user", "content": "Bearer tok-xyz"}],
        response_text="done with ?api_key=secret",
        tool_calls=[{"id": "tc1", "name": "bash", "arguments": {"cmd": "sk-abc123def456789"}}],
    )

    assert record == {
        "session_id": "session-1",
        "turn": 2,
        "timestamp": "2026-04-21T18:34:56.123Z",
        "messages": [{"role": "user", "content": "[REDACTED]"}],
        "response_text": "done with ?api_key=[REDACTED]",
        "tool_calls": [{"id": "tc1", "name": "bash", "arguments": {"cmd": "[REDACTED]"}}],
    }


def test_build_trace_record_raw_mode_preserves_payloads_and_absolute_skill_hint() -> None:
    record = build_trace_record(
        session_id="session-1",
        turn=1,
        timestamp="2026-04-21T18:34:56.123Z",
        messages=[{"role": "user", "content": "Bearer tok-xyz"}],
        response_text="sk-abc123def456789",
        tool_calls=[],
        skill_hint="/tmp/skills/demo/SKILL.md",
        raw_records=True,
    )

    assert record["messages"][0]["content"] == "Bearer tok-xyz"
    assert record["response_text"] == "sk-abc123def456789"
    assert record["skill_hint"] == "/tmp/skills/demo/SKILL.md"


def test_openai_parsers_keep_invalid_tool_arguments_as_raw_text() -> None:
    text, tool_calls = parse_openai_response({
        "choices": [{
            "message": {
                "content": "using a tool",
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "bash", "arguments": "{not-json"},
                }],
            }
        }]
    })

    assert text == "using a tool"
    assert tool_calls == [{"id": "call_1", "name": "bash", "arguments": {"_raw": "{not-json"}}]


def test_openai_stream_parser_accumulates_split_tool_arguments() -> None:
    text, tool_calls = accumulate_openai_stream([
        'data: {"choices":[{"delta":{"content":"ok","tool_calls":[{"index":0,"id":"call_1","function":{"name":"bash","arguments":"{\\"cmd\\":"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"ls\\"}"}}]}}]}',
        "data: [DONE]",
    ])

    assert text == "ok"
    assert tool_calls == [{"id": "call_1", "name": "bash", "arguments": {"cmd": "ls"}}]


def test_append_chunk_lines_keeps_partial_line_and_flushes_overflow() -> None:
    lines: list[str] = []
    stderr = io.StringIO()
    carry = append_chunk_lines(lines, "", b"data: par", max_carry_bytes=16, stderr=stderr)
    carry = append_chunk_lines(lines, carry, b"tial\nnext", max_carry_bytes=16, stderr=stderr)

    assert lines == ["data: partial"]
    assert carry == "next"

    carry = append_chunk_lines(lines, carry, b"x" * 20, turn=3, max_carry_bytes=16, stderr=stderr)
    assert carry == ""
    assert lines[-1] == "next" + ("x" * 20)
    assert "[turn 3] carry-buffer overflow" in stderr.getvalue()


def test_scrub_redacts_bearer_keys_and_url_credentials() -> None:
    assert scrub("Bearer tok-xyz sk-abc123def456789 ?token=secret") == (
        "[REDACTED] [REDACTED] ?token=[REDACTED]"
    )
