from __future__ import annotations

import json
import re
from bisect import bisect_right
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._shared_text import (
    clean_identifier as _clean_identifier,
    clean_text as _clean_text,
    now_utc_timestamp as _now_utc_timestamp,
    _sha256_text,
    _first_present,
    _coerce_numeric,
)


EXEMPLAR_SOURCE_BUNDLE_SCHEMA_VERSION = 1
CANONICAL_BUNDLE_TYPE = "candidate_skill_record_bundle"
CANONICAL_SOURCE_KINDS = ("repository", "evaluation_result_store")
CANONICAL_SOURCE_LOAD_STATUSES = ("loaded", "missing", "parse_failed", "empty")
CANONICAL_RECORD_KINDS = ("repository_skill", "evaluated_skill_version")
DEFAULT_EXEMPLAR_SOURCES_STATE_KEY = "exemplar_sources"
DEFAULT_EXEMPLAR_SELECTION_STATE_KEY = "exemplar_selection"
VISIBLE_EXPERIMENT_STATUSES = ("baseline", "keep")
EXEMPLAR_SELECTION_SCHEMA_VERSION = 1
CANONICAL_SELECTION_TYPE = "selected_exemplar_record_bundle"
CANONICAL_SELECTION_DEDUPE_STRATEGIES = ("content_hash", "skill_id", "none")
SKILL_CONTENT_SCHEMA_VERSION = 1
EXEMPLAR_PAYLOAD_SCHEMA_VERSION = 1
CANONICAL_EXEMPLAR_PAYLOAD_TYPE = "selected_exemplar_payload"
SKILL_VERSION_SNAPSHOT_SCHEMA_VERSION = 1
CANONICAL_VERSION_SNAPSHOT_BUNDLE_TYPE = "skill_version_snapshot_bundle"

_HEADING_PATTERN = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)
_FRONTMATTER_DESCRIPTION_PATTERN = re.compile(
    r"^---\s*\n.*?^description:\s*(.+?)\s*$.*?^---\s*$",
    re.MULTILINE | re.DOTALL,
)
_FRONTMATTER_BLOCK_PATTERN = re.compile(r"\A---\n(.*?)\n---(?:\n|$)", re.DOTALL)
_HEADING_ENTRY_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_ORDERED_STEP_PATTERN = re.compile(r"^\s*\d+\.\s+.+$", re.MULTILINE)
_SEARCH_TEXT_PATTERN = re.compile(r"[^a-z0-9]+")


