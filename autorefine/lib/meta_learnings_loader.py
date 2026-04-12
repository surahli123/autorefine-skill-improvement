from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

if __package__:
    from .target_skill_scoring_context import build_target_skill_scoring_context
else:
    _CURRENT_DIR = Path(__file__).resolve().parent
    if str(_CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(_CURRENT_DIR))
    from target_skill_scoring_context import build_target_skill_scoring_context


META_LEARNINGS_BUNDLE_SCHEMA_VERSION = 1
CANONICAL_ENTRY_TYPE = "meta_learning_rule"
CANONICAL_BUNDLE_TYPE = "parsed_meta_learnings"
CANONICAL_LOAD_STATUSES = ("loaded", "missing", "parse_failed", "empty")
CANONICAL_STATUS_VALUES = ("candidate", "active", "superseded", "rejected")
CANONICAL_CONFIDENCE_VALUES = ("high", "medium", "low")
CANONICAL_PRECEDENCE_VALUES = ("high", "medium", "low")
CANONICAL_REVIEW_STATUS_VALUES = ("pending", "approved", "superseded")
CANONICAL_SOURCE_KIND_VALUES = (
    "prior_campaign",
    "reference_skill",
    "meta_learning",
    "best_practice",
)
DEFAULT_META_LEARNINGS_FILENAME = "meta-learnings.md"
REQUIRED_TOP_LEVEL_SECTIONS = (
    "# AutoRefine Meta-Learnings",
    "## Curation Rules",
    "## Entry Template",
)
REQUIRED_APPLICABILITY_FIELDS = (
    "skill_patterns",
    "agent_targets",
    "scenario_targets",
    "scope_type",
    "scope_ref",
    "when_to_apply",
    "do_not_apply_when",
)
REQUIRED_SUPPORTING_EVIDENCE_FIELDS = (
    "case_id",
    "source_kind",
    "source_ref",
    "evidence_locator",
    "excerpt_or_metric",
    "why_it_supports",
)
ENTRY_ID_PATTERN = re.compile(r"^ML-\d{4}-\d{2}-\d{2}-\d{3}$")
ENTRY_HEADING_PATTERN = re.compile(r"^###\s+(.+?)\s*\|\s*(.+?)\s*$")
_PRECEDENCE_RANK = {
    "high": 0,
    "medium": 1,
    "low": 2,
}
_SEARCH_NORMALIZATION_PATTERN = re.compile(r"[^a-z0-9]+")


