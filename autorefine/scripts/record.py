"""
autorefine/scripts/record.py
----------------------------
Gulf 1 Trace Recorder — local HTTP proxy that intercepts OpenAI-compatible and
Anthropic-compatible API calls, records every turn to JSONL, forwards unchanged.

ANALOGY: data pipeline tap. Client = producer, upstream API = sink. This script
inserts a transparent recording stage in the middle — like a Kafka consumer group
mirroring every event to a second topic without disrupting the original flow.

USAGE:
    python autorefine/scripts/record.py --skill /path/to/SKILL.md [--port 8765] [--records-dir records]

    export ANTHROPIC_BASE_URL=http://localhost:8765
    export OPENAI_BASE_URL=http://localhost:8765/v1
    # Run Claude Code or any OpenAI-compatible client. Ctrl-C to stop.

TECH STACK:
    - httpx (outbound): handles streaming responses cleanly; confirmed installed.
    - stdlib http.server + socketserver (inbound): zero new deps. Blocking I/O
      per thread is fine for single-user local recording (no burst concurrency).
    - Why not FastAPI/uvicorn? Not confirmed installed; stdlib is zero-dep.

SESSION MODEL (v1 simplification):
    One process = one session_id. All requests share the same ID. For v2
    multi-window support, key session_id on client IP+port or a custom header.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import signal
import socketserver
import sys
import threading
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from gulf_trace_record import (  # noqa: E402
    MAX_CARRY_BYTES,
    _CREDENTIAL_PATTERN,
    _URL_CRED_PATTERN,
    accumulate_anthropic_stream,
    accumulate_openai_stream,
    append_chunk_lines,
    build_trace_record,
    now_iso,
    parse_anthropic_response,
    parse_openai_response,
    record_skill_hint,
    scrub,
    scrub_json,
)

# ---------------------------------------------------------------------------
# Global state shared across all request handler threads.
# Using module-level globals with a lock is the simplest correct approach for
# a single-process threaded server. Analogy: a shared experiment counter in
# an A/B test harness — all threads update it under a mutex.
# ---------------------------------------------------------------------------

SESSION_ID: str = str(uuid.uuid4())          # stable for this process lifetime
_turn_lock = threading.Lock()
_turn_counter: int = 0                        # incremented per captured turn
_records_file: Any = None                     # open file handle, set at startup
_records_path: Path | None = None            # for the shutdown banner
_skill_hint: str | None = None               # path from --skill flag, sanitized by default
_raw_records: bool = False                   # opt-in: preserve raw payloads and absolute paths
_server_port: int = 8765                     # resolved from --port
PASSTHROUGH_ALLOWED_PREFIXES: tuple[str, ...] = ("/v1/",)
ALLOWED_UPSTREAM_HOSTS: dict[str, set[str]] = {
    "anthropic": {"api.anthropic.com"},
    "openai": {"api.openai.com"},
}


def _scrub(text: str) -> str:
    return scrub(text)


def _next_turn() -> int:
    """Thread-safe turn counter. Returns the new turn number (1-indexed)."""
    global _turn_counter
    with _turn_lock:
        _turn_counter += 1
        return _turn_counter


def _now_iso() -> str:
    """UTC ISO 8601 with millisecond precision + Z suffix, e.g. '2026-04-21T18:34:56.123Z'.
    Gulf 1 schema uses Z not +00:00; datetime.isoformat() emits the latter, so we format manually.
    """
    return now_iso()


def _derive_skill_slug(skill_arg: str | None) -> str:
    if not skill_arg:
        return "unclassified"
    name = Path(skill_arg).name
    if name.startswith(".") and name.count(".") == 1:
        return "unclassified"
    stem = Path(skill_arg).stem.lstrip(".").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    if not slug or len(slug) < 2:
        return "unclassified"
    return slug


def _is_loopback_base_url(value: str) -> bool:
    """Return True when an upstream base URL would point back at this local proxy."""
    host = (urlparse(value).hostname or "").lower()
    return host == "localhost" or host == "::1" or host.startswith("127.")


def _validate_upstream_base_url(
    value: str,
    provider: str,
    allow_custom: bool,
) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if _is_loopback_base_url(value):
        raise ValueError(f"{provider} upstream points to a local address and would create a forwarding loop")
    if parsed.scheme != "https":
        raise ValueError(f"{provider} upstream must use https: {value}")
    if not allow_custom and host not in ALLOWED_UPSTREAM_HOSTS[provider]:
        raise ValueError(
            f"unsafe upstream host for {provider}: {host}. "
            "Pass --allow-custom-upstream to use a trusted custom HTTPS endpoint."
        )
    return value.rstrip("/")


def _join_upstream_url(base: str, path: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/v1") and path.startswith("/v1/"):
        return base + path[len("/v1"):]
    return base + path


def _scrub_json(value: Any) -> Any:
    return scrub_json(value)


def _record_skill_hint(value: str) -> str:
    return record_skill_hint(value, raw_records=_raw_records)


# ---------------------------------------------------------------------------
# Record writer
# ---------------------------------------------------------------------------

_write_lock = threading.Lock()


def write_record(
    turn: int,
    messages: list[dict],
    response_text: str,
    tool_calls: list[dict],
    upstream_model: str | None = None,
    error: str | None = None,
) -> None:
    """Append one JSONL line conforming to Gulf 1 Trace Record Schema.

    Required fields always emitted. Optional fields (skill_hint, upstream_model,
    error) are OMITTED entirely when None — not set to null. Consumer contract
    says "treat as absent, not error," so we don't even emit the key.
    """
    record = build_trace_record(
        session_id=SESSION_ID,
        turn=turn,
        timestamp=_now_iso(),
        messages=messages,
        response_text=response_text,
        tool_calls=tool_calls,
        skill_hint=_skill_hint,
        upstream_model=upstream_model,
        error=error,
        raw_records=_raw_records,
    )

    line = json.dumps(record, ensure_ascii=False)

    with _write_lock:
        if _records_file is not None:
            _records_file.write(line + "\n")
            _records_file.flush()   # flush after each turn so partial sessions
                                    # are readable even if the process is killed


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------

def _parse_openai_response(body: dict) -> tuple[str, list[dict]]:
    """Extract text and tool_calls from a non-streaming OpenAI response.

    OpenAI format:
        choices[0].message.content  → text
        choices[0].message.tool_calls → [{id, type, function: {name, arguments}}]
    """
    return parse_openai_response(body)


def _parse_anthropic_response(body: dict) -> tuple[str, list[dict]]:
    """Extract text and tool_calls from a non-streaming Anthropic response.

    Anthropic format:
        content: [{type: "text", text: "..."}, {type: "tool_use", id, name, input}]
    """
    return parse_anthropic_response(body)


def _accumulate_openai_stream(lines: list[str]) -> tuple[str, list[dict]]:
    """Accumulate text deltas from OpenAI SSE streaming lines.

    OpenAI streaming sends lines like:
        data: {"choices":[{"delta":{"content":"Hello"}}]}
        data: [DONE]

    We concatenate all content deltas. Tool call deltas are more complex
    (streamed incrementally with index/function.name/function.arguments chunks)
    — we accumulate them by index, then parse the final combined arguments.
    """
    return accumulate_openai_stream(lines)


def _accumulate_anthropic_stream(lines: list[str]) -> tuple[str, list[dict]]:
    """Accumulate text and tool_use blocks from Anthropic SSE streaming lines.

    Anthropic streaming events include:
        event: content_block_start   → opens a new block (text or tool_use)
        event: content_block_delta   → delta for current block
        event: content_block_stop    → closes block

    We track open blocks by index and merge deltas into them.
    """
    return accumulate_anthropic_stream(lines)


def _append_chunk_lines(
    accumulated_lines: list[str],
    carry: str,
    chunk: bytes,
    turn: int | None = None,
) -> str:
    """Append complete newline-terminated lines from a streamed byte chunk.

    SSE lines can span TCP chunk boundaries, so we keep trailing partial bytes in
    `carry` until a later chunk completes the line.
    """
    return append_chunk_lines(
        accumulated_lines,
        carry,
        chunk,
        turn=turn,
        max_carry_bytes=MAX_CARRY_BYTES,
        stderr=sys.stderr,
    )


# ---------------------------------------------------------------------------
# HTTP proxy handler
# ---------------------------------------------------------------------------

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler: records POST /v1/messages and /v1/chat/completions,
    passes everything else through unchanged.

    ANALOGY: logging middleware in Express.js — sits between client and server,
    captures the request/response pair, then passes it through unmodified.
    """
    protocol_version = "HTTP/1.1"

    # Silence the default per-request log lines (we print our own summaries)
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: N802
        pass

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST requests: proxy + record for /v1/messages and
        /v1/chat/completions; passthrough for everything else."""
        path = self.path.split("?")[0]  # strip query string

        if path in ("/v1/messages", "/v1/chat/completions"):
            self._handle_recorded_post(path)
        else:
            self._handle_passthrough()

    def do_GET(self) -> None:  # noqa: N802
        self._handle_passthrough()

    def do_DELETE(self) -> None:  # noqa: N802
        self._handle_passthrough()

    def do_PUT(self) -> None:  # noqa: N802
        self._handle_passthrough()

    def _read_body(self) -> bytes:
        """Read the full request body based on Content-Length header."""
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def _build_upstream_url(self, path: str) -> str:
        """Resolve the upstream URL for a given path.

        Rules from spec:
          /v1/messages      → ANTHROPIC_BASE_URL (default: https://api.anthropic.com)
          /v1/chat/completions → OPENAI_BASE_URL (default: https://api.openai.com)
        """
        if path == "/v1/messages":
            base = os.environ.get("ANTHROPIC_BASE_URL_REAL", "https://api.anthropic.com")
            return _join_upstream_url(base, path)
        else:
            base = os.environ.get("OPENAI_BASE_URL_REAL", "https://api.openai.com")
            return _join_upstream_url(base, path)

    def _forward_headers(self) -> dict[str, str]:
        """Build headers to forward upstream, excluding Host (which httpx sets).

        We also exclude Content-Length — httpx will recalculate it. We pass
        through Authorization, x-api-key, anthropic-version, etc. verbatim so
        the upstream auth works exactly as the client configured it.
        """
        skip = {"host", "content-length", "transfer-encoding"}
        return {
            k: v for k, v in self.headers.items()
            if k.lower() not in skip
        }

    def _send_response_to_client(
        self,
        status: int,
        headers: dict[str, str],
        body: bytes,
    ) -> None:
        """Write status + headers + body back to the client."""
        self.send_response(status)
        for k, v in headers.items():
            # Don't forward hop-by-hop headers
            if k.lower() not in {
                "transfer-encoding",
                "connection",
                "keep-alive",
                "content-length",
                "content-encoding",
            }:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_response(self, description: str) -> None:
        """Send a synthetic 500 JSON error to the client."""
        self._send_json_error(500, f"upstream failure: {description}")

    def _send_json_error(self, status: int, description: str) -> None:
        body = json.dumps({"error": description}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_recorded_post(self, path: str) -> None:
        """Core recording flow: read body → parse → forward → extract → write JSONL → relay.
        On any upstream error: write record with error= populated, send 500 to client, keep running.
        """
        raw_body = self._read_body()

        # Parse request JSON — if malformed, treat as upstream error
        try:
            req_body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            err_desc = _scrub(f"malformed request body: {exc}")
            turn = _next_turn()
            write_record(
                turn=turn,
                messages=[],
                response_text="",
                tool_calls=[],
                error=err_desc,
            )
            self._send_error_response(err_desc)
            return

        messages: list[dict] = req_body.get("messages", [])
        upstream_model: str | None = req_body.get("model") or None
        is_streaming: bool = bool(req_body.get("stream", False))

        upstream_url = self._build_upstream_url(path)
        forward_headers = self._forward_headers()

        turn = _next_turn()

        try:
            if is_streaming:
                self._handle_streaming(
                    upstream_url, forward_headers, raw_body,
                    turn, messages, upstream_model, path,
                )
            else:
                self._handle_non_streaming(
                    upstream_url, forward_headers, raw_body,
                    turn, messages, upstream_model, path,
                )
        except Exception as exc:  # noqa: BLE001
            # Catch-all: upstream unreachable, timeout, TLS error, etc.
            err_desc = _scrub(f"{type(exc).__name__}: {exc}")
            write_record(
                turn=turn,
                messages=messages,
                response_text="",
                tool_calls=[],
                upstream_model=upstream_model,
                error=err_desc,
            )
            self._send_error_response(err_desc)
            print(f"  [turn {turn}] upstream error: {err_desc}", file=sys.stderr)

    def _handle_non_streaming(
        self,
        upstream_url: str,
        forward_headers: dict[str, str],
        raw_body: bytes,
        turn: int,
        messages: list[dict],
        upstream_model: str | None,
        path: str,
    ) -> None:
        """Forward a non-streaming POST, parse the response, write record."""
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(upstream_url, headers=forward_headers, content=raw_body)

        resp_body = resp.content
        resp_headers = dict(resp.headers)

        # Parse the response body to extract text + tool_calls
        error: str | None = None
        response_text = ""
        tool_calls: list[dict] = []

        if resp.status_code >= 400:
            error_text = _scrub(resp_body[:200].decode(errors="replace"))
            error = f"HTTP {resp.status_code}: {error_text}"
        else:
            try:
                resp_json = resp.json()
                if path == "/v1/messages":
                    response_text, tool_calls = _parse_anthropic_response(resp_json)
                else:
                    response_text, tool_calls = _parse_openai_response(resp_json)
            except Exception as exc:  # noqa: BLE001
                error = _scrub(f"response parse error: {exc}")

        write_record(
            turn=turn,
            messages=messages,
            response_text=response_text,
            tool_calls=tool_calls,
            upstream_model=upstream_model,
            error=error,
        )

        print(f"  [turn {turn}] captured ({len(response_text)} chars text, "
              f"{len(tool_calls)} tool calls)", file=sys.stderr)

        # Relay response to client unchanged
        self._send_response_to_client(resp.status_code, resp_headers, resp_body)

    def _handle_streaming(
        self,
        upstream_url: str,
        forward_headers: dict[str, str],
        raw_body: bytes,
        turn: int,
        messages: list[dict],
        upstream_model: str | None,
        path: str,
    ) -> None:
        """Relay streaming POST to client in real-time while accumulating SSE lines for recording.

        ANALOGY: T-junction in a data pipeline — stream flows to client immediately AND
        we tap a copy into the accumulator. Client sees no added latency; parse happens
        after the stream closes.
        """
        accumulated_lines: list[str] = []
        error: str | None = None
        response_status = 200
        response_headers: dict[str, str] = {}
        response_body_chunks: list[bytes] = []

        with httpx.Client(timeout=120.0) as client:
            with client.stream("POST", upstream_url,
                               headers=forward_headers, content=raw_body) as resp:
                response_status = resp.status_code
                response_headers = dict(resp.headers)

                if resp.status_code >= 400:
                    # Non-streaming error response — read it all
                    body = resp.read()
                    error_text = _scrub(body[:200].decode(errors="replace"))
                    error = f"HTTP {resp.status_code}: {error_text}"
                    response_body_chunks.append(body)
                else:
                    # Stream body to client, accumulate for parsing
                    # Send headers first
                    self.send_response(response_status)
                    for k, v in response_headers.items():
                        # We re-chunk the upstream stream ourselves, so forwarding
                        # upstream content/transfer-encoding would mislabel bytes.
                        if k.lower() not in {"transfer-encoding", "connection",
                                             "keep-alive", "content-length",
                                             "content-encoding"}:
                            self.send_header(k, v)
                    # Use chunked transfer so client can receive incrementally
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()

                    chunk_carry = ""
                    for chunk in resp.iter_bytes(chunk_size=1024):
                        # Relay chunk to client immediately
                        hex_size = f"{len(chunk):X}\r\n".encode()
                        self.wfile.write(hex_size)
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                        response_body_chunks.append(chunk)
                        # Accumulate text for parsing
                        chunk_carry = _append_chunk_lines(
                            accumulated_lines=accumulated_lines,
                            carry=chunk_carry,
                            chunk=chunk,
                            turn=turn,
                        )

                    if chunk_carry:
                        accumulated_lines.append(chunk_carry.rstrip("\r"))

                    # Terminate chunked transfer
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()

        # Parse the accumulated stream after it's fully received
        response_text = ""
        tool_calls: list[dict] = []

        if error is None:
            try:
                if path == "/v1/messages":
                    response_text, tool_calls = _accumulate_anthropic_stream(
                        accumulated_lines
                    )
                else:
                    response_text, tool_calls = _accumulate_openai_stream(
                        accumulated_lines
                    )
            except Exception as exc:  # noqa: BLE001
                error = _scrub(f"stream parse error: {exc}")

        write_record(
            turn=turn,
            messages=messages,
            response_text=response_text,
            tool_calls=tool_calls,
            upstream_model=upstream_model,
            error=error,
        )

        print(f"  [turn {turn}] captured streaming ({len(response_text)} chars text, "
              f"{len(tool_calls)} tool calls)", file=sys.stderr)

        # If we had an error (4xx/5xx), we haven't sent headers yet
        if error and response_status >= 400:
            full_body = b"".join(response_body_chunks)
            self._send_response_to_client(
                response_status, response_headers, full_body
            )

    def _handle_passthrough(self) -> None:
        """Forward any non-recorded request to upstream unchanged.

        This handles /v1/models, /v1/tokenize, health checks, etc. — anything
        a Claude Code client might call that we don't need to record.
        """
        path = self.path
        path_no_query = path.split("?")[0]
        raw_body = self._read_body()

        if not any(path_no_query.startswith(p) for p in PASSTHROUGH_ALLOWED_PREFIXES):
            body = json.dumps({"error": f"path not allowed: {path_no_query}"}).encode("utf-8")
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        lower_headers = {k.lower(): v for k, v in self.headers.items()}
        has_anthropic_auth = (
            "x-api-key" in lower_headers
            or "anthropic-version" in lower_headers
        )
        has_openai_auth = "authorization" in lower_headers
        if has_anthropic_auth == has_openai_auth:
            self._send_json_error(400, "ambiguous passthrough target")
            return

        if has_anthropic_auth:
            base = os.environ.get("ANTHROPIC_BASE_URL_REAL", "https://api.anthropic.com")
        else:
            base = os.environ.get("OPENAI_BASE_URL_REAL", "https://api.openai.com")

        upstream_url = _join_upstream_url(base, path)
        forward_headers = self._forward_headers()

        try:
            method = self.command
            with httpx.Client(timeout=30.0) as client:
                resp = client.request(
                    method, upstream_url,
                    headers=forward_headers,
                    content=raw_body if raw_body else None,
                )
            self._send_response_to_client(resp.status_code, dict(resp.headers), resp.content)
        except Exception as exc:  # noqa: BLE001
            self._send_error_response(_scrub(str(exc)))


# ---------------------------------------------------------------------------
# ThreadingTCPServer — allows concurrent request handling
# ---------------------------------------------------------------------------

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """One thread per request (stdlib pattern). GIL fine — bottleneck is network I/O.
    daemon_threads=True: child threads don't block Ctrl-C exit.
    """
    daemon_threads = True
    allow_reuse_address = True


# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------

def _print_banner(port: int, records_path: Path, skill_hint: str | None) -> None:
    """Print the startup banner that tells the user what to do next.

    The most important thing to communicate:
    1. What to export (the key action the user must take)
    2. Where records go (so they can find them)
    3. Privacy warning (records may still include sensitive content)
    """
    print()
    print("=" * 60)
    print("  Gulf 1 Trace Recorder — ready")
    print("=" * 60)
    print()
    print(f"  Session ID : {SESSION_ID}")
    print(f"  Records    : {records_path.resolve()}")
    if skill_hint:
        print(f"  Skill hint : {skill_hint}")
    print()
    print("  To record your API calls, export these env vars:")
    print()
    print(f"    export ANTHROPIC_BASE_URL=http://localhost:{port}")
    print(f"    export OPENAI_BASE_URL=http://localhost:{port}/v1")
    print()
    print("  Then run Claude Code (or any OpenAI-compatible client) as normal.")
    print("  Every turn will be captured to the records file above.")
    print()
    print("  *** PII WARNING ***")
    print("  Records are local. Credential-like tokens are scrubbed by default,")
    print("  but prompts and responses may still contain sensitive content.")
    print("  Do not share the .jsonl file without reviewing for sensitive content.")
    print()
    print("  Ctrl-C to stop.")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Shutdown handler
# ---------------------------------------------------------------------------

_server_ref: ThreadedHTTPServer | None = None


def _handle_sigint(signum: int, frame: Any) -> None:
    """Graceful Ctrl-C: flush + close records file, print turn count, exit 0.

    In-flight writes are safe: httpx is synchronous per thread, so each
    write_record() completes before its thread yields — no partial lines.
    """
    print()  # newline after ^C
    print("Stopping recorder...")

    global _records_file
    file_to_close = None
    with _write_lock:
        if _records_file is not None:
            file_to_close = _records_file
        _records_file = None
    if file_to_close is not None:
        file_to_close.flush()
        file_to_close.close()

    with _turn_lock:
        turns_captured = _turn_counter
    path_str = str(_records_path.resolve()) if _records_path else "?"
    print(f"Recorded {turns_captured} turn{'s' if turns_captured != 1 else ''} to {path_str}")

    if _server_ref is not None:
        # shutdown() blocks until the server loop exits; call in a thread
        # so we can reach sys.exit() without deadlocking.
        t = threading.Thread(target=_server_ref.shutdown, daemon=True)
        t.start()

    sys.exit(0)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse args, open records file, start server, block until Ctrl-C."""
    global _records_file, _records_path, _skill_hint, _raw_records, _server_port, _server_ref

    parser = argparse.ArgumentParser(
        description=(
            "Gulf 1 Trace Recorder — local HTTP proxy that records "
            "Claude Code / OpenAI-compatible API sessions to JSONL."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python autorefine/scripts/record.py \\\n"
            "    --skill ~/.claude/skills/react-debug/SKILL.md \\\n"
            "    --port 8765 \\\n"
            "    --records-dir records\n\n"
            "Then:\n"
            "  export ANTHROPIC_BASE_URL=http://localhost:8765\n"
            "  export OPENAI_BASE_URL=http://localhost:8765/v1\n"
            "  claude  # or any OpenAI-compatible client\n"
        ),
    )
    parser.add_argument(
        "--skill",
        metavar="PATH",
        help="Path to the SKILL.md file under test. Basename is stored as skill_hint unless --raw-records is used.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        metavar="PORT",
        help="Port to bind the local proxy to (default: 8765).",
    )
    parser.add_argument(
        "--records-dir",
        default="records",
        metavar="DIR",
        help="Directory to write JSONL session files (default: records).",
    )
    parser.add_argument(
        "--allow-custom-upstream",
        action="store_true",
        help="Allow trusted custom HTTPS upstream base URLs instead of only official API hosts.",
    )
    parser.add_argument(
        "--raw-records",
        action="store_true",
        help="Preserve raw messages, responses, tool calls, and absolute skill paths in records.",
    )
    args = parser.parse_args()

    _server_port = args.port
    _raw_records = args.raw_records

    # Resolve --skill to an absolute path, if provided
    if args.skill:
        _skill_hint = str(Path(args.skill).resolve())
        if not Path(_skill_hint).exists():
            print(
                f"Warning: --skill path does not exist: {_skill_hint}\n"
                "Continuing — skill_hint will be recorded but may be invalid.",
                file=sys.stderr,
            )

    # Set ANTHROPIC_BASE_URL_REAL / OPENAI_BASE_URL_REAL from env BEFORE we
    # override those vars. This lets the proxy find the real upstream even
    # after the user exports the proxy's own URL as ANTHROPIC_BASE_URL.
    #
    # Why: the user will run `export ANTHROPIC_BASE_URL=http://localhost:8765`
    # so that their client points at US. We need to remember the ORIGINAL
    # upstream URL (or the default) so we know where to forward.
    #
    # We read these BEFORE printing the banner (which tells the user to export
    # those vars) so the env state is captured at server startup, not after
    # the user exports.
    real_anthropic = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    real_openai = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")

    try:
        real_anthropic = _validate_upstream_base_url(
            real_anthropic,
            "anthropic",
            args.allow_custom_upstream,
        )
        real_openai = _validate_upstream_base_url(
            real_openai,
            "openai",
            args.allow_custom_upstream,
        )
    except ValueError as exc:
        detail = str(exc)
        if "forwarding loop" not in detail:
            detail = f"unsafe upstream: {detail}"
        print(
            "Refusing to start: " + detail,
            file=sys.stderr,
        )
        sys.exit(1)

    os.environ["ANTHROPIC_BASE_URL_REAL"] = real_anthropic
    os.environ["OPENAI_BASE_URL_REAL"] = real_openai

    # Create the records directory (analogous to creating an output partition
    # in a data pipeline before writing parquet files)
    records_dir = Path(args.records_dir)
    records_dir.mkdir(parents=True, exist_ok=True)
    # PII warning in banner: keep directory private to the current user.
    os.chmod(records_dir, 0o700)
    skill_slug = _derive_skill_slug(args.skill)
    skill_records_dir = records_dir / skill_slug
    skill_records_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(skill_records_dir, 0o700)

    # Start the HTTP server and bind the port before creating records file.
    # This avoids orphaning a session file when the port is already occupied.
    server = ThreadedHTTPServer(("127.0.0.1", _server_port), ProxyHandler, bind_and_activate=False)
    try:
        server.server_bind()
        server.server_activate()
    except OSError:
        print(
            f"Port {_server_port} is in use — stop the other process or pass --port <other>",
            file=sys.stderr,
        )
        sys.exit(1)
    _server_ref = server

    # One file per session, named by session_id — like a partition key
    _records_path = skill_records_dir / f"{SESSION_ID}.jsonl"
    # Open in append mode (safe if file already exists, though session_id is
    # always fresh since it's a UUIDv4 generated at startup)
    fd = os.open(str(_records_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    _records_file = os.fdopen(fd, "a", encoding="utf-8")

    # Register SIGINT handler BEFORE starting the server loop
    signal.signal(signal.SIGINT, _handle_sigint)

    _print_banner(_server_port, _records_path, _skill_hint)

    # serve_forever() blocks here until _handle_sigint calls server.shutdown()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        # Fallback in case SIGINT handler doesn't fire (e.g. Windows)
        _handle_sigint(0, None)


if __name__ == "__main__":
    main()
