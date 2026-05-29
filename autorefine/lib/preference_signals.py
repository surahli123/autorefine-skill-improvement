from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ._shared_text import (
    clean_identifier as _clean_identifier,
    clean_text as _clean_text,
)


CANONICAL_PREFERENCE_KEYS = (
    "verbosity",
    "structure_change",
    "mutation_operation",
    "section_focus",
    "voice_style",
    "instruction_density",
    "example_density",
    "reference_usage",
)
CANONICAL_PREFERENCE_VALUES = {
    "verbosity": ("terse", "balanced", "detailed"),
    "structure_change": ("preserve", "allow_local", "allow_major"),
    "mutation_operation": (
        "prefer_add",
        "prefer_modify",
        "prefer_remove",
        "avoid_add",
        "avoid_modify",
        "avoid_remove",
    ),
    "section_focus": ("prefer", "avoid", "deprioritize"),
    "voice_style": ("instructional", "descriptive", "neutral"),
    "instruction_density": ("lighter", "balanced", "heavier"),
    "example_density": ("fewer", "balanced", "more"),
    "reference_usage": ("inline", "read_when", "minimal"),
}
CANONICAL_PREFERENCE_DETECTION_MODES = (
    "ambient_diff",
    "mid_session_override_scan",
    "manual_entry",
)
CANONICAL_PREFERENCE_SOURCE_KINDS = (
    "preferences_md",
    "user_override_scan_task",
    "human_confirmation",
)

_CANONICAL_CONFIDENCE_VALUES = ("high", "medium", "low")
_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
_OVERRIDE_MUTATION_TYPE_TO_OPERATION = {
    "add": "add",
    "added": "add",
    "append": "add",
    "insert": "add",
    "inserted": "add",
    "modify": "modify",
    "modified": "modify",
    "edit": "modify",
    "edited": "modify",
    "update": "modify",
    "updated": "modify",
    "rewrite": "modify",
    "rewritten": "modify",
    "remove": "remove",
    "removed": "remove",
    "delete": "remove",
    "deleted": "remove",
}


def _clone_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _clone_json_value(item) for key, item in value.items()}
    if isinstance(value, set):
        return sorted(_clone_json_value(item) for item in value)
    if isinstance(value, list):
        return [_clone_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_clone_json_value(item) for item in value]
    return value


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    normalized = _clean_text(value).lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"expected boolean-compatible value, received {value!r}")


def _coerce_optional_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer when provided")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError(f"{field_name} must be an integer when provided")

    normalized = _clean_text(value)
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer when provided") from exc


def _normalize_string_list(value: Any, *, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, (list, tuple)):
        normalized_items: list[str] = []
        for item in value:
            normalized_item = _clean_text(item)
            if normalized_item and normalized_item not in normalized_items:
                normalized_items.append(normalized_item)
        return normalized_items

    normalized = _clean_text(value)
    if not normalized:
        return list(default or [])
    return [normalized]


def _normalize_required_non_empty_text(
    raw_value: Any,
    *,
    field_name: str,
) -> str:
    normalized_value = _clean_text(raw_value)
    if not normalized_value:
        raise ValueError(f"{field_name} is required")
    return normalized_value


def _normalize_allowed_value(
    raw_value: Any,
    *,
    field_name: str,
    allowed_values: tuple[str, ...],
) -> str:
    normalized_value = _clean_text(raw_value)
    if normalized_value not in allowed_values:
        raise ValueError(
            f"{field_name} must be one of {allowed_values}; received {raw_value!r}"
        )
    return normalized_value


def _json_key(value: Any) -> str:
    return json.dumps(_clone_json_value(value), sort_keys=True, ensure_ascii=True)


def _normalize_preference_key(value: Any, *, field_name: str) -> str:
    return _normalize_allowed_value(
        value,
        field_name=field_name,
        allowed_values=CANONICAL_PREFERENCE_KEYS,
    )


def _normalize_preference_value(
    *,
    preference_key: str,
    value: Any,
    field_name: str,
) -> str:
    allowed_values = CANONICAL_PREFERENCE_VALUES.get(preference_key)
    if not allowed_values:
        raise ValueError(f"unsupported preference_key {preference_key!r}")
    return _normalize_allowed_value(
        value,
        field_name=field_name,
        allowed_values=allowed_values,
    )


