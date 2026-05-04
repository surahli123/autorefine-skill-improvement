"""Gulf 1 trace record construction and provider response parsing."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

MAX_CARRY_BYTES: int = 1 * 1024 * 1024
_CREDENTIAL_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9\-_]{10,}|sk-ant-[A-Za-z0-9\-_]{10,}|Bearer\s+\S+)",
    re.IGNORECASE,
)
_URL_CRED_PATTERN = re.compile(r"(?i)([?&])(api_key|token|key|secret)=([^\s&]+)")


def now_iso() -> str:
    """UTC ISO 8601 with millisecond precision and a Z suffix."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def scrub(text: str) -> str:
    text = _CREDENTIAL_PATTERN.sub("[REDACTED]", text)
    text = _URL_CRED_PATTERN.sub(r"\1\2=[REDACTED]", text)
    return text


def scrub_json(value: Any) -> Any:
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrub_json(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub_json(item) for key, item in value.items()}
    return value


def record_skill_hint(value: str, *, raw_records: bool = False) -> str:
    return value if raw_records else Path(value).name


def build_trace_record(
    *,
    session_id: str,
    turn: int,
    messages: list[dict],
    response_text: str,
    tool_calls: list[dict],
    timestamp: str | None = None,
    skill_hint: str | None = None,
    upstream_model: str | None = None,
    error: str | None = None,
    raw_records: bool = False,
) -> dict[str, Any]:
    """Build one Gulf 1 Trace Record payload.

    Optional fields are omitted when not provided to preserve the existing
    JSONL contract used by the recorder script and downstream consumers.
    """
    record: dict[str, Any] = {
        "session_id": session_id,
        "turn": turn,
        "timestamp": timestamp or now_iso(),
        "messages": messages if raw_records else scrub_json(messages),
        "response_text": response_text if raw_records else scrub(response_text),
        "tool_calls": tool_calls if raw_records else scrub_json(tool_calls),
    }

    if skill_hint is not None:
        record["skill_hint"] = record_skill_hint(skill_hint, raw_records=raw_records)
    if upstream_model is not None:
        record["upstream_model"] = upstream_model
    if error is not None:
        record["error"] = error

    return record


def parse_openai_response(body: dict) -> tuple[str, list[dict]]:
    """Extract text and tool calls from a non-streaming OpenAI response."""
    text = ""
    tool_calls: list[dict] = []

    choices = body.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        text = message.get("content") or ""
        raw_tcs = message.get("tool_calls") or []
        for tc in raw_tcs:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {"_raw": raw_args}
            tool_calls.append({
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "arguments": args,
            })

    return text, tool_calls


def parse_anthropic_response(body: dict) -> tuple[str, list[dict]]:
    """Extract text and tool calls from a non-streaming Anthropic response."""
    text_parts: list[str] = []
    tool_calls: list[dict] = []

    for block in body.get("content", []):
        btype = block.get("type", "")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "name": block.get("name", ""),
                "arguments": block.get("input", {}),
            })

    return "".join(text_parts), tool_calls


def accumulate_openai_stream(lines: list[str]) -> tuple[str, list[dict]]:
    """Accumulate text and tool-call deltas from OpenAI SSE lines."""
    text_parts: list[str] = []
    tc_map: dict[int, dict] = {}

    for line in lines:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data_str = line[5:].strip()
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        choices = chunk.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})

        content = delta.get("content")
        if content:
            text_parts.append(content)

        for tc_delta in delta.get("tool_calls", []):
            idx = tc_delta.get("index", 0)
            if idx not in tc_map:
                tc_map[idx] = {"id": "", "name": "", "arguments_str": ""}
            entry = tc_map[idx]
            entry["id"] = entry["id"] or tc_delta.get("id", "")
            fn = tc_delta.get("function", {})
            entry["name"] = entry["name"] or fn.get("name", "")
            entry["arguments_str"] += fn.get("arguments", "")

    tool_calls: list[dict] = []
    for idx in sorted(tc_map.keys()):
        entry = tc_map[idx]
        raw_args = entry["arguments_str"]
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {"_raw": raw_args}
        tool_calls.append({
            "id": entry["id"],
            "name": entry["name"],
            "arguments": args,
        })

    return "".join(text_parts), tool_calls


def accumulate_anthropic_stream(lines: list[str]) -> tuple[str, list[dict]]:
    """Accumulate text and tool-use blocks from Anthropic SSE lines."""
    text_parts: list[str] = []
    block_map: dict[int, dict] = {}
    current_index: int = 0

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("event:"):
            event_type = line[6:].strip()
            i += 1
            data_line = ""
            while i < len(lines) and not lines[i].strip().startswith("data:"):
                i += 1
            if i < len(lines):
                data_line = lines[i].strip()

            if not data_line.startswith("data:"):
                i += 1
                continue
            data_str = data_line[5:].strip()

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                i += 1
                continue

            if event_type == "content_block_start":
                idx = data.get("index", 0)
                current_index = idx
                block = data.get("content_block", {})
                btype = block.get("type", "text")
                block_map[idx] = {
                    "type": btype,
                    "text_parts": [],
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input_str": "",
                }

            elif event_type == "content_block_delta":
                idx = data.get("index", current_index)
                delta = data.get("delta", {})
                dtype = delta.get("type", "")
                entry = block_map.get(idx)
                if entry is None:
                    i += 1
                    continue
                if dtype == "text_delta":
                    entry["text_parts"].append(delta.get("text", ""))
                elif dtype == "input_json_delta":
                    entry["input_str"] += delta.get("partial_json", "")

        i += 1

    tool_calls: list[dict] = []
    for idx in sorted(block_map.keys()):
        entry = block_map[idx]
        if entry["type"] == "text":
            text_parts.extend(entry["text_parts"])
        elif entry["type"] == "tool_use":
            raw_input = entry["input_str"]
            try:
                args = json.loads(raw_input) if raw_input else {}
            except json.JSONDecodeError:
                args = {"_raw": raw_input}
            tool_calls.append({
                "id": entry["id"],
                "name": entry["name"],
                "arguments": args,
            })

    return "".join(text_parts), tool_calls


def append_chunk_lines(
    accumulated_lines: list[str],
    carry: str,
    chunk: bytes,
    *,
    turn: int | None = None,
    max_carry_bytes: int = MAX_CARRY_BYTES,
    stderr: TextIO | None = None,
) -> str:
    """Append complete newline-terminated lines from a streamed byte chunk."""
    text = carry + chunk.decode(errors="replace")
    parts = text.split("\n")
    for full_line in parts[:-1]:
        accumulated_lines.append(full_line.rstrip("\r"))
    new_carry = parts[-1]
    carry_size = len(new_carry.encode("utf-8", errors="replace"))
    if carry_size > max_carry_bytes:
        accumulated_lines.append(new_carry.rstrip("\r"))
        turn_str = "?" if turn is None else str(turn)
        print(
            f"[turn {turn_str}] carry-buffer overflow: flushing {carry_size} bytes without newline",
            file=stderr or sys.stderr,
        )
        return ""
    return new_carry
