"""
test_records_to_gulf1_py.py — pytest tests for records-to-gulf1.py

Covers:
  1. auto-classify: success / failure / do-not-trigger heuristics
  2. missing required field → clear error with line number
  3. source_trace preserves session_id + turn
  4. missing optional field (skill_hint) → no crash
  5. directory input reads all .jsonl files
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import importlib.util

import pytest

# ── Load the converter module by file path (filename has hyphens, so we can't
#    use a normal import statement — instead we use importlib to load it
#    directly from disk, like `load_source` in older Python).  ────────────────
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "records_to_gulf1",
    SCRIPTS_DIR / "records-to-gulf1.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["records_to_gulf1"] = _mod
_spec.loader.exec_module(_mod)

# Aliases for convenience in tests.
build_output_row = _mod.build_output_row
classify_auto = _mod.classify_auto
collect_input_files = _mod.collect_input_files
validate_record = _mod.validate_record


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_turn(
    session_id="sess-abc123",
    turn=1,
    response_text="Here is the answer.",
    tool_calls=None,
    error=None,
    skill_hint=None,
    extra_messages=None,
):
    """
    Factory for a minimal valid trace record.
    Think of this like a test-data builder in a data pipeline test suite.
    """
    record = {
        "session_id": session_id,
        "turn": turn,
        "timestamp": "2026-04-21T18:34:56.123Z",
        "messages": (extra_messages or [{"role": "user", "content": "Help me debug this."}]),
        "response_text": response_text,
        "tool_calls": tool_calls if tool_calls is not None else [],
    }
    if error is not None:
        record["error"] = error
    if skill_hint is not None:
        record["skill_hint"] = skill_hint
    return record


THREE_TURN_JSONL = (
    '{"session_id":"sess-abc","turn":1,"timestamp":"2026-04-21T00:00:01Z","messages":[{"role":"user","content":"What time is it?"}],"response_text":"It is noon.","tool_calls":[]}\n'
    '{"session_id":"sess-abc","turn":2,"timestamp":"2026-04-21T00:00:02Z","messages":[{"role":"user","content":"Run this code"}],"response_text":"","tool_calls":[],"error":"upstream 500"}\n'
    '{"session_id":"sess-abc","turn":3,"timestamp":"2026-04-21T00:00:03Z","messages":[{"role":"user","content":"Ping"}],"response_text":"","tool_calls":[]}\n'
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def write_jsonl(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


def run_converter(input_path: str, output_path: str, classify: str = "auto"):
    """
    Run the converter end-to-end via its main() function by patching sys.argv.
    Returns the list of output rows as dicts.
    """
    converter_main = _mod.main

    old_argv = sys.argv[:]
    sys.argv = [
        "records-to-gulf1.py",
        "--input", input_path,
        "--output", output_path,
        "--classify", classify,
    ]
    try:
        converter_main()
    finally:
        sys.argv = old_argv

    rows = []
    with open(output_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ─── Test 1: auto-classify heuristics ────────────────────────────────────────

class TestClassifyAuto:
    """
    The three heuristic rules, tested independently.
    Analogy: unit-testing each labeling function in a Snorkel LF suite.
    """

    def test_success_nonempty_response(self):
        record = make_turn(response_text="Here is my answer.", tool_calls=[])
        cls, conf, reason = classify_auto(record)
        assert cls == "success"
        assert conf == "low"
        assert reason == "non_empty_response_but_no_success_criteria_matched"

    def test_failure_error_field_present(self):
        record = make_turn(response_text="", error="upstream 500 Internal Server Error")
        cls, conf, reason = classify_auto(record)
        assert cls == "failure"
        assert conf == "high"
        assert "error" in reason.lower()

    def test_do_not_trigger_empty_response_no_tools(self):
        record = make_turn(response_text="", tool_calls=[])
        cls, conf, reason = classify_auto(record)
        assert cls == "do-not-trigger"
        assert conf == "medium"
        assert "empty" in reason.lower()

    def test_error_field_takes_priority_over_empty_response(self):
        # Even if response is empty, explicit error → failure (Rule 1 > Rule 2).
        record = make_turn(response_text="", tool_calls=[], error="timeout")
        cls, conf, _ = classify_auto(record)
        assert cls == "failure"

    def test_success_with_tool_calls_only(self):
        # Tool calls but no text → still success (non-empty tool_calls means skill acted).
        record = make_turn(
            response_text="",
            tool_calls=[{"id": "t1", "name": "read_file", "arguments": {"path": "/foo"}}],
        )
        # Rule 2 requires BOTH empty response AND empty tool_calls.
        cls, _, _ = classify_auto(record)
        assert cls == "success"


# ─── Test 2: missing required field → error with line number ─────────────────

class TestValidation:
    def test_missing_session_id_raises(self):
        bad = {
            "turn": 1,
            "timestamp": "2026-04-21T00:00:00Z",
            "messages": [],
            "response_text": "",
            "tool_calls": [],
        }
        with pytest.raises(ValueError) as exc_info:
            validate_record(bad, "/fake/path.jsonl", 42)
        msg = str(exc_info.value)
        assert "/fake/path.jsonl:42" in msg
        assert "session_id" in msg

    def test_missing_turn_raises(self):
        bad = {
            "session_id": "s1",
            "timestamp": "2026-04-21T00:00:00Z",
            "messages": [],
            "response_text": "",
            "tool_calls": [],
        }
        with pytest.raises(ValueError) as exc_info:
            validate_record(bad, "records/foo.jsonl", 7)
        msg = str(exc_info.value)
        assert "records/foo.jsonl:7" in msg
        assert "turn" in msg

    def test_missing_messages_raises(self):
        bad = {
            "session_id": "s1",
            "turn": 1,
            "timestamp": "2026-04-21T00:00:00Z",
            "response_text": "",
            "tool_calls": [],
        }
        with pytest.raises(ValueError):
            validate_record(bad, "x.jsonl", 1)

    def test_malformed_tool_calls_not_list_raises(self):
        bad = {
            "session_id": "s1",
            "turn": 1,
            "timestamp": "2026-04-21T00:00:00Z",
            "messages": [],
            "response_text": "",
            "tool_calls": "not-a-list",
        }
        with pytest.raises(ValueError) as exc_info:
            validate_record(bad, "x.jsonl", 3)
        assert "tool_calls" in str(exc_info.value)

    def test_malformed_response_text_not_string_raises(self):
        bad = {
            "session_id": "s1",
            "turn": 1,
            "timestamp": "2026-04-21T00:00:00Z",
            "messages": [],
            "response_text": {"text": "nested"},
            "tool_calls": [],
        }
        with pytest.raises(ValueError) as exc_info:
            validate_record(bad, "x.jsonl", 4)
        msg = str(exc_info.value)
        assert "response_text" in msg
        assert "string" in msg

    def test_malformed_session_id_not_string_raises(self):
        bad = make_turn()
        bad["session_id"] = 123
        with pytest.raises(ValueError, match="session_id.*string"):
            validate_record(bad, "x.jsonl", 5)

    @pytest.mark.parametrize("bad_turn", [0, -1, "1", 1.2])
    def test_malformed_turn_not_positive_integer_raises(self, bad_turn):
        bad = make_turn()
        bad["turn"] = bad_turn
        with pytest.raises(ValueError, match="turn.*positive integer"):
            validate_record(bad, "x.jsonl", 6)

    def test_malformed_timestamp_not_string_raises(self):
        bad = make_turn()
        bad["timestamp"] = None
        with pytest.raises(ValueError, match="timestamp.*string"):
            validate_record(bad, "x.jsonl", 7)

    def test_valid_record_does_not_raise(self):
        good = make_turn()
        # Should not raise.
        validate_record(good, "x.jsonl", 1)

    def test_main_exits_on_malformed_jsonl_with_file_and_line(self, tmp_path, capsys):
        in_file = tmp_path / "bad.jsonl"
        out_file = tmp_path / "out.jsonl"
        good = make_turn()
        in_file.write_text(
            json.dumps(good) + "\n" + '{"session_id":"x","turn":2,\n',
            encoding="utf-8",
        )

        old_argv = sys.argv[:]
        sys.argv = [
            "records-to-gulf1.py",
            "--input", str(in_file),
            "--output", str(out_file),
            "--classify", "auto",
        ]
        try:
            with pytest.raises(SystemExit) as exc_info:
                _mod.main()
        finally:
            sys.argv = old_argv

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert str(in_file) in err
        assert ":2]" in err


# ─── Test 3: source_trace preserves session_id + turn ────────────────────────

class TestSourceTrace:
    def test_source_trace_fields(self, tmp_path):
        """
        The cross-reference embedded in every output row must carry through
        session_id and turn exactly as they appeared in the input record.
        Like a foreign key test in a data warehouse — the join key must survive ETL.
        """
        jsonl_file = tmp_path / "session.jsonl"
        write_jsonl(jsonl_file, THREE_TURN_JSONL)

        out_file = str(tmp_path / "out.jsonl")
        rows = run_converter(str(jsonl_file), out_file, classify="auto")

        assert len(rows) == 3

        # Turn 1 — should be success
        assert rows[0]["source_trace"]["session_id"] == "sess-abc"
        assert rows[0]["source_trace"]["turn"] == 1

        # Turn 2 — should be failure (error field)
        assert rows[1]["source_trace"]["session_id"] == "sess-abc"
        assert rows[1]["source_trace"]["turn"] == 2

        # Turn 3 — should be do-not-trigger
        assert rows[2]["source_trace"]["session_id"] == "sess-abc"
        assert rows[2]["source_trace"]["turn"] == 3

    def test_ids_match_classifications(self, tmp_path):
        jsonl_file = tmp_path / "session.jsonl"
        write_jsonl(jsonl_file, THREE_TURN_JSONL)
        out_file = str(tmp_path / "out.jsonl")
        rows = run_converter(str(jsonl_file), out_file, classify="auto")

        assert rows[0]["id"] == "success-1"
        assert rows[1]["id"] == "failure-1"
        assert rows[2]["id"] == "dnt-1"


# ─── Test 4: missing optional field (skill_hint) ─────────────────────────────

class TestOptionalFields:
    def test_missing_skill_hint_no_crash(self, tmp_path):
        """
        skill_hint is optional. Omitting it must not crash or emit an error.
        """
        record = make_turn()  # no skill_hint kwarg → field absent
        assert "skill_hint" not in record

        jsonl_file = tmp_path / "no_hint.jsonl"
        write_jsonl(jsonl_file, json.dumps(record) + "\n")

        out_file = str(tmp_path / "out.jsonl")
        rows = run_converter(str(jsonl_file), out_file, classify="auto")

        assert len(rows) == 1
        # skill_hint should NOT appear in output when absent in input.
        assert "skill_hint" not in rows[0]

    def test_skill_hint_forwarded_when_present(self, tmp_path):
        record = make_turn(skill_hint="/Users/alice/.claude/skills/my-skill/SKILL.md")
        jsonl_file = tmp_path / "with_hint.jsonl"
        write_jsonl(jsonl_file, json.dumps(record) + "\n")

        out_file = str(tmp_path / "out.jsonl")
        rows = run_converter(str(jsonl_file), out_file, classify="auto")

        assert rows[0]["skill_hint"] == "/Users/alice/.claude/skills/my-skill/SKILL.md"

    def test_missing_upstream_model_no_crash(self, tmp_path):
        record = make_turn()
        assert "upstream_model" not in record

        jsonl_file = tmp_path / "no_model.jsonl"
        write_jsonl(jsonl_file, json.dumps(record) + "\n")
        out_file = str(tmp_path / "out.jsonl")
        rows = run_converter(str(jsonl_file), out_file, classify="none")
        assert len(rows) == 1


# ─── Test 5: directory input reads all .jsonl files ──────────────────────────

class TestDirectoryInput:
    def test_reads_multiple_jsonl_files(self, tmp_path):
        """
        Two sessions in two separate files → converter merges them.
        Analogous to reading a partitioned Parquet dataset where each file is
        one partition (one session).
        """
        # Session A: 1 turn (success)
        sess_a = make_turn(session_id="sess-A", turn=1, response_text="Answer A.")
        (tmp_path / "session-A.jsonl").write_text(json.dumps(sess_a) + "\n")

        # Session B: 2 turns (success + failure)
        sess_b1 = make_turn(session_id="sess-B", turn=1, response_text="Answer B1.")
        sess_b2 = make_turn(session_id="sess-B", turn=2, response_text="", error="timeout")
        (tmp_path / "session-B.jsonl").write_text(
            json.dumps(sess_b1) + "\n" + json.dumps(sess_b2) + "\n"
        )

        out_file = str(tmp_path / "merged.jsonl")
        rows = run_converter(str(tmp_path), out_file, classify="auto")

        assert len(rows) == 3

        session_ids = {r["source_trace"]["session_id"] for r in rows}
        assert session_ids == {"sess-A", "sess-B"}

    def test_non_jsonl_files_ignored(self, tmp_path):
        """
        A .txt file in the directory should be silently ignored.
        """
        record = make_turn()
        (tmp_path / "data.jsonl").write_text(json.dumps(record) + "\n")
        (tmp_path / "readme.txt").write_text("This is not JSONL.\n")

        out_file = str(tmp_path / "out.jsonl")
        rows = run_converter(str(tmp_path), out_file, classify="none")
        assert len(rows) == 1

    def test_classify_none_produces_unclassified(self, tmp_path):
        """
        --classify none must emit rows with classification == 'unclassified'
        regardless of response content.
        """
        record = make_turn(response_text="Hello.")
        jsonl_file = tmp_path / "data.jsonl"
        write_jsonl(jsonl_file, json.dumps(record) + "\n")

        out_file = str(tmp_path / "out.jsonl")
        rows = run_converter(str(jsonl_file), out_file, classify="none")

        assert rows[0]["classification"] == "unclassified"
        assert rows[0]["id"].startswith("unclassified-")

    def test_recurses_nested_records_dirs_and_preserves_skill_hint(self, tmp_path):
        records_root = tmp_path / "records"
        skill_a_dir = records_root / "skill-a"
        skill_b_dir = records_root / "skill-b"
        skill_a_dir.mkdir(parents=True)
        skill_b_dir.mkdir(parents=True)

        rec_a = make_turn(
            session_id="sess-skill-a",
            turn=1,
            response_text="A response",
            skill_hint="/Users/alice/.claude/skills/skill-a/SKILL.md",
        )
        rec_b = make_turn(
            session_id="sess-skill-b",
            turn=1,
            response_text="B response",
            skill_hint="/Users/alice/.claude/skills/skill-b/SKILL.md",
        )

        (skill_a_dir / "a.jsonl").write_text(json.dumps(rec_a) + "\n", encoding="utf-8")
        (skill_b_dir / "b.jsonl").write_text(json.dumps(rec_b) + "\n", encoding="utf-8")

        out_file = str(tmp_path / "out.jsonl")
        rows = run_converter(str(records_root), out_file, classify="none")

        assert len(rows) == 2
        by_session = {row["source_trace"]["session_id"]: row for row in rows}
        assert by_session["sess-skill-a"]["skill_hint"].endswith("/skill-a/SKILL.md")
        assert by_session["sess-skill-b"]["skill_hint"].endswith("/skill-b/SKILL.md")

    def test_reads_nested_skill_directories_and_preserves_skill_hint(self, tmp_path):
        records_root = tmp_path / "records"
        (records_root / "skill-alpha").mkdir(parents=True)
        (records_root / "skill-beta").mkdir(parents=True)

        alpha = make_turn(
            session_id="sess-alpha",
            turn=1,
            response_text="alpha ok",
            skill_hint="/skills/alpha/SKILL.md",
        )
        beta = make_turn(
            session_id="sess-beta",
            turn=1,
            response_text="beta ok",
            skill_hint="/skills/beta/SKILL.md",
        )

        (records_root / "skill-alpha" / "sess-alpha.jsonl").write_text(
            json.dumps(alpha) + "\n", encoding="utf-8"
        )
        (records_root / "skill-beta" / "sess-beta.jsonl").write_text(
            json.dumps(beta) + "\n", encoding="utf-8"
        )

        out_file = str(tmp_path / "merged-recursive.jsonl")
        rows = run_converter(str(records_root), out_file, classify="auto")

        assert len(rows) == 2
        hints = {row.get("skill_hint") for row in rows}
        assert hints == {"/skills/alpha/SKILL.md", "/skills/beta/SKILL.md"}


class TestCollectInputFilesLayout:
    def test_collects_two_level_skill_jsonl_files(self, tmp_path):
        records_root = tmp_path / "records"
        (records_root / "slug-a").mkdir(parents=True)
        (records_root / "slug-b").mkdir(parents=True)
        (records_root / "slug-a" / "x.jsonl").write_text("{}", encoding="utf-8")
        (records_root / "slug-b" / "y.jsonl").write_text("{}", encoding="utf-8")

        files = collect_input_files(str(records_root))
        assert {p.name for p in files} == {"x.jsonl", "y.jsonl"}

    def test_collects_flat_jsonl_when_two_level_layout_missing(self, tmp_path):
        records_root = tmp_path / "records"
        records_root.mkdir()
        (records_root / "x.jsonl").write_text("{}", encoding="utf-8")

        files = collect_input_files(str(records_root))
        assert [p.name for p in files] == ["x.jsonl"]

    def test_does_not_collect_deep_nested_orphan_jsonl(self, tmp_path):
        records_root = tmp_path / "records"
        (records_root / "slug-a" / "nested").mkdir(parents=True)
        (records_root / "slug-a" / "x.jsonl").write_text("{}", encoding="utf-8")
        (records_root / "slug-a" / "nested" / "orphan.jsonl").write_text("{}", encoding="utf-8")

        files = collect_input_files(str(records_root))
        assert {p.name for p in files} == {"x.jsonl"}

    def test_flat_fallback_collects_root_unrelated_jsonl(self, tmp_path):
        records_root = tmp_path / "records"
        records_root.mkdir()
        (records_root / "unrelated.jsonl").write_text("{}", encoding="utf-8")

        files = collect_input_files(str(records_root))
        assert [p.name for p in files] == ["unrelated.jsonl"]


def test_mixed_layout_discovers_both_flat_and_nested(tmp_path):
    records_root = tmp_path / "records"
    nested_dir = records_root / "slug-a"
    nested_dir.mkdir(parents=True)

    flat_record = make_turn(
        session_id="session-flat",
        turn=1,
        response_text="flat response",
    )
    nested_record = make_turn(
        session_id="session-nested",
        turn=1,
        response_text="nested response",
    )

    (records_root / "flat.jsonl").write_text(json.dumps(flat_record) + "\n", encoding="utf-8")
    (nested_dir / "nested.jsonl").write_text(json.dumps(nested_record) + "\n", encoding="utf-8")

    out_file = str(tmp_path / "out.jsonl")
    rows = run_converter(str(records_root), out_file, classify="none")

    found_session_ids = {row["source_trace"]["session_id"] for row in rows}
    assert found_session_ids == {"session-flat", "session-nested"}


def test_converter_refuses_to_overwrite_input_file(tmp_path, capsys):
    input_file = tmp_path / "session.jsonl"
    original = json.dumps(make_turn()) + "\n"
    input_file.write_text(original, encoding="utf-8")

    old_argv = sys.argv[:]
    sys.argv = [
        "records-to-gulf1.py",
        "--input", str(input_file),
        "--output", str(input_file),
    ]
    try:
        with pytest.raises(SystemExit) as exc:
            _mod.main()
    finally:
        sys.argv = old_argv

    assert exc.value.code == 1
    assert "must not match an input file" in capsys.readouterr().err
    assert input_file.read_text(encoding="utf-8") == original


def test_converter_refuses_to_overwrite_existing_output_without_force(tmp_path, capsys):
    input_file = tmp_path / "session.jsonl"
    output_file = tmp_path / "existing.jsonl"
    input_file.write_text(json.dumps(make_turn()) + "\n", encoding="utf-8")
    output_file.write_text("keep me\n", encoding="utf-8")

    old_argv = sys.argv[:]
    sys.argv = [
        "records-to-gulf1.py",
        "--input", str(input_file),
        "--output", str(output_file),
    ]
    try:
        with pytest.raises(SystemExit) as exc:
            _mod.main()
    finally:
        sys.argv = old_argv

    assert exc.value.code == 1
    assert "refusing to overwrite existing output file" in capsys.readouterr().err
    assert output_file.read_text(encoding="utf-8") == "keep me\n"


def test_converter_refuses_to_write_through_symlink(tmp_path, capsys):
    input_file = tmp_path / "session.jsonl"
    target_file = tmp_path / "target.jsonl"
    output_link = tmp_path / "linked-output.jsonl"
    input_file.write_text(json.dumps(make_turn()) + "\n", encoding="utf-8")
    target_file.write_text("keep target\n", encoding="utf-8")
    output_link.symlink_to(target_file)

    old_argv = sys.argv[:]
    sys.argv = [
        "records-to-gulf1.py",
        "--input", str(input_file),
        "--output", str(output_link),
    ]
    try:
        with pytest.raises(SystemExit) as exc:
            _mod.main()
    finally:
        sys.argv = old_argv

    assert exc.value.code == 1
    assert "refusing to write through symlink" in capsys.readouterr().err
    assert target_file.read_text(encoding="utf-8") == "keep target\n"


def test_converter_force_overwrites_existing_output(tmp_path):
    input_file = tmp_path / "session.jsonl"
    output_file = tmp_path / "existing.jsonl"
    input_file.write_text(json.dumps(make_turn()) + "\n", encoding="utf-8")
    output_file.write_text("replace me\n", encoding="utf-8")

    old_argv = sys.argv[:]
    sys.argv = [
        "records-to-gulf1.py",
        "--input", str(input_file),
        "--output", str(output_file),
        "--force",
    ]
    try:
        _mod.main()
    finally:
        sys.argv = old_argv

    rows = [json.loads(line) for line in output_file.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["source_trace"]["session_id"] == "sess-abc123"