class MetaLearningsValidationError(ValueError):
    """Validation failure for curated meta-learnings markdown."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _clean_text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _strip_wrapping_delimiters(value: str) -> str:
    cleaned = value.strip()
    while len(cleaned) >= 2:
        if cleaned[0] == cleaned[-1] and cleaned[0] in {"`", '"', "'"}:
            cleaned = cleaned[1:-1].strip()
            continue
        break
    return cleaned


def _parse_inline_value(raw_value: str) -> Any:
    cleaned = raw_value.strip()
    if not cleaned:
        return ""

    if cleaned.startswith("[") and cleaned.endswith("]"):
        inner = cleaned[1:-1].strip()
        if not inner:
            return []
        return [
            _strip_wrapping_delimiters(part)
            for part in inner.split(",")
            if _strip_wrapping_delimiters(part)
        ]

    return _strip_wrapping_delimiters(cleaned)


def _split_key_value(line: str) -> tuple[str, str]:
    if ":" not in line:
        raise ValueError(f"expected '<key>: <value>' line, received {line!r}")
    key, raw_value = line.split(":", 1)
    return (_clean_text(key), raw_value)


def _now_utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_iso_timestamp(value: Any, *, field_name: str) -> str:
    normalized = _clean_text(value)
    if not normalized:
        raise ValueError(f"{field_name} requires a non-empty ISO timestamp")

    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} requires a valid ISO timestamp") from exc

    return normalized


def _normalize_string_list(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    normalized_items: list[str] = []
    for index, item in enumerate(value):
        normalized_item = _clean_text(item)
        if not normalized_item:
            raise ValueError(f"{field_name}[{index}] must be non-empty")
        normalized_items.append(normalized_item)

    return normalized_items


def _normalize_optional_string_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return _normalize_string_list(list(value), field_name=field_name)

    normalized = _clean_text(value)
    if not normalized:
        return []
    return [normalized]


def _normalize_enum(value: Any, *, field_name: str, allowed_values: tuple[str, ...]) -> str:
    normalized = _clean_text(value)
    if normalized not in allowed_values:
        raise ValueError(
            f"{field_name} must be one of {allowed_values}; received {value!r}"
        )
    return normalized


def _normalize_non_empty_text(value: Any, *, field_name: str) -> str:
    normalized = _clean_text(value)
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _normalize_search_text(value: Any) -> str:
    normalized = _clean_text(value).lower()
    if not normalized:
        return ""
    return " ".join(_SEARCH_NORMALIZATION_PATTERN.sub(" ", normalized).split())


def _stable_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _normalize_skill_metadata(raw_metadata: Any) -> dict[str, Any]:
    if raw_metadata is None:
        return {}

    if isinstance(raw_metadata, str):
        normalized_text = _clean_text(raw_metadata)
        return {"summary": normalized_text} if normalized_text else {}

    if not isinstance(raw_metadata, Mapping):
        raise TypeError("target_context.skill_metadata must be a mapping when provided")

    normalized_metadata: dict[str, Any] = {}

    skill_id = _clean_text(_first_present(raw_metadata, "skill_id", "id"))
    if skill_id:
        normalized_metadata["skill_id"] = skill_id

    title = _clean_text(
        _first_present(raw_metadata, "title", "label", "skill_name", "name")
    )
    if title:
        normalized_metadata["title"] = title

    summary = _clean_text(
        _first_present(raw_metadata, "summary", "description", "objective")
    )
    if summary:
        normalized_metadata["summary"] = summary

    relative_path = _clean_text(_first_present(raw_metadata, "relative_path", "path"))
    if relative_path:
        normalized_metadata["relative_path"] = relative_path

    absolute_path = _clean_text(_first_present(raw_metadata, "absolute_path"))
    if absolute_path:
        normalized_metadata["absolute_path"] = absolute_path

    tags = _normalize_optional_string_list(raw_metadata.get("tags"), field_name="target_context.skill_metadata.tags")
    if tags:
        normalized_metadata["tags"] = tags

    return normalized_metadata


def _extract_target_skill_metadata(target_context: Mapping[str, Any]) -> dict[str, Any]:
    explicit_metadata = _first_present(
        target_context,
        "skill_metadata",
        "selected_skill",
        "fixture_skill",
    )
    if explicit_metadata is not None:
        return _normalize_skill_metadata(explicit_metadata)

    inferred_metadata = {
        "skill_id": _first_present(target_context, "skill_id"),
        "skill_name": _first_present(target_context, "skill_name", "title", "label"),
        "summary": _first_present(target_context, "summary", "description"),
        "relative_path": _first_present(target_context, "relative_path", "skill_path"),
        "absolute_path": _first_present(target_context, "absolute_path"),
        "tags": target_context.get("tags"),
    }
    return _normalize_skill_metadata(inferred_metadata)


def _build_skill_metadata_search_text(skill_metadata: Mapping[str, Any] | None) -> str:
    if not isinstance(skill_metadata, Mapping):
        return ""

    text_fragments: list[str] = []
    for field_name in ("skill_id", "title", "summary", "relative_path", "absolute_path"):
        normalized = _clean_text(skill_metadata.get(field_name))
        if normalized:
            text_fragments.append(normalized)

    tags = skill_metadata.get("tags")
    if isinstance(tags, list):
        text_fragments.extend(_clean_text(tag) for tag in tags if _clean_text(tag))

    return _normalize_search_text(" ".join(text_fragments))


def _matches_keyword_filters(
    keywords: list[str],
    *,
    searchable_text: str,
) -> bool:
    if not keywords:
        return True
    if not searchable_text:
        return False

    normalized_keywords = [
        normalized_keyword
        for normalized_keyword in (_normalize_search_text(keyword) for keyword in keywords)
        if normalized_keyword
    ]
    if not normalized_keywords:
        return True

    return any(keyword in searchable_text for keyword in normalized_keywords)


def _normalize_target_context(target_context: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(target_context, Mapping):
        raise TypeError("target_context must be a mapping")

    required_fields = (
        "skill_pattern",
        "agent_target",
        "scenario_target",
        "scope_type",
        "scope_ref",
    )

    normalized_context: dict[str, Any] = {}
    for field_name in required_fields:
        normalized_context[field_name] = _normalize_non_empty_text(
            target_context.get(field_name),
            field_name=f"target_context.{field_name}",
        )

    skill_metadata = _extract_target_skill_metadata(target_context)
    if skill_metadata:
        normalized_context["skill_metadata"] = skill_metadata

    campaign_objective = _clean_text(
        _first_present(target_context, "campaign_objective", "objective", "analysis_goal")
    )
    if campaign_objective:
        normalized_context["campaign_objective"] = campaign_objective

    optional_text_fields = {
        "selected_eval_strategy_id": _first_present(
            target_context,
            "selected_eval_strategy_id",
            "eval_strategy_id",
            "strategy_id",
        ),
        "analysis_goal": _first_present(target_context, "analysis_goal"),
        "target_section": _first_present(
            target_context,
            "target_section",
            "section_focus",
            "section",
            "target_location",
        ),
        "target_domain": _first_present(
            target_context,
            "target_domain",
            "domain",
            "domain_context",
        ),
    }
    for field_name, raw_value in optional_text_fields.items():
        normalized_value = _clean_text(raw_value)
        if normalized_value:
            normalized_context[field_name] = normalized_value

    optional_list_fields = {
        "goals": target_context.get("goals"),
        "failure_focus": target_context.get("failure_focus"),
        "structure_signals": _first_present(
            target_context,
            "structure_signals",
            "structure_tags",
            "workflow_signals",
        ),
        "domain_tags": _first_present(target_context, "domain_tags", "tags"),
    }
    for field_name, raw_value in optional_list_fields.items():
        normalized_values = _normalize_optional_string_list(
            raw_value,
            field_name=f"target_context.{field_name}",
        )
        if normalized_values:
            normalized_context[field_name] = normalized_values

    scoring_context = build_target_skill_scoring_context(
        {
            **dict(target_context),
            "skill_metadata": skill_metadata,
            "campaign_objective": campaign_objective or target_context.get("campaign_objective"),
        }
    )
    if scoring_context:
        normalized_context["scoring_context"] = scoring_context

    return normalized_context


def _default_meta_learnings_directory() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_meta_learnings_path(
    meta_learnings_path: str | Path | None = None,
    *,
    state: Mapping[str, Any] | None = None,
    default_skill_directory: str | Path | None = None,
) -> Path:
    """Resolve the campaign-setup meta-learnings source path.

    Precedence:
    1. Explicit function argument.
    2. `state["meta_learnings_path"]` when present and non-empty.
    3. `<default_skill_directory>/meta-learnings.md`.
    4. The repository's bundled `autorefine/meta-learnings.md`.
    """

    if meta_learnings_path is not None:
        return Path(meta_learnings_path).expanduser()

    configured_state_path = None
    if state is not None:
        if not isinstance(state, Mapping):
            raise TypeError("state must be a mapping when provided")
        configured_state_path = _clean_text(state.get("meta_learnings_path"))

    if configured_state_path:
        return Path(configured_state_path).expanduser()

    if default_skill_directory is not None:
        default_directory = Path(default_skill_directory).expanduser()
    else:
        default_directory = _default_meta_learnings_directory()

    return default_directory / DEFAULT_META_LEARNINGS_FILENAME


def _build_base_bundle(
    meta_learnings_path: Path,
    *,
    target_context: dict[str, Any],
    loaded_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": META_LEARNINGS_BUNDLE_SCHEMA_VERSION,
        "bundle_type": CANONICAL_BUNDLE_TYPE,
        "meta_learnings_path": str(meta_learnings_path.resolve()),
        "loaded_at": loaded_at,
        "load_status": "empty",
        "target_context": dict(target_context),
        "entries": [],
        "actionable_entry_ids": [],
        "historical_entry_ids": [],
        "blocked_entry_ids": [],
    }


def _build_transfer_traceability(
    *,
    meta_learnings_path: Path,
    curator_version: str | None,
    transfer_parameters: Mapping[str, Any],
    actionable_entry_ids: list[str],
    historical_entry_ids: list[str],
    blocked_entry_ids: list[str],
) -> dict[str, Any]:
    resolved_path = str(meta_learnings_path.resolve())
    normalized_transfer_parameters = deepcopy(dict(transfer_parameters))
    transfer_signature = _stable_sha256(_stable_json_dumps(normalized_transfer_parameters))
    trace_material = {
        "curator_source": resolved_path,
        "curator_version": curator_version,
        "transfer_parameters": normalized_transfer_parameters,
        "actionable_entry_ids": actionable_entry_ids,
        "historical_entry_ids": historical_entry_ids,
        "blocked_entry_ids": blocked_entry_ids,
    }
    trace_digest = hashlib.sha256(_stable_json_dumps(trace_material).encode("utf-8")).hexdigest()

    filter_refs = [
        f"curator_source:{resolved_path}",
        f"transfer_signature:{transfer_signature}",
        f"skill_pattern:{normalized_transfer_parameters.get('skill_pattern')}",
        f"agent_target:{normalized_transfer_parameters.get('agent_target')}",
        f"scenario_target:{normalized_transfer_parameters.get('scenario_target')}",
        f"scope_type:{normalized_transfer_parameters.get('scope_type')}",
        f"scope_ref:{normalized_transfer_parameters.get('scope_ref')}",
    ]
    if curator_version:
        filter_refs.insert(1, f"curator_version:{curator_version}")

    return {
        "trace_id": f"ml-transfer-{trace_digest[:12]}",
        "transfer_signature": transfer_signature,
        "actionable_entry_refs": [f"{resolved_path}#{entry_id}" for entry_id in actionable_entry_ids],
        "historical_entry_refs": [f"{resolved_path}#{entry_id}" for entry_id in historical_entry_ids],
        "blocked_entry_refs": [f"{resolved_path}#{entry_id}" for entry_id in blocked_entry_ids],
        "filter_refs": filter_refs,
    }


def _attach_reporting_metadata(
    bundle: dict[str, Any],
    *,
    meta_learnings_path: Path,
    target_context: Mapping[str, Any],
    curator_version: str | None,
) -> dict[str, Any]:
    normalized_transfer_parameters = deepcopy(dict(target_context))
    bundle["curator_source"] = str(meta_learnings_path.resolve())
    bundle["curator_version"] = curator_version
    bundle["transfer_parameters"] = normalized_transfer_parameters
    bundle["transfer_traceability"] = _build_transfer_traceability(
        meta_learnings_path=meta_learnings_path,
        curator_version=curator_version,
        transfer_parameters=normalized_transfer_parameters,
        actionable_entry_ids=list(bundle.get("actionable_entry_ids", [])),
        historical_entry_ids=list(bundle.get("historical_entry_ids", [])),
        blocked_entry_ids=list(bundle.get("blocked_entry_ids", [])),
    )
    return bundle


def _validate_required_sections(markdown_text: str) -> list[str]:
    errors: list[str] = []
    for section_heading in REQUIRED_TOP_LEVEL_SECTIONS:
        if section_heading not in markdown_text:
            errors.append(f"missing required section: {section_heading}")
    return errors


def _extract_entry_blocks(markdown_text: str) -> list[tuple[str, str, list[str]]]:
    lines = markdown_text.splitlines()
    blocks: list[tuple[str, str, list[str]]] = []
    current_entry_id: str | None = None
    current_title: str | None = None
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_entry_id, current_title, current_lines
        if current_entry_id is not None and current_title is not None:
            blocks.append((current_entry_id, current_title, current_lines))
        current_entry_id = None
        current_title = None
        current_lines = []

    for raw_line in lines:
        heading_match = ENTRY_HEADING_PATTERN.match(raw_line.strip())
        if heading_match:
            flush_current()
            entry_id = _clean_text(heading_match.group(1))
            title = _clean_text(heading_match.group(2))

            # Template placeholders stay in the document for weak-agent readability,
            # but the runtime bundle only consumes curated entries with canonical ids.
            if ENTRY_ID_PATTERN.match(entry_id):
                current_entry_id = entry_id
                current_title = title
            continue

        if current_entry_id is not None:
            current_lines.append(raw_line.rstrip("\n"))

    flush_current()
    return blocks


def _parse_applicability_conditions(
    body_lines: list[str],
    start_index: int,
    *,
    entry_id: str,
) -> tuple[dict[str, Any], int]:
    parsed_mapping: dict[str, Any] = {}
    index = start_index

    while index < len(body_lines):
        line = body_lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if not line.startswith("  - "):
            break

        key, raw_value = _split_key_value(line[4:].strip())
        parsed_mapping[key] = _parse_inline_value(raw_value)
        index += 1

    if not parsed_mapping:
        raise MetaLearningsValidationError(
            [f"{entry_id}: applicability_conditions must contain nested bullet fields"]
        )

    return (parsed_mapping, index)


def _parse_supporting_evidence(
    body_lines: list[str],
    start_index: int,
    *,
    entry_id: str,
) -> tuple[list[dict[str, Any]], int]:
    evidence_rows: list[dict[str, Any]] = []
    index = start_index
    current_row: dict[str, Any] | None = None

    while index < len(body_lines):
        line = body_lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if line.startswith("- "):
            break
        if line.startswith("  - "):
            if current_row is not None:
                evidence_rows.append(current_row)

            key, raw_value = _split_key_value(line[4:].strip())
            current_row = {key: _parse_inline_value(raw_value)}
            index += 1
            continue

        if line.startswith("    "):
            if current_row is None:
                raise MetaLearningsValidationError(
                    [f"{entry_id}: supporting_evidence contains nested fields before a case_id row"]
                )
            key, raw_value = _split_key_value(stripped)
            current_row[key] = _parse_inline_value(raw_value)
            index += 1
            continue

        break

    if current_row is not None:
        evidence_rows.append(current_row)

    if not evidence_rows:
        raise MetaLearningsValidationError(
            [f"{entry_id}: supporting_evidence must contain at least one evidence row"]
        )

    return (evidence_rows, index)


def _parse_entry_fields(
    entry_id: str,
    body_lines: list[str],
) -> dict[str, Any]:
    parsed_fields: dict[str, Any] = {}
    index = 0

    while index < len(body_lines):
        line = body_lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if not line.startswith("- "):
            raise MetaLearningsValidationError(
                [f"{entry_id}: unsupported line outside bullet structure: {stripped!r}"]
            )

        key, raw_value = _split_key_value(line[2:].strip())
        if key == "applicability_conditions":
            parsed_value, index = _parse_applicability_conditions(
                body_lines,
                index + 1,
                entry_id=entry_id,
            )
            parsed_fields[key] = parsed_value
            continue

        if key == "supporting_evidence":
            parsed_value, index = _parse_supporting_evidence(
                body_lines,
                index + 1,
                entry_id=entry_id,
            )
            parsed_fields[key] = parsed_value
            continue

        parsed_fields[key] = _parse_inline_value(raw_value)
        index += 1

    return parsed_fields


def _normalize_supporting_evidence_row(
    row: dict[str, Any],
    *,
    entry_id: str,
    row_index: int,
) -> dict[str, str]:
    if not isinstance(row, dict):
        raise ValueError(
            f"{entry_id}: supporting_evidence[{row_index}] must be a mapping"
        )

    normalized_row: dict[str, str] = {}
    for field_name in REQUIRED_SUPPORTING_EVIDENCE_FIELDS:
        normalized_row[field_name] = _normalize_non_empty_text(
            row.get(field_name),
            field_name=f"{entry_id}.supporting_evidence[{row_index}].{field_name}",
        )

    normalized_row["source_kind"] = _normalize_enum(
        normalized_row["source_kind"],
        field_name=f"{entry_id}.supporting_evidence[{row_index}].source_kind",
        allowed_values=CANONICAL_SOURCE_KIND_VALUES,
    )

    return normalized_row


def _validate_required_mapping_fields(
    mapping: Mapping[str, Any],
    *,
    required_fields: tuple[str, ...],
    field_name: str,
) -> None:
    missing_fields = [name for name in required_fields if name not in mapping]
    if missing_fields:
        raise ValueError(f"{field_name} is missing required fields: {missing_fields}")


def _normalize_entry(
    *,
    entry_id: str,
    title: str,
    parsed_fields: dict[str, Any],
    target_context: dict[str, Any],
) -> dict[str, Any]:
    if not ENTRY_ID_PATTERN.match(entry_id):
        raise ValueError(f"entry_id must match ML-YYYY-MM-DD-NNN; received {entry_id!r}")

    normalized_title = _normalize_non_empty_text(title, field_name=f"{entry_id}.title")

    normalized_applicability = parsed_fields.get("applicability_conditions")
    if not isinstance(normalized_applicability, Mapping):
        raise ValueError(f"{entry_id}.applicability_conditions is required")
    _validate_required_mapping_fields(
        normalized_applicability,
        required_fields=REQUIRED_APPLICABILITY_FIELDS,
        field_name=f"{entry_id}.applicability_conditions",
    )

    applicability_conditions = {
        "skill_patterns": _normalize_string_list(
            normalized_applicability.get("skill_patterns"),
            field_name=f"{entry_id}.applicability_conditions.skill_patterns",
        ),
        "agent_targets": _normalize_string_list(
            normalized_applicability.get("agent_targets"),
            field_name=f"{entry_id}.applicability_conditions.agent_targets",
        ),
        "scenario_targets": _normalize_string_list(
            normalized_applicability.get("scenario_targets"),
            field_name=f"{entry_id}.applicability_conditions.scenario_targets",
        ),
        "scope_type": _normalize_non_empty_text(
            normalized_applicability.get("scope_type"),
            field_name=f"{entry_id}.applicability_conditions.scope_type",
        ),
        "scope_ref": _normalize_non_empty_text(
            normalized_applicability.get("scope_ref"),
            field_name=f"{entry_id}.applicability_conditions.scope_ref",
        ),
        "when_to_apply": _normalize_non_empty_text(
            normalized_applicability.get("when_to_apply"),
            field_name=f"{entry_id}.applicability_conditions.when_to_apply",
        ),
        "do_not_apply_when": _normalize_non_empty_text(
            normalized_applicability.get("do_not_apply_when"),
            field_name=f"{entry_id}.applicability_conditions.do_not_apply_when",
        ),
    }

    supporting_evidence_raw = parsed_fields.get("supporting_evidence")
    if not isinstance(supporting_evidence_raw, list) or not supporting_evidence_raw:
        raise ValueError(f"{entry_id}.supporting_evidence is required")

    supporting_evidence = [
        _normalize_supporting_evidence_row(row, entry_id=entry_id, row_index=index)
        for index, row in enumerate(supporting_evidence_raw)
    ]

    normalized_entry = {
        "entry_id": entry_id,
        "title": normalized_title,
        "entry_type": _normalize_enum(
            parsed_fields.get("entry_type"),
            field_name=f"{entry_id}.entry_type",
            allowed_values=(CANONICAL_ENTRY_TYPE,),
        ),
        "status": _normalize_enum(
            parsed_fields.get("status"),
            field_name=f"{entry_id}.status",
            allowed_values=CANONICAL_STATUS_VALUES,
        ),
        "learning": _normalize_non_empty_text(
            parsed_fields.get("learning"),
            field_name=f"{entry_id}.learning",
        ),
        "applicability_conditions": applicability_conditions,
        "supporting_evidence": supporting_evidence,
        "confidence": _normalize_enum(
            parsed_fields.get("confidence"),
            field_name=f"{entry_id}.confidence",
            allowed_values=CANONICAL_CONFIDENCE_VALUES,
        ),
        "promotion_basis": _normalize_non_empty_text(
            parsed_fields.get("promotion_basis"),
            field_name=f"{entry_id}.promotion_basis",
        ),
        "precedence": _normalize_enum(
            parsed_fields.get("precedence"),
            field_name=f"{entry_id}.precedence",
            allowed_values=CANONICAL_PRECEDENCE_VALUES,
        ),
        "review_status": _normalize_enum(
            parsed_fields.get("review_status"),
            field_name=f"{entry_id}.review_status",
            allowed_values=CANONICAL_REVIEW_STATUS_VALUES,
        ),
        "supporting_case_ids": _normalize_string_list(
            parsed_fields.get("supporting_case_ids"),
            field_name=f"{entry_id}.supporting_case_ids",
        ),
        "derived_from_entry_ids": _normalize_string_list(
            parsed_fields.get("derived_from_entry_ids"),
            field_name=f"{entry_id}.derived_from_entry_ids",
        ),
        "last_reviewed_at": _normalize_iso_timestamp(
            parsed_fields.get("last_reviewed_at"),
            field_name=f"{entry_id}.last_reviewed_at",
        ),
        "normalized_entry_type": CANONICAL_ENTRY_TYPE,
    }

    applicability_conditions["skill_metadata_keywords"] = _normalize_optional_string_list(
        _first_present(
            normalized_applicability,
            "skill_metadata_keywords",
            "metadata_keywords",
            "skill_metadata_any",
        ),
        field_name=f"{entry_id}.applicability_conditions.skill_metadata_keywords",
    )
    applicability_conditions["objective_keywords"] = _normalize_optional_string_list(
        _first_present(
            normalized_applicability,
            "objective_keywords",
            "campaign_objective_keywords",
            "objective_keywords_any",
            "objective_any",
        ),
        field_name=f"{entry_id}.applicability_conditions.objective_keywords",
    )

    is_actionable, block_reason = _resolve_actionability(
        normalized_entry,
        target_context=target_context,
    )
    normalized_entry["is_actionable"] = is_actionable
    normalized_entry["block_reason"] = block_reason
    return normalized_entry


def _matches_target_context(
    applicability_conditions: dict[str, Any],
    *,
    target_context: dict[str, Any],
) -> bool:
    skill_patterns = applicability_conditions["skill_patterns"]
    agent_targets = applicability_conditions["agent_targets"]
    scenario_targets = applicability_conditions["scenario_targets"]
    scope_type = applicability_conditions["scope_type"]
    scope_ref = applicability_conditions["scope_ref"]

    if target_context["skill_pattern"] not in skill_patterns:
        return False
    if target_context["scenario_target"] not in scenario_targets:
        return False
    if target_context["agent_target"] not in agent_targets and "any_skill_md" not in agent_targets:
        return False
    if scope_type != target_context["scope_type"]:
        return False
    if scope_ref not in {target_context["scope_ref"], "any_skill_md"}:
        return False
    return True


def _matches_relevance_filters(
    applicability_conditions: dict[str, Any],
    *,
    target_context: dict[str, Any],
) -> bool:
    if not _matches_keyword_filters(
        applicability_conditions.get("skill_metadata_keywords", []),
        searchable_text=_build_skill_metadata_search_text(target_context.get("skill_metadata")),
    ):
        return False

    if not _matches_keyword_filters(
        applicability_conditions.get("objective_keywords", []),
        searchable_text=_normalize_search_text(target_context.get("campaign_objective")),
    ):
        return False

    return True


def _resolve_actionability(
    normalized_entry: dict[str, Any],
    *,
    target_context: dict[str, Any],
) -> tuple[bool, str | None]:
    status = normalized_entry["status"]
    review_status = normalized_entry["review_status"]
    supporting_case_ids = normalized_entry["supporting_case_ids"]

    if status != "active":
        return (False, "status_not_active")
    if review_status != "approved":
        return (False, "pending_review")
    if len(supporting_case_ids) < 1:
        return (False, "insufficient_supporting_evidence")
    if not _matches_target_context(
        normalized_entry["applicability_conditions"],
        target_context=target_context,
    ):
        return (False, "context_mismatch")
    if not _matches_relevance_filters(
        normalized_entry["applicability_conditions"],
        target_context=target_context,
    ):
        return (False, "relevance_mismatch")
    return (True, None)


def _parse_meta_learnings_entries(
    markdown_text: str,
    *,
    target_context: dict[str, Any],
) -> list[dict[str, Any]]:
    errors = _validate_required_sections(markdown_text)
    if errors:
        raise MetaLearningsValidationError(errors)

    entry_blocks = _extract_entry_blocks(markdown_text)
    if not entry_blocks:
        return []

    normalized_entries: list[dict[str, Any]] = []
    entry_errors: list[str] = []

    for entry_id, title, body_lines in entry_blocks:
        try:
            parsed_fields = _parse_entry_fields(entry_id, body_lines)
            normalized_entries.append(
                _normalize_entry(
                    entry_id=entry_id,
                    title=title,
                    parsed_fields=parsed_fields,
                    target_context=target_context,
                )
            )
        except (MetaLearningsValidationError, TypeError, ValueError) as exc:
            if isinstance(exc, MetaLearningsValidationError):
                entry_errors.extend(exc.errors)
            else:
                entry_errors.append(str(exc))

    if entry_errors:
        raise MetaLearningsValidationError(entry_errors)

    return normalized_entries


def _sort_actionable_entry_ids(entries: list[dict[str, Any]]) -> list[str]:
    actionable_entries = [entry for entry in entries if entry["is_actionable"]]
    prioritized_entries = sorted(
        actionable_entries,
        key=lambda entry: _PRECEDENCE_RANK[entry["precedence"]],
    )
    return [entry["entry_id"] for entry in prioritized_entries]


def load_meta_learnings_bundle(
    meta_learnings_path: str | Path,
    *,
    target_context: Mapping[str, Any],
    loaded_at: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    resolved_path = Path(meta_learnings_path).expanduser()
    normalized_loaded_at = (
        _normalize_iso_timestamp(loaded_at, field_name="loaded_at")
        if loaded_at is not None
        else _now_utc_timestamp()
    )
    normalized_target_context = _normalize_target_context(target_context)
    bundle = _build_base_bundle(
        resolved_path,
        target_context=normalized_target_context,
        loaded_at=normalized_loaded_at,
    )

    if not resolved_path.exists():
        bundle["load_status"] = "missing"
        return _attach_reporting_metadata(
            bundle,
            meta_learnings_path=resolved_path,
            target_context=normalized_target_context,
            curator_version=None,
        )

    markdown_text = resolved_path.read_text(encoding="utf-8")
    curator_version = _stable_sha256(markdown_text)

    try:
        entries = _parse_meta_learnings_entries(
            markdown_text,
            target_context=normalized_target_context,
        )
    except MetaLearningsValidationError as exc:
        if strict:
            raise
        bundle["load_status"] = "parse_failed"
        bundle["validation_errors"] = exc.errors
        return _attach_reporting_metadata(
            bundle,
            meta_learnings_path=resolved_path,
            target_context=normalized_target_context,
            curator_version=curator_version,
        )

    bundle["entries"] = entries
    bundle["actionable_entry_ids"] = _sort_actionable_entry_ids(entries)
    bundle["historical_entry_ids"] = [
        entry["entry_id"]
        for entry in entries
        if entry["status"] in {"superseded", "rejected"}
    ]
    bundle["blocked_entry_ids"] = [
        entry["entry_id"]
        for entry in entries
        if not entry["is_actionable"] and entry["entry_id"] not in bundle["historical_entry_ids"]
    ]
    bundle["load_status"] = "empty" if not entries else "loaded"
    return _attach_reporting_metadata(
        bundle,
        meta_learnings_path=resolved_path,
        target_context=normalized_target_context,
        curator_version=curator_version,
    )


def load_meta_learnings_bundle_from_state(
    state: Mapping[str, Any] | None,
    *,
    target_context: Mapping[str, Any],
    loaded_at: str | None = None,
    strict: bool = False,
    default_skill_directory: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve the source path from bootstrap state, then load the bundle."""

    resolved_path = resolve_meta_learnings_path(
        state=state,
        default_skill_directory=default_skill_directory,
    )
    return load_meta_learnings_bundle(
        resolved_path,
        target_context=target_context,
        loaded_at=loaded_at,
        strict=strict,
    )