class ExemplarSourceValidationError(ValueError):
    """Validation failure for exemplar source configuration."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    normalized = _clean_text(value).lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"expected boolean-compatible value, received {value!r}")


def _coerce_positive_int(value: Any, *, field_name: str, default: int) -> int:
    if value is None or _clean_text(value) == "":
        return default
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive integer")

    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer") from exc

    if normalized <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return normalized


def _normalize_percentage_metric(value: Any) -> float | None:
    numeric = _coerce_numeric(value)
    if numeric is None or numeric < 0:
        return None
    if numeric <= 1:
        return numeric
    if numeric <= 100:
        return numeric / 100
    return None


def _normalize_threshold(value: Any, *, field_name: str) -> float | None:
    if value is None or _clean_text(value) == "":
        return None
    normalized = _normalize_percentage_metric(value)
    if normalized is None:
        raise ValueError(
            f"{field_name} must be a percentage between 0-1 or 0-100; received {value!r}"
        )
    return normalized


def _read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        return handle.read()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"expected JSON object in {path}, received {type(data).__name__}")
    return data


def _clone_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _clone_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_clone_json_value(item) for item in value]
    return value


def _extract_title(skill_text: str, *, default: str) -> str:
    match = _HEADING_PATTERN.search(skill_text)
    if match is not None:
        return match.group(1).strip()
    return default


def _extract_summary(skill_text: str, *, default: str) -> str:
    frontmatter_match = _FRONTMATTER_DESCRIPTION_PATTERN.search(skill_text)
    if frontmatter_match is not None:
        return frontmatter_match.group(1).strip().strip("'\"")
    return default


def _normalize_skill_text(skill_text: str) -> str:
    normalized = skill_text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return ""
    return normalized.rstrip("\n") + "\n"


def _parse_skill_frontmatter(skill_text: str) -> tuple[dict[str, str], str, bool, int]:
    match = _FRONTMATTER_BLOCK_PATTERN.match(skill_text)
    if match is None:
        return {}, skill_text, False, 0

    frontmatter: dict[str, str] = {}
    for line in match.group(1).splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#") or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        normalized_key = _clean_identifier(key)
        if not normalized_key:
            continue
        frontmatter[normalized_key] = _clean_text(raw_value).strip("'\"")

    return frontmatter, skill_text[match.end() :], True, match.end()


def _extract_heading_entries(skill_text: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for match in _HEADING_ENTRY_PATTERN.finditer(skill_text):
        headings.append(
            {
                "level": len(match.group(1)),
                "text": match.group(2).strip(),
            }
        )
    return headings


def _normalize_search_text(value: str) -> str:
    normalized = _clean_text(value).lower()
    if not normalized:
        return ""
    return " ".join(_SEARCH_TEXT_PATTERN.sub(" ", normalized).split())


def _build_line_start_offsets(text: str) -> list[int]:
    line_starts = [0]
    for match in re.finditer(r"\n", text):
        next_offset = match.end()
        if next_offset < len(text):
            line_starts.append(next_offset)
    return line_starts


def _line_number_for_offset(line_starts: list[int], offset: int) -> int:
    if not line_starts:
        return 1
    bounded_offset = max(offset, 0)
    return max(1, bisect_right(line_starts, bounded_offset))


def _line_end_for_span(text: str, line_starts: list[int], start: int, end: int) -> int:
    if end <= start:
        return _line_number_for_offset(line_starts, start)

    trimmed_end = end
    while trimmed_end > start and text[trimmed_end - 1] == "\n":
        trimmed_end -= 1

    if trimmed_end <= start:
        return _line_number_for_offset(line_starts, start)
    return _line_number_for_offset(line_starts, trimmed_end - 1)


def _byte_offset(text: str, char_offset: int) -> int:
    return len(text[:char_offset].encode("utf-8"))


def _clone_heading_path(path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(entry) for entry in path]


def _build_skill_content_chunks(
    normalized_text: str,
    *,
    body_start_offset: int,
    source_path: str | None = None,
    relative_path: str | None = None,
) -> list[dict[str, Any]]:
    if not normalized_text:
        return []

    line_starts = _build_line_start_offsets(normalized_text)
    normalized_source_path = _clean_text(source_path) or None
    normalized_relative_path = _clean_text(relative_path) or None
    locator_path = normalized_relative_path or normalized_source_path

    heading_matches = [
        {
            "start": match.start(),
            "level": len(match.group(1)),
            "text": match.group(2).strip(),
        }
        for match in _HEADING_ENTRY_PATTERN.finditer(normalized_text, body_start_offset)
    ]

    chunks: list[dict[str, Any]] = []
    section_id_counts: dict[str, int] = {}

    def append_chunk(
        *,
        start: int,
        end: int,
        chunk_kind: str,
        section_id: str,
        heading_path: list[dict[str, Any]],
    ) -> None:
        if end <= start:
            return

        chunk_text = normalized_text[start:end]
        if not chunk_text.strip():
            return

        line_start = _line_number_for_offset(line_starts, start)
        line_end = _line_end_for_span(normalized_text, line_starts, start, end)
        chunk_id = f"chunk_{len(chunks) + 1:03d}_{section_id}"

        chunks.append(
            {
                "chunk_id": chunk_id,
                "chunk_kind": chunk_kind,
                "order": len(chunks) + 1,
                "section_id": section_id,
                "heading_path": _clone_heading_path(heading_path),
                "text": chunk_text,
                "content_hash": _sha256_text(chunk_text),
                "char_start": start,
                "char_end": end,
                "line_start": line_start,
                "line_end": line_end,
                "byte_start": _byte_offset(normalized_text, start),
                "byte_end": _byte_offset(normalized_text, end),
                "source_locator": {
                    "path": locator_path,
                    "relative_path": normalized_relative_path,
                    "absolute_path": normalized_source_path,
                    "offset_basis": "normalized_text_utf8",
                    "section_id": section_id,
                    "heading_path": [entry["text"] for entry in heading_path],
                    "heading_path_ids": [entry["section_id"] for entry in heading_path],
                },
            }
        )

    if body_start_offset > 0:
        append_chunk(
            start=0,
            end=body_start_offset,
            chunk_kind="frontmatter",
            section_id="frontmatter",
            heading_path=[],
        )

    if not heading_matches:
        body_text = normalized_text[body_start_offset:]
        if body_text.strip():
            append_chunk(
                start=body_start_offset,
                end=len(normalized_text),
                chunk_kind="document",
                section_id="body" if body_start_offset > 0 else "document",
                heading_path=[],
            )
        return chunks

    first_heading_start = heading_matches[0]["start"]
    if first_heading_start > body_start_offset:
        append_chunk(
            start=body_start_offset,
            end=first_heading_start,
            chunk_kind="preamble",
            section_id="preamble",
            heading_path=[],
        )

    heading_stack: list[dict[str, Any]] = []
    for index, heading in enumerate(heading_matches):
        while heading_stack and heading_stack[-1]["level"] >= heading["level"]:
            heading_stack.pop()

        heading_slug = _clean_identifier(heading["text"], default=f"section_{index + 1}") or f"section_{index + 1}"
        parent_section_ids = [entry["section_id"] for entry in heading_stack]
        base_section_id = (
            "__".join(parent_section_ids + [heading_slug])
            if parent_section_ids
            else heading_slug
        )
        occurrence = section_id_counts.get(base_section_id, 0) + 1
        section_id_counts[base_section_id] = occurrence
        section_id = base_section_id if occurrence == 1 else f"{base_section_id}__{occurrence}"

        current_path = _clone_heading_path(heading_stack)
        current_path.append(
            {
                "level": heading["level"],
                "text": heading["text"],
                "section_id": section_id,
            }
        )
        heading_stack = current_path

        chunk_end = (
            heading_matches[index + 1]["start"]
            if index + 1 < len(heading_matches)
            else len(normalized_text)
        )
        append_chunk(
            start=heading["start"],
            end=chunk_end,
            chunk_kind="section",
            section_id=section_id,
            heading_path=current_path,
        )

    return chunks


def _build_skill_content_snapshot(
    skill_text: str,
    *,
    default_title: str,
    source_path: str | None = None,
    relative_path: str | None = None,
) -> dict[str, Any]:
    normalized_text = _normalize_skill_text(skill_text)
    frontmatter, body_text, has_frontmatter, body_start_offset = _parse_skill_frontmatter(normalized_text)
    title = _extract_title(body_text or normalized_text, default=default_title)
    summary = _clean_text(frontmatter.get("description")) or title
    headings = _extract_heading_entries(body_text or normalized_text)
    body_search_text = "\n".join(part for part in (title, summary, body_text) if part)
    chunks = _build_skill_content_chunks(
        normalized_text,
        body_start_offset=body_start_offset,
        source_path=source_path,
        relative_path=relative_path,
    )

    return {
        "schema_version": SKILL_CONTENT_SCHEMA_VERSION,
        "normalized_text": normalized_text,
        "body_text": body_text,
        "frontmatter": frontmatter,
        "has_frontmatter": has_frontmatter,
        "title": title,
        "summary": summary,
        "headings": headings,
        "chunks": chunks,
        "chunk_count": len(chunks),
        "ordered_step_count": len(_ORDERED_STEP_PATTERN.findall(body_text)),
        "line_count": len(normalized_text.splitlines()),
        "body_line_count": len(body_text.splitlines()),
        "char_count": len(normalized_text),
        "search_text": _normalize_search_text(body_search_text),
    }


def _relative_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _normalize_source_config(raw_source: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    errors: list[str] = []
    source_id = _clean_identifier(raw_source.get("source_id"))
    if not source_id:
        errors.append(f"exemplar_sources[{index}].source_id is required")

    source_kind = _clean_text(raw_source.get("source_kind"))
    if source_kind not in CANONICAL_SOURCE_KINDS:
        errors.append(
            f"exemplar_sources[{index}].source_kind must be one of "
            f"{CANONICAL_SOURCE_KINDS}; received {raw_source.get('source_kind')!r}"
        )

    location = _clean_text(raw_source.get("location"))
    if not location:
        errors.append(f"exemplar_sources[{index}].location is required")

    if errors:
        raise ExemplarSourceValidationError(errors)

    normalized = {
        "source_id": source_id,
        "source_kind": source_kind,
        "location": str(Path(location).expanduser()),
    }

    analysis_goal = _clean_text(raw_source.get("analysis_goal"))
    if analysis_goal:
        normalized["analysis_goal"] = analysis_goal

    return normalized


def resolve_exemplar_source_configs(
    exemplar_sources: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
    *,
    state: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Resolve normalized exemplar source configuration."""

    if exemplar_sources is None and state is not None:
        if not isinstance(state, Mapping):
            raise TypeError("state must be a mapping when provided")
        exemplar_sources = state.get(DEFAULT_EXEMPLAR_SOURCES_STATE_KEY)

    if exemplar_sources is None:
        return []

    if not isinstance(exemplar_sources, (list, tuple)):
        raise TypeError("exemplar_sources must be a list or tuple")

    normalized_sources: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    for index, raw_source in enumerate(exemplar_sources):
        if not isinstance(raw_source, Mapping):
            raise TypeError(f"exemplar_sources[{index}] must be a mapping")
        normalized_source = _normalize_source_config(raw_source, index=index)
        source_id = normalized_source["source_id"]
        if source_id in seen_source_ids:
            raise ExemplarSourceValidationError(
                [f"duplicate exemplar source_id {source_id!r} is not allowed"]
            )
        seen_source_ids.add(source_id)
        normalized_sources.append(normalized_source)

    return normalized_sources