def _normalize_preference_source_ref(value: Any, *, field_name: str) -> Any:
    if isinstance(value, Mapping):
        normalized_mapping = _clone_json_value(value)
        if not normalized_mapping:
            raise ValueError(f"{field_name} must not be empty")
        return normalized_mapping

    normalized_text = _clean_text(value)
    if not normalized_text:
        raise ValueError(f"{field_name} is required")
    return normalized_text


def _normalize_preference_scope(
    raw_scope: Any,
    *,
    preference_key: str,
    field_name: str,
) -> dict[str, Any]:
    if raw_scope is None:
        raw_scope = {}
    if not isinstance(raw_scope, Mapping):
        raise ValueError(f"{field_name} must be a mapping")

    normalized_scope = _clone_json_value(raw_scope)
    section_ids = _normalize_string_list(normalized_scope.get("section_ids"), default=[])
    if section_ids:
        normalized_scope["section_ids"] = section_ids
    elif "section_ids" in normalized_scope:
        normalized_scope["section_ids"] = []

    if preference_key == "section_focus" and not section_ids:
        raise ValueError(f"{field_name}.section_ids is required when preference_key = section_focus")

    return normalized_scope


def _normalize_preference_confidence_metadata(
    raw_metadata: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(raw_metadata, Mapping):
        raise ValueError(f"{field_name} must be a mapping")

    normalized_metadata = _clone_json_value(raw_metadata)
    normalized_metadata["signal_confidence"] = _normalize_allowed_value(
        normalized_metadata.get("signal_confidence"),
        field_name=f"{field_name}.signal_confidence",
        allowed_values=_CANONICAL_CONFIDENCE_VALUES,
    )
    normalized_metadata["source_confidence"] = _normalize_allowed_value(
        normalized_metadata.get("source_confidence"),
        field_name=f"{field_name}.source_confidence",
        allowed_values=_CANONICAL_CONFIDENCE_VALUES,
    )
    normalized_metadata["confidence_reason"] = _normalize_required_non_empty_text(
        normalized_metadata.get("confidence_reason"),
        field_name=f"{field_name}.confidence_reason",
    )
    support_count = _coerce_optional_int(
        normalized_metadata.get("support_count"),
        field_name=f"{field_name}.support_count",
    )
    if support_count is None or support_count < 1:
        raise ValueError(f"{field_name}.support_count must be an integer >= 1")
    normalized_metadata["support_count"] = support_count
    normalized_metadata["confirmation_bonus_applied"] = _coerce_bool(
        normalized_metadata.get("confirmation_bonus_applied"),
        default=False,
    )
    return normalized_metadata


def _normalize_preference_override_entry(
    raw_entry: Any,
    *,
    preference_key: str,
    preference_value: str,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(raw_entry, Mapping):
        raise ValueError(f"{field_name} must be a mapping")

    normalized_entry = _clone_json_value(raw_entry)
    experiment_id = _coerce_optional_int(
        normalized_entry.get("experiment_id"),
        field_name=f"{field_name}.experiment_id",
    )
    if experiment_id is None or experiment_id < 0:
        raise ValueError(f"{field_name}.experiment_id must be an integer >= 0")
    normalized_entry["experiment_id"] = experiment_id

    completed_experiment_slot = _coerce_optional_int(
        normalized_entry.get("completed_experiment_slot"),
        field_name=f"{field_name}.completed_experiment_slot",
    )
    if completed_experiment_slot is None or completed_experiment_slot < 1:
        raise ValueError(f"{field_name}.completed_experiment_slot must be an integer >= 1")
    normalized_entry["completed_experiment_slot"] = completed_experiment_slot

    normalized_entry["source_kind"] = _normalize_allowed_value(
        normalized_entry.get("source_kind"),
        field_name=f"{field_name}.source_kind",
        allowed_values=CANONICAL_PREFERENCE_SOURCE_KINDS,
    )
    normalized_entry["source_ref"] = _normalize_preference_source_ref(
        normalized_entry.get("source_ref"),
        field_name=f"{field_name}.source_ref",
    )
    normalized_entry["agent_verdict"] = _normalize_allowed_value(
        normalized_entry.get("agent_verdict"),
        field_name=f"{field_name}.agent_verdict",
        allowed_values=("keep", "discard"),
    )
    normalized_entry["user_verdict"] = _normalize_allowed_value(
        normalized_entry.get("user_verdict"),
        field_name=f"{field_name}.user_verdict",
        allowed_values=("keep", "discard"),
    )
    normalized_entry["override_direction"] = _normalize_allowed_value(
        normalized_entry.get("override_direction"),
        field_name=f"{field_name}.override_direction",
        allowed_values=("keep_to_discard", "discard_to_keep"),
    )
    normalized_entry["changed_locations"] = _normalize_string_list(
        normalized_entry.get("changed_locations"),
        default=[],
    )
    normalized_entry["mutation_types"] = _normalize_string_list(
        normalized_entry.get("mutation_types"),
        default=[],
    )
    normalized_entry["preference_key"] = _normalize_preference_key(
        preference_key,
        field_name=f"{field_name}.preference_key",
    )
    normalized_entry["preference_value"] = _normalize_preference_value(
        preference_key=normalized_entry["preference_key"],
        value=preference_value,
        field_name=f"{field_name}.preference_value",
    )
    normalized_entry["source_confidence"] = _normalize_allowed_value(
        normalized_entry.get("source_confidence"),
        field_name=f"{field_name}.source_confidence",
        allowed_values=_CANONICAL_CONFIDENCE_VALUES,
    )
    normalized_entry["confidence_reason"] = _normalize_required_non_empty_text(
        normalized_entry.get("confidence_reason"),
        field_name=f"{field_name}.confidence_reason",
    )
    return normalized_entry


def _normalize_preference_detected_from(
    raw_value: Any,
    *,
    preference_key: str,
    preference_value: str,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")

    normalized_detected_from = _clone_json_value(raw_value)
    normalized_detected_from["detection_mode"] = _normalize_allowed_value(
        normalized_detected_from.get("detection_mode"),
        field_name=f"{field_name}.detection_mode",
        allowed_values=CANONICAL_PREFERENCE_DETECTION_MODES,
    )
    normalized_detected_from["source_kind"] = _normalize_allowed_value(
        normalized_detected_from.get("source_kind"),
        field_name=f"{field_name}.source_kind",
        allowed_values=CANONICAL_PREFERENCE_SOURCE_KINDS,
    )
    normalized_detected_from["source_ref"] = _normalize_preference_source_ref(
        normalized_detected_from.get("source_ref"),
        field_name=f"{field_name}.source_ref",
    )
    support_count = _coerce_optional_int(
        normalized_detected_from.get("support_count"),
        field_name=f"{field_name}.support_count",
    )
    if support_count is None or support_count < 1:
        raise ValueError(f"{field_name}.support_count must be an integer >= 1")
    normalized_detected_from["support_count"] = support_count

    normalized_rows: list[dict[str, Any]] = []
    raw_rows = normalized_detected_from.get("normalized_override_entries")
    if raw_rows is None:
        raw_rows = []
    if not isinstance(raw_rows, list):
        raise ValueError(f"{field_name}.normalized_override_entries must be a list")
    for index, raw_row in enumerate(raw_rows):
        normalized_rows.append(
            _normalize_preference_override_entry(
                raw_row,
                preference_key=preference_key,
                preference_value=preference_value,
                field_name=f"{field_name}.normalized_override_entries[{index}]",
            )
        )

    if (
        normalized_detected_from["detection_mode"] == "mid_session_override_scan"
        and not normalized_rows
    ):
        raise ValueError(
            f"{field_name}.normalized_override_entries must be non-empty when detection_mode = mid_session_override_scan"
        )
    normalized_detected_from["normalized_override_entries"] = normalized_rows
    normalized_detected_from["confidence_metadata"] = _normalize_preference_confidence_metadata(
        normalized_detected_from.get("confidence_metadata"),
        field_name=f"{field_name}.confidence_metadata",
    )
    return normalized_detected_from


def normalize_preference_signal_payload(raw_payload: Any) -> dict[str, Any]:
    if not isinstance(raw_payload, Mapping):
        raise ValueError("preference_signal payload must be a mapping")

    payload = _clone_json_value(raw_payload)
    preference_key = _normalize_preference_key(
        payload.get("preference_key"),
        field_name="preference_signal.preference_key",
    )
    preference_value = _normalize_preference_value(
        preference_key=preference_key,
        value=payload.get("preference_value"),
        field_name="preference_signal.preference_value",
    )
    payload["preference_key"] = preference_key
    payload["preference_value"] = preference_value
    payload["preference_statement"] = _normalize_required_non_empty_text(
        payload.get("preference_statement"),
        field_name="preference_signal.preference_statement",
    )
    payload["detected_from"] = _normalize_preference_detected_from(
        payload.get("detected_from"),
        preference_key=preference_key,
        preference_value=preference_value,
        field_name="preference_signal.detected_from",
    )
    payload["confirmation_state"] = _normalize_required_non_empty_text(
        payload.get("confirmation_state"),
        field_name="preference_signal.confirmation_state",
    )
    payload["preference_scope"] = _normalize_preference_scope(
        payload.get("preference_scope"),
        preference_key=preference_key,
        field_name="preference_signal.preference_scope",
    )
    expiry_policy = payload.get("expiry_policy")
    if isinstance(expiry_policy, Mapping):
        payload["expiry_policy"] = _clone_json_value(expiry_policy)
    else:
        payload["expiry_policy"] = _normalize_required_non_empty_text(
            expiry_policy,
            field_name="preference_signal.expiry_policy",
        )
    return payload


_normalize_preference_signal_payload = normalize_preference_signal_payload


def _bump_confidence(confidence: str) -> str:
    confidence_rank = _CONFIDENCE_RANK.get(confidence)
    if confidence_rank is None:
        return confidence
    for candidate_confidence, candidate_rank in _CONFIDENCE_RANK.items():
        if candidate_rank == min(confidence_rank + 1, max(_CONFIDENCE_RANK.values())):
            return candidate_confidence
    return confidence


def _normalize_override_mutation_operation(value: Any) -> str | None:
    normalized_value = _clean_identifier(value)
    if not normalized_value:
        return None
    return _OVERRIDE_MUTATION_TYPE_TO_OPERATION.get(normalized_value)


def _normalize_user_override_scan_entry(
    raw_entry: Any,
    *,
    default_completed_experiment_slot: int | None,
) -> dict[str, Any]:
    if not isinstance(raw_entry, Mapping):
        raise ValueError("user_override_scan.experiment_window[] must be a mapping")

    normalized_entry = _clone_json_value(raw_entry)
    experiment_id = _coerce_optional_int(
        normalized_entry.get("experiment_id"),
        field_name="user_override_scan.experiment_window[].experiment_id",
    )
    normalized_entry["experiment_id"] = experiment_id

    agent_verdict = _clean_text(normalized_entry.get("agent_verdict"))
    user_verdict = _clean_text(normalized_entry.get("user_verdict"))
    if agent_verdict not in {"keep", "discard"}:
        agent_verdict = None
    if user_verdict not in {"keep", "discard"}:
        user_verdict = None
    normalized_entry["agent_verdict"] = agent_verdict
    normalized_entry["user_verdict"] = user_verdict

    override_detected = _coerce_bool(
        normalized_entry.get("override_detected"),
        default=bool(
            agent_verdict
            and user_verdict
            and agent_verdict != user_verdict
        ),
    )
    normalized_entry["override_detected"] = override_detected
    override_direction = _clean_text(normalized_entry.get("override_direction"))
    if (
        override_direction not in {"keep_to_discard", "discard_to_keep"}
        and override_detected
        and agent_verdict
        and user_verdict
    ):
        override_direction = f"{agent_verdict}_to_{user_verdict}"
    normalized_entry["override_direction"] = override_direction or None
    normalized_entry["changed_locations"] = _normalize_string_list(
        normalized_entry.get("changed_locations"),
        default=[],
    )
    normalized_entry["mutation_types"] = _normalize_string_list(
        normalized_entry.get("mutation_types"),
        default=[],
    )
    normalized_entry["normalized_mutation_operations"] = [
        operation
        for operation in (
            _normalize_override_mutation_operation(value)
            for value in normalized_entry["mutation_types"]
        )
        if operation
    ]

    row_completed_slot = None
    completion_cadence = normalized_entry.get("completion_cadence")
    if isinstance(completion_cadence, Mapping):
        row_completed_slot = _coerce_optional_int(
            completion_cadence.get("completed_experiments"),
            field_name="user_override_scan.experiment_window[].completion_cadence.completed_experiments",
        )
    normalized_entry["completed_experiment_slot"] = row_completed_slot or default_completed_experiment_slot
    return normalized_entry


def _normalize_user_override_scan_task(scan_task: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(scan_task, Mapping):
        raise TypeError("scan_task must be a mapping")

    normalized_task = _clone_json_value(scan_task)
    task_type = _clean_text(normalized_task.get("task_type"), default="user_override_scan")
    if task_type != "user_override_scan":
        raise ValueError(f"scan_task.task_type must be 'user_override_scan'; received {task_type!r}")
    completed_experiment_slot = _coerce_optional_int(
        normalized_task.get("completed_experiment_slot"),
        field_name="scan_task.completed_experiment_slot",
    )
    if completed_experiment_slot is not None and completed_experiment_slot < 1:
        raise ValueError("scan_task.completed_experiment_slot must be >= 1 when provided")
    experiment_window = normalized_task.get("experiment_window")
    if not isinstance(experiment_window, list):
        raise ValueError("scan_task.experiment_window must be a list")

    normalized_task["task_type"] = task_type
    normalized_task["completed_experiment_slot"] = completed_experiment_slot
    normalized_task["experiment_window"] = [
        _normalize_user_override_scan_entry(
            raw_entry,
            default_completed_experiment_slot=completed_experiment_slot,
        )
        for raw_entry in experiment_window
    ]
    return normalized_task


def _default_override_scan_source_ref(scan_task: Mapping[str, Any]) -> str:
    completed_experiment_slot = _coerce_optional_int(
        scan_task.get("completed_experiment_slot"),
        field_name="scan_task.completed_experiment_slot",
    )
    if completed_experiment_slot is not None:
        return f"checkpoint-tasks/exp{completed_experiment_slot}-user-override-scan.json"
    trigger_experiment_id = _coerce_optional_int(
        scan_task.get("trigger_experiment_id"),
        field_name="scan_task.trigger_experiment_id",
    )
    if trigger_experiment_id is not None:
        return f"user_override_scan:experiment:{trigger_experiment_id}"
    return "user_override_scan"


def _default_preference_expiry_policy() -> dict[str, Any]:
    return {
        "mode": "until_user_override",
        "expires_on_conflict": True,
    }


def _derive_preference_signal_confidence(
    *,
    support_count: int,
    row_confidences: list[str],
    confirmation_state: str,
    confidence_reason: str,
) -> dict[str, Any]:
    if support_count >= 3 and row_confidences and all(value == "high" for value in row_confidences):
        source_confidence = "high"
    elif support_count >= 2:
        source_confidence = "medium"
    else:
        source_confidence = "low"

    confirmation_bonus_applied = confirmation_state == "confirmed"
    signal_confidence = (
        _bump_confidence(source_confidence)
        if confirmation_bonus_applied
        else source_confidence
    )
    return {
        "signal_confidence": signal_confidence,
        "source_confidence": source_confidence,
        "confidence_reason": confidence_reason,
        "confirmation_bonus_applied": confirmation_bonus_applied,
        "support_count": support_count,
    }


def _build_preference_statement(
    *,
    preference_key: str,
    preference_value: str,
    section_ids: list[str],
) -> str:
    if preference_key == "mutation_operation":
        operation = preference_value.removeprefix("prefer_").removeprefix("avoid_")
        verb_phrase = {
            "add": "additive mutations",
            "modify": "modification-heavy mutations",
            "remove": "removal mutations",
        }.get(operation, f"{operation} mutations")
        if preference_value.startswith("avoid_"):
            if section_ids:
                return f"Avoid {verb_phrase} on {', '.join(section_ids)}."
            return f"Avoid {verb_phrase}."
        if section_ids:
            return f"Prefer {verb_phrase} on {', '.join(section_ids)}."
        return f"Prefer {verb_phrase}."

    if preference_key == "section_focus":
        if preference_value == "avoid":
            return f"Avoid focusing mutations on {', '.join(section_ids)}."
        if preference_value == "prefer":
            return f"Prefer focusing mutations on {', '.join(section_ids)}."
        return f"Deprioritize mutations on {', '.join(section_ids)}."

    return f"Prefer {preference_key.replace('_', ' ')} = {preference_value}."


def _build_override_confidence_reason(
    *,
    preference_key: str,
    preference_value: str,
    direction: str,
    section_ids: list[str],
    support_count: int,
) -> str:
    section_suffix = f" across {', '.join(section_ids)}" if section_ids else ""
    return (
        f"Derived from {support_count} consistent {direction} overrides supporting "
        f"{preference_key}={preference_value}{section_suffix}."
    )


def build_preference_signal_payload_from_override_scan(
    scan_task: Mapping[str, Any],
    *,
    preference_key: str,
    preference_value: str,
    supporting_entries: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
    preference_statement: str | None = None,
    preference_scope: Mapping[str, Any] | None = None,
    source_ref: str | Mapping[str, Any] | None = None,
    confirmation_state: str = "confirmed",
    expiry_policy: Any | None = None,
) -> dict[str, Any]:
    normalized_task = _normalize_user_override_scan_task(scan_task)
    normalized_preference_key = _normalize_preference_key(
        preference_key,
        field_name="preference_key",
    )
    normalized_preference_value = _normalize_preference_value(
        preference_key=normalized_preference_key,
        value=preference_value,
        field_name="preference_value",
    )

    candidate_entries = [
        _normalize_user_override_scan_entry(
            raw_entry,
            default_completed_experiment_slot=normalized_task.get("completed_experiment_slot"),
        )
        for raw_entry in (supporting_entries or ())
    ]
    if not candidate_entries:
        candidate_entries = [
            entry
            for entry in normalized_task["experiment_window"]
            if entry.get("override_detected") is True
            and entry.get("override_direction") in {"keep_to_discard", "discard_to_keep"}
        ]

    if not candidate_entries:
        raise ValueError("supporting_entries must include at least one override row")

    if normalized_preference_key == "section_focus":
        scope_seed = preference_scope if isinstance(preference_scope, Mapping) else {}
        resolved_section_ids = _normalize_string_list(scope_seed.get("section_ids"), default=[])
        if not resolved_section_ids:
            shared_sections = set(candidate_entries[0].get("changed_locations") or [])
            for entry in candidate_entries[1:]:
                shared_sections &= set(entry.get("changed_locations") or [])
            resolved_section_ids = sorted(shared_sections)
        normalized_preference_scope = _normalize_preference_scope(
            {"section_ids": resolved_section_ids, **(scope_seed if isinstance(scope_seed, Mapping) else {})},
            preference_key=normalized_preference_key,
            field_name="preference_scope",
        )
    else:
        normalized_preference_scope = _normalize_preference_scope(
            preference_scope or {},
            preference_key=normalized_preference_key,
            field_name="preference_scope",
        )

    detected_source_ref = source_ref or _default_override_scan_source_ref(normalized_task)
    direction = _clean_text(candidate_entries[0].get("override_direction")) or "keep_to_discard"
    support_count = len(candidate_entries)
    section_ids = _normalize_string_list(normalized_preference_scope.get("section_ids"), default=[])

    row_confidences: list[str] = []
    normalized_override_entries: list[dict[str, Any]] = []
    base_source_ref = _normalize_preference_source_ref(
        detected_source_ref,
        field_name="detected_from.source_ref",
    )
    for entry in candidate_entries:
        matched_operations = set(entry.get("normalized_mutation_operations") or [])
        if normalized_preference_key == "mutation_operation":
            expected_operation = normalized_preference_value.removeprefix("prefer_").removeprefix("avoid_")
            row_matches = expected_operation in matched_operations
            row_confidence = "high" if row_matches and len(matched_operations) == 1 else "medium"
        elif normalized_preference_key == "section_focus":
            entry_sections = set(entry.get("changed_locations") or [])
            row_matches = bool(section_ids) and set(section_ids).issubset(entry_sections)
            row_confidence = "high" if row_matches and len(entry_sections) == len(section_ids) else "medium"
        else:
            row_matches = True
            row_confidence = "medium"
        if not row_matches:
            continue

        row_confidences.append(row_confidence)
        experiment_id = entry.get("experiment_id")
        row_source_ref = (
            f"{base_source_ref}#experiment-{experiment_id}"
            if experiment_id is not None
            else base_source_ref
        )
        normalized_override_entries.append(
            _normalize_preference_override_entry(
                {
                    "experiment_id": experiment_id,
                    "completed_experiment_slot": entry.get("completed_experiment_slot"),
                    "source_kind": "user_override_scan_task",
                    "source_ref": row_source_ref,
                    "agent_verdict": entry.get("agent_verdict"),
                    "user_verdict": entry.get("user_verdict"),
                    "override_direction": entry.get("override_direction"),
                    "changed_locations": entry.get("changed_locations"),
                    "mutation_types": entry.get("mutation_types"),
                    "preference_key": normalized_preference_key,
                    "preference_value": normalized_preference_value,
                    "source_confidence": row_confidence,
                    "confidence_reason": _build_override_confidence_reason(
                        preference_key=normalized_preference_key,
                        preference_value=normalized_preference_value,
                        direction=direction,
                        section_ids=section_ids,
                        support_count=support_count,
                    ),
                },
                preference_key=normalized_preference_key,
                preference_value=normalized_preference_value,
                field_name="detected_from.normalized_override_entries[]",
            )
        )

    if not normalized_override_entries:
        raise ValueError("supporting_entries did not match the requested preference signal")

    confidence_reason = _build_override_confidence_reason(
        preference_key=normalized_preference_key,
        preference_value=normalized_preference_value,
        direction=direction,
        section_ids=section_ids,
        support_count=len(normalized_override_entries),
    )
    payload = {
        "preference_key": normalized_preference_key,
        "preference_value": normalized_preference_value,
        "preference_statement": _clean_text(preference_statement)
        or _build_preference_statement(
            preference_key=normalized_preference_key,
            preference_value=normalized_preference_value,
            section_ids=section_ids,
        ),
        "detected_from": {
            "detection_mode": "mid_session_override_scan",
            "source_kind": "user_override_scan_task",
            "source_ref": base_source_ref,
            "support_count": len(normalized_override_entries),
            "normalized_override_entries": normalized_override_entries,
            "confidence_metadata": _derive_preference_signal_confidence(
                support_count=len(normalized_override_entries),
                row_confidences=row_confidences,
                confirmation_state=confirmation_state,
                confidence_reason=confidence_reason,
            ),
        },
        "confirmation_state": _clean_text(confirmation_state, default="confirmed") or "confirmed",
        "preference_scope": normalized_preference_scope,
        "expiry_policy": _clone_json_value(expiry_policy)
        if expiry_policy is not None
        else _default_preference_expiry_policy(),
    }
    return normalize_preference_signal_payload(payload)


def derive_preference_signal_candidates_from_override_scan(
    scan_task: Mapping[str, Any],
    *,
    confirmation_state: str = "suggested",
    expiry_policy: Any | None = None,
    source_ref: str | Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    normalized_task = _normalize_user_override_scan_task(scan_task)
    override_rows = [
        entry
        for entry in normalized_task["experiment_window"]
        if entry.get("override_detected") is True
        and entry.get("override_direction") in {"keep_to_discard", "discard_to_keep"}
    ]
    if len(override_rows) < 2:
        return []

    candidate_payloads: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    rows_by_direction: dict[str, list[dict[str, Any]]] = {
        "keep_to_discard": [],
        "discard_to_keep": [],
    }
    for row in override_rows:
        rows_by_direction[row["override_direction"]].append(row)

    for direction, grouped_rows in rows_by_direction.items():
        if len(grouped_rows) < 2:
            continue

        shared_operations = set(grouped_rows[0].get("normalized_mutation_operations") or [])
        for row in grouped_rows[1:]:
            shared_operations &= set(row.get("normalized_mutation_operations") or [])
        if len(shared_operations) == 1:
            operation = next(iter(shared_operations))
            preference_value = f"{'avoid' if direction == 'keep_to_discard' else 'prefer'}_{operation}"
            payload = build_preference_signal_payload_from_override_scan(
                normalized_task,
                preference_key="mutation_operation",
                preference_value=preference_value,
                supporting_entries=grouped_rows,
                confirmation_state=confirmation_state,
                expiry_policy=expiry_policy,
                source_ref=source_ref,
            )
            signature = _json_key(
                {
                    "preference_key": payload["preference_key"],
                    "preference_value": payload["preference_value"],
                    "preference_scope": payload["preference_scope"],
                }
            )
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                candidate_payloads.append(payload)

        shared_sections = set(grouped_rows[0].get("changed_locations") or [])
        for row in grouped_rows[1:]:
            shared_sections &= set(row.get("changed_locations") or [])
        if shared_sections:
            payload = build_preference_signal_payload_from_override_scan(
                normalized_task,
                preference_key="section_focus",
                preference_value="avoid" if direction == "keep_to_discard" else "prefer",
                supporting_entries=grouped_rows,
                preference_scope={"section_ids": sorted(shared_sections)},
                confirmation_state=confirmation_state,
                expiry_policy=expiry_policy,
                source_ref=source_ref,
            )
            signature = _json_key(
                {
                    "preference_key": payload["preference_key"],
                    "preference_value": payload["preference_value"],
                    "preference_scope": payload["preference_scope"],
                }
            )
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                candidate_payloads.append(payload)

    return candidate_payloads