def load_meta_learnings_bootstrap_context_from_state(
    state: Mapping[str, Any] | None,
    *,
    target_context: Mapping[str, Any],
    loaded_at: str | None = None,
    strict: bool = False,
    default_skill_directory: str | Path | None = None,
) -> dict[str, Any]:
    """Load the curated bundle, then assemble the campaign bootstrap context.

    Campaign bootstrap should thread the selected curated-learnings bundle
    directly into context assembly so downstream consumers see the same
    filtered payload that bootstrap resolved for the current run.
    """

    filtered_curated_learnings = load_meta_learnings_bundle_from_state(
        state,
        target_context=target_context,
        loaded_at=loaded_at,
        strict=strict,
        default_skill_directory=default_skill_directory,
    )
    return build_meta_learnings_bootstrap_context(
        target_context=target_context,
        state=state,
        loaded_at=loaded_at,
        strict=strict,
        default_skill_directory=default_skill_directory,
        filtered_curated_learnings=filtered_curated_learnings,
    )


def _resolve_explicit_filtered_curated_learnings(
    *,
    parsed_meta_learnings: Mapping[str, Any] | None = None,
    filtered_curated_learnings: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    explicit_bundle = (
        filtered_curated_learnings
        if filtered_curated_learnings is not None
        else parsed_meta_learnings
    )

    if (
        filtered_curated_learnings is not None
        and parsed_meta_learnings is not None
        and filtered_curated_learnings != parsed_meta_learnings
    ):
        raise ValueError(
            "filtered_curated_learnings and parsed_meta_learnings must match when both are provided"
        )

    if explicit_bundle is None:
        return None

    if not isinstance(explicit_bundle, Mapping):
        raise TypeError("filtered_curated_learnings must be a mapping when provided")

    return deepcopy(dict(explicit_bundle))


def build_meta_learnings_bootstrap_context(
    *,
    target_context: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    loaded_at: str | None = None,
    strict: bool = False,
    default_skill_directory: str | Path | None = None,
    parsed_meta_learnings: Mapping[str, Any] | None = None,
    filtered_curated_learnings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the initial campaign config/context payload for parsed meta-learnings.

    Campaign bootstrap consumers should carry this object in the loaded run
    context so Phase 7 and resume flows can reuse one resolved bundle instead of
    re-reading the markdown file ad hoc within mutation design. Callers that
    already hold the filtered curated-learnings bundle may pass it explicitly to
    avoid reloading the source document during campaign-context assembly.
    """

    normalized_target_context = _normalize_target_context(target_context)
    explicit_filtered_bundle = _resolve_explicit_filtered_curated_learnings(
        parsed_meta_learnings=parsed_meta_learnings,
        filtered_curated_learnings=filtered_curated_learnings,
    )

    if explicit_filtered_bundle is None:
        resolved_path = resolve_meta_learnings_path(
            state=state,
            default_skill_directory=default_skill_directory,
        )
        parsed_bundle = load_meta_learnings_bundle(
            resolved_path,
            target_context=normalized_target_context,
            loaded_at=loaded_at,
            strict=strict,
        )
    else:
        explicit_path = _clean_text(explicit_filtered_bundle.get("meta_learnings_path"))
        resolved_path = (
            Path(explicit_path).expanduser()
            if explicit_path
            else resolve_meta_learnings_path(
                state=state,
                default_skill_directory=default_skill_directory,
            )
        )
        parsed_bundle = explicit_filtered_bundle

    return {
        "meta_learnings_path": str(resolved_path.resolve()),
        "target_context": dict(normalized_target_context),
        "parsed_meta_learnings": parsed_bundle,
        "curator_source": parsed_bundle.get("curator_source"),
        "curator_version": parsed_bundle.get("curator_version"),
        "transfer_parameters": deepcopy(parsed_bundle.get("transfer_parameters", dict(normalized_target_context))),
        "transfer_traceability": deepcopy(parsed_bundle.get("transfer_traceability")),
    }


__all__ = [
    "CANONICAL_BUNDLE_TYPE",
    "CANONICAL_CONFIDENCE_VALUES",
    "CANONICAL_ENTRY_TYPE",
    "CANONICAL_LOAD_STATUSES",
    "CANONICAL_PRECEDENCE_VALUES",
    "CANONICAL_REVIEW_STATUS_VALUES",
    "CANONICAL_SOURCE_KIND_VALUES",
    "CANONICAL_STATUS_VALUES",
    "DEFAULT_META_LEARNINGS_FILENAME",
    "META_LEARNINGS_BUNDLE_SCHEMA_VERSION",
    "MetaLearningsValidationError",
    "build_meta_learnings_bootstrap_context",
    "load_meta_learnings_bundle",
    "load_meta_learnings_bootstrap_context_from_state",
    "load_meta_learnings_bundle_from_state",
    "resolve_meta_learnings_path",
]