def resolve_exemplar_selection_config(
    exemplar_selection: Mapping[str, Any] | None = None,
    *,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve normalized exemplar-selection configuration."""

    if exemplar_selection is None and state is not None:
        if not isinstance(state, Mapping):
            raise TypeError("state must be a mapping when provided")
        raw_from_state = state.get(DEFAULT_EXEMPLAR_SELECTION_STATE_KEY)
        if raw_from_state is not None:
            exemplar_selection = raw_from_state

    if exemplar_selection is None:
        exemplar_selection = {}

    if not isinstance(exemplar_selection, Mapping):
        raise TypeError("exemplar_selection must be a mapping")

    enabled_record_kinds = exemplar_selection.get("enabled_record_kinds")
    if enabled_record_kinds is None:
        normalized_record_kinds = list(CANONICAL_RECORD_KINDS)
    else:
        if not isinstance(enabled_record_kinds, (list, tuple)):
            raise ValueError("exemplar_selection.enabled_record_kinds must be a list or tuple")
        normalized_record_kinds = []
        for index, raw_kind in enumerate(enabled_record_kinds):
            normalized_kind = _clean_text(raw_kind)
            if normalized_kind not in CANONICAL_RECORD_KINDS:
                raise ValueError(
                    "exemplar_selection.enabled_record_kinds[{index}] must be one of "
                    f"{CANONICAL_RECORD_KINDS}; received {raw_kind!r}".format(index=index)
                )
            if normalized_kind not in normalized_record_kinds:
                normalized_record_kinds.append(normalized_kind)

    allowed_experiment_statuses = exemplar_selection.get("allowed_experiment_statuses")
    if allowed_experiment_statuses is None:
        normalized_statuses = list(VISIBLE_EXPERIMENT_STATUSES)
    else:
        if not isinstance(allowed_experiment_statuses, (list, tuple)):
            raise ValueError(
                "exemplar_selection.allowed_experiment_statuses must be a list or tuple"
            )
        normalized_statuses = []
        for index, raw_status in enumerate(allowed_experiment_statuses):
            normalized_status = _clean_text(raw_status)
            if normalized_status not in VISIBLE_EXPERIMENT_STATUSES:
                raise ValueError(
                    "exemplar_selection.allowed_experiment_statuses[{index}] must be one of "
                    f"{VISIBLE_EXPERIMENT_STATUSES}; received {raw_status!r}".format(index=index)
                )
            if normalized_status not in normalized_statuses:
                normalized_statuses.append(normalized_status)

    dedupe_strategy = _clean_text(
        exemplar_selection.get("dedupe_strategy"),
        default="content_hash",
    )
    if dedupe_strategy not in CANONICAL_SELECTION_DEDUPE_STRATEGIES:
        raise ValueError(
            "exemplar_selection.dedupe_strategy must be one of "
            f"{CANONICAL_SELECTION_DEDUPE_STRATEGIES}; received {dedupe_strategy!r}"
        )

    return {
        "enabled_record_kinds": normalized_record_kinds,
        "allowed_experiment_statuses": normalized_statuses,
        "require_evaluation_metrics": _coerce_bool(
            exemplar_selection.get("require_evaluation_metrics"),
            default=False,
        ),
        "minimum_final_score": _normalize_threshold(
            exemplar_selection.get("minimum_final_score"),
            field_name="exemplar_selection.minimum_final_score",
        ),
        "minimum_weighted_score": _normalize_threshold(
            exemplar_selection.get("minimum_weighted_score"),
            field_name="exemplar_selection.minimum_weighted_score",
        ),
        "minimum_pass_rate": _normalize_threshold(
            exemplar_selection.get("minimum_pass_rate"),
            field_name="exemplar_selection.minimum_pass_rate",
        ),
        "minimum_score_ratio": _normalize_threshold(
            exemplar_selection.get("minimum_score_ratio"),
            field_name="exemplar_selection.minimum_score_ratio",
        ),
        "max_selected_records": _coerce_positive_int(
            exemplar_selection.get("max_selected_records"),
            field_name="exemplar_selection.max_selected_records",
            default=10,
        ),
        "dedupe_strategy": dedupe_strategy,
        "prefer_selected_candidate": _coerce_bool(
            exemplar_selection.get("prefer_selected_candidate"),
            default=True,
        ),
    }


def _resolve_repository_skill_paths(source_root: Path) -> list[Path]:
    if source_root.is_file():
        return [source_root] if source_root.name == "SKILL.md" else []
    return sorted(
        path
        for path in source_root.rglob("SKILL.md")
        if path.is_file() and not any(part.startswith(".") for part in path.parts)
    )


def _build_repository_record(
    *,
    source: dict[str, Any],
    source_root: Path,
    skill_path: Path,
) -> dict[str, Any]:
    skill_text = _read_text(skill_path)
    references_path = skill_path.with_name("references.md")
    title_default = skill_path.parent.name or skill_path.stem
    relative_path = _relative_path(
        skill_path,
        source_root if source_root.is_dir() else source_root.parent,
    )
    skill_content = _build_skill_content_snapshot(
        skill_text,
        default_title=title_default,
        source_path=str(skill_path),
        relative_path=relative_path,
    )
    title = skill_content["title"]
    summary = skill_content["summary"]

    return {
        "record_id": f"{source['source_id']}:{_clean_identifier(skill_path.parent.name or skill_path.stem)}",
        "record_kind": "repository_skill",
        "source_id": source["source_id"],
        "source_kind": source["source_kind"],
        "skill_id": _clean_identifier(title, default=_clean_identifier(title_default)),
        "version_label": None,
        "title": title,
        "summary": summary,
        "skill_path": str(skill_path),
        "relative_path": relative_path,
        "references_path": str(references_path) if references_path.is_file() else None,
        "skill_text": skill_text,
        "skill_content": skill_content,
        "content_hash": _sha256_text(skill_content["normalized_text"]),
        "evaluation_context": None,
        "provenance": {
            "analysis_goal": source.get("analysis_goal"),
            "repository_root": str(source_root if source_root.is_dir() else source_root.parent),
            "resolved_from": source["location"],
        },
    }


def _load_repository_source(source: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_root = Path(source["location"])
    summary = dict(source)
    if not source_root.exists():
        summary.update({"load_status": "missing", "record_count": 0})
        return summary, []

    try:
        skill_paths = _resolve_repository_skill_paths(source_root)
        records = [
            _build_repository_record(source=source, source_root=source_root, skill_path=skill_path)
            for skill_path in skill_paths
        ]
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        summary.update(
            {
                "load_status": "parse_failed",
                "record_count": 0,
                "error": str(exc),
            }
        )
        return summary, []

    summary.update(
        {
            "load_status": "loaded" if records else "empty",
            "record_count": len(records),
        }
    )
    return summary, records


def _resolve_result_store_paths(location: Path) -> tuple[Path, Path, Path]:
    if location.is_file():
        if location.name != "results.json":
            raise ValueError("evaluation_result_store file location must point to results.json")
        store_root = location.parent
        results_path = location
    else:
        store_root = location
        results_path = store_root / "results.json"
    return (
        store_root,
        results_path,
        store_root / "session_close_holdout" / "variant_results.json",
    )


def _resolve_version_artifact_snapshot_path(
    experiment: Mapping[str, Any], *, store_root: Path
) -> Path | None:
    version_artifact = experiment.get("version_artifact")
    if not isinstance(version_artifact, Mapping):
        return None

    snapshot_text = _clean_text(version_artifact.get("snapshot_path"))
    if not snapshot_text:
        return None

    snapshot_path = Path(snapshot_text).expanduser()
    if not snapshot_path.is_absolute():
        snapshot_path = store_root / snapshot_path
    return snapshot_path


def _resolve_skill_snapshot_path(experiment: Mapping[str, Any], *, store_root: Path) -> Path | None:
    version_artifact_snapshot_path = _resolve_version_artifact_snapshot_path(
        experiment,
        store_root=store_root,
    )
    if version_artifact_snapshot_path is not None:
        return version_artifact_snapshot_path

    raw_snapshot_path = _first_present(
        experiment,
        "skill_snapshot",
        "skill_path",
        "absolute_skill_path",
    )
    snapshot_text = _clean_text(raw_snapshot_path)
    if snapshot_text:
        snapshot_path = Path(snapshot_text).expanduser()
        if not snapshot_path.is_absolute():
            snapshot_path = store_root / snapshot_path
        return snapshot_path

    iteration_path_text = _clean_text(experiment.get("iteration_path"))
    if not iteration_path_text:
        return None

    iteration_path = Path(iteration_path_text).expanduser()
    if not iteration_path.is_absolute():
        iteration_path = store_root / iteration_path
    default_name = "skill_before.md" if _clean_text(experiment.get("status")) == "baseline" else "skill_after.md"
    return iteration_path / default_name


def _index_variant_results(
    variant_payload: dict[str, Any],
) -> tuple[dict[Any, dict[str, Any]], dict[str, Any] | None, str | None]:
    raw_variant_results = variant_payload.get("variant_results")
    if raw_variant_results is None:
        return {}, None, None
    if not isinstance(raw_variant_results, list):
        raise TypeError("variant_results.json requires variant_results as a list")

    indexed: dict[Any, dict[str, Any]] = {}
    for item in raw_variant_results:
        if not isinstance(item, Mapping):
            continue
        experiment_id = item.get("experiment_id")
        version = _clean_text(item.get("version"))
        if experiment_id is not None:
            indexed[experiment_id] = dict(item)
        if version:
            indexed[version] = dict(item)
    selected_candidate_summary = variant_payload.get("selected_candidate_summary")
    source_results_ref = _clean_text(variant_payload.get("source_results_ref")) or None
    if isinstance(selected_candidate_summary, Mapping):
        return indexed, dict(selected_candidate_summary), source_results_ref
    return indexed, None, source_results_ref


def _build_result_store_records(
    *,
    source: dict[str, Any],
    store_root: Path,
    results_path: Path,
    results_payload: dict[str, Any],
    variant_results_path: Path | None,
    variant_results_by_key: dict[Any, dict[str, Any]],
    selected_candidate_summary: dict[str, Any] | None,
    variant_source_results_ref: str | None,
) -> list[dict[str, Any]]:
    experiments = results_payload.get("experiments")
    if not isinstance(experiments, list):
        raise TypeError("results.json requires experiments as a list")

    records: list[dict[str, Any]] = []
    visible_experiments = [
        experiment
        for experiment in experiments
        if isinstance(experiment, Mapping)
        and _clean_text(experiment.get("status")) in VISIBLE_EXPERIMENT_STATUSES
    ]

    skill_name = _clean_text(results_payload.get("skill_name"))
    def experiment_sort_key(item: Mapping[str, Any]) -> tuple[int, str]:
        raw_id = item.get("id")
        try:
            return (0, str(int(raw_id)))
        except (TypeError, ValueError):
            return (1, _clean_text(raw_id))

    for visible_index, experiment in enumerate(sorted(visible_experiments, key=experiment_sort_key)):
        experiment_id = experiment.get("id")
        status = _clean_text(experiment.get("status"))
        version_label = f"v{visible_index}"
        variant_result = variant_results_by_key.get(experiment_id) or variant_results_by_key.get(version_label)
        version_artifact = (
            _clone_json_value(experiment.get("version_artifact"))
            if isinstance(experiment.get("version_artifact"), Mapping)
            else None
        )
        version_id = (
            _clean_text(version_artifact.get("version_id"))
            if isinstance(version_artifact, Mapping)
            else ""
        ) or None
        parent_version_id = (
            _clean_text(version_artifact.get("parent_version_id"))
            if isinstance(version_artifact, Mapping)
            else ""
        ) or None

        skill_path = _resolve_skill_snapshot_path(experiment, store_root=store_root)
        if skill_path is None or not skill_path.is_file():
            continue

        skill_text = _read_text(skill_path)
        title_default = _clean_text(skill_name, default=skill_path.stem)
        relative_path = _relative_path(skill_path, store_root)
        skill_content = _build_skill_content_snapshot(
            skill_text,
            default_title=title_default,
            source_path=str(skill_path),
            relative_path=relative_path,
        )
        title = skill_content["title"]
        summary = skill_content["summary"]

        records.append(
            {
                "record_id": f"{source['source_id']}:{version_label}",
                "record_kind": "evaluated_skill_version",
                "source_id": source["source_id"],
                "source_kind": source["source_kind"],
                "skill_id": _clean_identifier(skill_name or title, default=_clean_identifier(title_default)),
                "version_label": version_label,
                "version_id": version_id,
                "parent_version_id": parent_version_id,
                "title": title,
                "summary": summary,
                "skill_path": str(skill_path),
                "relative_path": relative_path,
                "references_path": None,
                "skill_text": skill_text,
                "skill_content": skill_content,
                "content_hash": _sha256_text(skill_content["normalized_text"]),
                "version_artifact": version_artifact,
                "evaluation_context": {
                    "experiment_id": experiment_id,
                    "status": status,
                    "score": experiment.get("score"),
                    "max_score": experiment.get("max_score"),
                    "pass_rate": experiment.get("pass_rate"),
                    "weighted_score": experiment.get("weighted_score"),
                    "final_score": (
                        variant_result.get("final_score")
                        if isinstance(variant_result, Mapping)
                        else None
                    ),
                    "source_results_ref": (
                        variant_source_results_ref
                        or _clean_text(results_payload.get("source_results_ref"), default="results.json")
                    ),
                },
                "provenance": {
                    "analysis_goal": source.get("analysis_goal"),
                    "results_path": str(results_path),
                    "variant_results_ref": str(variant_results_path) if variant_results_path is not None else None,
                    "selected_candidate_summary": selected_candidate_summary,
                },
            }
        )

    return records


def _normalize_score_ratio(score: Any, max_score: Any) -> float | None:
    normalized_score = _coerce_numeric(score)
    normalized_max_score = _coerce_numeric(max_score)
    if (
        normalized_score is None
        or normalized_max_score is None
        or normalized_max_score <= 0
        or normalized_score < 0
    ):
        return None

    ratio = normalized_score / normalized_max_score
    if ratio < 0:
        return None
    if ratio > 1 and ratio <= 100:
        return ratio / 100
    if ratio > 1:
        return None
    return ratio


def _extract_record_metrics(record: Mapping[str, Any]) -> dict[str, Any]:
    evaluation_context = record.get("evaluation_context")
    if not isinstance(evaluation_context, Mapping):
        evaluation_context = {}

    final_score_pct = _normalize_percentage_metric(evaluation_context.get("final_score"))
    weighted_score_pct = _normalize_percentage_metric(evaluation_context.get("weighted_score"))
    pass_rate_pct = _normalize_percentage_metric(evaluation_context.get("pass_rate"))
    score_ratio_pct = _normalize_score_ratio(
        evaluation_context.get("score"),
        evaluation_context.get("max_score"),
    )
    rank_score_pct = next(
        (
            metric
            for metric in (
                final_score_pct,
                weighted_score_pct,
                pass_rate_pct,
                score_ratio_pct,
            )
            if metric is not None
        ),
        None,
    )

    return {
        "final_score_pct": final_score_pct,
        "weighted_score_pct": weighted_score_pct,
        "pass_rate_pct": pass_rate_pct,
        "score_ratio_pct": score_ratio_pct,
        "rank_score_pct": rank_score_pct,
        "has_evaluation_metrics": rank_score_pct is not None,
    }


def _record_matches_selected_candidate(record: Mapping[str, Any]) -> bool:
    provenance = record.get("provenance")
    if not isinstance(provenance, Mapping):
        return False

    selected_candidate_summary = provenance.get("selected_candidate_summary")
    if not isinstance(selected_candidate_summary, Mapping):
        return False

    evaluation_context = record.get("evaluation_context")
    if not isinstance(evaluation_context, Mapping):
        evaluation_context = {}

    summary_version = _clean_text(selected_candidate_summary.get("version"))
    summary_experiment_id = selected_candidate_summary.get("experiment_id")
    record_version = _clean_text(record.get("version_label"))
    record_experiment_id = evaluation_context.get("experiment_id")

    return bool(
        (summary_version and summary_version == record_version)
        or (
            summary_experiment_id is not None
            and record_experiment_id is not None
            and summary_experiment_id == record_experiment_id
        )
    )


def _build_selection_metadata(
    record: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    metrics = _extract_record_metrics(record)
    evaluation_context = record.get("evaluation_context")
    if not isinstance(evaluation_context, Mapping):
        evaluation_context = {}

    return {
        "metrics": metrics,
        "experiment_status": _clean_text(evaluation_context.get("status")),
        "is_selected_candidate": _record_matches_selected_candidate(record),
        "dedupe_strategy": config["dedupe_strategy"],
    }


def _selection_sort_key(item: Mapping[str, Any], *, config: Mapping[str, Any]) -> tuple[Any, ...]:
    record = item["record"]
    selection_metadata = item["selection_metadata"]
    metrics = selection_metadata["metrics"]

    return (
        0
        if config["prefer_selected_candidate"] and selection_metadata["is_selected_candidate"]
        else 1,
        -(metrics["rank_score_pct"] if metrics["rank_score_pct"] is not None else -1.0),
        -(metrics["final_score_pct"] if metrics["final_score_pct"] is not None else -1.0),
        -(metrics["weighted_score_pct"] if metrics["weighted_score_pct"] is not None else -1.0),
        -(metrics["pass_rate_pct"] if metrics["pass_rate_pct"] is not None else -1.0),
        -(metrics["score_ratio_pct"] if metrics["score_ratio_pct"] is not None else -1.0),
        0 if _clean_text(record.get("record_kind")) == "evaluated_skill_version" else 1,
        0 if _clean_text(record.get("source_kind")) == "evaluation_result_store" else 1,
        _clean_text(record.get("title")).lower(),
        _clean_text(record.get("record_id")),
    )


def _selection_dedupe_key(record: Mapping[str, Any], *, config: Mapping[str, Any]) -> str | None:
    dedupe_strategy = config["dedupe_strategy"]
    if dedupe_strategy == "none":
        return None

    if dedupe_strategy == "content_hash":
        return _clean_text(record.get("content_hash")) or _clean_text(record.get("record_id"))

    skill_id = _clean_text(record.get("skill_id"))
    if skill_id:
        return skill_id
    return _clean_text(record.get("content_hash")) or _clean_text(record.get("record_id"))


def _build_selection_rejection(
    record: Mapping[str, Any],
    *,
    reason: str,
    detail: str,
    selection_metadata: Mapping[str, Any],
    dedupe_key: str | None = None,
) -> dict[str, Any]:
    return {
        "record_id": _clean_text(record.get("record_id")),
        "record_kind": _clean_text(record.get("record_kind")),
        "source_id": _clean_text(record.get("source_id")),
        "reason": reason,
        "detail": detail,
        "dedupe_key": dedupe_key,
        "metrics": dict(selection_metadata["metrics"]),
    }


def _build_selected_exemplar_payload(
    selected_records: list[Mapping[str, Any]],
    *,
    selected_at: str,
    selected_record_ids: list[str],
) -> dict[str, Any]:
    exemplars: list[dict[str, Any]] = []
    selected_candidate_record_id: str | None = None

    for record in selected_records:
        selection_metadata = record.get("selection_metadata")
        if not isinstance(selection_metadata, Mapping):
            selection_metadata = {}

        metrics = selection_metadata.get("metrics")
        if not isinstance(metrics, Mapping):
            metrics = _extract_record_metrics(record)

        evaluation_context = record.get("evaluation_context")
        if not isinstance(evaluation_context, Mapping):
            evaluation_context = {}

        selection = {
            "selection_rank": selection_metadata.get("selection_rank"),
            "is_selected_candidate": bool(selection_metadata.get("is_selected_candidate")),
            "dedupe_strategy": _clean_text(selection_metadata.get("dedupe_strategy")) or None,
            "dedupe_key": _clean_text(selection_metadata.get("dedupe_key")) or None,
        }
        if selection["is_selected_candidate"] and selected_candidate_record_id is None:
            selected_candidate_record_id = _clean_text(record.get("record_id")) or None

        exemplars.append(
            {
                "record_id": _clean_text(record.get("record_id")),
                "record_kind": _clean_text(record.get("record_kind")),
                "skill_id": _clean_text(record.get("skill_id")),
                "version_label": _clean_text(record.get("version_label")) or None,
                "title": _clean_text(record.get("title")),
                "summary": _clean_text(record.get("summary")),
                "selection": selection,
                "skill_content": _clone_json_value(record.get("skill_content") or {}),
                "provenance": {
                    "source_id": _clean_text(record.get("source_id")),
                    "source_kind": _clean_text(record.get("source_kind")),
                    "skill_path": _clean_text(record.get("skill_path")) or None,
                    "relative_path": _clean_text(record.get("relative_path")) or None,
                    "references_path": _clean_text(record.get("references_path")) or None,
                    "content_hash": _clean_text(record.get("content_hash")) or None,
                    **(
                        _clone_json_value(record.get("provenance"))
                        if isinstance(record.get("provenance"), Mapping)
                        else {}
                    ),
                },
                "performance": {
                    "has_evaluation_metrics": bool(metrics.get("has_evaluation_metrics")),
                    "experiment_id": evaluation_context.get("experiment_id"),
                    "experiment_status": _clean_text(evaluation_context.get("status")) or None,
                    "score": evaluation_context.get("score"),
                    "max_score": evaluation_context.get("max_score"),
                    "pass_rate": evaluation_context.get("pass_rate"),
                    "weighted_score": evaluation_context.get("weighted_score"),
                    "final_score": evaluation_context.get("final_score"),
                    "source_results_ref": _clean_text(evaluation_context.get("source_results_ref")) or None,
                    "metrics": _clone_json_value(metrics),
                },
            }
        )

    return {
        "schema_version": EXEMPLAR_PAYLOAD_SCHEMA_VERSION,
        "payload_type": CANONICAL_EXEMPLAR_PAYLOAD_TYPE,
        "selected_at": selected_at,
        "selected_record_ids": list(selected_record_ids),
        "selected_candidate_record_id": selected_candidate_record_id,
        "exemplar_count": len(exemplars),
        "exemplars": exemplars,
    }


def _version_label_sort_key(version_label: str | None, *, experiment_id: Any) -> tuple[int, int, str]:
    normalized_label = _clean_text(version_label)
    if normalized_label.startswith("v") and normalized_label[1:].isdigit():
        return (0, int(normalized_label[1:]), normalized_label)
    raw_experiment_id = _clean_text(experiment_id)
    if raw_experiment_id.isdigit():
        return (1, int(raw_experiment_id), raw_experiment_id)
    return (2, 0, normalized_label or raw_experiment_id)


def build_skill_version_snapshot_bundle(
    records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a replayable version-snapshot bundle from evaluated skill records."""

    if not isinstance(records, (list, tuple)):
        raise TypeError("records must be a list or tuple")

    emitted_at = _now_utc_timestamp() if generated_at is None else _clean_text(generated_at)
    if generated_at is not None and not emitted_at:
        raise ValueError("generated_at must be an ISO timestamp when provided")

    grouped_records: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, Mapping):
            raise TypeError(f"records[{index}] must be a mapping")
        if _clean_text(raw_record.get("record_kind")) != "evaluated_skill_version":
            continue

        source_id = _clean_text(raw_record.get("source_id"))
        skill_id = _clean_text(raw_record.get("skill_id"))
        if not source_id or not skill_id:
            continue
        grouped_records.setdefault((source_id, skill_id), []).append(dict(raw_record))

    version_snapshots: list[dict[str, Any]] = []
    skill_lineages: list[dict[str, Any]] = []

    for (source_id, skill_id), lineage_records in sorted(grouped_records.items()):
        ordered_records = sorted(
            lineage_records,
            key=lambda record: _version_label_sort_key(
                _clean_text(record.get("version_label")) or None,
                experiment_id=(
                    (record.get("evaluation_context") or {}).get("experiment_id")
                    if isinstance(record.get("evaluation_context"), Mapping)
                    else None
                ),
            ),
        )
        previous_snapshot: dict[str, Any] | None = None
        lineage_snapshot_ids: list[str] = []
        lineage_version_labels: list[str] = []

        for record in ordered_records:
            evaluation_context = (
                record.get("evaluation_context")
                if isinstance(record.get("evaluation_context"), Mapping)
                else {}
            )
            provenance = (
                record.get("provenance")
                if isinstance(record.get("provenance"), Mapping)
                else {}
            )
            version_label = _clean_text(record.get("version_label")) or None
            version_id = _clean_text(record.get("version_id")) or None
            parent_version_id = _clean_text(record.get("parent_version_id")) or None
            snapshot_id = version_id or f"{_clean_text(record.get('record_id'))}@{version_label or 'snapshot'}"
            snapshot = {
                "snapshot_id": snapshot_id,
                "record_id": _clean_text(record.get("record_id")),
                "record_kind": _clean_text(record.get("record_kind")),
                "source_id": source_id,
                "source_kind": _clean_text(record.get("source_kind")),
                "skill_id": skill_id,
                "version_label": version_label,
                "version_id": version_id,
                "parent_snapshot_id": (
                    parent_version_id
                    or (
                        _clean_text(previous_snapshot.get("snapshot_id"))
                        if previous_snapshot is not None
                        else None
                    )
                ),
                "parent_record_id": (
                    _clean_text(previous_snapshot.get("record_id"))
                    if previous_snapshot is not None
                    else None
                ),
                "parent_version_label": (
                    _clean_text(previous_snapshot.get("version_label"))
                    if previous_snapshot is not None
                    else None
                ),
                "title": _clean_text(record.get("title")),
                "summary": _clean_text(record.get("summary")),
                "skill_path": _clean_text(record.get("skill_path")) or None,
                "relative_path": _clean_text(record.get("relative_path")) or None,
                "content_hash": _clean_text(record.get("content_hash")) or None,
                "skill_content": _clone_json_value(record.get("skill_content") or {}),
                "evaluation_context": _clone_json_value(evaluation_context),
                "metrics": _extract_record_metrics(record),
                "version_provenance": {
                    "results_path": _clean_text(provenance.get("results_path")) or None,
                    "variant_results_ref": _clean_text(provenance.get("variant_results_ref")) or None,
                    "version_artifact": (
                        _clone_json_value(record.get("version_artifact"))
                        if isinstance(record.get("version_artifact"), Mapping)
                        else None
                    ),
                    "selected_candidate_summary": (
                        _clone_json_value(provenance.get("selected_candidate_summary"))
                        if isinstance(provenance.get("selected_candidate_summary"), Mapping)
                        else None
                    ),
                },
            }
            version_snapshots.append(snapshot)
            lineage_snapshot_ids.append(snapshot_id)
            if version_label:
                lineage_version_labels.append(version_label)
            previous_snapshot = snapshot

        if lineage_snapshot_ids:
            skill_lineages.append(
                {
                    "source_id": source_id,
                    "skill_id": skill_id,
                    "snapshot_ids": lineage_snapshot_ids,
                    "version_labels": lineage_version_labels,
                    "latest_snapshot_id": lineage_snapshot_ids[-1],
                }
            )

    return {
        "schema_version": SKILL_VERSION_SNAPSHOT_SCHEMA_VERSION,
        "bundle_type": CANONICAL_VERSION_SNAPSHOT_BUNDLE_TYPE,
        "generated_at": emitted_at,
        "snapshot_count": len(version_snapshots),
        "version_snapshots": version_snapshots,
        "snapshot_index": {
            snapshot["snapshot_id"]: index
            for index, snapshot in enumerate(version_snapshots)
            if _clean_text(snapshot.get("snapshot_id"))
        },
        "record_id_index": {
            snapshot["record_id"]: snapshot["snapshot_id"]
            for snapshot in version_snapshots
            if _clean_text(snapshot.get("record_id")) and _clean_text(snapshot.get("snapshot_id"))
        },
        "skill_lineages": skill_lineages,
    }


