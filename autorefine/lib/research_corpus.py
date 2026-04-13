from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_right
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._shared_text import (
    clean_identifier as _clean_identifier,
    clean_text as _clean_text,
    now_utc_timestamp as _now_utc_timestamp,
)
from .exemplar_source_loader import (
    CANONICAL_EXEMPLAR_PAYLOAD_TYPE,
    CANONICAL_VERSION_SNAPSHOT_BUNDLE_TYPE,
)
from .target_skill_scoring_context import build_target_skill_scoring_context


RESEARCH_CORPUS_SCHEMA_VERSION = 1
CANONICAL_RESEARCH_CORPUS_BUNDLE_TYPE = "normalized_research_corpus"
RESEARCH_CORPUS_STORAGE_SCHEMA_VERSION = 2
CANONICAL_RESEARCH_CORPUS_STORAGE_TYPE = "research_corpus_storage"
SUPPORTED_RESEARCH_CORPUS_STORAGE_SCHEMA_VERSIONS = (1, RESEARCH_CORPUS_STORAGE_SCHEMA_VERSION)
PATTERN_STORE_SCHEMA_VERSION = 1
CANONICAL_PATTERN_STORE_TYPE = "normalized_pattern_store"
CANONICAL_PATTERN_PROJECTION_KINDS = ("tactic", "structure", "heuristic")
CANONICAL_RESEARCH_ENTRY_TYPES = (
    "pattern_observation",
    "case_study",
    "meta_learning_rule",
    "preference_signal",
    "mutation_hypothesis",
)
CANONICAL_RESEARCH_SOURCE_KINDS = (
    "reference_skill",
    "design_doc",
    "best_practice",
    "article",
    "repo",
    "meta_learning",
    "preference_log",
    "prior_campaign",
    "repository",
    "evaluation_result_store",
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
CANONICAL_CONFIDENCE_VALUES = ("high", "medium", "low")
CANONICAL_STATUS_VALUES = ("candidate", "active", "superseded", "rejected")
CANONICAL_PATTERN_TRANSFER_TYPES = ("positive_pattern", "anti_pattern", "heuristic")
CANONICAL_PATTERN_OBJECT_SCHEMA_VERSION = 1
CANONICAL_PATTERN_EVIDENCE_REFERENCE_SCHEMA_VERSION = 1
PATTERN_EVIDENCE_LOOKUP_SCHEMA_VERSION = 1
CANONICAL_PATTERN_EVIDENCE_LOOKUP_TYPE = "resolved_pattern_evidence_lookup"
CANONICAL_PATTERN_EVIDENCE_LOOKUP_STATUSES = ("resolved", "unresolved")
CANONICAL_PATTERN_EVIDENCE_LOOKUP_STRATEGIES = (
    "span",
    "section_quote",
    "document_quote",
    "section",
    "unresolved",
)
CANONICAL_PATTERN_TYPE_FIELDS = (
    "pattern_type_tactic",
    "pattern_type_structure",
    "pattern_type_heuristic",
)
CANONICAL_PATTERN_NORMALIZATION_SCHEMA_VERSION = 1
PATTERN_STORE_PROVENANCE_INDEX_FIELDS = (
    "source_entry_id",
    "source_id",
    "canonical_location",
    "retrieval_id",
    "research_artifact_ref",
    "raw_artifact_ref",
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_PATTERN_PROJECTION_KIND_BY_PREFIX = {
    "tp": "tactic",
    "sp": "structure",
    "hp": "heuristic",
}
_PATTERN_PROVENANCE_INDEX_TO_RECORD_FIELD = {
    "source_entry_id": "source_entry_ids",
    "source_id": "source_ids",
    "canonical_location": "canonical_locations",
    "retrieval_id": "retrieval_ids",
    "research_artifact_ref": "research_artifact_refs",
    "raw_artifact_ref": "raw_artifact_refs",
}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "after",
    "as",
    "at",
    "be",
    "before",
    "by",
    "do",
    "each",
    "for",
    "from",
    "help",
    "into",
    "is",
    "it",
    "keep",
    "of",
    "on",
    "or",
    "so",
    "that",
    "the",
    "their",
    "then",
    "to",
    "use",
    "when",
    "with",
}
_CANONICAL_PATTERN_PHRASE_ALIASES = (
    (
        re.compile(r"\b(?:explicit\s+)?completion\s+gates?\b"),
        "exitcondition",
        "phrase_alias:completion_gates->exitcondition",
    ),
    (
        re.compile(r"\b(?:explicit\s+)?exit\s+conditions?\b"),
        "exitcondition",
        "phrase_alias:exit_conditions->exitcondition",
    ),
    (
        re.compile(r"\b(?:completion|acceptance|exit)\s+criteria\b"),
        "exitcondition",
        "phrase_alias:exit_criteria->exitcondition",
    ),
    (
        re.compile(r"\bweak\s+(?:coding\s+)?agents?\b"),
        "weakagent",
        "phrase_alias:weak_agents->weakagent",
    ),
    (
        re.compile(r"\bon\s+track\b"),
        "reducedrift",
        "phrase_alias:on_track->reducedrift",
    ),
    (
        re.compile(r"\b(?:reduce|prevent|avoid)\s+drift\b"),
        "reducedrift",
        "phrase_alias:drift_control->reducedrift",
    ),
    (
        re.compile(r"\bnumbered\s+(?:steps?|phases?)\b"),
        "numberedstep",
        "phrase_alias:numbered_steps->numberedstep",
    ),
)
_CANONICAL_PATTERN_TOKEN_ALIASES = {
    "conditions": "condition",
    "criteria": "condition",
    "criterion": "condition",
    "agents": "agent",
    "phases": "phase",
    "steps": "step",
}
_CANONICAL_PATTERN_SLOT_TERMS = {
    "mechanism_terms": {"exitcondition", "verificationgate", "rollbacknote", "checkpoint"},
    "outcome_terms": {"reducedrift", "improvereliability", "lowerverbosity"},
    "agent_terms": {"weakagent", "rovodev", "claudecode", "anyskillmd"},
    "context_terms": {"numberedstep", "pipeline", "phase"},
}
_CANONICAL_PATTERN_LABEL_ALIASES = {
    "completion_gate": "explicit_exit_conditions",
    "completion_gates": "explicit_exit_conditions",
    "explicit_completion_gate": "explicit_exit_conditions",
    "explicit_completion_gates": "explicit_exit_conditions",
    "exit_condition": "explicit_exit_conditions",
    "exit_conditions": "explicit_exit_conditions",
    "explicit_exit_condition": "explicit_exit_conditions",
    "explicit_exit_conditions": "explicit_exit_conditions",
    "exit_criteria": "explicit_exit_conditions",
    "completion_criteria": "explicit_exit_conditions",
}
_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
_STATUS_RANK = {"rejected": 0, "superseded": 1, "candidate": 2, "active": 3}
_SOURCE_KIND_RANK = {
    "reference_skill": 6,
    "best_practice": 5,
    "design_doc": 4,
    "article": 4,
    "meta_learning": 4,
    "prior_campaign": 3,
    "evaluation_result_store": 3,
    "repo": 2,
    "repository": 2,
    "preference_log": 1,
}
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
_RESEARCH_CORPUS_REQUIRED_ENTRY_FIELDS = (
    "entry_id",
    "entry_type",
    "title",
    "summary",
    "source_kind",
    "source_ref",
    "retrieval_context",
    "captured_at",
    "captured_by",
    "source_timestamps",
    "applicability",
    "evidence",
    "confidence",
    "status",
    "derived_from_entry_ids",
    "traceability",
    "type_payload",
)


class ResearchCorpusValidationError(ValueError):
    """Validation failure for normalized research corpus assembly."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


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


def _normalize_iso_timestamp(value: Any, *, field_name: str, default: str | None = None) -> str:
    normalized = _clean_text(value, default=default or "")
    if not normalized:
        raise ValueError(f"{field_name} requires a non-empty ISO timestamp")

    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} requires a valid ISO timestamp") from exc

    return normalized


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


def _coerce_numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    normalized = _clean_text(value)
    if not normalized:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


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


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


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
        allowed_values=CANONICAL_CONFIDENCE_VALUES,
    )
    normalized_metadata["source_confidence"] = _normalize_allowed_value(
        normalized_metadata.get("source_confidence"),
        field_name=f"{field_name}.source_confidence",
        allowed_values=CANONICAL_CONFIDENCE_VALUES,
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
        allowed_values=CANONICAL_CONFIDENCE_VALUES,
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


def _normalize_preference_signal_payload(raw_payload: Any) -> dict[str, Any]:
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
    return _normalize_preference_signal_payload(payload)


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


def _json_key(value: Any) -> str:
    return json.dumps(_clone_json_value(value), sort_keys=True, ensure_ascii=True)


def _normalize_target_context(target_context: Mapping[str, Any] | None) -> dict[str, Any]:
    if target_context is None:
        return {}
    if not isinstance(target_context, Mapping):
        raise TypeError("target_context must be a mapping when provided")

    normalized: dict[str, Any] = {}
    for key in ("skill_pattern", "agent_target", "scenario_target", "scope_type", "scope_ref"):
        value = _clean_text(target_context.get(key))
        if value:
            normalized[key] = value

    skill_metadata = target_context.get("skill_metadata")
    if isinstance(skill_metadata, Mapping):
        normalized["skill_metadata"] = _clone_json_value(skill_metadata)

    objective = _clean_text(target_context.get("objective"))
    if objective:
        normalized["objective"] = objective

    optional_text_fields = {
        "selected_eval_strategy_id": target_context.get("selected_eval_strategy_id"),
        "analysis_goal": target_context.get("analysis_goal"),
        "target_section": target_context.get("target_section"),
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
            normalized[field_name] = normalized_value

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
        normalized_values = _normalize_string_list(raw_value, default=[])
        if normalized_values:
            normalized[field_name] = normalized_values

    scoring_context = build_target_skill_scoring_context(
        {
            **dict(target_context),
            "skill_metadata": normalized.get("skill_metadata", target_context.get("skill_metadata")),
            "objective": objective or target_context.get("objective"),
        }
    )
    if scoring_context:
        normalized["scoring_context"] = scoring_context

    return normalized


def _default_applicability(
    *,
    target_context: Mapping[str, Any],
    default_scope_type: str,
    default_scope_ref: str,
) -> dict[str, Any]:
    skill_pattern = _clean_text(target_context.get("skill_pattern"))
    agent_target = _clean_text(target_context.get("agent_target"), default="any_skill_md")
    scenario_target = _clean_text(target_context.get("scenario_target"), default="individual")
    return {
        "skill_patterns": [skill_pattern] if skill_pattern else [],
        "agent_targets": [agent_target] if agent_target else [],
        "scenario_targets": [scenario_target] if scenario_target else [],
        "scope_type": default_scope_type,
        "scope_ref": default_scope_ref,
    }


def _normalize_applicability(
    raw_applicability: Any,
    *,
    target_context: Mapping[str, Any],
    default_scope_type: str,
    default_scope_ref: str,
) -> dict[str, Any]:
    base = _default_applicability(
        target_context=target_context,
        default_scope_type=default_scope_type,
        default_scope_ref=default_scope_ref,
    )
    if raw_applicability is None:
        return base
    if not isinstance(raw_applicability, Mapping):
        raise TypeError("applicability must be a mapping when provided")

    normalized = dict(base)
    normalized["skill_patterns"] = _normalize_string_list(
        raw_applicability.get("skill_patterns"),
        default=base["skill_patterns"],
    )
    normalized["agent_targets"] = _normalize_string_list(
        raw_applicability.get("agent_targets"),
        default=base["agent_targets"],
    )
    normalized["scenario_targets"] = _normalize_string_list(
        raw_applicability.get("scenario_targets"),
        default=base["scenario_targets"],
    )
    normalized["scope_type"] = _clean_text(
        raw_applicability.get("scope_type"),
        default=base["scope_type"],
    )
    normalized["scope_ref"] = _clean_text(
        raw_applicability.get("scope_ref"),
        default=base["scope_ref"],
    )
    return normalized


def _normalize_evidence(raw_evidence: Any) -> list[dict[str, Any]]:
    if raw_evidence is None:
        return []
    if not isinstance(raw_evidence, list):
        raise TypeError("evidence must be a list when provided")

    normalized: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_evidence):
        if not isinstance(raw_item, Mapping):
            raise TypeError(f"evidence[{index}] must be a mapping")

        item = {
            "kind": _clean_text(raw_item.get("kind"), default="source_excerpt") or "source_excerpt",
            "source": _clean_text(raw_item.get("source"), default="unknown") or "unknown",
            "locator": _clean_text(raw_item.get("locator"), default=f"evidence[{index}]"),
        }
        excerpt = _clean_text(raw_item.get("excerpt"))
        if excerpt:
            item["excerpt"] = excerpt
        metric = raw_item.get("metric")
        if metric is not None:
            item["metric"] = _clone_json_value(metric)
        artifact_ref = raw_item.get("artifact_ref")
        if artifact_ref is not None:
            item["artifact_ref"] = _clone_json_value(artifact_ref)
        normalized.append(item)

    return normalized


def _normalize_source_ref(
    raw_source_ref: Any,
    *,
    default_source_id: str,
    default_location: str,
    default_canonical_location: str,
    default_locator: str,
    default_artifact_kind: str,
    default_display_name: str,
    default_content_hash: str,
    default_accessed_at: str,
) -> dict[str, Any]:
    source_ref = dict(raw_source_ref) if isinstance(raw_source_ref, Mapping) else {}

    source_id = _clean_text(source_ref.get("source_id"), default=default_source_id)
    if not source_id:
        raise ValueError("source_ref.source_id is required")

    location = _clean_text(source_ref.get("location"), default=default_location)
    canonical_location = _clean_text(
        source_ref.get("canonical_location"),
        default=default_canonical_location or location,
    )
    locator = _clean_text(source_ref.get("locator"), default=default_locator)
    artifact_kind = _clean_text(
        source_ref.get("artifact_kind"),
        default=default_artifact_kind,
    )
    display_name = _clean_text(
        source_ref.get("display_name"),
        default=default_display_name,
    )
    content_hash = _clean_text(
        source_ref.get("content_hash"),
        default=default_content_hash,
    )

    citation_metadata = (
        dict(source_ref.get("citation_metadata"))
        if isinstance(source_ref.get("citation_metadata"), Mapping)
        else {}
    )
    normalized_citation_metadata = {
        "title": _clean_text(citation_metadata.get("title"), default=display_name or source_id) or source_id,
        "author_or_org": _clean_text(citation_metadata.get("author_or_org")) or "unknown",
        "published_at": citation_metadata.get("published_at"),
        "publication_or_site": _clean_text(citation_metadata.get("publication_or_site")) or "unknown",
        "canonical_url": citation_metadata.get("canonical_url"),
        "accessed_at": _normalize_iso_timestamp(
            citation_metadata.get("accessed_at"),
            field_name="source_ref.citation_metadata.accessed_at",
            default=default_accessed_at,
        ),
    }

    return {
        "source_id": source_id,
        "location": location or canonical_location,
        "canonical_location": canonical_location or location,
        "locator": locator or default_locator,
        "artifact_kind": artifact_kind or default_artifact_kind,
        "display_name": display_name or source_id,
        "content_hash": content_hash or default_content_hash,
        "citation_metadata": normalized_citation_metadata,
    }


def _normalize_retrieval_context(
    raw_retrieval_context: Any,
    *,
    default_retrieval_id: str,
    default_stage: str,
    default_run_path: str,
    default_analysis_goal: str,
    default_retrieved_via: str,
    default_selection_basis: str,
) -> dict[str, Any]:
    retrieval_context = dict(raw_retrieval_context) if isinstance(raw_retrieval_context, Mapping) else {}
    return {
        "retrieval_id": _clean_text(
            retrieval_context.get("retrieval_id"),
            default=default_retrieval_id,
        ) or default_retrieval_id,
        "stage": _clean_text(retrieval_context.get("stage"), default=default_stage) or default_stage,
        "run_path": _clean_text(retrieval_context.get("run_path"), default=default_run_path) or default_run_path,
        "analysis_goal": _clean_text(
            retrieval_context.get("analysis_goal"),
            default=default_analysis_goal,
        ) or default_analysis_goal,
        "retrieved_via": _clean_text(
            retrieval_context.get("retrieved_via"),
            default=default_retrieved_via,
        ) or default_retrieved_via,
        "selection_basis": _clean_text(
            retrieval_context.get("selection_basis"),
            default=default_selection_basis,
        ) or default_selection_basis,
    }


def _normalize_source_timestamps(
    raw_source_timestamps: Any,
    *,
    default_timestamp: str,
) -> dict[str, Any]:
    source_timestamps = dict(raw_source_timestamps) if isinstance(raw_source_timestamps, Mapping) else {}
    return {
        "retrieval_started_at": _normalize_iso_timestamp(
            source_timestamps.get("retrieval_started_at"),
            field_name="source_timestamps.retrieval_started_at",
            default=default_timestamp,
        ),
        "retrieval_completed_at": _normalize_iso_timestamp(
            source_timestamps.get("retrieval_completed_at"),
            field_name="source_timestamps.retrieval_completed_at",
            default=default_timestamp,
        ),
        "retrieved_at": _normalize_iso_timestamp(
            source_timestamps.get("retrieved_at"),
            field_name="source_timestamps.retrieved_at",
            default=default_timestamp,
        ),
        "source_observed_at": _normalize_iso_timestamp(
            source_timestamps.get("source_observed_at"),
            field_name="source_timestamps.source_observed_at",
            default=default_timestamp,
        ),
        "source_last_modified_at": source_timestamps.get("source_last_modified_at"),
    }


def _normalize_traceability(
    raw_traceability: Any,
    *,
    research_artifact_ref: str,
    raw_artifact_refs: list[str],
    session_log_refs: list[str],
    evidence_count: int,
    lineage_parent_ids: list[str],
    normalization_note: str,
) -> dict[str, Any]:
    traceability = _clone_json_value(raw_traceability) if isinstance(raw_traceability, Mapping) else {}
    traceability["research_artifact_ref"] = _clean_text(
        traceability.get("research_artifact_ref"),
        default=research_artifact_ref,
    ) or research_artifact_ref
    traceability["raw_artifact_refs"] = _normalize_string_list(
        traceability.get("raw_artifact_refs"),
        default=raw_artifact_refs,
    )
    traceability["session_log_refs"] = _normalize_string_list(
        traceability.get("session_log_refs"),
        default=session_log_refs,
    )
    evidence_refs = traceability.get("evidence_refs")
    if isinstance(evidence_refs, list) and all(isinstance(item, int) for item in evidence_refs):
        traceability["evidence_refs"] = sorted(dict.fromkeys(evidence_refs))
    else:
        traceability["evidence_refs"] = list(range(evidence_count))
    traceability["lineage_parent_ids"] = _normalize_string_list(
        traceability.get("lineage_parent_ids"),
        default=lineage_parent_ids,
    )
    traceability["normalization_note"] = _clean_text(
        traceability.get("normalization_note"),
        default=normalization_note,
    ) or normalization_note
    return traceability


def _normalize_required_traceability(
    raw_traceability: Any,
    *,
    field_name: str,
    evidence_count: int,
) -> dict[str, Any]:
    traceability = _normalize_required_mapping(
        raw_traceability,
        field_name=field_name,
    )

    research_artifact_ref = _clean_text(traceability.get("research_artifact_ref"))
    if not research_artifact_ref:
        raise ValueError(f"{field_name}.research_artifact_ref is required")
    traceability["research_artifact_ref"] = research_artifact_ref

    raw_artifact_refs = traceability.get("raw_artifact_refs")
    if not isinstance(raw_artifact_refs, (list, tuple)):
        raise ValueError(
            f"{field_name}.raw_artifact_refs must contain at least one non-empty string"
        )
    normalized_raw_artifact_refs = _normalize_string_list(raw_artifact_refs)
    if not normalized_raw_artifact_refs:
        raise ValueError(
            f"{field_name}.raw_artifact_refs must contain at least one non-empty string"
        )
    traceability["raw_artifact_refs"] = normalized_raw_artifact_refs

    traceability["session_log_refs"] = _normalize_string_list(
        traceability.get("session_log_refs"),
        default=[],
    )

    raw_evidence_refs = traceability.get("evidence_refs")
    if not isinstance(raw_evidence_refs, list) or not raw_evidence_refs:
        raise ValueError(
            f"{field_name}.evidence_refs must contain at least one integer"
        )

    normalized_evidence_refs: list[int] = []
    for index, raw_evidence_ref in enumerate(raw_evidence_refs):
        if isinstance(raw_evidence_ref, bool) or not isinstance(raw_evidence_ref, int):
            raise ValueError(
                f"{field_name}.evidence_refs[{index}] must be an integer"
            )
        if raw_evidence_ref < 0 or raw_evidence_ref >= evidence_count:
            raise ValueError(
                f"{field_name}.evidence_refs[{index}] must reference an existing evidence index"
            )
        if raw_evidence_ref not in normalized_evidence_refs:
            normalized_evidence_refs.append(raw_evidence_ref)
    traceability["evidence_refs"] = normalized_evidence_refs

    traceability["lineage_parent_ids"] = _normalize_string_list(
        traceability.get("lineage_parent_ids"),
        default=[],
    )

    normalization_note = _clean_text(traceability.get("normalization_note"))
    if normalization_note:
        traceability["normalization_note"] = normalization_note
    elif "normalization_note" in traceability:
        traceability["normalization_note"] = ""

    return traceability


def _normalize_pattern_evidence_reference(
    raw_reference: Any,
    *,
    source_ref: Mapping[str, Any] | None,
    retrieval_context: Mapping[str, Any] | None,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    reference = dict(raw_reference) if isinstance(raw_reference, Mapping) else {}
    source_ref_mapping = source_ref if isinstance(source_ref, Mapping) else {}
    retrieval_context_mapping = retrieval_context if isinstance(retrieval_context, Mapping) else {}
    primary_evidence = evidence[0] if evidence and isinstance(evidence[0], Mapping) else {}

    source_location_mapping = (
        dict(reference.get("source_location"))
        if isinstance(reference.get("source_location"), Mapping)
        else {}
    )
    quote = _clean_text(
        reference.get("quote"),
        default=_clean_text(
            reference.get("excerpt"),
            default=_clean_text(primary_evidence.get("excerpt")),
        ),
    )
    source_hash = _clean_text(
        reference.get("source_hash"),
        default=_clean_text(source_ref_mapping.get("content_hash"), default="unknown"),
    ) or "unknown"

    span_mapping = dict(reference.get("span")) if isinstance(reference.get("span"), Mapping) else {}
    span = {
        "line_start": _coerce_optional_int(
            span_mapping.get("line_start", source_location_mapping.get("line_start")),
            field_name="pattern_observation.evidence_reference.span.line_start",
        ),
        "line_end": _coerce_optional_int(
            span_mapping.get("line_end", source_location_mapping.get("line_end")),
            field_name="pattern_observation.evidence_reference.span.line_end",
        ),
        "char_start": _coerce_optional_int(
            span_mapping.get("char_start", source_location_mapping.get("char_start")),
            field_name="pattern_observation.evidence_reference.span.char_start",
        ),
        "char_end": _coerce_optional_int(
            span_mapping.get("char_end", source_location_mapping.get("char_end")),
            field_name="pattern_observation.evidence_reference.span.char_end",
        ),
        "byte_start": _coerce_optional_int(
            span_mapping.get("byte_start", source_location_mapping.get("byte_start")),
            field_name="pattern_observation.evidence_reference.span.byte_start",
        ),
        "byte_end": _coerce_optional_int(
            span_mapping.get("byte_end", source_location_mapping.get("byte_end")),
            field_name="pattern_observation.evidence_reference.span.byte_end",
        ),
    }
    has_span = any(value is not None for value in span.values())
    offset_basis = _clean_text(
        span_mapping.get("offset_basis", source_location_mapping.get("offset_basis")),
        default="normalized_text_utf8" if has_span else "unknown",
    ) or ("normalized_text_utf8" if has_span else "unknown")

    if not quote and not has_span:
        raise ValueError(
            "pattern_observation.evidence_reference requires a quote or a span"
        )

    return {
        "schema_version": CANONICAL_PATTERN_EVIDENCE_REFERENCE_SCHEMA_VERSION,
        "source_hash": source_hash,
        "source_location": {
            "locator": _clean_text(
                source_location_mapping.get("locator", reference.get("locator")),
                default=_clean_text(
                    primary_evidence.get("locator"),
                    default=_clean_text(source_ref_mapping.get("locator"), default="unknown"),
                ),
            )
            or "unknown",
            "section_id": _clean_text(
                source_location_mapping.get("section_id", reference.get("section_id"))
            )
            or None,
            "heading_path": _normalize_string_list(
                source_location_mapping.get("heading_path", reference.get("heading_path")),
                default=[],
            ),
        },
        "quote": quote or None,
        "span": {
            **span,
            "offset_basis": offset_basis,
        }
        if has_span
        else None,
        "retrieval_fingerprint": _clean_text(
            reference.get("retrieval_fingerprint"),
            default="",
        )
        or (
            _clean_text(retrieval_context_mapping.get("retrieval_id"))
            if reference.get("retrieval_fingerprint") is not None
            else None
        ),
    }


def _normalize_pattern_payload(
    raw_payload: Any,
    *,
    title: str,
    summary: str,
    analysis_goal: str,
    source_ref: Mapping[str, Any] | None = None,
    retrieval_context: Mapping[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
    pattern_mapping = payload.get("pattern")
    if not isinstance(pattern_mapping, Mapping):
        pattern_mapping = {}
    normalized_evidence = list(evidence or [])
    canonical_pattern_fields = {
        "pattern_label",
        "pattern_statement",
        "transfer_type",
        "applicability_reason",
        "mutation_leverage",
        "evidence_reference",
        "canonical_pattern",
        "canonical_form",
        *CANONICAL_PATTERN_TYPE_FIELDS,
    }
    preserved_payload_fields = {
        str(key): _clone_json_value(value)
        for key, value in payload.items()
        if str(key) not in canonical_pattern_fields and str(key) != "pattern"
    }
    preserved_nested_pattern_fields = {
        str(key): _clone_json_value(value)
        for key, value in pattern_mapping.items()
        if str(key) not in canonical_pattern_fields and str(key) != "schema_version"
    }

    transfer_type = _clean_text(
        payload.get("transfer_type"),
        default=_clean_text(pattern_mapping.get("transfer_type"), default="positive_pattern"),
    )
    if transfer_type not in CANONICAL_PATTERN_TRANSFER_TYPES:
        transfer_type = "positive_pattern"

    pattern_label = _clean_identifier(
        payload.get("pattern_label"),
        default=_clean_identifier(
            pattern_mapping.get("pattern_label"),
            default=_clean_identifier(title) or "pattern_observation",
        )
        or "pattern_observation",
    )
    pattern_statement = _clean_text(
        payload.get("pattern_statement"),
        default=_clean_text(
            pattern_mapping.get("pattern_statement"),
            default=summary or title,
        )
        or title,
    ) or title
    applicability_reason = _clean_text(
        payload.get("applicability_reason"),
        default=_clean_text(
            pattern_mapping.get("applicability_reason"),
            default=summary or title,
        )
        or title,
    ) or title
    mutation_leverage = _clean_text(
        payload.get("mutation_leverage"),
        default=_clean_text(
            pattern_mapping.get("mutation_leverage"),
            default=analysis_goal or "Use the donor pattern as mutation inspiration.",
        )
        or "Use the donor pattern as mutation inspiration.",
    ) or "Use the donor pattern as mutation inspiration."

    pattern_types: dict[str, str] = {}
    for field_name in CANONICAL_PATTERN_TYPE_FIELDS:
        pattern_type = _clean_text(
            payload.get(field_name),
            default=_clean_text(
                pattern_mapping.get(field_name),
                default=transfer_type,
            ),
        )
        if pattern_type not in CANONICAL_PATTERN_TRANSFER_TYPES:
            pattern_type = transfer_type
        pattern_types[field_name] = pattern_type

    evidence_reference = _normalize_pattern_evidence_reference(
        payload.get("evidence_reference", pattern_mapping.get("evidence_reference")),
        source_ref=source_ref,
        retrieval_context=retrieval_context,
        evidence=normalized_evidence,
    )
    canonical_pattern = _build_canonical_pattern_form(
        source_pattern_label=pattern_label,
        pattern_statement=pattern_statement,
        applicability_reason=applicability_reason,
        mutation_leverage=mutation_leverage,
    )
    pattern_label = canonical_pattern["canonical_label"] or pattern_label

    normalized_nested_pattern = {
        **preserved_nested_pattern_fields,
        "schema_version": CANONICAL_PATTERN_OBJECT_SCHEMA_VERSION,
        "pattern_label": pattern_label or "pattern_observation",
        "pattern_statement": pattern_statement,
        "transfer_type": transfer_type,
        "applicability_reason": applicability_reason,
        "mutation_leverage": mutation_leverage,
        "evidence_reference": _clone_json_value(evidence_reference),
        "canonical_form": _clone_json_value(canonical_pattern),
        **pattern_types,
    }

    return {
        **preserved_payload_fields,
        "pattern_label": pattern_label or "pattern_observation",
        "pattern_statement": pattern_statement,
        "transfer_type": transfer_type,
        "applicability_reason": applicability_reason,
        "mutation_leverage": mutation_leverage,
        "evidence_reference": evidence_reference,
        "canonical_pattern": canonical_pattern,
        **pattern_types,
        "pattern": normalized_nested_pattern,
    }


def _lookup_optional_int(value: Any) -> int | None:
    try:
        return _coerce_optional_int(value, field_name="pattern_evidence_lookup")
    except ValueError:
        return None


def _line_start_offsets(text: str) -> list[int]:
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


def _normalize_locator_lookup_token(value: Any) -> str:
    normalized = _clean_text(value).lower()
    if not normalized:
        return ""
    normalized = normalized.lstrip("#").strip()
    return normalized


def _resolve_char_span_from_line_numbers(
    text: str,
    *,
    line_start: int | None,
    line_end: int | None,
) -> tuple[int, int] | None:
    if not text or line_start is None:
        return None

    line_starts = _line_start_offsets(text)
    if not line_starts:
        return None

    bounded_start = max(1, min(line_start, len(line_starts)))
    bounded_end = max(bounded_start, min(line_end or bounded_start, len(line_starts)))
    char_start = line_starts[bounded_start - 1]
    char_end = line_starts[bounded_end] if bounded_end < len(line_starts) else len(text)
    if char_end <= char_start:
        return None
    return (char_start, char_end)


def _resolve_reference_char_span(
    evidence_reference: Mapping[str, Any],
    *,
    normalized_text: str,
) -> tuple[int, int] | None:
    span_mapping = (
        evidence_reference.get("span")
        if isinstance(evidence_reference.get("span"), Mapping)
        else {}
    )

    char_start = _lookup_optional_int(span_mapping.get("char_start"))
    char_end = _lookup_optional_int(span_mapping.get("char_end"))
    if (
        char_start is not None
        and char_end is not None
        and 0 <= char_start < char_end <= len(normalized_text)
    ):
        return (char_start, char_end)

    return _resolve_char_span_from_line_numbers(
        normalized_text,
        line_start=_lookup_optional_int(span_mapping.get("line_start")),
        line_end=_lookup_optional_int(span_mapping.get("line_end")),
    )


def _find_section_for_span(
    sections: list[Mapping[str, Any]],
    *,
    char_start: int,
    char_end: int,
) -> dict[str, Any] | None:
    for section in sections:
        section_start = _lookup_optional_int(section.get("char_start"))
        section_end = _lookup_optional_int(section.get("char_end"))
        if (
            section_start is not None
            and section_end is not None
            and char_start >= section_start
            and char_end <= section_end
        ):
            return _clone_json_value(section)
    return None


def _find_section_by_reference(
    sections: list[Mapping[str, Any]],
    *,
    evidence_reference: Mapping[str, Any],
) -> dict[str, Any] | None:
    source_location = (
        evidence_reference.get("source_location")
        if isinstance(evidence_reference.get("source_location"), Mapping)
        else {}
    )
    requested_section_id = _clean_text(source_location.get("section_id"))
    if requested_section_id:
        for section in sections:
            if _clean_text(section.get("section_id")) == requested_section_id:
                return _clone_json_value(section)

    heading_path = _normalize_string_list(source_location.get("heading_path"), default=[])
    requested_heading = heading_path[-1] if heading_path else ""
    if requested_heading:
        for section in sections:
            if _clean_text(section.get("heading")) == requested_heading:
                return _clone_json_value(section)

    locator_token = _normalize_locator_lookup_token(
        source_location.get("locator", evidence_reference.get("locator"))
    )
    if locator_token:
        for section in sections:
            candidate_tokens = {
                _normalize_locator_lookup_token(section.get("heading")),
                _normalize_locator_lookup_token(section.get("section_id")),
                _normalize_locator_lookup_token(
                    section.get("source_locator", {}).get("section_id")
                    if isinstance(section.get("source_locator"), Mapping)
                    else None
                ),
            }
            candidate_tokens.discard("")
            if locator_token in candidate_tokens:
                return _clone_json_value(section)

    return None


def _build_lookup_section_summary(section: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(section, Mapping):
        return None

    source_locator = (
        section.get("source_locator")
        if isinstance(section.get("source_locator"), Mapping)
        else {}
    )
    return {
        "section_id": _clean_text(section.get("section_id")) or None,
        "section_kind": _clean_text(section.get("section_kind")) or None,
        "heading": _clean_text(section.get("heading")) or None,
        "heading_level": _lookup_optional_int(section.get("heading_level")),
        "order": _lookup_optional_int(section.get("order")),
        "locator": _clean_text(source_locator.get("section_id"), default=section.get("section_id")) or None,
    }


def _build_lookup_result(
    *,
    evidence_reference: Mapping[str, Any],
    source_document: Mapping[str, Any],
    normalized_text: str,
    resolution_status: str,
    resolution_strategy: str,
    resolved_excerpt: str | None,
    resolved_char_start: int | None,
    resolved_char_end: int | None,
    resolved_section: Mapping[str, Any] | None,
) -> dict[str, Any]:
    document_mapping = (
        source_document.get("document")
        if isinstance(source_document.get("document"), Mapping)
        else {}
    )
    source_location = (
        evidence_reference.get("source_location")
        if isinstance(evidence_reference.get("source_location"), Mapping)
        else {}
    )
    requested_section_id = _clean_text(source_location.get("section_id"))
    reference_quote = _clean_text(evidence_reference.get("quote"))
    source_hash = _clean_text(evidence_reference.get("source_hash"))
    document_hash = _clean_text(document_mapping.get("content_hash"))
    source_hash_match = (
        source_hash == document_hash
        if source_hash and source_hash != "unknown" and document_hash
        else None
    )

    resolved_span = None
    if (
        resolved_char_start is not None
        and resolved_char_end is not None
        and 0 <= resolved_char_start < resolved_char_end <= len(normalized_text)
    ):
        line_starts = _line_start_offsets(normalized_text)
        resolved_span = {
            "line_start": _line_number_for_offset(line_starts, resolved_char_start),
            "line_end": _line_end_for_span(
                normalized_text,
                line_starts,
                resolved_char_start,
                resolved_char_end,
            ),
            "char_start": resolved_char_start,
            "char_end": resolved_char_end,
            "byte_start": _byte_offset(normalized_text, resolved_char_start),
            "byte_end": _byte_offset(normalized_text, resolved_char_end),
            "offset_basis": "normalized_text_utf8",
        }

    resolved_section_summary = _build_lookup_section_summary(resolved_section)
    section_id_match = (
        requested_section_id == resolved_section_summary.get("section_id")
        if requested_section_id and isinstance(resolved_section_summary, Mapping)
        else None
    )
    quote_match = (
        reference_quote in resolved_excerpt
        if reference_quote and resolved_excerpt
        else None
    )

    return {
        "schema_version": PATTERN_EVIDENCE_LOOKUP_SCHEMA_VERSION,
        "lookup_type": CANONICAL_PATTERN_EVIDENCE_LOOKUP_TYPE,
        "resolution_status": resolution_status,
        "resolution_strategy": resolution_strategy,
        "source_hash_match": source_hash_match,
        "section_id_match": section_id_match,
        "quote_match": quote_match,
        "resolved_excerpt": resolved_excerpt,
        "resolved_span": resolved_span,
        "resolved_section": resolved_section_summary,
        "source_document_ref": _clone_json_value(source_document.get("source_ref"))
        if isinstance(source_document.get("source_ref"), Mapping)
        else None,
        "evidence_reference": _clone_json_value(evidence_reference),
    }


def resolve_pattern_evidence_reference(
    evidence_reference: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve a stored pattern evidence reference back to its originating source snippet."""

    if not isinstance(evidence_reference, Mapping):
        raise TypeError("evidence_reference must be a mapping")
    if not isinstance(source_document, Mapping):
        raise TypeError("source_document must be a mapping")

    document_mapping = (
        source_document.get("document")
        if isinstance(source_document.get("document"), Mapping)
        else {}
    )
    normalized_text = _clean_text(document_mapping.get("normalized_text"))
    if not normalized_text:
        raise ValueError("source_document.document.normalized_text is required")

    sections = (
        source_document.get("sections")
        if isinstance(source_document.get("sections"), list)
        else []
    )
    normalized_sections = [
        _clone_json_value(section)
        for section in sections
        if isinstance(section, Mapping)
    ]

    requested_quote = _clean_text(evidence_reference.get("quote"))
    resolved_span = _resolve_reference_char_span(
        evidence_reference,
        normalized_text=normalized_text,
    )
    if resolved_span is not None:
        char_start, char_end = resolved_span
        excerpt = normalized_text[char_start:char_end].rstrip("\n")
        containing_section = _find_section_for_span(
            normalized_sections,
            char_start=char_start,
            char_end=char_end,
        )
        return _build_lookup_result(
            evidence_reference=evidence_reference,
            source_document=source_document,
            normalized_text=normalized_text,
            resolution_status="resolved",
            resolution_strategy="span",
            resolved_excerpt=excerpt or None,
            resolved_char_start=char_start,
            resolved_char_end=char_end,
            resolved_section=containing_section,
        )

    referenced_section = _find_section_by_reference(
        normalized_sections,
        evidence_reference=evidence_reference,
    )
    if referenced_section is not None:
        section_start = _lookup_optional_int(referenced_section.get("char_start"))
        section_end = _lookup_optional_int(referenced_section.get("char_end"))
        section_text = _clean_text(referenced_section.get("text"), default="")
        if requested_quote and section_text:
            relative_start = section_text.find(requested_quote)
            if relative_start >= 0 and section_start is not None:
                char_start = section_start + relative_start
                char_end = char_start + len(requested_quote)
                return _build_lookup_result(
                    evidence_reference=evidence_reference,
                    source_document=source_document,
                    normalized_text=normalized_text,
                    resolution_status="resolved",
                    resolution_strategy="section_quote",
                    resolved_excerpt=requested_quote,
                    resolved_char_start=char_start,
                    resolved_char_end=char_end,
                    resolved_section=referenced_section,
                )

        if (
            section_text
            and section_start is not None
            and section_end is not None
            and section_end > section_start
        ):
            return _build_lookup_result(
                evidence_reference=evidence_reference,
                source_document=source_document,
                normalized_text=normalized_text,
                resolution_status="resolved",
                resolution_strategy="section",
                resolved_excerpt=section_text.rstrip("\n") or None,
                resolved_char_start=section_start,
                resolved_char_end=section_end,
                resolved_section=referenced_section,
            )

    if requested_quote:
        char_start = normalized_text.find(requested_quote)
        if char_start >= 0:
            char_end = char_start + len(requested_quote)
            containing_section = _find_section_for_span(
                normalized_sections,
                char_start=char_start,
                char_end=char_end,
            )
            return _build_lookup_result(
                evidence_reference=evidence_reference,
                source_document=source_document,
                normalized_text=normalized_text,
                resolution_status="resolved",
                resolution_strategy="document_quote",
                resolved_excerpt=requested_quote,
                resolved_char_start=char_start,
                resolved_char_end=char_end,
                resolved_section=containing_section,
            )

    return _build_lookup_result(
        evidence_reference=evidence_reference,
        source_document=source_document,
        normalized_text=normalized_text,
        resolution_status="unresolved",
        resolution_strategy="unresolved",
        resolved_excerpt=None,
        resolved_char_start=None,
        resolved_char_end=None,
        resolved_section=referenced_section,
    )


def resolve_pattern_entry_source_context(
    entry: Mapping[str, Any],
    source_document: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve the primary evidence reference for a normalized pattern entry."""

    if not isinstance(entry, Mapping):
        raise TypeError("entry must be a mapping")

    type_payload = (
        entry.get("type_payload")
        if isinstance(entry.get("type_payload"), Mapping)
        else {}
    )
    nested_pattern = (
        type_payload.get("pattern")
        if isinstance(type_payload.get("pattern"), Mapping)
        else {}
    )
    evidence_reference = (
        type_payload.get("evidence_reference", nested_pattern.get("evidence_reference"))
        if isinstance(
            type_payload.get("evidence_reference", nested_pattern.get("evidence_reference")),
            Mapping,
        )
        else None
    )
    if evidence_reference is None:
        raise ValueError("entry.type_payload.evidence_reference is required")

    resolved_lookup = resolve_pattern_evidence_reference(
        evidence_reference,
        source_document,
    )
    return {
        **resolved_lookup,
        "entry_id": _clean_text(entry.get("entry_id")) or None,
        "entry_type": _clean_text(entry.get("entry_type")) or None,
        "pattern_label": _clean_text(
            type_payload.get(
                "pattern_label",
                nested_pattern.get("pattern_label"),
            )
        )
        or None,
        "pattern_statement": _clean_text(
            type_payload.get(
                "pattern_statement",
                nested_pattern.get("pattern_statement"),
            )
        )
        or None,
    }


def _normalize_case_study_payload(
    raw_payload: Any,
    *,
    record_id: str,
    skill_id: str,
    version_label: str | None,
    source_results_ref: str | None,
) -> dict[str, Any]:
    payload = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
    normalized_payload = {
        "campaign_ref": _clean_text(
            payload.get("campaign_ref"),
            default=source_results_ref or record_id,
        ) or record_id,
        "skill_id": _clean_text(payload.get("skill_id"), default=skill_id) or skill_id,
        "version_before": _clean_text(payload.get("version_before")),
        "version_after": _clean_text(
            payload.get("version_after"),
            default=version_label or "",
        ) or "",
        "same_input_set_verified": _coerce_bool(
            payload.get("same_input_set_verified"),
            default=False,
        ),
        "observed_delta": _clone_json_value(payload.get("observed_delta")),
        "takeaway": _clean_text(payload.get("takeaway")),
    }
    if not normalized_payload["version_before"] or not normalized_payload["version_after"]:
        raise ValueError("case_study payload requires version_before and version_after")
    if not normalized_payload["takeaway"]:
        raise ValueError("case_study payload requires takeaway")
    return normalized_payload


def _collect_pattern_semantic_terms(*values: str) -> tuple[list[str], list[str]]:
    semantic_terms: list[str] = []
    applied_rules: list[str] = []

    for raw_value in values:
        normalized = _clean_text(raw_value).lower().replace("_", " ").replace("-", " ")
        if not normalized:
            continue

        for pattern, replacement, rule_id in _CANONICAL_PATTERN_PHRASE_ALIASES:
            if pattern.search(normalized):
                normalized = pattern.sub(f" {replacement} ", normalized)
                if rule_id not in applied_rules:
                    applied_rules.append(rule_id)

        for raw_token in _TOKEN_PATTERN.findall(normalized):
            if raw_token in _STOPWORDS:
                continue

            token = raw_token
            if token.endswith("ies") and len(token) > 4:
                token = token[:-3] + "y"
            elif token.endswith("ing") and len(token) > 5:
                token = token[:-3]
            elif token.endswith("ed") and len(token) > 4:
                token = token[:-2]
            elif token.endswith("s") and len(token) > 4:
                token = token[:-1]

            canonical_token = _CANONICAL_PATTERN_TOKEN_ALIASES.get(token, token)
            if canonical_token != token:
                rule_id = f"token_alias:{token}->{canonical_token}"
                if rule_id not in applied_rules:
                    applied_rules.append(rule_id)
            token = canonical_token

            if token and token not in _STOPWORDS and token not in semantic_terms:
                semantic_terms.append(token)

    semantic_terms.sort()
    return semantic_terms, applied_rules


def _build_pattern_semantic_slots(semantic_terms: list[str]) -> dict[str, list[str]]:
    used_terms: set[str] = set()
    slots: dict[str, list[str]] = {}
    for slot_name, allowed_terms in _CANONICAL_PATTERN_SLOT_TERMS.items():
        matched_terms = [term for term in semantic_terms if term in allowed_terms]
        slots[slot_name] = matched_terms
        used_terms.update(matched_terms)

    slots["other_terms"] = [term for term in semantic_terms if term not in used_terms]
    return slots


def _derive_canonical_pattern_label(
    *,
    source_pattern_label: str,
    semantic_terms: list[str],
) -> str:
    normalized_source_label = _clean_identifier(source_pattern_label)
    aliased_label = _CANONICAL_PATTERN_LABEL_ALIASES.get(normalized_source_label)
    if aliased_label:
        return aliased_label

    if "exitcondition" in semantic_terms:
        return "explicit_exit_conditions"

    if normalized_source_label and normalized_source_label not in {"pattern", "pattern_observation"}:
        return normalized_source_label

    if semantic_terms:
        return "_".join(semantic_terms[:4])

    return "pattern_observation"


def _build_canonical_pattern_form(
    *,
    source_pattern_label: str,
    pattern_statement: str,
    applicability_reason: str,
    mutation_leverage: str,
) -> dict[str, Any]:
    semantic_terms, applied_rules = _collect_pattern_semantic_terms(
        source_pattern_label,
        pattern_statement,
        applicability_reason,
        mutation_leverage,
    )
    semantic_slots = _build_pattern_semantic_slots(semantic_terms)
    signature_terms = [
        *semantic_slots["mechanism_terms"],
        *semantic_slots["outcome_terms"],
        *semantic_slots["agent_terms"],
        *semantic_slots["context_terms"],
    ]
    if not signature_terms:
        signature_terms = list(semantic_terms)
    canonical_label = _derive_canonical_pattern_label(
        source_pattern_label=source_pattern_label,
        semantic_terms=semantic_terms,
    )
    return {
        "schema_version": CANONICAL_PATTERN_NORMALIZATION_SCHEMA_VERSION,
        "canonical_label": canonical_label,
        "semantic_signature": "|".join(signature_terms),
        "semantic_signature_terms": signature_terms,
        "semantic_terms": semantic_terms,
        "semantic_slots": semantic_slots,
        "source_pattern_label": _clean_identifier(source_pattern_label) or None,
        "normalization_rules_applied": applied_rules,
    }


def _semantic_token_set(value: str) -> set[str]:
    tokens, _ = _collect_pattern_semantic_terms(value)
    return set(tokens)


def _build_semantic_signature(entry: Mapping[str, Any]) -> dict[str, Any]:
    entry_type = _clean_text(entry.get("entry_type"))
    type_payload = entry.get("type_payload")
    if not isinstance(type_payload, Mapping):
        type_payload = {}

    if entry_type == "pattern_observation":
        canonical_pattern = (
            type_payload.get("canonical_pattern")
            if isinstance(type_payload.get("canonical_pattern"), Mapping)
            else {}
        )
        canonical_label = _clean_text(canonical_pattern.get("canonical_label"))
        semantic_terms = _normalize_string_list(
            canonical_pattern.get("semantic_signature_terms"),
            default=_normalize_string_list(canonical_pattern.get("semantic_terms"), default=[]),
        )
        semantic_signature = _clean_text(canonical_pattern.get("semantic_signature"))
        if canonical_label or semantic_signature or semantic_terms:
            return {
                "mode": "token_overlap",
                "canonical_label": canonical_label or "pattern_observation",
                "tokens": set(semantic_terms or _semantic_token_set(semantic_signature)),
                "threshold": 0.5,
                "minimum_intersection": 2,
            }

        semantic_text = " ".join(
            part
            for part in (
                _clean_text(entry.get("summary")),
                _clean_text(type_payload.get("pattern_statement")),
                _clean_text(type_payload.get("applicability_reason")),
            )
            if part
        )
        return {
            "mode": "token_overlap",
            "tokens": _semantic_token_set(semantic_text),
            "threshold": 0.6,
            "minimum_intersection": 4,
        }

    if entry_type == "case_study":
        return {
            "mode": "exact_key",
            "key": (
                _clean_text(type_payload.get("skill_id")),
                _clean_text(type_payload.get("version_before")),
                _clean_text(type_payload.get("version_after")),
                bool(type_payload.get("same_input_set_verified")),
            ),
        }

    if entry_type == "meta_learning_rule":
        return {
            "mode": "exact_key",
            "key": (
                _clean_text(type_payload.get("rule_statement")),
                _clean_text(entry.get("summary")),
            ),
        }

    if entry_type == "preference_signal":
        preference_key = _clean_text(type_payload.get("preference_key"))
        preference_value = _clean_text(type_payload.get("preference_value"))
        return {
            "mode": "exact_key",
            "key": (
                preference_key,
                preference_value,
                _clean_text(type_payload.get("preference_statement")),
                _json_key(type_payload.get("preference_scope")),
            ),
        }

    return {
        "mode": "exact_key",
        "key": (
            _clean_text(entry.get("title")),
            _clean_text(entry.get("summary")),
            _json_key(type_payload),
        ),
    }


def _semantic_signatures_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if left.get("mode") != right.get("mode"):
        return False
    if left.get("mode") == "exact_key":
        return left.get("key") == right.get("key")

    left_label = _clean_text(left.get("canonical_label"))
    right_label = _clean_text(right.get("canonical_label"))
    if left_label and right_label and left_label != right_label:
        return False

    left_tokens = set(left.get("tokens") or ())
    right_tokens = set(right.get("tokens") or ())
    if not left_tokens or not right_tokens:
        return False

    intersection_count = len(left_tokens & right_tokens)
    if intersection_count < min(
        int(left.get("minimum_intersection", 0)),
        int(right.get("minimum_intersection", 0)),
    ):
        return False

    similarity = intersection_count / len(left_tokens | right_tokens)
    return similarity >= max(
        float(left.get("threshold", 1.0)),
        float(right.get("threshold", 1.0)),
    )


def _generate_entry_id(
    *,
    entry_type: str,
    title: str,
    semantic_signature: Mapping[str, Any],
    default_source_id: str,
) -> str:
    prefix = {
        "pattern_observation": "rc-pattern",
        "case_study": "rc-case",
        "meta_learning_rule": "rc-meta",
        "preference_signal": "rc-preference",
        "mutation_hypothesis": "rc-hypothesis",
    }.get(entry_type, "rc-entry")
    slug = _clean_identifier(title, default=default_source_id) or default_source_id
    digest = hashlib.sha256(_json_key(semantic_signature).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{slug}-{digest}"


def _pattern_text_signature(value: Any) -> tuple[str, ...]:
    return tuple(sorted(_semantic_token_set(_clean_text(value))))


def _build_pattern_variant_signature(entry: Mapping[str, Any]) -> dict[str, Any]:
    type_payload = entry.get("type_payload")
    payload = type_payload if isinstance(type_payload, Mapping) else {}
    canonical_pattern = (
        payload.get("canonical_pattern")
        if isinstance(payload.get("canonical_pattern"), Mapping)
        else {}
    )
    transfer_type = _clean_text(payload.get("transfer_type"), default="positive_pattern") or "positive_pattern"
    pattern_label = (
        _clean_identifier(
            payload.get("pattern_label"),
            default=_clean_identifier(canonical_pattern.get("canonical_label"), default="pattern_observation")
            or "pattern_observation",
        )
        or "pattern_observation"
    )
    canonical_signature_terms = _normalize_string_list(
        canonical_pattern.get("semantic_signature_terms"),
        default=_normalize_string_list(canonical_pattern.get("semantic_terms"), default=[]),
    )
    canonical_signature = _clean_text(canonical_pattern.get("semantic_signature"))
    if not canonical_signature and canonical_signature_terms:
        canonical_signature = "|".join(canonical_signature_terms)

    return {
        "pattern_label": pattern_label,
        "transfer_type": transfer_type,
        "pattern_type_tactic": _clean_text(payload.get("pattern_type_tactic"), default=transfer_type) or transfer_type,
        "pattern_type_structure": _clean_text(payload.get("pattern_type_structure"), default=transfer_type) or transfer_type,
        "pattern_type_heuristic": _clean_text(payload.get("pattern_type_heuristic"), default=transfer_type) or transfer_type,
        "canonical_signature": canonical_signature,
        "pattern_statement": _pattern_text_signature(payload.get("pattern_statement")),
        "applicability_reason": _pattern_text_signature(payload.get("applicability_reason")),
        "mutation_leverage": _pattern_text_signature(payload.get("mutation_leverage")),
    }


def _build_pattern_variant_details(entry: Mapping[str, Any]) -> dict[str, Any]:
    type_payload = entry.get("type_payload")
    payload = type_payload if isinstance(type_payload, Mapping) else {}
    canonical_pattern = (
        payload.get("canonical_pattern")
        if isinstance(payload.get("canonical_pattern"), Mapping)
        else {}
    )
    return {
        "pattern_label": _clean_text(payload.get("pattern_label")),
        "transfer_type": _clean_text(payload.get("transfer_type")),
        "pattern_statement": _clean_text(payload.get("pattern_statement")),
        "applicability_reason": _clean_text(payload.get("applicability_reason")),
        "mutation_leverage": _clean_text(payload.get("mutation_leverage")),
        "pattern_type_tactic": _clean_text(payload.get("pattern_type_tactic")),
        "pattern_type_structure": _clean_text(payload.get("pattern_type_structure")),
        "pattern_type_heuristic": _clean_text(payload.get("pattern_type_heuristic")),
        "canonical_signature": _clean_text(canonical_pattern.get("semantic_signature")),
        "evidence_reference": _clone_json_value(payload.get("evidence_reference")),
    }


def _pattern_variant_diff_fields(
    left_signature: Mapping[str, Any],
    right_signature: Mapping[str, Any],
) -> list[str]:
    differing_fields: list[str] = []
    ordered_fields = (
        "pattern_label",
        "transfer_type",
        "pattern_type_tactic",
        "pattern_type_structure",
        "pattern_type_heuristic",
        "canonical_signature",
        "pattern_statement",
        "applicability_reason",
        "mutation_leverage",
    )
    for field_name in ordered_fields:
        if _json_key(left_signature.get(field_name)) != _json_key(right_signature.get(field_name)):
            differing_fields.append(field_name)
    return differing_fields


def _pattern_evidence_reference_rank(entry: Mapping[str, Any]) -> tuple[int, int, int]:
    type_payload = entry.get("type_payload")
    payload = type_payload if isinstance(type_payload, Mapping) else {}
    evidence_reference = (
        payload.get("evidence_reference")
        if isinstance(payload.get("evidence_reference"), Mapping)
        else {}
    )
    span = (
        evidence_reference.get("span")
        if isinstance(evidence_reference.get("span"), Mapping)
        else {}
    )
    has_span = int(any(value is not None for value in span.values()))
    has_quote = int(bool(_clean_text(evidence_reference.get("quote"))))
    has_fingerprint = int(bool(_clean_text(evidence_reference.get("retrieval_fingerprint"))))
    return has_span, has_quote, has_fingerprint


def _pattern_variant_representative_rank(entry: Mapping[str, Any]) -> tuple[int, int, int, int, int, int, int]:
    source_kind = _clean_text(entry.get("source_kind"))
    evidence_rank = _pattern_evidence_reference_rank(entry)
    return (
        _STATUS_RANK.get(_clean_text(entry.get("status")), -1),
        _SOURCE_KIND_RANK.get(source_kind, 0),
        _CONFIDENCE_RANK.get(_clean_text(entry.get("confidence")), -1),
        evidence_rank[0],
        evidence_rank[1],
        evidence_rank[2],
        len(entry.get("evidence") or []),
    )


def _pattern_variant_representative_identity(entry: Mapping[str, Any]) -> tuple[str, str]:
    source_ref = entry.get("source_ref")
    source_mapping = source_ref if isinstance(source_ref, Mapping) else {}
    return (
        _clean_text(source_mapping.get("source_id")),
        _clean_text(entry.get("entry_id")),
    )


def _pattern_entry_is_preferred(candidate_entry: Mapping[str, Any], current_entry: Mapping[str, Any]) -> bool:
    candidate_rank = _pattern_variant_representative_rank(candidate_entry)
    current_rank = _pattern_variant_representative_rank(current_entry)
    if candidate_rank != current_rank:
        return candidate_rank > current_rank
    return _pattern_variant_representative_identity(candidate_entry) < _pattern_variant_representative_identity(
        current_entry
    )


def _build_pattern_variant_group(entry: Mapping[str, Any]) -> dict[str, Any]:
    signature = _build_pattern_variant_signature(entry)
    source_ref = entry.get("source_ref")
    retrieval_context = entry.get("retrieval_context")
    source_timestamps = entry.get("source_timestamps")
    return {
        "signature_key": _json_key(signature),
        "signature": signature,
        "representative_entry": _clone_json_value(entry),
        "entry_ids": _normalize_string_list(entry.get("entry_id")),
        "source_refs": [_clone_json_value(source_ref)] if isinstance(source_ref, Mapping) else [],
        "retrieval_contexts": [_clone_json_value(retrieval_context)] if isinstance(retrieval_context, Mapping) else [],
        "source_timestamps": [_clone_json_value(source_timestamps)] if isinstance(source_timestamps, Mapping) else [],
    }


def _merge_pattern_variant_groups(current: dict[str, Any], incoming: dict[str, Any]) -> None:
    if current["entry"].get("entry_type") != "pattern_observation":
        return

    current_groups = current.get("pattern_variant_groups")
    if not isinstance(current_groups, list):
        current_groups = [_build_pattern_variant_group(current["entry"])]
        current["pattern_variant_groups"] = current_groups

    incoming_groups = incoming.get("pattern_variant_groups")
    if not isinstance(incoming_groups, list):
        incoming_groups = [_build_pattern_variant_group(incoming["entry"])]

    for incoming_group in incoming_groups:
        signature_key = _clean_text(incoming_group.get("signature_key"))
        matching_group = next(
            (
                existing_group
                for existing_group in current_groups
                if _clean_text(existing_group.get("signature_key")) == signature_key
            ),
            None,
        )
        if matching_group is None:
            current_groups.append(_clone_json_value(incoming_group))
            continue

        matching_group["entry_ids"] = list(
            dict.fromkeys(
                _normalize_string_list(matching_group.get("entry_ids"))
                + _normalize_string_list(incoming_group.get("entry_ids"))
            )
        )
        matching_group["source_refs"] = _merge_unique_dicts(
            list(matching_group.get("source_refs") or []) + list(incoming_group.get("source_refs") or []),
            identity_fields=("source_id", "canonical_location", "content_hash"),
        )
        matching_group["retrieval_contexts"] = _merge_unique_dicts(
            list(matching_group.get("retrieval_contexts") or []) + list(incoming_group.get("retrieval_contexts") or []),
            identity_fields=("retrieval_id", "stage", "run_path"),
        )
        matching_group["source_timestamps"] = _merge_unique_dicts(
            list(matching_group.get("source_timestamps") or []) + list(incoming_group.get("source_timestamps") or []),
            identity_fields=("retrieval_started_at", "retrieval_completed_at", "retrieved_at"),
        )

        representative_entry = (
            incoming_group.get("representative_entry")
            if isinstance(incoming_group.get("representative_entry"), Mapping)
            else {}
        )
        current_representative = (
            matching_group.get("representative_entry")
            if isinstance(matching_group.get("representative_entry"), Mapping)
            else {}
        )
        if representative_entry and (
            not current_representative
            or _pattern_entry_is_preferred(representative_entry, current_representative)
        ):
            matching_group["representative_entry"] = _clone_json_value(representative_entry)


def _select_canonical_pattern_variant_group(pattern_variant_groups: list[dict[str, Any]]) -> dict[str, Any] | None:
    canonical_group: dict[str, Any] | None = None
    canonical_entry: Mapping[str, Any] | None = None
    for group in pattern_variant_groups:
        representative_entry = (
            group.get("representative_entry")
            if isinstance(group.get("representative_entry"), Mapping)
            else None
        )
        if representative_entry is None:
            continue
        if canonical_entry is None or _pattern_entry_is_preferred(representative_entry, canonical_entry):
            canonical_group = group
            canonical_entry = representative_entry
    return canonical_group


def _apply_pattern_variant_representative(current_entry: dict[str, Any], representative_entry: Mapping[str, Any]) -> None:
    for field_name in (
        "title",
        "summary",
        "source_kind",
        "source_ref",
        "retrieval_context",
        "captured_at",
        "captured_by",
        "source_timestamps",
        "type_payload",
    ):
        if field_name in representative_entry:
            current_entry[field_name] = _clone_json_value(representative_entry.get(field_name))


def _merge_applicability(current_applicability: Any, incoming_applicability: Any) -> dict[str, Any]:
    current_mapping = dict(current_applicability) if isinstance(current_applicability, Mapping) else {}
    incoming_mapping = dict(incoming_applicability) if isinstance(incoming_applicability, Mapping) else {}

    merged = _clone_json_value(current_mapping)
    for field_name in ("skill_patterns", "agent_targets", "scenario_targets"):
        merged[field_name] = list(
            dict.fromkeys(
                _normalize_string_list(current_mapping.get(field_name))
                + _normalize_string_list(incoming_mapping.get(field_name))
            )
        )

    for field_name in ("scope_type", "scope_ref"):
        current_value = _clean_text(current_mapping.get(field_name))
        incoming_value = _clean_text(incoming_mapping.get(field_name))
        merged[field_name] = current_value or incoming_value or None

    return merged


def _merge_unique_dicts(items: list[dict[str, Any]], *, identity_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, ...]] = set()
    for item in items:
        key = tuple(_clean_text(item.get(field)) for field in identity_fields)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(item)
    return merged


def _merge_evidence(
    current_evidence: list[dict[str, Any]],
    incoming_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = list(current_evidence)
    seen = {_json_key(item) for item in current_evidence}
    for item in incoming_evidence:
        serialized = _json_key(item)
        if serialized in seen:
            continue
        seen.add(serialized)
        merged.append(item)
    return merged


def _normalize_reference_candidate(
    raw_entry: Mapping[str, Any],
    *,
    target_context: Mapping[str, Any],
) -> dict[str, Any]:
    entry_type = _clean_text(raw_entry.get("entry_type"))
    if entry_type not in CANONICAL_RESEARCH_ENTRY_TYPES:
        raise ResearchCorpusValidationError(
            [f"reference entry_type must be one of {CANONICAL_RESEARCH_ENTRY_TYPES}; received {entry_type!r}"]
        )

    title = _clean_text(raw_entry.get("title"))
    summary = _clean_text(raw_entry.get("summary"), default=title)
    if not title:
        raise ResearchCorpusValidationError(["reference entry title is required"])

    source_kind = _clean_text(raw_entry.get("source_kind"), default="reference_skill") or "reference_skill"
    captured_at = _normalize_iso_timestamp(
        raw_entry.get("captured_at"),
        field_name="reference_entry.captured_at",
    )
    source_ref = _normalize_source_ref(
        raw_entry.get("source_ref"),
        default_source_id=_clean_identifier(title, default="reference_entry"),
        default_location=title,
        default_canonical_location=title,
        default_locator=title,
        default_artifact_kind="normalized_reference_entry",
        default_display_name=title,
        default_content_hash=_sha256_text(f"{title}\n{summary}"),
        default_accessed_at=captured_at,
    )
    retrieval_context = _normalize_retrieval_context(
        raw_entry.get("retrieval_context"),
        default_retrieval_id=f"{source_ref['source_id']}:reference",
        default_stage="phase_6_5_research_intake",
        default_run_path="unknown",
        default_analysis_goal="normalize reference entry",
        default_retrieved_via="read_and_extract",
        default_selection_basis="explicit_reference_entry",
    )
    source_timestamps = _normalize_source_timestamps(
        raw_entry.get("source_timestamps"),
        default_timestamp=captured_at,
    )
    type_payload = _clone_json_value(raw_entry.get("type_payload") or {})
    evidence = _normalize_evidence(raw_entry.get("evidence"))
    if entry_type == "pattern_observation":
        type_payload = _normalize_pattern_payload(
            type_payload,
            title=title,
            summary=summary,
            analysis_goal=_clean_text(
                (raw_entry.get("retrieval_context") or {}).get("analysis_goal"),
                default="normalize reference entry",
            )
            or "normalize reference entry",
            source_ref=source_ref,
            retrieval_context=retrieval_context,
            evidence=evidence,
        )
    elif entry_type == "preference_signal":
        type_payload = _normalize_preference_signal_payload(type_payload)
    captured_by = (
        _clone_json_value(raw_entry.get("captured_by"))
        if isinstance(raw_entry.get("captured_by"), Mapping)
        else {"stage": retrieval_context["stage"], "method": "normalized_reference_entry"}
    )
    applicability = _normalize_applicability(
        raw_entry.get("applicability"),
        target_context=target_context,
        default_scope_type="pattern_family",
        default_scope_ref=_clean_text(target_context.get("skill_pattern"), default="any_skill_md") or "any_skill_md",
    )
    traceability = _normalize_traceability(
        raw_entry.get("traceability"),
        research_artifact_ref=f"reference-entry:{source_ref['source_id']}",
        raw_artifact_refs=[],
        session_log_refs=[],
        evidence_count=len(evidence),
        lineage_parent_ids=[],
        normalization_note="Normalized from an incoming reference entry.",
    )
    semantic_signature = _build_semantic_signature(
        {
            "entry_type": entry_type,
            "title": title,
            "summary": summary,
            "type_payload": type_payload,
        }
    )
    entry_id = _clean_text(raw_entry.get("entry_id"))
    if not entry_id:
        entry_id = _generate_entry_id(
            entry_type=entry_type,
            title=title,
            semantic_signature=semantic_signature,
            default_source_id=source_ref["source_id"],
        )

    normalized_entry = {
        "entry_id": entry_id,
        "schema_version": RESEARCH_CORPUS_SCHEMA_VERSION,
        "entry_type": entry_type,
        "title": title,
        "summary": summary,
        "source_kind": source_kind,
        "source_ref": source_ref,
        "retrieval_context": retrieval_context,
        "captured_at": captured_at,
        "captured_by": captured_by,
        "source_timestamps": source_timestamps,
        "applicability": applicability,
        "evidence": evidence,
        "confidence": _clean_text(raw_entry.get("confidence"), default="medium") or "medium",
        "status": _clean_text(raw_entry.get("status"), default="active") or "active",
        "derived_from_entry_ids": _normalize_string_list(raw_entry.get("derived_from_entry_ids")),
        "traceability": traceability,
        "type_payload": type_payload,
    }

    return {
        "entry": normalized_entry,
        "semantic_signature": semantic_signature,
        "source_refs": [source_ref],
        "retrieval_contexts": [retrieval_context],
        "source_timestamps": [source_timestamps],
        "exemplar_refs": [],
        "contributing_entry_ids": [entry_id],
        "pattern_variant_groups": (
            [_build_pattern_variant_group(normalized_entry)]
            if entry_type == "pattern_observation"
            else []
        ),
    }


def _default_exemplar_evidence(
    *,
    title: str,
    summary: str,
    performance: Mapping[str, Any],
    source_results_ref: str | None,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if summary:
        evidence.append(
            {
                "kind": "source_excerpt",
                "source": "exemplar_payload",
                "locator": title,
                "excerpt": summary,
            }
        )

    final_score = _coerce_numeric(performance.get("final_score"))
    if final_score is not None:
        evidence.append(
            {
                "kind": "metric",
                "source": "evaluation_result_store",
                "locator": "performance.final_score",
                "metric": {
                    "name": "final_score",
                    "value": final_score,
                    "unit": "percent",
                },
                "artifact_ref": (
                    {
                        "path": source_results_ref,
                        "label": "evaluation result store",
                    }
                    if source_results_ref
                    else None
                ),
            }
        )

    return evidence


def _normalize_exemplar_candidate(
    raw_exemplar: Mapping[str, Any],
    *,
    exemplar_payload_selected_at: str,
    exemplar_normalization: Mapping[str, Any] | None,
    target_context: Mapping[str, Any],
) -> dict[str, Any]:
    record_id = _clean_text(raw_exemplar.get("record_id"))
    if not record_id:
        raise ResearchCorpusValidationError(["exemplar record_id is required"])

    record_kind = _clean_text(raw_exemplar.get("record_kind"))
    if record_kind not in {"repository_skill", "evaluated_skill_version"}:
        raise ResearchCorpusValidationError([f"unsupported exemplar record_kind {record_kind!r}"])

    title = _clean_text(raw_exemplar.get("title"), default=record_id) or record_id
    summary = _clean_text(raw_exemplar.get("summary"), default=title) or title
    skill_id = _clean_text(raw_exemplar.get("skill_id"), default=_clean_identifier(title)) or _clean_identifier(title)
    version_label = _clean_text(raw_exemplar.get("version_label")) or None
    selection = (
        dict(raw_exemplar.get("selection"))
        if isinstance(raw_exemplar.get("selection"), Mapping)
        else {}
    )
    provenance = (
        dict(raw_exemplar.get("provenance"))
        if isinstance(raw_exemplar.get("provenance"), Mapping)
        else {}
    )
    performance = (
        dict(raw_exemplar.get("performance"))
        if isinstance(raw_exemplar.get("performance"), Mapping)
        else {}
    )
    normalization = dict(exemplar_normalization) if isinstance(exemplar_normalization, Mapping) else {}

    requested_entry_type = _clean_text(normalization.get("entry_type"))
    if requested_entry_type == "case_study" and record_kind != "evaluated_skill_version":
        requested_entry_type = "pattern_observation"
    if not requested_entry_type:
        requested_entry_type = "pattern_observation"

    analysis_goal = _clean_text(provenance.get("analysis_goal"), default="normalize selected exemplar") or "normalize selected exemplar"
    skill_path = _clean_text(provenance.get("skill_path"))
    relative_path = _clean_text(provenance.get("relative_path"), default=skill_path) or skill_path or record_id
    references_path = _clean_text(provenance.get("references_path")) or None
    content_hash = _clean_text(
        provenance.get("content_hash"),
        default=_sha256_text(f"{title}\n{summary}"),
    ) or _sha256_text(f"{title}\n{summary}")
    source_kind = _clean_text(
        provenance.get("source_kind"),
        default="evaluation_result_store" if record_kind == "evaluated_skill_version" else "repository",
    ) or ("evaluation_result_store" if record_kind == "evaluated_skill_version" else "repository")
    source_id = _clean_text(provenance.get("source_id"), default=record_id) or record_id
    source_results_ref = _clean_text(
        performance.get("source_results_ref"),
        default=_clean_text(provenance.get("results_path")),
    ) or None

    source_ref = _normalize_source_ref(
        normalization.get("source_ref"),
        default_source_id=source_id,
        default_location=skill_path or relative_path or record_id,
        default_canonical_location=skill_path or relative_path or record_id,
        default_locator=references_path or relative_path or record_id,
        default_artifact_kind="evaluated_skill_version" if record_kind == "evaluated_skill_version" else "repository_skill",
        default_display_name=title,
        default_content_hash=content_hash,
        default_accessed_at=exemplar_payload_selected_at,
    )
    retrieval_context = _normalize_retrieval_context(
        normalization.get("retrieval_context"),
        default_retrieval_id=f"exemplar:{record_id}",
        default_stage="exemplar_selection",
        default_run_path=source_results_ref or "selected_exemplar_payload",
        default_analysis_goal=analysis_goal,
        default_retrieved_via="selected_exemplar_payload",
        default_selection_basis=(
            f"selection_rank:{selection.get('selection_rank')}"
            if selection.get("selection_rank") is not None
            else "selected_exemplar_payload"
        ),
    )
    source_timestamps = _normalize_source_timestamps(
        normalization.get("source_timestamps"),
        default_timestamp=exemplar_payload_selected_at,
    )

    case_study_payload: dict[str, Any] | None = None
    if requested_entry_type == "case_study":
        try:
            case_study_payload = _normalize_case_study_payload(
                normalization.get("type_payload"),
                record_id=record_id,
                skill_id=skill_id,
                version_label=version_label,
                source_results_ref=source_results_ref,
            )
            if not case_study_payload["same_input_set_verified"]:
                case_study_payload = None
        except (TypeError, ValueError):
            case_study_payload = None

    if case_study_payload is not None:
        entry_type = "case_study"
        type_payload = case_study_payload
        default_scope_type = "skill_lineage"
        default_scope_ref = type_payload["skill_id"]
        normalization_mode = "case_study"
        normalization_note = "Promoted evaluated exemplar into case_study because same_input_set_verified = true."
    else:
        entry_type = "pattern_observation"
        type_payload = _clone_json_value(normalization.get("type_payload") or {})
        default_scope_type = "pattern_family"
        default_scope_ref = _clean_text(target_context.get("skill_pattern"), default="any_skill_md") or "any_skill_md"
        normalization_mode = "pattern_observation"
        normalization_note = (
            "Repository exemplar reduced to pattern_observation."
            if record_kind == "repository_skill"
            else "Evaluated exemplar reduced to pattern_observation because case-study proof was not available."
        )

    applicability = _normalize_applicability(
        normalization.get("applicability"),
        target_context=target_context,
        default_scope_type=default_scope_type,
        default_scope_ref=default_scope_ref,
    )
    evidence = _normalize_evidence(normalization.get("evidence"))
    if not evidence:
        evidence = _default_exemplar_evidence(
            title=title,
            summary=summary,
            performance=performance,
            source_results_ref=source_results_ref,
        )
    if entry_type == "pattern_observation":
        type_payload = _normalize_pattern_payload(
            normalization.get("type_payload"),
            title=title,
            summary=summary,
            analysis_goal=analysis_goal,
            source_ref=source_ref,
            retrieval_context=retrieval_context,
            evidence=evidence,
        )

    traceability = _normalize_traceability(
        normalization.get("traceability"),
        research_artifact_ref=f"selected_exemplar_payload:{record_id}",
        raw_artifact_refs=[path for path in (skill_path, references_path) if path],
        session_log_refs=[],
        evidence_count=len(evidence),
        lineage_parent_ids=[],
        normalization_note=normalization_note,
    )
    semantic_signature = _build_semantic_signature(
        {
            "entry_type": entry_type,
            "title": _clean_text(normalization.get("title"), default=title) or title,
            "summary": _clean_text(normalization.get("summary"), default=summary) or summary,
            "type_payload": type_payload,
        }
    )
    normalized_title = _clean_text(normalization.get("title"), default=title) or title
    normalized_summary = _clean_text(normalization.get("summary"), default=summary) or summary
    entry_id = _clean_text(normalization.get("entry_id"))
    if not entry_id:
        entry_id = _generate_entry_id(
            entry_type=entry_type,
            title=normalized_title,
            semantic_signature=semantic_signature,
            default_source_id=source_ref["source_id"],
        )

    normalized_entry = {
        "entry_id": entry_id,
        "schema_version": RESEARCH_CORPUS_SCHEMA_VERSION,
        "entry_type": entry_type,
        "title": normalized_title,
        "summary": normalized_summary,
        "source_kind": source_kind,
        "source_ref": source_ref,
        "retrieval_context": retrieval_context,
        "captured_at": _normalize_iso_timestamp(
            normalization.get("captured_at"),
            field_name="exemplar_entry.captured_at",
            default=exemplar_payload_selected_at,
        ),
        "captured_by": (
            _clone_json_value(normalization.get("captured_by"))
            if isinstance(normalization.get("captured_by"), Mapping)
            else {"stage": "exemplar_selection", "method": "loader_normalized"}
        ),
        "source_timestamps": source_timestamps,
        "applicability": applicability,
        "evidence": evidence,
        "confidence": _clean_text(normalization.get("confidence"), default="medium") or "medium",
        "status": _clean_text(normalization.get("status"), default="active") or "active",
        "derived_from_entry_ids": _normalize_string_list(normalization.get("derived_from_entry_ids")),
        "traceability": traceability,
        "type_payload": type_payload,
    }

    return {
        "entry": normalized_entry,
        "semantic_signature": semantic_signature,
        "source_refs": [source_ref],
        "retrieval_contexts": [retrieval_context],
        "source_timestamps": [source_timestamps],
        "exemplar_refs": [
            {
                "record_id": record_id,
                "record_kind": record_kind,
                "normalization_mode": normalization_mode,
                "selection": _clone_json_value(selection),
                "source_id": source_id,
                "source_kind": source_kind,
            }
        ],
        "contributing_entry_ids": [entry_id],
        "pattern_variant_groups": (
            [_build_pattern_variant_group(normalized_entry)]
            if entry_type == "pattern_observation"
            else []
        ),
    }


def _merge_candidate_wrappers(current: dict[str, Any], incoming: dict[str, Any]) -> None:
    current_entry = current["entry"]
    incoming_entry = incoming["entry"]

    current["source_refs"] = _merge_unique_dicts(
        current["source_refs"] + incoming["source_refs"],
        identity_fields=("source_id", "canonical_location", "content_hash"),
    )
    current["retrieval_contexts"] = _merge_unique_dicts(
        current["retrieval_contexts"] + incoming["retrieval_contexts"],
        identity_fields=("retrieval_id", "stage", "run_path"),
    )
    current["source_timestamps"] = _merge_unique_dicts(
        current["source_timestamps"] + incoming["source_timestamps"],
        identity_fields=("retrieval_started_at", "retrieval_completed_at", "retrieved_at"),
    )
    current["exemplar_refs"] = _merge_unique_dicts(
        current["exemplar_refs"] + incoming["exemplar_refs"],
        identity_fields=("record_id", "record_kind", "normalization_mode"),
    )
    current["contributing_entry_ids"] = list(
        dict.fromkeys(current["contributing_entry_ids"] + incoming["contributing_entry_ids"])
    )

    current_entry["evidence"] = _merge_evidence(
        current_entry.get("evidence", []),
        incoming_entry.get("evidence", []),
    )
    current_entry["derived_from_entry_ids"] = list(
        dict.fromkeys(
            _normalize_string_list(current_entry.get("derived_from_entry_ids"))
            + _normalize_string_list(incoming_entry.get("derived_from_entry_ids"))
        )
    )
    current_entry["applicability"] = _merge_applicability(
        current_entry.get("applicability"),
        incoming_entry.get("applicability"),
    )

    if _CONFIDENCE_RANK.get(_clean_text(incoming_entry.get("confidence")), -1) > _CONFIDENCE_RANK.get(
        _clean_text(current_entry.get("confidence")),
        -1,
    ):
        current_entry["confidence"] = incoming_entry.get("confidence")

    if _STATUS_RANK.get(_clean_text(incoming_entry.get("status")), -1) > _STATUS_RANK.get(
        _clean_text(current_entry.get("status")),
        -1,
    ):
        current_entry["status"] = incoming_entry.get("status")

    _merge_pattern_variant_groups(current, incoming)
    pattern_variant_groups = current.get("pattern_variant_groups")
    if isinstance(pattern_variant_groups, list) and pattern_variant_groups:
        canonical_group = _select_canonical_pattern_variant_group(pattern_variant_groups)
        if canonical_group is not None:
            representative_entry = (
                canonical_group.get("representative_entry")
                if isinstance(canonical_group.get("representative_entry"), Mapping)
                else None
            )
            if representative_entry is not None:
                _apply_pattern_variant_representative(current_entry, representative_entry)
                current_entry["applicability"] = _merge_applicability(
                    current_entry.get("applicability"),
                    incoming_entry.get("applicability"),
                )

    traceability = current_entry.get("traceability")
    if not isinstance(traceability, Mapping):
        traceability = {}
    traceability = dict(traceability)
    incoming_traceability = incoming_entry.get("traceability")
    if isinstance(incoming_traceability, Mapping):
        traceability["raw_artifact_refs"] = _normalize_string_list(
            traceability.get("raw_artifact_refs"),
            default=[],
        )
        traceability["raw_artifact_refs"] = list(
            dict.fromkeys(
                traceability["raw_artifact_refs"]
                + _normalize_string_list(incoming_traceability.get("raw_artifact_refs"))
            )
        )
        traceability["session_log_refs"] = _normalize_string_list(
            traceability.get("session_log_refs"),
            default=[],
        )
        traceability["session_log_refs"] = list(
            dict.fromkeys(
                traceability["session_log_refs"]
                + _normalize_string_list(incoming_traceability.get("session_log_refs"))
            )
        )
        traceability["lineage_parent_ids"] = _normalize_string_list(
            traceability.get("lineage_parent_ids"),
            default=[],
        )
        traceability["lineage_parent_ids"] = list(
            dict.fromkeys(
                traceability["lineage_parent_ids"]
                + _normalize_string_list(incoming_traceability.get("lineage_parent_ids"))
            )
        )

    traceability["evidence_refs"] = list(range(len(current_entry["evidence"])))
    traceability["contributing_sources"] = _clone_json_value(current["source_refs"])
    traceability["contributing_retrieval_contexts"] = _clone_json_value(current["retrieval_contexts"])
    traceability["contributing_source_timestamps"] = _clone_json_value(current["source_timestamps"])
    traceability["contributing_exemplar_record_ids"] = [
        exemplar_ref["record_id"]
        for exemplar_ref in current["exemplar_refs"]
        if _clean_text(exemplar_ref.get("record_id"))
    ]
    traceability["semantic_dedupe"] = {
        "strategy": "type_specific_semantic_match",
        "merged_entry_ids": list(current["contributing_entry_ids"]),
    }
    traceability["normalization_note"] = (
        _clean_text(traceability.get("normalization_note"))
        + " Merged semantically identical contributing entries."
    ).strip()
    current_entry["traceability"] = traceability


def _finalize_candidate_wrapper(candidate: dict[str, Any]) -> dict[str, Any]:
    entry = candidate["entry"]
    pattern_variant_groups = (
        candidate.get("pattern_variant_groups")
        if isinstance(candidate.get("pattern_variant_groups"), list)
        else []
    )
    canonical_group = (
        _select_canonical_pattern_variant_group(pattern_variant_groups)
        if pattern_variant_groups
        else None
    )
    if canonical_group is not None:
        representative_entry = (
            canonical_group.get("representative_entry")
            if isinstance(canonical_group.get("representative_entry"), Mapping)
            else None
        )
        if representative_entry is not None:
            _apply_pattern_variant_representative(entry, representative_entry)

    traceability = entry.get("traceability")
    if not isinstance(traceability, Mapping):
        traceability = {}
    traceability = dict(traceability)
    traceability["evidence_refs"] = list(range(len(entry.get("evidence", []))))
    traceability["contributing_sources"] = _clone_json_value(candidate["source_refs"])
    traceability["contributing_retrieval_contexts"] = _clone_json_value(candidate["retrieval_contexts"])
    traceability["contributing_source_timestamps"] = _clone_json_value(candidate["source_timestamps"])
    traceability["contributing_exemplar_record_ids"] = [
        exemplar_ref["record_id"]
        for exemplar_ref in candidate["exemplar_refs"]
        if _clean_text(exemplar_ref.get("record_id"))
    ]
    traceability["contributing_exemplars"] = _clone_json_value(candidate["exemplar_refs"])
    traceability["semantic_dedupe"] = {
        "strategy": "type_specific_semantic_match",
        "merged_entry_ids": list(candidate["contributing_entry_ids"]),
    }
    if canonical_group is not None:
        canonical_signature = (
            canonical_group.get("signature")
            if isinstance(canonical_group.get("signature"), Mapping)
            else {}
        )
        canonical_entry_ids = _normalize_string_list(canonical_group.get("entry_ids"))
        traceability["semantic_dedupe"]["duplicate_entry_ids"] = (
            canonical_entry_ids if len(canonical_entry_ids) > 1 else []
        )
        traceability["semantic_dedupe"]["incompatible_variants"] = []

        for group in pattern_variant_groups:
            if group is canonical_group:
                continue
            representative_entry = (
                group.get("representative_entry")
                if isinstance(group.get("representative_entry"), Mapping)
                else {}
            )
            group_signature = group.get("signature") if isinstance(group.get("signature"), Mapping) else {}
            traceability["semantic_dedupe"]["incompatible_variants"].append(
                {
                    "entry_id": _clean_text(representative_entry.get("entry_id")),
                    "entry_ids": _normalize_string_list(group.get("entry_ids")),
                    "resolution": "kept_as_incompatible_variant",
                    "differing_fields": _pattern_variant_diff_fields(canonical_signature, group_signature),
                    "variant": _build_pattern_variant_details(representative_entry),
                    "source_ref": _clone_json_value(representative_entry.get("source_ref")),
                    "retrieval_context": _clone_json_value(representative_entry.get("retrieval_context")),
                    "source_timestamps": _clone_json_value(representative_entry.get("source_timestamps")),
                    "confidence": _clean_text(representative_entry.get("confidence")),
                    "status": _clean_text(representative_entry.get("status")),
                }
            )
    entry["traceability"] = traceability
    return entry


def _build_reference_index(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        entry_id = candidate["entry"]["entry_id"]
        raw_artifact_refs = _normalize_string_list(candidate["entry"].get("traceability", {}).get("raw_artifact_refs"))
        for source_ref in candidate["source_refs"]:
            source_id = _clean_text(source_ref.get("source_id"))
            canonical_location = _clean_text(source_ref.get("canonical_location"))
            key = (source_id, canonical_location)
            bucket = indexed.setdefault(
                key,
                {
                    "source_id": source_id,
                    "canonical_location": canonical_location,
                    "entry_ids": [],
                    "raw_artifact_refs": [],
                },
            )
            if entry_id not in bucket["entry_ids"]:
                bucket["entry_ids"].append(entry_id)
            bucket["raw_artifact_refs"] = list(
                dict.fromkeys(bucket["raw_artifact_refs"] + raw_artifact_refs)
            )

    return list(indexed.values())


def _build_exemplar_index(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        entry_id = candidate["entry"]["entry_id"]
        for exemplar_ref in candidate["exemplar_refs"]:
            record_id = _clean_text(exemplar_ref.get("record_id"))
            if not record_id:
                continue
            bucket = indexed.setdefault(
                record_id,
                {
                    "record_id": record_id,
                    "record_kind": _clean_text(exemplar_ref.get("record_kind")),
                    "normalization_mode": _clean_text(exemplar_ref.get("normalization_mode")),
                    "entry_ids": [],
                    "selection": _clone_json_value(exemplar_ref.get("selection") or {}),
                    "source_id": _clean_text(exemplar_ref.get("source_id")),
                    "source_kind": _clean_text(exemplar_ref.get("source_kind")),
                },
            )
            if entry_id not in bucket["entry_ids"]:
                bucket["entry_ids"].append(entry_id)
            mode = _clean_text(exemplar_ref.get("normalization_mode"))
            if bucket["normalization_mode"] != mode:
                bucket["normalization_mode"] = "mixed"
    return list(indexed.values())


def _normalize_exemplar_payload_candidates(
    exemplar_payload: Mapping[str, Any] | None,
    *,
    exemplar_normalizations: Mapping[str, Any] | None,
    target_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if exemplar_payload is None:
        return []
    if not isinstance(exemplar_payload, Mapping):
        raise TypeError("exemplar_payload must be a mapping when provided")

    payload_type = _clean_text(exemplar_payload.get("payload_type"))
    if payload_type and payload_type != CANONICAL_EXEMPLAR_PAYLOAD_TYPE:
        raise ResearchCorpusValidationError(
            [f"exemplar_payload.payload_type must be {CANONICAL_EXEMPLAR_PAYLOAD_TYPE!r}; received {payload_type!r}"]
        )

    selected_at = _normalize_iso_timestamp(
        exemplar_payload.get("selected_at"),
        field_name="exemplar_payload.selected_at",
        default=_now_utc_timestamp(),
    )
    exemplars = exemplar_payload.get("exemplars")
    if exemplars is None:
        return []
    if not isinstance(exemplars, list):
        raise TypeError("exemplar_payload.exemplars must be a list")

    normalized: list[dict[str, Any]] = []
    normalization_map = exemplar_normalizations if isinstance(exemplar_normalizations, Mapping) else {}
    for index, raw_exemplar in enumerate(exemplars):
        if not isinstance(raw_exemplar, Mapping):
            raise TypeError(f"exemplar_payload.exemplars[{index}] must be a mapping")
        record_id = _clean_text(raw_exemplar.get("record_id"))
        normalized.append(
            _normalize_exemplar_candidate(
                raw_exemplar,
                exemplar_payload_selected_at=selected_at,
                exemplar_normalization=(
                    normalization_map.get(record_id)
                    if isinstance(normalization_map.get(record_id), Mapping)
                    else None
                ),
                target_context=target_context,
            )
        )
    return normalized


def _build_exemplar_payload_from_version_snapshot_bundle(
    version_snapshot_bundle: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if version_snapshot_bundle is None:
        return None
    if not isinstance(version_snapshot_bundle, Mapping):
        raise TypeError("version_snapshot_bundle must be a mapping when provided")

    bundle_type = _clean_text(version_snapshot_bundle.get("bundle_type"))
    if bundle_type and bundle_type != CANONICAL_VERSION_SNAPSHOT_BUNDLE_TYPE:
        raise ResearchCorpusValidationError(
            [
                "version_snapshot_bundle.bundle_type must be "
                f"{CANONICAL_VERSION_SNAPSHOT_BUNDLE_TYPE!r}; received {bundle_type!r}"
            ]
        )

    version_snapshots = version_snapshot_bundle.get("version_snapshots")
    if version_snapshots is None:
        return None
    if not isinstance(version_snapshots, list):
        raise TypeError("version_snapshot_bundle.version_snapshots must be a list")

    selected_at = _normalize_iso_timestamp(
        version_snapshot_bundle.get("generated_at"),
        field_name="version_snapshot_bundle.generated_at",
        default=_now_utc_timestamp(),
    )
    exemplars: list[dict[str, Any]] = []
    selected_candidate_record_id: str | None = None

    for index, raw_snapshot in enumerate(version_snapshots):
        if not isinstance(raw_snapshot, Mapping):
            raise TypeError(f"version_snapshot_bundle.version_snapshots[{index}] must be a mapping")

        record_id = _clean_text(raw_snapshot.get("record_id"))
        if not record_id:
            continue

        version_provenance = (
            raw_snapshot.get("version_provenance")
            if isinstance(raw_snapshot.get("version_provenance"), Mapping)
            else {}
        )
        selected_candidate_summary = (
            version_provenance.get("selected_candidate_summary")
            if isinstance(version_provenance.get("selected_candidate_summary"), Mapping)
            else None
        )
        evaluation_context = (
            raw_snapshot.get("evaluation_context")
            if isinstance(raw_snapshot.get("evaluation_context"), Mapping)
            else {}
        )
        version_label = _clean_text(raw_snapshot.get("version_label")) or None
        experiment_id = evaluation_context.get("experiment_id")
        is_selected_candidate = False
        if selected_candidate_summary is not None:
            is_selected_candidate = bool(
                (version_label and version_label == _clean_text(selected_candidate_summary.get("version")))
                or (
                    experiment_id is not None
                    and selected_candidate_summary.get("experiment_id") == experiment_id
                )
            )
        if is_selected_candidate:
            selected_candidate_record_id = record_id

        metrics = (
            raw_snapshot.get("metrics")
            if isinstance(raw_snapshot.get("metrics"), Mapping)
            else {}
        )
        skill_content = (
            raw_snapshot.get("skill_content")
            if isinstance(raw_snapshot.get("skill_content"), Mapping)
            else {}
        )
        exemplars.append(
            {
                "record_id": record_id,
                "record_kind": _clean_text(
                    raw_snapshot.get("record_kind"),
                    default="evaluated_skill_version",
                )
                or "evaluated_skill_version",
                "skill_id": _clean_text(raw_snapshot.get("skill_id")),
                "version_label": version_label,
                "title": _clean_text(raw_snapshot.get("title")),
                "summary": _clean_text(raw_snapshot.get("summary")),
                "selection": {
                    "selection_rank": index + 1,
                    "is_selected_candidate": is_selected_candidate,
                    "dedupe_strategy": "version_snapshot_bundle",
                    "dedupe_key": record_id,
                },
                "skill_content": _clone_json_value(skill_content),
                "provenance": {
                    "source_id": _clean_text(raw_snapshot.get("source_id")),
                    "source_kind": _clean_text(raw_snapshot.get("source_kind")),
                    "skill_path": _clean_text(raw_snapshot.get("skill_path")) or None,
                    "relative_path": _clean_text(raw_snapshot.get("relative_path")) or None,
                    "references_path": None,
                    "content_hash": _clean_text(raw_snapshot.get("content_hash")) or None,
                    **(
                        _clone_json_value(version_provenance)
                        if version_provenance
                        else {}
                    ),
                },
                "performance": {
                    "has_evaluation_metrics": bool(metrics.get("has_evaluation_metrics")),
                    "experiment_id": experiment_id,
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
        "schema_version": 1,
        "payload_type": CANONICAL_EXEMPLAR_PAYLOAD_TYPE,
        "selected_at": selected_at,
        "selected_record_ids": [
            exemplar["record_id"]
            for exemplar in exemplars
            if _clean_text(exemplar.get("record_id"))
        ],
        "selected_candidate_record_id": selected_candidate_record_id,
        "exemplar_count": len(exemplars),
        "exemplars": exemplars,
    }


def _build_candidate_wrapper_from_persisted_entry(
    persisted_entry: Mapping[str, Any],
) -> dict[str, Any]:
    entry = _clone_json_value(persisted_entry)
    traceability = (
        entry.get("traceability")
        if isinstance(entry.get("traceability"), Mapping)
        else {}
    )
    contributing_sources = (
        traceability.get("contributing_sources")
        if isinstance(traceability.get("contributing_sources"), list)
        else []
    )
    source_refs = [
        _clone_json_value(source_ref)
        for source_ref in contributing_sources
        if isinstance(source_ref, Mapping)
    ]
    if not source_refs and isinstance(entry.get("source_ref"), Mapping):
        source_refs = [_clone_json_value(entry.get("source_ref"))]

    contributing_retrieval_contexts = (
        traceability.get("contributing_retrieval_contexts")
        if isinstance(traceability.get("contributing_retrieval_contexts"), list)
        else []
    )
    retrieval_contexts = [
        _clone_json_value(retrieval_context)
        for retrieval_context in contributing_retrieval_contexts
        if isinstance(retrieval_context, Mapping)
    ]
    if not retrieval_contexts and isinstance(entry.get("retrieval_context"), Mapping):
        retrieval_contexts = [_clone_json_value(entry.get("retrieval_context"))]

    contributing_source_timestamps = (
        traceability.get("contributing_source_timestamps")
        if isinstance(traceability.get("contributing_source_timestamps"), list)
        else []
    )
    source_timestamps = [
        _clone_json_value(timestamp_payload)
        for timestamp_payload in contributing_source_timestamps
        if isinstance(timestamp_payload, Mapping)
    ]
    if not source_timestamps and isinstance(entry.get("source_timestamps"), Mapping):
        source_timestamps = [_clone_json_value(entry.get("source_timestamps"))]

    contributing_exemplars = (
        traceability.get("contributing_exemplars")
        if isinstance(traceability.get("contributing_exemplars"), list)
        else []
    )
    exemplar_refs = [
        _clone_json_value(exemplar_ref)
        for exemplar_ref in contributing_exemplars
        if isinstance(exemplar_ref, Mapping)
    ]
    if not exemplar_refs:
        contributing_exemplar_record_ids = _normalize_string_list(
            traceability.get("contributing_exemplar_record_ids"),
            default=[],
        )
        research_artifact_ref = _clean_text(traceability.get("research_artifact_ref"))
        inferred_record_id = (
            research_artifact_ref.split(":", 1)[1]
            if research_artifact_ref.startswith("selected_exemplar_payload:")
            else None
        )
        inferred_ids = contributing_exemplar_record_ids or ([inferred_record_id] if inferred_record_id else [])
        normalization_mode = (
            "case_study" if _clean_text(entry.get("entry_type")) == "case_study" else "pattern_observation"
        )
        for record_id in inferred_ids:
            exemplar_refs.append(
                {
                    "record_id": record_id,
                    "record_kind": (
                        "evaluated_skill_version"
                        if _clean_text(entry.get("source_kind")) == "evaluation_result_store"
                        else "repository_skill"
                    ),
                    "normalization_mode": normalization_mode,
                    "selection": {},
                    "source_id": _clean_text(entry.get("source_ref", {}).get("source_id")),
                    "source_kind": _clean_text(entry.get("source_kind")),
                }
            )

    return {
        "entry": entry,
        "source_refs": source_refs,
        "retrieval_contexts": retrieval_contexts,
        "source_timestamps": source_timestamps,
        "exemplar_refs": exemplar_refs,
        "contributing_entry_ids": [_clean_text(entry.get("entry_id"))],
        "pattern_variant_groups": (
            [_build_pattern_variant_group(entry)]
            if _clean_text(entry.get("entry_type")) == "pattern_observation"
            else []
        ),
    }


def assemble_normalized_research_corpus(
    *,
    reference_entries: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None = None,
    exemplar_payload: Mapping[str, Any] | None = None,
    version_snapshot_bundle: Mapping[str, Any] | None = None,
    exemplar_normalizations: Mapping[str, Any] | None = None,
    target_context: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the downstream normalized research-corpus view from references and exemplars."""

    normalized_target_context = _normalize_target_context(target_context)
    emitted_at = _normalize_iso_timestamp(
        generated_at,
        field_name="generated_at",
        default=_now_utc_timestamp(),
    )

    normalized_candidates: list[dict[str, Any]] = []
    if reference_entries is not None:
        if not isinstance(reference_entries, (list, tuple)):
            raise TypeError("reference_entries must be a list or tuple when provided")
        for index, raw_entry in enumerate(reference_entries):
            if not isinstance(raw_entry, Mapping):
                raise TypeError(f"reference_entries[{index}] must be a mapping")
            normalized_candidates.append(
                _normalize_reference_candidate(
                    raw_entry,
                    target_context=normalized_target_context,
                )
            )

    synthesized_exemplar_payload = _build_exemplar_payload_from_version_snapshot_bundle(
        version_snapshot_bundle
    )
    normalized_candidates.extend(
        _normalize_exemplar_payload_candidates(
            exemplar_payload,
            exemplar_normalizations=exemplar_normalizations,
            target_context=normalized_target_context,
        )
    )
    normalized_candidates.extend(
        _normalize_exemplar_payload_candidates(
            synthesized_exemplar_payload,
            exemplar_normalizations=exemplar_normalizations,
            target_context=normalized_target_context,
        )
    )

    deduplicated_candidates: list[dict[str, Any]] = []
    for candidate in normalized_candidates:
        matching_candidate = next(
            (
                existing
                for existing in deduplicated_candidates
                if existing["entry"]["entry_type"] == candidate["entry"]["entry_type"]
                and _semantic_signatures_match(
                    existing["semantic_signature"],
                    candidate["semantic_signature"],
                )
            ),
            None,
        )
        if matching_candidate is None:
            deduplicated_candidates.append(candidate)
            continue
        _merge_candidate_wrappers(matching_candidate, candidate)

    entries = [_finalize_candidate_wrapper(candidate) for candidate in deduplicated_candidates]
    entry_index = {
        entry["entry_id"]: index for index, entry in enumerate(entries)
    }

    return {
        "schema_version": RESEARCH_CORPUS_SCHEMA_VERSION,
        "bundle_type": CANONICAL_RESEARCH_CORPUS_BUNDLE_TYPE,
        "generated_at": emitted_at,
        "target_context": normalized_target_context,
        "entries": entries,
        "entry_index": entry_index,
        "reference_index": _build_reference_index(deduplicated_candidates),
        "exemplar_index": _build_exemplar_index(deduplicated_candidates),
    }


def build_research_corpus_view_from_storage(
    *,
    corpus_storage_path: str | Path,
    target_context: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
    version_snapshot_bundle: Mapping[str, Any] | None = None,
    latest_pattern_versions_only: bool = True,
) -> dict[str, Any]:
    """Build the downstream research-corpus view from persisted normalized entries."""

    storage_payload = load_research_corpus_storage(corpus_storage_path=corpus_storage_path)
    normalized_target_context = _normalize_target_context(target_context)
    emitted_at = _normalize_iso_timestamp(
        generated_at,
        field_name="generated_at",
        default=_now_utc_timestamp(),
    )

    persisted_records = storage_payload.get("records")
    if persisted_records is None:
        persisted_records = []
    if not isinstance(persisted_records, list):
        raise TypeError("persisted storage records must be a list")

    candidate_wrappers: list[dict[str, Any]] = []
    for index, raw_record in enumerate(persisted_records):
        if not isinstance(raw_record, Mapping):
            raise TypeError(f"persisted storage records[{index}] must be a mapping")
        candidate_wrappers.append(_build_candidate_wrapper_from_persisted_entry(raw_record))

    pattern_records = storage_payload.get("pattern_records")
    if pattern_records is None:
        pattern_records = []
    if not isinstance(pattern_records, list):
        raise TypeError("persisted storage pattern_records must be a list")

    pattern_versions: list[dict[str, Any]] = []
    if latest_pattern_versions_only:
        latest_by_pattern_id: dict[str, dict[str, Any]] = {}
        for raw_pattern_record in pattern_records:
            if not isinstance(raw_pattern_record, Mapping):
                continue
            pattern_record = _clone_json_value(raw_pattern_record)
            pattern_id = _clean_text(pattern_record.get("pattern_id"))
            version = _lookup_optional_int(pattern_record.get("version")) or 0
            existing_record = latest_by_pattern_id.get(pattern_id)
            if existing_record is None or (_lookup_optional_int(existing_record.get("version")) or 0) < version:
                latest_by_pattern_id[pattern_id] = pattern_record
        pattern_versions = sorted(
            latest_by_pattern_id.values(),
            key=_pattern_record_sort_key,
        )
    else:
        pattern_versions = [
            _clone_json_value(pattern_record)
            for pattern_record in pattern_records
            if isinstance(pattern_record, Mapping)
        ]
        pattern_versions.sort(key=_pattern_record_sort_key)

    return {
        "schema_version": RESEARCH_CORPUS_SCHEMA_VERSION,
        "bundle_type": CANONICAL_RESEARCH_CORPUS_BUNDLE_TYPE,
        "generated_at": emitted_at,
        "target_context": normalized_target_context,
        "entries": [
            _clone_json_value(record)
            for record in persisted_records
            if isinstance(record, Mapping)
        ],
        "entry_index": {
            _clean_text(record.get("entry_id")): index
            for index, record in enumerate(persisted_records)
            if isinstance(record, Mapping) and _clean_text(record.get("entry_id"))
        },
        "reference_index": _build_reference_index(candidate_wrappers),
        "exemplar_index": _build_exemplar_index(candidate_wrappers),
        "pattern_store_type": _clean_text(
            storage_payload.get("pattern_store_type"),
            default=CANONICAL_PATTERN_STORE_TYPE,
        )
        or CANONICAL_PATTERN_STORE_TYPE,
        "pattern_store_schema_version": (
            _lookup_optional_int(storage_payload.get("pattern_store_schema_version"))
            or PATTERN_STORE_SCHEMA_VERSION
        ),
        "pattern_versions": pattern_versions,
        "pattern_version_index": {
            _clean_text(pattern_record.get("pattern_version_id")): index
            for index, pattern_record in enumerate(pattern_versions)
            if _clean_text(pattern_record.get("pattern_version_id"))
        },
        "version_snapshot_bundle": (
            _clone_json_value(version_snapshot_bundle)
            if isinstance(version_snapshot_bundle, Mapping)
            else None
        ),
    }


def _normalize_research_storage_path(corpus_storage_path: str | Path) -> Path:
    normalized_path = Path(corpus_storage_path).expanduser()
    if normalized_path.name in {"", ".", ".."}:
        raise ValueError("corpus_storage_path must target a writable JSON file path")
    return normalized_path


def _iso_to_datetime(value: str, *, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} requires a valid ISO timestamp") from exc


def _normalize_required_mapping(
    raw_value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return _clone_json_value(raw_value)


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


def _normalize_ingest_source(raw_ingest_source: Any) -> str:
    normalized_source = _clean_text(raw_ingest_source)
    return normalized_source or "pattern_extraction_ingest"


def _normalize_required_timestamp_mapping(
    raw_value: Any,
    *,
    field_name: str,
    required_fields: tuple[str, ...],
) -> dict[str, Any]:
    normalized_mapping = _normalize_required_mapping(raw_value, field_name=field_name)
    for required_field in required_fields:
        normalized_mapping[required_field] = _normalize_iso_timestamp(
            normalized_mapping.get(required_field),
            field_name=f"{field_name}.{required_field}",
        )
    return normalized_mapping


def _normalize_research_corpus_record(
    raw_record: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    record_field = f"normalized_records[{index}]"
    normalized_record = _clone_json_value(raw_record)
    missing_fields = [
        field_name
        for field_name in _RESEARCH_CORPUS_REQUIRED_ENTRY_FIELDS
        if field_name not in normalized_record
    ]
    if missing_fields:
        raise ValueError(
            f"{record_field} is missing required fields: {missing_fields}"
        )

    normalized_record["entry_id"] = _normalize_required_non_empty_text(
        normalized_record.get("entry_id"),
        field_name=f"{record_field}.entry_id",
    )
    normalized_record["entry_type"] = _normalize_allowed_value(
        normalized_record.get("entry_type"),
        field_name=f"{record_field}.entry_type",
        allowed_values=CANONICAL_RESEARCH_ENTRY_TYPES,
    )
    normalized_record["title"] = _normalize_required_non_empty_text(
        normalized_record.get("title"),
        field_name=f"{record_field}.title",
    )
    normalized_record["summary"] = _normalize_required_non_empty_text(
        normalized_record.get("summary"),
        field_name=f"{record_field}.summary",
    )
    normalized_record["source_kind"] = _normalize_allowed_value(
        normalized_record.get("source_kind"),
        field_name=f"{record_field}.source_kind",
        allowed_values=CANONICAL_RESEARCH_SOURCE_KINDS,
    )
    normalized_record["source_ref"] = _normalize_required_mapping(
        normalized_record.get("source_ref"),
        field_name=f"{record_field}.source_ref",
    )
    if not _clean_text(normalized_record["source_ref"].get("source_id")):
        raise ValueError(f"{record_field}.source_ref.source_id is required")
    if not _clean_text(
        normalized_record["source_ref"].get("canonical_location")
        or normalized_record["source_ref"].get("location")
    ):
        raise ValueError(
            f"{record_field}.source_ref.canonical_location (or location) is required"
        )

    normalized_record["retrieval_context"] = _normalize_required_mapping(
        normalized_record.get("retrieval_context"),
        field_name=f"{record_field}.retrieval_context",
    )
    if not _clean_text(normalized_record["retrieval_context"].get("retrieval_id")):
        raise ValueError(f"{record_field}.retrieval_context.retrieval_id is required")

    normalized_record["captured_at"] = _normalize_iso_timestamp(
        normalized_record.get("captured_at"),
        field_name=f"{record_field}.captured_at",
    )
    normalized_record["captured_by"] = _normalize_required_mapping(
        normalized_record.get("captured_by"),
        field_name=f"{record_field}.captured_by",
    )
    if not _clean_text(normalized_record["captured_by"].get("stage")):
        raise ValueError(f"{record_field}.captured_by.stage is required")
    if not _clean_text(normalized_record["captured_by"].get("method")):
        raise ValueError(f"{record_field}.captured_by.method is required")

    normalized_record["source_timestamps"] = _normalize_required_timestamp_mapping(
        normalized_record.get("source_timestamps"),
        field_name=f"{record_field}.source_timestamps",
        required_fields=(
            "retrieval_started_at",
            "retrieval_completed_at",
            "retrieved_at",
        ),
    )
    normalized_record["applicability"] = _normalize_required_mapping(
        normalized_record.get("applicability"),
        field_name=f"{record_field}.applicability",
    )
    try:
        normalized_record["evidence"] = _normalize_evidence(
            normalized_record.get("evidence"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{record_field}.evidence {exc}") from exc
    normalized_record["confidence"] = _normalize_allowed_value(
        normalized_record.get("confidence"),
        field_name=f"{record_field}.confidence",
        allowed_values=CANONICAL_CONFIDENCE_VALUES,
    )
    normalized_record["status"] = _normalize_allowed_value(
        normalized_record.get("status"),
        field_name=f"{record_field}.status",
        allowed_values=CANONICAL_STATUS_VALUES,
    )
    normalized_record["derived_from_entry_ids"] = _normalize_string_list(
        normalized_record.get("derived_from_entry_ids"),
        default=[],
    )
    normalized_record["traceability"] = _normalize_required_traceability(
        normalized_record.get("traceability"),
        field_name=f"{record_field}.traceability",
        evidence_count=len(normalized_record["evidence"]),
    )
    normalized_record["type_payload"] = _normalize_required_mapping(
        normalized_record.get("type_payload"),
        field_name=f"{record_field}.type_payload",
    )
    if normalized_record["entry_type"] == "pattern_observation":
        normalized_record["type_payload"] = _normalize_pattern_payload(
            normalized_record["type_payload"],
            title=normalized_record["title"],
            summary=normalized_record["summary"],
            analysis_goal=_clean_text(
                normalized_record["retrieval_context"].get("analysis_goal"),
                default="pattern extraction ingest",
            )
            or "pattern extraction ingest",
            source_ref=normalized_record["source_ref"],
            retrieval_context=normalized_record["retrieval_context"],
            evidence=normalized_record["evidence"],
        )
    elif normalized_record["entry_type"] == "preference_signal":
        normalized_record["type_payload"] = _normalize_preference_signal_payload(
            normalized_record["type_payload"]
        )
    return normalized_record


def _build_research_corpus_trust_signals(entry: Mapping[str, Any]) -> dict[str, Any]:
    traceability = entry.get("traceability")
    traceability_mapping = traceability if isinstance(traceability, Mapping) else {}
    source_timestamps = entry.get("source_timestamps")
    source_timestamp_mapping = (
        source_timestamps if isinstance(source_timestamps, Mapping) else {}
    )

    timestamp_span_seconds: float | None = None
    try:
        retrieval_started_at = _iso_to_datetime(
            _clean_text(source_timestamp_mapping.get("retrieval_started_at")),
            field_name="source_timestamps.retrieval_started_at",
        )
        retrieval_completed_at = _iso_to_datetime(
            _clean_text(source_timestamp_mapping.get("retrieval_completed_at")),
            field_name="source_timestamps.retrieval_completed_at",
        )
        timestamp_span_seconds = max(
            0.0,
            (retrieval_completed_at - retrieval_started_at).total_seconds(),
        )
    except ValueError:
        timestamp_span_seconds = None

    has_source_identity = bool(
        _clean_text(entry.get("source_kind"))
        and isinstance(entry.get("source_ref"), Mapping)
        and _clean_text(entry.get("source_ref", {}).get("source_id"))
        and _clean_text(
            entry.get("source_ref", {}).get("canonical_location")
            or entry.get("source_ref", {}).get("location")
        )
    )
    has_retrieval_context = bool(
        isinstance(entry.get("retrieval_context"), Mapping)
        and _clean_text(entry.get("retrieval_context", {}).get("retrieval_id"))
    )
    has_traceability = bool(
        _clean_text(traceability_mapping.get("research_artifact_ref"))
        and _normalize_string_list(traceability_mapping.get("raw_artifact_refs"))
    )

    trust_signals: dict[str, Any] = {
        "confidence": _clean_text(entry.get("confidence")),
        "status": _clean_text(entry.get("status")),
        "evidence_count": len(entry.get("evidence") or []),
        "traceability_ref_count": len(
            _normalize_string_list(traceability_mapping.get("raw_artifact_refs"))
        )
        + len(_normalize_string_list(traceability_mapping.get("session_log_refs")))
        + len(_normalize_string_list(traceability_mapping.get("lineage_parent_ids"))),
        "has_source_identity": has_source_identity,
        "has_retrieval_context": has_retrieval_context,
        "has_traceability": has_traceability,
        "provenance_complete": (
            has_source_identity and has_retrieval_context and has_traceability
        ),
    }
    if timestamp_span_seconds is not None:
        trust_signals["retrieval_span_seconds"] = timestamp_span_seconds

    if entry.get("entry_type") == "case_study":
        trust_signals["same_input_set_verified"] = _coerce_bool(
            entry.get("type_payload", {}).get("same_input_set_verified"),
            default=False,
        )
    elif entry.get("entry_type") == "pattern_observation":
        type_payload = entry.get("type_payload")
        type_payload_mapping = type_payload if isinstance(type_payload, Mapping) else {}
        evidence_reference = type_payload_mapping.get("evidence_reference")
        evidence_reference_mapping = (
            evidence_reference if isinstance(evidence_reference, Mapping) else {}
        )
        span_mapping = (
            evidence_reference_mapping.get("span")
            if isinstance(evidence_reference_mapping.get("span"), Mapping)
            else {}
        )
        trust_signals["has_structured_evidence_reference"] = bool(
            evidence_reference_mapping
        )
        trust_signals["evidence_reference_has_quote"] = bool(
            _clean_text(evidence_reference_mapping.get("quote"))
        )
        trust_signals["evidence_reference_has_span"] = bool(
            isinstance(span_mapping, Mapping) and any(value is not None for value in span_mapping.values())
        )
        trust_signals["evidence_reference_has_retrieval_fingerprint"] = bool(
            _clean_text(evidence_reference_mapping.get("retrieval_fingerprint"))
        )

    return trust_signals


def _iter_pattern_projection_specs():
    from .heuristic_extractor import extract_heuristic_pattern
    from .structure_extractor import extract_structure_pattern
    from .tactic_extractor import extract_tactic_pattern

    return (
        ("tactic", extract_tactic_pattern),
        ("structure", extract_structure_pattern),
        ("heuristic", extract_heuristic_pattern),
    )


def _pattern_version_id(pattern_id: str, version: int) -> str:
    return f"{pattern_id}@v{version}"


def _pattern_projection_kind(pattern_id: Any) -> str:
    normalized_pattern_id = _clean_text(pattern_id)
    prefix = normalized_pattern_id.split("-", 1)[0]
    return _PATTERN_PROJECTION_KIND_BY_PREFIX.get(prefix, "unknown")


def _dedupe_json_items(items: list[Any]) -> list[Any]:
    deduplicated: list[Any] = []
    seen_keys: set[str] = set()
    for item in items:
        json_key = _json_key(item)
        if json_key in seen_keys:
            continue
        seen_keys.add(json_key)
        deduplicated.append(_clone_json_value(item))
    return deduplicated


def _pattern_record_sort_key(pattern_record: Mapping[str, Any]) -> tuple[str, str, int]:
    pattern_id = _clean_text(pattern_record.get("pattern_id"))
    version = _lookup_optional_int(pattern_record.get("version")) or 0
    return (
        _clean_text(
            pattern_record.get("projection_kind"),
            default=_pattern_projection_kind(pattern_id),
        )
        or _pattern_projection_kind(pattern_id),
        pattern_id,
        version,
    )


def _pattern_contributor_sort_key(projected_pattern: Mapping[str, Any]) -> tuple[float, int, int, int, str]:
    confidence_score = _coerce_numeric(projected_pattern.get("confidence_score")) or 0.0
    confidence_label = _clean_text(projected_pattern.get("confidence"), default="low")
    status = _clean_text(projected_pattern.get("status"), default="candidate")
    source_kind = _clean_text(projected_pattern.get("source_kind"), default="unknown")
    source_entry_id = _clean_text(projected_pattern.get("source_entry_id"))
    return (
        -confidence_score,
        -_CONFIDENCE_RANK.get(confidence_label, 0),
        -_STATUS_RANK.get(status, 0),
        -_SOURCE_KIND_RANK.get(source_kind, 0),
        source_entry_id,
    )


def _build_pattern_store_contributor(projected_pattern: Mapping[str, Any]) -> dict[str, Any]:
    origin_metadata = (
        projected_pattern.get("origin_metadata")
        if isinstance(projected_pattern.get("origin_metadata"), Mapping)
        else {}
    )
    source_ref = (
        origin_metadata.get("source_ref")
        if isinstance(origin_metadata.get("source_ref"), Mapping)
        else {}
    )
    retrieval_context = (
        origin_metadata.get("retrieval_context")
        if isinstance(origin_metadata.get("retrieval_context"), Mapping)
        else {}
    )
    traceability = (
        origin_metadata.get("traceability")
        if isinstance(origin_metadata.get("traceability"), Mapping)
        else {}
    )
    return {
        "source_entry_id": _clean_text(projected_pattern.get("source_entry_id")),
        "source_entry_type": _clean_text(projected_pattern.get("source_entry_type")),
        "source_kind": _clean_text(projected_pattern.get("source_kind"), default="unknown")
        or "unknown",
        "confidence": _clean_text(projected_pattern.get("confidence"), default="medium") or "medium",
        "confidence_score": _coerce_numeric(projected_pattern.get("confidence_score")) or 0.0,
        "status": _clean_text(projected_pattern.get("status"), default="candidate") or "candidate",
        "evidence_count": _lookup_optional_int(projected_pattern.get("evidence_count")) or 0,
        "source_id": _clean_text(source_ref.get("source_id")) or None,
        "canonical_location": _clean_text(
            source_ref.get("canonical_location"),
            default=source_ref.get("location"),
        )
        or None,
        "retrieval_id": _clean_text(retrieval_context.get("retrieval_id")) or None,
        "research_artifact_ref": _clean_text(traceability.get("research_artifact_ref")) or None,
        "raw_artifact_refs": _normalize_string_list(traceability.get("raw_artifact_refs"), default=[]),
        "evidence_reference": _clone_json_value(projected_pattern.get("evidence_reference"))
        if isinstance(projected_pattern.get("evidence_reference"), Mapping)
        else None,
        "origin_metadata": _clone_json_value(origin_metadata) if origin_metadata else None,
    }


def _build_pattern_store_snapshot_body(projected_patterns: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_patterns = sorted(
        (_clone_json_value(projected_pattern) for projected_pattern in projected_patterns),
        key=_pattern_contributor_sort_key,
    )
    if not sorted_patterns:
        raise ValueError("pattern snapshots require at least one projected pattern")

    representative_pattern = sorted_patterns[0]
    projected_pattern = (
        representative_pattern.get("pattern")
        if isinstance(representative_pattern.get("pattern"), Mapping)
        else {}
    )
    canonical_form = (
        projected_pattern.get("canonical_form")
        if isinstance(projected_pattern.get("canonical_form"), Mapping)
        else {}
    )
    contributors = [
        _build_pattern_store_contributor(projected_pattern)
        for projected_pattern in sorted_patterns
    ]
    evidence_references = _dedupe_json_items(
        [
            contributor["evidence_reference"]
            for contributor in contributors
            if isinstance(contributor.get("evidence_reference"), Mapping)
        ]
    )
    source_entry_ids = [
        contributor["source_entry_id"]
        for contributor in contributors
        if _clean_text(contributor.get("source_entry_id"))
    ]
    source_entry_types = list(
        dict.fromkeys(
            contributor["source_entry_type"]
            for contributor in contributors
            if _clean_text(contributor.get("source_entry_type"))
        )
    )
    source_kinds = list(
        dict.fromkeys(
            contributor["source_kind"]
            for contributor in contributors
            if _clean_text(contributor.get("source_kind"))
        )
    )
    source_ids = list(
        dict.fromkeys(
            contributor["source_id"]
            for contributor in contributors
            if _clean_text(contributor.get("source_id"))
        )
    )
    canonical_locations = list(
        dict.fromkeys(
            contributor["canonical_location"]
            for contributor in contributors
            if _clean_text(contributor.get("canonical_location"))
        )
    )
    retrieval_ids = list(
        dict.fromkeys(
            contributor["retrieval_id"]
            for contributor in contributors
            if _clean_text(contributor.get("retrieval_id"))
        )
    )
    research_artifact_refs = list(
        dict.fromkeys(
            contributor["research_artifact_ref"]
            for contributor in contributors
            if _clean_text(contributor.get("research_artifact_ref"))
        )
    )
    raw_artifact_refs = list(
        dict.fromkeys(
            raw_artifact_ref
            for contributor in contributors
            for raw_artifact_ref in _normalize_string_list(
                contributor.get("raw_artifact_refs"),
                default=[],
            )
        )
    )
    derived_from_entry_ids = list(
        dict.fromkeys(
            derived_from_entry_id
            for projected_pattern in sorted_patterns
            for derived_from_entry_id in _normalize_string_list(
                projected_pattern.get("derived_from_entry_ids"),
                default=[],
            )
        )
    )

    snapshot_body = {
        "pattern_id": _clean_text(representative_pattern.get("pattern_id")),
        "projection_kind": _clean_text(
            representative_pattern.get("projection_kind"),
            default=_pattern_projection_kind(representative_pattern.get("pattern_id")),
        )
        or _pattern_projection_kind(representative_pattern.get("pattern_id")),
        "pattern": _clone_json_value(projected_pattern),
        "canonical_label": _clean_text(
            canonical_form.get("canonical_label"),
            default=projected_pattern.get("pattern_label"),
        )
        or _clean_text(projected_pattern.get("pattern_label"), default="pattern"),
        "semantic_signature": _clean_text(canonical_form.get("semantic_signature")) or None,
        "projected_transfer_type": _clean_text(
            projected_pattern.get("transfer_type"),
            default="heuristic",
        )
        or "heuristic",
        "representative_source_entry_id": _clean_text(
            representative_pattern.get("source_entry_id")
        )
        or None,
        "representative_source_entry_type": _clean_text(
            representative_pattern.get("source_entry_type")
        )
        or None,
        "primary_evidence_reference": _clone_json_value(
            representative_pattern.get("evidence_reference")
        )
        if isinstance(representative_pattern.get("evidence_reference"), Mapping)
        else None,
        "evidence_references": evidence_references,
        "contributors": contributors,
        "derived_from_entry_ids": derived_from_entry_ids,
        "provenance": {
            "source_entry_ids": source_entry_ids,
            "source_entry_types": source_entry_types,
            "source_kinds": source_kinds,
            "source_ids": source_ids,
            "canonical_locations": canonical_locations,
            "retrieval_ids": retrieval_ids,
            "research_artifact_refs": research_artifact_refs,
            "raw_artifact_refs": raw_artifact_refs,
        },
    }
    return snapshot_body


def _build_pattern_store_snapshot(projected_patterns: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot_body = _build_pattern_store_snapshot_body(projected_patterns)
    return {
        **snapshot_body,
        "content_fingerprint": _sha256_text(_json_key(snapshot_body)),
    }


def _snapshot_body_from_pattern_record(pattern_record: Mapping[str, Any]) -> dict[str, Any]:
    provenance = (
        pattern_record.get("provenance")
        if isinstance(pattern_record.get("provenance"), Mapping)
        else {}
    )
    return {
        "pattern_id": _clean_text(pattern_record.get("pattern_id")),
        "projection_kind": _clean_text(
            pattern_record.get("projection_kind"),
            default=_pattern_projection_kind(pattern_record.get("pattern_id")),
        )
        or _pattern_projection_kind(pattern_record.get("pattern_id")),
        "pattern": _clone_json_value(pattern_record.get("pattern"))
        if isinstance(pattern_record.get("pattern"), Mapping)
        else {},
        "canonical_label": _clean_text(pattern_record.get("canonical_label")) or None,
        "semantic_signature": _clean_text(pattern_record.get("semantic_signature")) or None,
        "projected_transfer_type": _clean_text(
            pattern_record.get("projected_transfer_type"),
            default="heuristic",
        )
        or "heuristic",
        "representative_source_entry_id": _clean_text(
            pattern_record.get("representative_source_entry_id")
        )
        or None,
        "representative_source_entry_type": _clean_text(
            pattern_record.get("representative_source_entry_type")
        )
        or None,
        "primary_evidence_reference": _clone_json_value(
            pattern_record.get("primary_evidence_reference")
        )
        if isinstance(pattern_record.get("primary_evidence_reference"), Mapping)
        else None,
        "evidence_references": _clone_json_value(
            pattern_record.get("evidence_references")
            if isinstance(pattern_record.get("evidence_references"), list)
            else []
        ),
        "contributors": _clone_json_value(
            pattern_record.get("contributors")
            if isinstance(pattern_record.get("contributors"), list)
            else []
        ),
        "derived_from_entry_ids": _normalize_string_list(
            pattern_record.get("derived_from_entry_ids"),
            default=[],
        ),
        "provenance": {
            "source_entry_ids": _normalize_string_list(
                provenance.get("source_entry_ids"),
                default=[],
            ),
            "source_entry_types": _normalize_string_list(
                provenance.get("source_entry_types"),
                default=[],
            ),
            "source_kinds": _normalize_string_list(
                provenance.get("source_kinds"),
                default=[],
            ),
            "source_ids": _normalize_string_list(
                provenance.get("source_ids"),
                default=[],
            ),
            "canonical_locations": _normalize_string_list(
                provenance.get("canonical_locations"),
                default=[],
            ),
            "retrieval_ids": _normalize_string_list(
                provenance.get("retrieval_ids"),
                default=[],
            ),
            "research_artifact_refs": _normalize_string_list(
                provenance.get("research_artifact_refs"),
                default=[],
            ),
            "raw_artifact_refs": _normalize_string_list(
                provenance.get("raw_artifact_refs"),
                default=[],
            ),
        },
    }


def _build_pattern_change_history(
    *,
    current_snapshot: Mapping[str, Any],
    previous_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if previous_record is None:
        return {
            "change_type": "initial",
            "previous_version": None,
            "previous_pattern_version_id": None,
            "changed_fields": [],
            "previous_content_fingerprint": None,
        }

    previous_body = _snapshot_body_from_pattern_record(previous_record)
    current_body = _snapshot_body_from_pattern_record(current_snapshot)
    changed_fields = [
        field_name
        for field_name in sorted(current_body)
        if previous_body.get(field_name) != current_body.get(field_name)
    ]
    provenance_only_fields = {
        "contributors",
        "derived_from_entry_ids",
        "evidence_references",
        "primary_evidence_reference",
        "provenance",
        "representative_source_entry_id",
        "representative_source_entry_type",
    }
    change_type = (
        "provenance_update"
        if changed_fields and all(field_name in provenance_only_fields for field_name in changed_fields)
        else "pattern_revision"
    )
    return {
        "change_type": change_type,
        "previous_version": _lookup_optional_int(previous_record.get("version")),
        "previous_pattern_version_id": _clean_text(previous_record.get("pattern_version_id"))
        or None,
        "changed_fields": changed_fields,
        "previous_content_fingerprint": _clean_text(
            previous_record.get("content_fingerprint")
        )
        or _sha256_text(_json_key(previous_body)),
    }


def _build_pattern_version_record(
    snapshot: Mapping[str, Any],
    *,
    version: int,
    timestamp: str,
    ingest_source: str,
    previous_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    history = _build_pattern_change_history(
        current_snapshot=snapshot,
        previous_record=previous_record,
    )
    content_fingerprint = _clean_text(snapshot.get("content_fingerprint")) or _sha256_text(
        _json_key(_snapshot_body_from_pattern_record(snapshot))
    )
    return {
        "pattern_version_id": _pattern_version_id(
            _clean_text(snapshot.get("pattern_id")),
            version,
        ),
        "pattern_id": _clean_text(snapshot.get("pattern_id")),
        "version": version,
        "projection_kind": _clean_text(snapshot.get("projection_kind")) or _pattern_projection_kind(
            snapshot.get("pattern_id")
        ),
        "pattern": _clone_json_value(snapshot.get("pattern"))
        if isinstance(snapshot.get("pattern"), Mapping)
        else {},
        "canonical_label": _clean_text(snapshot.get("canonical_label")) or None,
        "semantic_signature": _clean_text(snapshot.get("semantic_signature")) or None,
        "projected_transfer_type": _clean_text(
            snapshot.get("projected_transfer_type"),
            default="heuristic",
        )
        or "heuristic",
        "representative_source_entry_id": _clean_text(
            snapshot.get("representative_source_entry_id")
        )
        or None,
        "representative_source_entry_type": _clean_text(
            snapshot.get("representative_source_entry_type")
        )
        or None,
        "primary_evidence_reference": _clone_json_value(snapshot.get("primary_evidence_reference"))
        if isinstance(snapshot.get("primary_evidence_reference"), Mapping)
        else None,
        "evidence_references": _clone_json_value(
            snapshot.get("evidence_references")
            if isinstance(snapshot.get("evidence_references"), list)
            else []
        ),
        "contributors": _clone_json_value(
            snapshot.get("contributors")
            if isinstance(snapshot.get("contributors"), list)
            else []
        ),
        "derived_from_entry_ids": _normalize_string_list(
            snapshot.get("derived_from_entry_ids"),
            default=[],
        ),
        "provenance": _clone_json_value(snapshot.get("provenance"))
        if isinstance(snapshot.get("provenance"), Mapping)
        else {},
        "content_fingerprint": content_fingerprint,
        "created_at": timestamp,
        "last_seen_at": timestamp,
        "ingest_source": ingest_source,
        "history": history,
    }


def _normalize_existing_pattern_record(
    raw_pattern_record: Mapping[str, Any],
    *,
    default_timestamp: str,
) -> dict[str, Any] | None:
    pattern_id = _clean_text(raw_pattern_record.get("pattern_id"))
    version = _lookup_optional_int(raw_pattern_record.get("version"))
    if not pattern_id or version is None or version < 1:
        return None

    normalized = _clone_json_value(raw_pattern_record)
    normalized["pattern_id"] = pattern_id
    normalized["version"] = version
    normalized["pattern_version_id"] = _clean_text(
        normalized.get("pattern_version_id"),
        default=_pattern_version_id(pattern_id, version),
    ) or _pattern_version_id(pattern_id, version)
    normalized["projection_kind"] = _clean_text(
        normalized.get("projection_kind"),
        default=_pattern_projection_kind(pattern_id),
    ) or _pattern_projection_kind(pattern_id)
    normalized["created_at"] = _normalize_iso_timestamp(
        normalized.get("created_at"),
        field_name=f"pattern_records.{pattern_id}.created_at",
        default=default_timestamp,
    )
    normalized["last_seen_at"] = _normalize_iso_timestamp(
        normalized.get("last_seen_at"),
        field_name=f"pattern_records.{pattern_id}.last_seen_at",
        default=normalized["created_at"],
    )
    normalized["ingest_source"] = _normalize_ingest_source(normalized.get("ingest_source"))
    if not isinstance(normalized.get("history"), Mapping):
        normalized["history"] = {
            "change_type": "initial" if version == 1 else "pattern_revision",
            "previous_version": version - 1 if version > 1 else None,
            "previous_pattern_version_id": (
                _pattern_version_id(pattern_id, version - 1) if version > 1 else None
            ),
            "changed_fields": [],
            "previous_content_fingerprint": None,
        }
    normalized["content_fingerprint"] = _clean_text(
        normalized.get("content_fingerprint")
    ) or _sha256_text(_json_key(_snapshot_body_from_pattern_record(normalized)))
    return normalized


def _build_pattern_store_indexes(
    pattern_records: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, dict[str, Any]], dict[str, list[str]]]:
    pattern_record_index: dict[str, int] = {}
    pattern_id_index: dict[str, dict[str, Any]] = {}
    pattern_provenance_index: dict[str, dict[str, list[str]]] = {
        field_name: {} for field_name in PATTERN_STORE_PROVENANCE_INDEX_FIELDS
    }

    for index, pattern_record in enumerate(pattern_records):
        pattern_version_id = _clean_text(pattern_record.get("pattern_version_id"))
        pattern_id = _clean_text(pattern_record.get("pattern_id"))
        version = _lookup_optional_int(pattern_record.get("version")) or 0
        if pattern_version_id:
            pattern_record_index[pattern_version_id] = index

        bucket = pattern_id_index.setdefault(
            pattern_id,
            {
                "pattern_id": pattern_id,
                "projection_kind": _clean_text(
                    pattern_record.get("projection_kind"),
                    default=_pattern_projection_kind(pattern_id),
                )
                or _pattern_projection_kind(pattern_id),
                "versions": [],
                "version_ids": [],
                "latest_version": None,
                "latest_pattern_version_id": None,
            },
        )
        bucket["versions"].append(version)
        bucket["version_ids"].append(pattern_version_id)
        bucket["latest_version"] = version
        bucket["latest_pattern_version_id"] = pattern_version_id

        provenance = (
            pattern_record.get("provenance")
            if isinstance(pattern_record.get("provenance"), Mapping)
            else {}
        )
        for field_name, record_field in _PATTERN_PROVENANCE_INDEX_TO_RECORD_FIELD.items():
            values = _normalize_string_list(provenance.get(record_field), default=[])
            for value in values:
                version_ids = pattern_provenance_index[field_name].setdefault(value, [])
                if pattern_version_id not in version_ids:
                    version_ids.append(pattern_version_id)

    return pattern_record_index, pattern_id_index, pattern_provenance_index


def _build_pattern_store_payload(
    pattern_records: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered_pattern_records = sorted(
        (_clone_json_value(pattern_record) for pattern_record in pattern_records),
        key=_pattern_record_sort_key,
    )
    (
        pattern_record_index,
        pattern_id_index,
        pattern_provenance_index,
    ) = _build_pattern_store_indexes(ordered_pattern_records)
    return {
        "pattern_store_schema_version": PATTERN_STORE_SCHEMA_VERSION,
        "pattern_store_type": CANONICAL_PATTERN_STORE_TYPE,
        "pattern_record_count": len(ordered_pattern_records),
        "pattern_records": ordered_pattern_records,
        "pattern_record_index": pattern_record_index,
        "pattern_id_index": pattern_id_index,
        "pattern_provenance_index": pattern_provenance_index,
    }


def _build_initial_pattern_store(
    records: list[dict[str, Any]],
    *,
    timestamp: str,
    ingest_source: str,
) -> dict[str, Any]:
    pattern_groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for projection_kind, extractor in _iter_pattern_projection_specs():
            projected_pattern = _clone_json_value(extractor(record))
            projected_pattern["projection_kind"] = projection_kind
            pattern_groups.setdefault(projected_pattern["pattern_id"], []).append(projected_pattern)

    initial_pattern_records = [
        _build_pattern_version_record(
            _build_pattern_store_snapshot(projected_patterns),
            version=1,
            timestamp=timestamp,
            ingest_source=ingest_source,
        )
        for _, projected_patterns in sorted(pattern_groups.items())
    ]
    return _build_pattern_store_payload(initial_pattern_records)


def _update_pattern_store(
    records: list[dict[str, Any]],
    *,
    existing_pattern_records: list[dict[str, Any]],
    timestamp: str,
    ingest_source: str,
) -> dict[str, Any]:
    if not existing_pattern_records:
        return _build_initial_pattern_store(
            records,
            timestamp=timestamp,
            ingest_source=ingest_source,
        )

    pattern_groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for projection_kind, extractor in _iter_pattern_projection_specs():
            projected_pattern = _clone_json_value(extractor(record))
            projected_pattern["projection_kind"] = projection_kind
            pattern_groups.setdefault(projected_pattern["pattern_id"], []).append(projected_pattern)

    existing_history_by_pattern_id: dict[str, list[dict[str, Any]]] = {}
    for existing_pattern_record in existing_pattern_records:
        pattern_id = _clean_text(existing_pattern_record.get("pattern_id"))
        if not pattern_id:
            continue
        existing_history_by_pattern_id.setdefault(pattern_id, []).append(
            _clone_json_value(existing_pattern_record)
        )
    for pattern_id in existing_history_by_pattern_id:
        existing_history_by_pattern_id[pattern_id].sort(key=_pattern_record_sort_key)

    updated_pattern_records: list[dict[str, Any]] = []
    all_pattern_ids = sorted(set(existing_history_by_pattern_id) | set(pattern_groups))
    for pattern_id in all_pattern_ids:
        pattern_history = existing_history_by_pattern_id.get(pattern_id, [])
        current_projected_patterns = pattern_groups.get(pattern_id)
        if current_projected_patterns is None:
            updated_pattern_records.extend(pattern_history)
            continue

        current_snapshot = _build_pattern_store_snapshot(current_projected_patterns)
        latest_record = pattern_history[-1] if pattern_history else None
        latest_fingerprint = _clean_text(
            latest_record.get("content_fingerprint") if latest_record else None
        )
        if latest_record is not None and latest_fingerprint == current_snapshot["content_fingerprint"]:
            refreshed_latest_record = _clone_json_value(latest_record)
            refreshed_latest_record["last_seen_at"] = timestamp
            refreshed_latest_record["ingest_source"] = ingest_source
            pattern_history = pattern_history[:-1] + [refreshed_latest_record]
        else:
            next_version = (
                (_lookup_optional_int(latest_record.get("version")) if latest_record else 0) + 1
            )
            pattern_history = pattern_history + [
                _build_pattern_version_record(
                    current_snapshot,
                    version=next_version,
                    timestamp=timestamp,
                    ingest_source=ingest_source,
                    previous_record=latest_record,
                )
            ]
        updated_pattern_records.extend(pattern_history)

    return _build_pattern_store_payload(updated_pattern_records)


def _normalize_storage_metadata_entry(
    raw_value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    metadata = _normalize_required_mapping(raw_value, field_name=field_name)
    metadata["ingested_at"] = _normalize_iso_timestamp(
        metadata.get("ingested_at"),
        field_name=f"{field_name}.ingested_at",
    )
    metadata["updated_at"] = _normalize_iso_timestamp(
        metadata.get("updated_at"),
        field_name=f"{field_name}.updated_at",
    )
    metadata["ingest_source"] = _normalize_ingest_source(
        metadata.get("ingest_source")
    )
    metadata["trust_signals"] = _normalize_required_mapping(
        metadata.get("trust_signals"),
        field_name=f"{field_name}.trust_signals",
    )
    return metadata


def _build_default_research_corpus_storage(*, timestamp: str) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_CORPUS_STORAGE_SCHEMA_VERSION,
        "storage_type": CANONICAL_RESEARCH_CORPUS_STORAGE_TYPE,
        "created_at": timestamp,
        "updated_at": timestamp,
        "record_count": 0,
        "records": [],
        "record_index": {},
        "record_metadata_index": {},
        "ingestion_history": [],
        **_build_pattern_store_payload([]),
    }


def _load_existing_research_corpus_storage(
    storage_path: Path,
) -> dict[str, Any]:
    if not storage_path.exists():
        return _build_default_research_corpus_storage(timestamp=_now_utc_timestamp())

    raw_payload = json.loads(storage_path.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, Mapping):
        raise ValueError("existing corpus storage must be a JSON object")

    schema_version = raw_payload.get("schema_version")
    if schema_version not in SUPPORTED_RESEARCH_CORPUS_STORAGE_SCHEMA_VERSIONS:
        raise ValueError(
            "existing corpus storage schema_version is unsupported: "
            f"{schema_version!r}"
        )
    storage_type = _clean_text(raw_payload.get("storage_type"))
    if storage_type != CANONICAL_RESEARCH_CORPUS_STORAGE_TYPE:
        raise ValueError(
            "existing corpus storage type is unsupported: "
            f"{storage_type!r}"
        )

    records_raw = raw_payload.get("records")
    if not isinstance(records_raw, list):
        raise ValueError("existing corpus storage records must be a list")
    metadata_index_raw = raw_payload.get("record_metadata_index")
    if metadata_index_raw is None:
        metadata_index_raw = {}
    if not isinstance(metadata_index_raw, Mapping):
        raise ValueError("existing corpus storage record_metadata_index must be a mapping")

    normalized_records: list[dict[str, Any]] = []
    normalized_metadata_index: dict[str, dict[str, Any]] = {}
    for index, raw_record in enumerate(records_raw):
        if not isinstance(raw_record, Mapping):
            raise ValueError(
                f"existing corpus storage records[{index}] must be a mapping"
            )
        normalized_record = _normalize_research_corpus_record(raw_record, index=index)
        entry_id = normalized_record["entry_id"]
        normalized_records.append(normalized_record)

        raw_metadata_entry = metadata_index_raw.get(entry_id)
        if raw_metadata_entry is not None:
            normalized_metadata_index[entry_id] = _normalize_storage_metadata_entry(
                raw_metadata_entry,
                field_name=f"record_metadata_index.{entry_id}",
            )

    normalized_history: list[dict[str, Any]] = []
    history_rows = raw_payload.get("ingestion_history")
    if isinstance(history_rows, list):
        for history_row in history_rows:
            if isinstance(history_row, Mapping):
                normalized_history.append(_clone_json_value(history_row))

    created_at = _normalize_iso_timestamp(
        raw_payload.get("created_at"),
        field_name="existing_storage.created_at",
        default=_now_utc_timestamp(),
    )
    updated_at = _normalize_iso_timestamp(
        raw_payload.get("updated_at"),
        field_name="existing_storage.updated_at",
        default=created_at,
    )

    raw_pattern_records = raw_payload.get("pattern_records")
    normalized_pattern_records: list[dict[str, Any]] = []
    if isinstance(raw_pattern_records, list):
        for raw_pattern_record in raw_pattern_records:
            if not isinstance(raw_pattern_record, Mapping):
                continue
            normalized_pattern_record = _normalize_existing_pattern_record(
                raw_pattern_record,
                default_timestamp=updated_at,
            )
            if normalized_pattern_record is not None:
                normalized_pattern_records.append(normalized_pattern_record)

    if normalized_pattern_records:
        pattern_store_payload = _build_pattern_store_payload(normalized_pattern_records)
    else:
        pattern_store_payload = _build_initial_pattern_store(
            normalized_records,
            timestamp=updated_at,
            ingest_source="storage_backfill",
        )

    return {
        "schema_version": RESEARCH_CORPUS_STORAGE_SCHEMA_VERSION,
        "storage_type": CANONICAL_RESEARCH_CORPUS_STORAGE_TYPE,
        "created_at": created_at,
        "updated_at": updated_at,
        "record_count": len(normalized_records),
        "records": normalized_records,
        "record_index": {
            record["entry_id"]: index for index, record in enumerate(normalized_records)
        },
        "record_metadata_index": normalized_metadata_index,
        "ingestion_history": normalized_history,
        **pattern_store_payload,
    }


def ingest_pattern_extraction_inputs(
    normalized_records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    *,
    corpus_storage_path: str | Path,
    ingestion_timestamp: str | None = None,
    ingest_source: str | None = None,
) -> dict[str, Any]:
    """Validate and persist normalized pattern-extraction records to corpus storage."""

    if not isinstance(normalized_records, (list, tuple)):
        raise TypeError("normalized_records must be a list or tuple")

    timestamp = _normalize_iso_timestamp(
        ingestion_timestamp,
        field_name="ingestion_timestamp",
        default=_now_utc_timestamp(),
    )
    normalized_source = _normalize_ingest_source(ingest_source)
    storage_path = _normalize_research_storage_path(corpus_storage_path)

    validation_errors: list[str] = []
    candidate_records: list[dict[str, Any]] = []
    for index, raw_record in enumerate(normalized_records):
        if not isinstance(raw_record, Mapping):
            validation_errors.append(
                f"normalized_records[{index}] must be a mapping"
            )
            continue
        try:
            candidate_records.append(
                _normalize_research_corpus_record(raw_record, index=index)
            )
        except (TypeError, ValueError) as exc:
            validation_errors.append(str(exc))

    if validation_errors:
        raise ResearchCorpusValidationError(validation_errors)

    existing_storage = _load_existing_research_corpus_storage(storage_path)
    records_by_id: dict[str, dict[str, Any]] = {
        record["entry_id"]: _clone_json_value(record)
        for record in existing_storage.get("records", [])
        if isinstance(record, Mapping)
    }
    metadata_index: dict[str, dict[str, Any]] = {
        _clean_text(entry_id): _clone_json_value(metadata)
        for entry_id, metadata in existing_storage.get("record_metadata_index", {}).items()
        if _clean_text(entry_id) and isinstance(metadata, Mapping)
    }
    existing_order = [record["entry_id"] for record in existing_storage.get("records", [])]

    inserted_entry_ids: list[str] = []
    updated_entry_ids: list[str] = []
    for record in candidate_records:
        entry_id = record["entry_id"]
        was_existing = entry_id in records_by_id
        records_by_id[entry_id] = record
        if not was_existing:
            inserted_entry_ids.append(entry_id)
            existing_order.append(entry_id)
        else:
            updated_entry_ids.append(entry_id)

        previous_metadata = metadata_index.get(entry_id, {})
        previous_ingested_at = _clean_text(previous_metadata.get("ingested_at"))
        metadata_index[entry_id] = {
            "ingested_at": previous_ingested_at or timestamp,
            "updated_at": timestamp,
            "ingest_source": normalized_source,
            "trust_signals": _build_research_corpus_trust_signals(record),
        }

    ordered_entry_ids = [entry_id for entry_id in existing_order if entry_id in records_by_id]
    ordered_records = [records_by_id[entry_id] for entry_id in ordered_entry_ids]
    normalized_metadata_index = {
        entry_id: metadata_index[entry_id] for entry_id in ordered_entry_ids if entry_id in metadata_index
    }

    ingestion_history = _clone_json_value(existing_storage.get("ingestion_history") or [])
    if not isinstance(ingestion_history, list):
        ingestion_history = []
    ingestion_history.append(
        {
            "ingested_at": timestamp,
            "ingest_source": normalized_source,
            "inserted_entry_ids": inserted_entry_ids,
            "updated_entry_ids": updated_entry_ids,
            "total_records_after_ingest": len(ordered_records),
        }
    )
    if len(ingestion_history) > 100:
        ingestion_history = ingestion_history[-100:]

    pattern_store_payload = _update_pattern_store(
        ordered_records,
        existing_pattern_records=[
            _clone_json_value(pattern_record)
            for pattern_record in existing_storage.get("pattern_records", [])
            if isinstance(pattern_record, Mapping)
        ],
        timestamp=timestamp,
        ingest_source=normalized_source,
    )

    storage_payload = {
        "schema_version": RESEARCH_CORPUS_STORAGE_SCHEMA_VERSION,
        "storage_type": CANONICAL_RESEARCH_CORPUS_STORAGE_TYPE,
        "created_at": existing_storage.get("created_at"),
        "updated_at": timestamp,
        "record_count": len(ordered_records),
        "records": ordered_records,
        "record_index": {
            entry_id: index for index, entry_id in enumerate(ordered_entry_ids)
        },
        "record_metadata_index": normalized_metadata_index,
        "ingestion_history": ingestion_history,
        **pattern_store_payload,
    }

    storage_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = storage_path.with_suffix(f"{storage_path.suffix}.tmp")
    serialized_payload = json.dumps(storage_payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    temporary_path.write_text(serialized_payload, encoding="utf-8")
    temporary_path.replace(storage_path)

    return _clone_json_value(storage_payload)


def load_research_corpus_storage(
    *,
    corpus_storage_path: str | Path,
) -> dict[str, Any]:
    """Load the persisted research corpus storage bundle, including pattern-store indexes."""

    storage_path = _normalize_research_storage_path(corpus_storage_path)
    return _clone_json_value(_load_existing_research_corpus_storage(storage_path))


def query_persisted_patterns(
    *,
    corpus_storage_path: str | Path,
    pattern_id: str | None = None,
    version: int | None = None,
    latest_only: bool = False,
    source_entry_id: str | None = None,
    source_id: str | None = None,
    canonical_location: str | None = None,
    retrieval_id: str | None = None,
    research_artifact_ref: str | None = None,
    raw_artifact_ref: str | None = None,
) -> dict[str, Any]:
    """Query persisted pattern versions by identity and provenance filters."""

    storage_payload = load_research_corpus_storage(corpus_storage_path=corpus_storage_path)
    pattern_records = storage_payload.get("pattern_records", [])
    if not isinstance(pattern_records, list):
        pattern_records = []
    pattern_record_index = (
        storage_payload.get("pattern_record_index")
        if isinstance(storage_payload.get("pattern_record_index"), Mapping)
        else {}
    )
    pattern_id_index = (
        storage_payload.get("pattern_id_index")
        if isinstance(storage_payload.get("pattern_id_index"), Mapping)
        else {}
    )
    pattern_provenance_index = (
        storage_payload.get("pattern_provenance_index")
        if isinstance(storage_payload.get("pattern_provenance_index"), Mapping)
        else {}
    )

    candidate_version_ids: set[str] = set()
    if pattern_id:
        pattern_bucket = (
            pattern_id_index.get(pattern_id)
            if isinstance(pattern_id_index.get(pattern_id), Mapping)
            else {}
        )
        if version is not None:
            requested_version_id = _pattern_version_id(pattern_id, version)
            candidate_version_ids.add(requested_version_id)
        else:
            candidate_version_ids.update(
                _normalize_string_list(pattern_bucket.get("version_ids"), default=[])
            )
    else:
        candidate_version_ids.update(
            _clean_text(pattern_record.get("pattern_version_id"))
            for pattern_record in pattern_records
            if isinstance(pattern_record, Mapping)
            and _clean_text(pattern_record.get("pattern_version_id"))
        )

    provenance_filters = {
        "source_entry_id": _clean_text(source_entry_id),
        "source_id": _clean_text(source_id),
        "canonical_location": _clean_text(canonical_location),
        "retrieval_id": _clean_text(retrieval_id),
        "research_artifact_ref": _clean_text(research_artifact_ref),
        "raw_artifact_ref": _clean_text(raw_artifact_ref),
    }
    for field_name, field_value in provenance_filters.items():
        if not field_value:
            continue
        field_index = (
            pattern_provenance_index.get(field_name)
            if isinstance(pattern_provenance_index.get(field_name), Mapping)
            else {}
        )
        matching_version_ids = set(
            _normalize_string_list(field_index.get(field_value), default=[])
        )
        candidate_version_ids &= matching_version_ids

    matched_pattern_records: list[dict[str, Any]] = []
    for pattern_version_id in sorted(candidate_version_ids):
        record_index = _lookup_optional_int(pattern_record_index.get(pattern_version_id))
        if record_index is None or record_index < 0 or record_index >= len(pattern_records):
            continue
        pattern_record = pattern_records[record_index]
        if not isinstance(pattern_record, Mapping):
            continue
        pattern_record_version = _lookup_optional_int(pattern_record.get("version"))
        if version is not None and pattern_record_version != version:
            continue
        matched_pattern_records.append(_clone_json_value(pattern_record))

    if latest_only:
        latest_by_pattern_id: dict[str, dict[str, Any]] = {}
        for pattern_record in matched_pattern_records:
            matched_pattern_id = _clean_text(pattern_record.get("pattern_id"))
            existing = latest_by_pattern_id.get(matched_pattern_id)
            if existing is None or (_lookup_optional_int(existing.get("version")) or 0) < (
                _lookup_optional_int(pattern_record.get("version")) or 0
            ):
                latest_by_pattern_id[matched_pattern_id] = pattern_record
        matched_pattern_records = sorted(
            latest_by_pattern_id.values(),
            key=_pattern_record_sort_key,
        )
    else:
        matched_pattern_records.sort(key=_pattern_record_sort_key)

    return {
        "storage_type": CANONICAL_RESEARCH_CORPUS_STORAGE_TYPE,
        "schema_version": RESEARCH_CORPUS_STORAGE_SCHEMA_VERSION,
        "pattern_store_type": CANONICAL_PATTERN_STORE_TYPE,
        "pattern_store_schema_version": PATTERN_STORE_SCHEMA_VERSION,
        "filters": {
            "pattern_id": _clean_text(pattern_id) or None,
            "version": version,
            "latest_only": latest_only,
            **{field_name: field_value or None for field_name, field_value in provenance_filters.items()},
        },
        "match_count": len(matched_pattern_records),
        "pattern_versions": matched_pattern_records,
    }


def lookup_persisted_pattern(
    *,
    corpus_storage_path: str | Path,
    pattern_id: str,
    version: int | None = None,
) -> dict[str, Any] | None:
    """Load one persisted pattern version by stable pattern_id and optional version."""

    query_result = query_persisted_patterns(
        corpus_storage_path=corpus_storage_path,
        pattern_id=pattern_id,
        version=version,
        latest_only=version is None,
    )
    matched_pattern_versions = query_result.get("pattern_versions", [])
    if not isinstance(matched_pattern_versions, list) or not matched_pattern_versions:
        return None
    return _clone_json_value(matched_pattern_versions[0])