def select_exemplar_skill_records(
    records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    exemplar_selection: Mapping[str, Any] | None = None,
    *,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Filter, rank, and deduplicate candidate skill records into exemplar selections."""

    if not isinstance(records, (list, tuple)):
        raise TypeError("records must be a list or tuple")

    config = resolve_exemplar_selection_config(exemplar_selection, state=state)
    selected_at = _now_utc_timestamp()
    eligible_items: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    threshold_fields = (
        ("minimum_final_score", "final_score_pct"),
        ("minimum_weighted_score", "weighted_score_pct"),
        ("minimum_pass_rate", "pass_rate_pct"),
        ("minimum_score_ratio", "score_ratio_pct"),
    )

    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, Mapping):
            raise TypeError(f"records[{index}] must be a mapping")

        record = dict(raw_record)
        record_kind = _clean_text(record.get("record_kind"))
        selection_metadata = _build_selection_metadata(record, config=config)

        if record_kind not in config["enabled_record_kinds"]:
            rejected_records.append(
                _build_selection_rejection(
                    record,
                    reason="record_kind_disabled",
                    detail=f"record kind {record_kind or '<missing>'} is not enabled by config",
                    selection_metadata=selection_metadata,
                )
            )
            continue

        if record_kind == "evaluated_skill_version":
            experiment_status = selection_metadata["experiment_status"]
            if experiment_status not in config["allowed_experiment_statuses"]:
                rejected_records.append(
                    _build_selection_rejection(
                        record,
                        reason="experiment_status_filtered",
                        detail=(
                            f"experiment status {experiment_status or '<missing>'} is not allowed by config"
                        ),
                        selection_metadata=selection_metadata,
                    )
                )
                continue

        metrics = selection_metadata["metrics"]
        if config["require_evaluation_metrics"] and not metrics["has_evaluation_metrics"]:
            rejected_records.append(
                _build_selection_rejection(
                    record,
                    reason="missing_evaluation_metrics",
                    detail="selection requires recorded evaluation metrics for this record",
                    selection_metadata=selection_metadata,
                )
            )
            continue

        threshold_rejection: dict[str, Any] | None = None
        for threshold_field, metric_field in threshold_fields:
            threshold_value = config[threshold_field]
            if threshold_value is None:
                continue

            metric_value = metrics[metric_field]
            if metric_value is None:
                threshold_rejection = _build_selection_rejection(
                    record,
                    reason="missing_metric_for_threshold",
                    detail=f"{metric_field} is required when {threshold_field} is configured",
                    selection_metadata=selection_metadata,
                )
                break
            if metric_value < threshold_value:
                threshold_rejection = _build_selection_rejection(
                    record,
                    reason="below_threshold",
                    detail=(
                        f"{metric_field}={metric_value:.3f} is below configured {threshold_field}="
                        f"{threshold_value:.3f}"
                    ),
                    selection_metadata=selection_metadata,
                )
                break

        if threshold_rejection is not None:
            rejected_records.append(threshold_rejection)
            continue

        eligible_items.append(
            {
                "record": record,
                "selection_metadata": selection_metadata,
            }
        )

    sorted_eligible_items = sorted(
        eligible_items,
        key=lambda item: _selection_sort_key(item, config=config),
    )

    selected_records: list[dict[str, Any]] = []
    selected_record_ids: list[str] = []
    seen_dedupe_keys: dict[str, str] = {}
    for item in sorted_eligible_items:
        record = item["record"]
        selection_metadata = item["selection_metadata"]
        dedupe_key = _selection_dedupe_key(record, config=config)
        if dedupe_key is not None and dedupe_key in seen_dedupe_keys:
            rejected_records.append(
                _build_selection_rejection(
                    record,
                    reason="duplicate_record",
                    detail=f"dedupe key already selected by {seen_dedupe_keys[dedupe_key]}",
                    selection_metadata=selection_metadata,
                    dedupe_key=dedupe_key,
                )
            )
            continue

        if len(selected_records) >= config["max_selected_records"]:
            rejected_records.append(
                _build_selection_rejection(
                    record,
                    reason="selection_limit_reached",
                    detail=(
                        f"max_selected_records={config['max_selected_records']} already satisfied by higher-ranked candidates"
                    ),
                    selection_metadata=selection_metadata,
                    dedupe_key=dedupe_key,
                )
            )
            continue

        record_id = _clean_text(record.get("record_id"))
        if dedupe_key is not None:
            seen_dedupe_keys[dedupe_key] = record_id

        annotated_record = dict(record)
        annotated_record["selection_metadata"] = {
            **selection_metadata,
            "selection_rank": len(selected_records) + 1,
            "dedupe_key": dedupe_key,
        }
        selected_records.append(annotated_record)
        selected_record_ids.append(record_id)

    return {
        "schema_version": EXEMPLAR_SELECTION_SCHEMA_VERSION,
        "selection_type": CANONICAL_SELECTION_TYPE,
        "selected_at": selected_at,
        "config": config,
        "candidate_count": len(records),
        "eligible_count": len(eligible_items),
        "selected_count": len(selected_records),
        "selected_record_ids": selected_record_ids,
        "selected_records": selected_records,
        "exemplar_payload": _build_selected_exemplar_payload(
            selected_records,
            selected_at=selected_at,
            selected_record_ids=selected_record_ids,
        ),
        "rejected_records": rejected_records,
    }


def _load_result_store_source(source: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    location = Path(source["location"])
    summary = dict(source)
    if not location.exists():
        summary.update({"load_status": "missing", "record_count": 0})
        return summary, []

    try:
        store_root, results_path, variant_results_path = _resolve_result_store_paths(location)
    except ValueError as exc:
        summary.update({"load_status": "parse_failed", "record_count": 0, "error": str(exc)})
        return summary, []

    if not results_path.is_file():
        summary.update({"load_status": "missing", "record_count": 0})
        return summary, []

    try:
        results_payload = _read_json(results_path)
        variant_results_by_key: dict[Any, dict[str, Any]] = {}
        selected_candidate_summary: dict[str, Any] | None = None
        variant_source_results_ref: str | None = None
        resolved_variant_results_path: Path | None = None
        if variant_results_path.is_file():
            variant_payload = _read_json(variant_results_path)
            (
                variant_results_by_key,
                selected_candidate_summary,
                variant_source_results_ref,
            ) = _index_variant_results(variant_payload)
            resolved_variant_results_path = variant_results_path

        records = _build_result_store_records(
            source=source,
            store_root=store_root,
            results_path=results_path,
            results_payload=results_payload,
            variant_results_path=resolved_variant_results_path,
            variant_results_by_key=variant_results_by_key,
            selected_candidate_summary=selected_candidate_summary,
            variant_source_results_ref=variant_source_results_ref,
        )
    except (OSError, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        summary.update(
            {
                "load_status": "parse_failed",
                "record_count": 0,
                "error": str(exc),
            }
        )
        return summary, []

    summary.update(
        {
            "load_status": "loaded" if records else "empty",
            "record_count": len(records),
            "results_path": str(results_path),
            "variant_results_path": str(variant_results_path) if variant_results_path.is_file() else None,
        }
    )
    return summary, records


def load_candidate_skill_records(
    exemplar_sources: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
    *,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load candidate skill records from normalized exemplar sources."""

    resolved_sources = resolve_exemplar_source_configs(exemplar_sources, state=state)
    loaded_at = _now_utc_timestamp()
    bundle = {
        "schema_version": EXEMPLAR_SOURCE_BUNDLE_SCHEMA_VERSION,
        "bundle_type": CANONICAL_BUNDLE_TYPE,
        "loaded_at": loaded_at,
        "source_count": len(resolved_sources),
        "record_count": 0,
        "sources": [],
        "records": [],
    }

    for source in resolved_sources:
        if source["source_kind"] == "repository":
            source_summary, records = _load_repository_source(source)
        elif source["source_kind"] == "evaluation_result_store":
            source_summary, records = _load_result_store_source(source)
        else:
            raise ExemplarSourceValidationError(
                [f"unsupported exemplar source kind {source['source_kind']!r}"]
            )

        bundle["sources"].append(source_summary)
        bundle["records"].extend(records)

    bundle["record_count"] = len(bundle["records"])
    bundle["version_snapshot_bundle"] = build_skill_version_snapshot_bundle(bundle["records"])
    bundle["selection"] = select_exemplar_skill_records(bundle["records"], state=state)
    return bundle


def load_candidate_skill_records_from_state(
    *,
    state: Mapping[str, Any],
    exemplar_sources: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
) -> dict[str, Any]:
    """Load candidate skill records using the state-backed exemplar source config."""

    return load_candidate_skill_records(exemplar_sources, state=state)


def load_skill_version_snapshot_bundle(
    exemplar_sources: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
    *,
    state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load the canonical version-snapshot bundle for evaluated skill variants."""

    candidate_bundle = load_candidate_skill_records(exemplar_sources, state=state)
    snapshot_bundle = candidate_bundle.get("version_snapshot_bundle")
    if isinstance(snapshot_bundle, Mapping):
        return _clone_json_value(snapshot_bundle)
    return build_skill_version_snapshot_bundle(candidate_bundle.get("records", []))
