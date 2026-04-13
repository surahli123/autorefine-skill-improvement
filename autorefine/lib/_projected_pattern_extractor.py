from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from ._shared_text import (
    clean_identifier as _clean_identifier,
    clean_text as _clean_text,
)


CANONICAL_PROJECTED_PATTERN_SCHEMA_VERSION = 1
CANONICAL_PROJECTED_PATTERN_EVIDENCE_REFERENCE_SCHEMA_VERSION = 1
CANONICAL_PROJECTED_PATTERN_ORIGIN_METADATA_SCHEMA_VERSION = 1
CANONICAL_PROJECTED_TRANSFER_TYPES = ("positive_pattern", "anti_pattern", "heuristic")
CANONICAL_PROJECTED_ENTRY_TYPES = (
    "pattern_observation",
    "case_study",
    "meta_learning_rule",
    "preference_signal",
    "mutation_hypothesis",
)
CANONICAL_PROJECTION_FIELDS = (
    "pattern_type_tactic",
    "pattern_type_structure",
    "pattern_type_heuristic",
)
CANONICAL_PATTERN_CONFIDENCE_ENGINE_SCHEMA_VERSION = 1
CANONICAL_PATTERN_CONFIDENCE_ENGINE_ID = "deterministic_pattern_confidence_v1"
_CONFIDENCE_LABEL_POINTS = {
    "low": 20,
    "medium": 35,
    "high": 50,
}
_STATUS_POINTS = {
    "candidate": 0,
    "active": 10,
    "superseded": -5,
    "rejected": -15,
}
_PATTERN_CONFIDENCE_MAX_POINTS = 100

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


def _json_key(value: Any) -> str:
    return json.dumps(_clone_json_value(value), sort_keys=True, ensure_ascii=True)


def _normalize_transfer_type(value: Any, *, default: str) -> str:
    normalized = _clean_text(value, default=default)
    if normalized not in CANONICAL_PROJECTED_TRANSFER_TYPES:
        return default
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
    return default


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


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        cleaned = _clean_text(item)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _extract_numeric_delta(observed_delta: Any) -> float | None:
    if isinstance(observed_delta, Mapping):
        preferred_fields = (
            "aggregate_delta",
            "score_delta",
            "delta_score",
            "final_score_delta",
            "delta",
        )
        for field_name in preferred_fields:
            numeric_value = _coerce_numeric(observed_delta.get(field_name))
            if numeric_value is not None:
                return numeric_value

        for nested_key in ("aggregate", "summary", "comparison"):
            nested = observed_delta.get(nested_key)
            if isinstance(nested, Mapping):
                nested_numeric = _extract_numeric_delta(nested)
                if nested_numeric is not None:
                    return nested_numeric

    return _coerce_numeric(observed_delta)


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _primary_evidence_item(normalized_corpus_item: Mapping[str, Any]) -> dict[str, Any] | None:
    evidence = normalized_corpus_item.get("evidence")
    if not isinstance(evidence, list):
        return None

    for item in evidence:
        if isinstance(item, Mapping):
            return _clone_json_value(item)
    return None


def _extract_payload_metadata(payload: Mapping[str, Any], nested_pattern: Mapping[str, Any]) -> dict[str, Any] | None:
    payload_metadata = payload.get("metadata")
    if isinstance(payload_metadata, Mapping):
        return _clone_json_value(payload_metadata)

    nested_metadata = nested_pattern.get("metadata")
    if isinstance(nested_metadata, Mapping):
        return _clone_json_value(nested_metadata)
    return None


def _build_projected_evidence_reference(normalized_corpus_item: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping_or_empty(normalized_corpus_item.get("type_payload"))
    nested_pattern = _mapping_or_empty(payload.get("pattern"))
    reference = _mapping_or_empty(
        payload.get("evidence_reference", nested_pattern.get("evidence_reference"))
    )
    source_ref = _mapping_or_empty(normalized_corpus_item.get("source_ref"))
    retrieval_context = _mapping_or_empty(normalized_corpus_item.get("retrieval_context"))
    primary_evidence = _primary_evidence_item(normalized_corpus_item) or {}

    source_location = _mapping_or_empty(reference.get("source_location"))
    span_mapping = _mapping_or_empty(reference.get("span"))

    line_start = span_mapping.get("line_start")
    line_end = span_mapping.get("line_end")
    char_start = span_mapping.get("char_start")
    char_end = span_mapping.get("char_end")
    byte_start = span_mapping.get("byte_start")
    byte_end = span_mapping.get("byte_end")
    has_span = any(
        value is not None
        for value in (line_start, line_end, char_start, char_end, byte_start, byte_end)
    )

    retrieval_id = _clean_text(retrieval_context.get("retrieval_id"))
    source_id = _clean_text(source_ref.get("source_id"))
    retrieval_fingerprint = _clean_text(reference.get("retrieval_fingerprint"))
    if not retrieval_fingerprint:
        if retrieval_id and source_id:
            retrieval_fingerprint = f"{retrieval_id}:{source_id}"
        else:
            retrieval_fingerprint = retrieval_id

    return {
        "schema_version": int(
            reference.get(
                "schema_version",
                CANONICAL_PROJECTED_PATTERN_EVIDENCE_REFERENCE_SCHEMA_VERSION,
            )
        ),
        "source_hash": _clean_text(
            reference.get("source_hash"),
            default=_clean_text(source_ref.get("content_hash"), default="unknown"),
        )
        or "unknown",
        "source_location": {
            "locator": _clean_text(
                source_location.get("locator", reference.get("locator")),
                default=_clean_text(
                    primary_evidence.get("locator"),
                    default=_clean_text(source_ref.get("locator"), default="unknown"),
                ),
            )
            or "unknown",
            "section_id": _clean_text(
                source_location.get("section_id", reference.get("section_id"))
            )
            or None,
            "heading_path": _normalize_string_list(
                source_location.get("heading_path", reference.get("heading_path"))
            ),
        },
        "quote": _clean_text(
            reference.get("quote"),
            default=_clean_text(
                reference.get("excerpt"),
                default=_clean_text(primary_evidence.get("excerpt")),
            ),
        )
        or None,
        "span": (
            {
                "line_start": line_start,
                "line_end": line_end,
                "char_start": char_start,
                "char_end": char_end,
                "byte_start": byte_start,
                "byte_end": byte_end,
                "offset_basis": _clean_text(
                    span_mapping.get("offset_basis"),
                    default="normalized_text_utf8" if has_span else "unknown",
                )
                or ("normalized_text_utf8" if has_span else "unknown"),
            }
            if has_span
            else None
        ),
        "retrieval_fingerprint": retrieval_fingerprint or None,
    }


def _build_projected_origin_metadata(
    normalized_corpus_item: Mapping[str, Any],
    *,
    evidence_reference: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _mapping_or_empty(normalized_corpus_item.get("type_payload"))
    nested_pattern = _mapping_or_empty(payload.get("pattern"))
    primary_evidence = _primary_evidence_item(normalized_corpus_item)
    evidence_reference_mapping = _mapping_or_empty(evidence_reference)
    source_location = _mapping_or_empty(evidence_reference_mapping.get("source_location"))
    source_ref = _mapping_or_empty(normalized_corpus_item.get("source_ref"))
    retrieval_context = _mapping_or_empty(normalized_corpus_item.get("retrieval_context"))
    traceability = _mapping_or_empty(normalized_corpus_item.get("traceability"))

    primary_snippet: dict[str, Any] | None
    if primary_evidence is not None:
        primary_snippet = primary_evidence
    elif _clean_text(source_location.get("locator")) or _clean_text(evidence_reference_mapping.get("quote")):
        primary_snippet = {
            "kind": "source_excerpt",
            "source": "evidence_reference",
            "locator": _clean_text(source_location.get("locator"), default="unknown") or "unknown",
            "excerpt": _clean_text(evidence_reference_mapping.get("quote")) or None,
        }
        span = evidence_reference_mapping.get("span")
        if isinstance(span, Mapping):
            primary_snippet["span"] = _clone_json_value(span)
    else:
        primary_snippet = None

    return {
        "schema_version": CANONICAL_PROJECTED_PATTERN_ORIGIN_METADATA_SCHEMA_VERSION,
        "source_entry_id": _clean_text(normalized_corpus_item.get("entry_id")),
        "source_entry_type": _clean_text(normalized_corpus_item.get("entry_type")),
        "source_kind": _clean_text(normalized_corpus_item.get("source_kind"), default="unknown")
        or "unknown",
        "source_ref": _clone_json_value(source_ref) if source_ref else None,
        "retrieval_context": _clone_json_value(retrieval_context) if retrieval_context else None,
        "traceability": _clone_json_value(traceability) if traceability else None,
        "payload_metadata": _extract_payload_metadata(payload, nested_pattern),
        "primary_snippet": primary_snippet,
    }


def _stable_pattern_id(
    *,
    entry_id: str,
    entry_type: str,
    pattern: Mapping[str, Any],
    pattern_id_prefix: str,
) -> str:
    canonical_form = _mapping_or_empty(pattern.get("canonical_form"))
    canonical_label = _clean_identifier(
        canonical_form.get("canonical_label"),
        default=_clean_identifier(pattern.get("pattern_label"), default="pattern"),
    ) or "pattern"
    semantic_signature = _clean_text(canonical_form.get("semantic_signature"))
    projected_transfer_type = _clean_text(
        pattern.get("transfer_type"),
        default="heuristic",
    ) or "heuristic"

    if semantic_signature:
        base = {
            "identity_mode": "canonical_pattern",
            "canonical_label": canonical_label,
            "semantic_signature": semantic_signature,
            "projected_transfer_type": projected_transfer_type,
        }
        slug = canonical_label
    else:
        base = {
            "identity_mode": "projected_pattern_fallback",
            "entry_type": entry_type,
            "pattern": _clone_json_value(pattern),
        }
        slug = _clean_identifier(entry_id, default=canonical_label) or canonical_label

    digest = hashlib.sha256(_json_key(base).encode("utf-8")).hexdigest()[:12]
    return f"{pattern_id_prefix}-{slug}-{digest}"


def _has_source_identity(item: Mapping[str, Any]) -> bool:
    source_ref = item.get("source_ref")
    if not isinstance(source_ref, Mapping):
        return False
    return bool(
        _clean_text(item.get("source_kind"))
        and _clean_text(source_ref.get("source_id"))
        and _clean_text(source_ref.get("canonical_location") or source_ref.get("location"))
    )


def _has_retrieval_context(item: Mapping[str, Any]) -> bool:
    retrieval_context = item.get("retrieval_context")
    return bool(
        isinstance(retrieval_context, Mapping)
        and _clean_text(retrieval_context.get("retrieval_id"))
    )


def _has_traceability(item: Mapping[str, Any]) -> bool:
    traceability = item.get("traceability")
    if not isinstance(traceability, Mapping):
        return False
    return bool(
        _clean_text(traceability.get("research_artifact_ref"))
        and _normalize_string_list(traceability.get("raw_artifact_refs"))
    )


def _build_confidence_rule_result(
    *,
    rule_id: str,
    points_awarded: int,
    reason: str,
    signal_value: Any,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "points_awarded": points_awarded,
        "reason": reason,
        "signal_value": _clone_json_value(signal_value),
    }


def _score_pattern_confidence(normalized_corpus_item: Mapping[str, Any]) -> dict[str, Any]:
    confidence_label = _clean_text(normalized_corpus_item.get("confidence"), default="medium")
    base_points = _CONFIDENCE_LABEL_POINTS.get(
        confidence_label,
        _CONFIDENCE_LABEL_POINTS["medium"],
    )

    status = _clean_text(normalized_corpus_item.get("status"), default="candidate")
    status_points = _STATUS_POINTS.get(status, 0)

    evidence_count = len(normalized_corpus_item.get("evidence") or [])
    evidence_points = min(evidence_count, 3) * 5

    has_source_identity = _has_source_identity(normalized_corpus_item)
    has_retrieval_context = _has_retrieval_context(normalized_corpus_item)
    has_traceability = _has_traceability(normalized_corpus_item)

    derived_from_entry_ids = _normalize_string_list(
        normalized_corpus_item.get("derived_from_entry_ids")
    )
    lineage_points = 5 if derived_from_entry_ids else 0

    rule_results = [
        _build_confidence_rule_result(
            rule_id="base_confidence_label",
            points_awarded=base_points,
            reason="Base confidence points come from the normalized corpus confidence label.",
            signal_value=confidence_label or "medium",
        ),
        _build_confidence_rule_result(
            rule_id="status",
            points_awarded=status_points,
            reason="Entry status adjusts how much trust to place in the extracted pattern.",
            signal_value=status or "candidate",
        ),
        _build_confidence_rule_result(
            rule_id="evidence_count",
            points_awarded=evidence_points,
            reason="Evidence points award 5 points per evidence item, capped at three items.",
            signal_value=evidence_count,
        ),
        _build_confidence_rule_result(
            rule_id="source_identity",
            points_awarded=5 if has_source_identity else 0,
            reason="Source identity requires source_kind plus a stable source_ref id/location pair.",
            signal_value=has_source_identity,
        ),
        _build_confidence_rule_result(
            rule_id="retrieval_context",
            points_awarded=5 if has_retrieval_context else 0,
            reason="Retrieval context requires a stable retrieval_id for replay.",
            signal_value=has_retrieval_context,
        ),
        _build_confidence_rule_result(
            rule_id="traceability",
            points_awarded=5 if has_traceability else 0,
            reason="Traceability requires a research artifact ref plus at least one raw artifact ref.",
            signal_value=has_traceability,
        ),
    ]

    total_points = (
        base_points
        + status_points
        + evidence_points
        + (5 if has_source_identity else 0)
        + (5 if has_retrieval_context else 0)
        + (5 if has_traceability else 0)
    )

    if derived_from_entry_ids:
        total_points += lineage_points
        rule_results.append(
            _build_confidence_rule_result(
                rule_id="lineage_support",
                points_awarded=lineage_points,
                reason="Patterns derived from prior entries keep a small lineage-support bonus.",
                signal_value=len(derived_from_entry_ids),
            )
        )

    entry_type = _clean_text(normalized_corpus_item.get("entry_type"))
    type_payload = normalized_corpus_item.get("type_payload")
    payload = type_payload if isinstance(type_payload, Mapping) else {}

    if entry_type == "case_study":
        same_input_set_verified = _coerce_bool(payload.get("same_input_set_verified"), default=False)
        case_study_points = 10 if same_input_set_verified else 0
        total_points += case_study_points
        rule_results.append(
            _build_confidence_rule_result(
                rule_id="case_study_same_input_verification",
                points_awarded=case_study_points,
                reason="Verified same-input case studies get an additional trust bonus.",
                signal_value=same_input_set_verified,
            )
        )
    elif entry_type == "preference_signal":
        confirmation_state = _clean_text(payload.get("confirmation_state")).lower()
        confirmation_points = 5 if confirmation_state == "confirmed" else 0
        total_points += confirmation_points
        rule_results.append(
            _build_confidence_rule_result(
                rule_id="preference_confirmation",
                points_awarded=confirmation_points,
                reason="Confirmed preference signals receive a small confidence bonus.",
                signal_value=confirmation_state or "unknown",
            )
        )

    awarded_points = max(0, min(total_points, _PATTERN_CONFIDENCE_MAX_POINTS))
    return {
        "schema_version": CANONICAL_PATTERN_CONFIDENCE_ENGINE_SCHEMA_VERSION,
        "engine_id": CANONICAL_PATTERN_CONFIDENCE_ENGINE_ID,
        "max_points": _PATTERN_CONFIDENCE_MAX_POINTS,
        "raw_points": total_points,
        "awarded_points": awarded_points,
        "score": round(awarded_points / _PATTERN_CONFIDENCE_MAX_POINTS, 3),
        "signals": {
            "confidence": confidence_label or "medium",
            "status": status or "candidate",
            "evidence_count": evidence_count,
            "has_source_identity": has_source_identity,
            "has_retrieval_context": has_retrieval_context,
            "has_traceability": has_traceability,
            "derived_from_entry_count": len(derived_from_entry_ids),
        },
        "rule_results": rule_results,
    }


def _build_canonical_pattern(
    *,
    pattern_label: str,
    pattern_statement: str,
    transfer_type: str,
    applicability_reason: str,
    mutation_leverage: str,
    pattern_type_tactic: str,
    pattern_type_structure: str,
    pattern_type_heuristic: str,
    canonical_form: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_transfer = _normalize_transfer_type(transfer_type, default="heuristic")
    pattern = {
        "schema_version": CANONICAL_PROJECTED_PATTERN_SCHEMA_VERSION,
        "pattern_label": pattern_label or "tactic_pattern",
        "pattern_statement": pattern_statement or pattern_label or "tactic pattern",
        "transfer_type": normalized_transfer,
        "applicability_reason": applicability_reason or pattern_statement or "Reusable tactic signal.",
        "mutation_leverage": mutation_leverage or applicability_reason or "Apply as mutation guidance.",
        "pattern_type_tactic": _normalize_transfer_type(pattern_type_tactic, default=normalized_transfer),
        "pattern_type_structure": _normalize_transfer_type(pattern_type_structure, default=normalized_transfer),
        "pattern_type_heuristic": _normalize_transfer_type(pattern_type_heuristic, default=normalized_transfer),
    }
    if isinstance(canonical_form, Mapping):
        pattern["canonical_form"] = _clone_json_value(canonical_form)
    return pattern


def _pattern_from_pattern_observation(item: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    nested_pattern = payload.get("pattern")
    nested_pattern_mapping = nested_pattern if isinstance(nested_pattern, Mapping) else {}
    canonical_form = (
        payload.get("canonical_pattern")
        if isinstance(payload.get("canonical_pattern"), Mapping)
        else (
            nested_pattern_mapping.get("canonical_form")
            if isinstance(nested_pattern_mapping.get("canonical_form"), Mapping)
            else None
        )
    )
    transfer_type = _normalize_transfer_type(
        payload.get("transfer_type", nested_pattern_mapping.get("transfer_type")),
        default="heuristic",
    )
    title = _clean_text(item.get("title"))
    summary = _clean_text(item.get("summary"), default=title) or title
    pattern_label = _clean_identifier(
        (
            canonical_form.get("canonical_label")
            if isinstance(canonical_form, Mapping)
            else payload.get("pattern_label", nested_pattern_mapping.get("pattern_label"))
        ),
        default=_clean_identifier(title, default="pattern_observation"),
    ) or "pattern_observation"
    return _build_canonical_pattern(
        pattern_label=pattern_label,
        pattern_statement=_clean_text(
            payload.get("pattern_statement", nested_pattern_mapping.get("pattern_statement")),
            default=summary,
        )
        or summary,
        transfer_type=transfer_type,
        applicability_reason=_clean_text(
            payload.get("applicability_reason", nested_pattern_mapping.get("applicability_reason")),
            default=summary,
        )
        or summary,
        mutation_leverage=_clean_text(
            payload.get("mutation_leverage", nested_pattern_mapping.get("mutation_leverage")),
            default=summary,
        )
        or summary,
        pattern_type_tactic=payload.get(
            "pattern_type_tactic",
            nested_pattern_mapping.get("pattern_type_tactic", transfer_type),
        ),
        pattern_type_structure=payload.get(
            "pattern_type_structure",
            nested_pattern_mapping.get("pattern_type_structure", transfer_type),
        ),
        pattern_type_heuristic=payload.get(
            "pattern_type_heuristic",
            nested_pattern_mapping.get("pattern_type_heuristic", transfer_type),
        ),
        canonical_form=canonical_form,
    )


def _pattern_from_case_study(item: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    same_input_set_verified = _coerce_bool(payload.get("same_input_set_verified"), default=False)
    observed_delta = payload.get("observed_delta")
    numeric_delta = _extract_numeric_delta(observed_delta)
    transfer_type = "heuristic"
    if same_input_set_verified and numeric_delta is not None:
        if numeric_delta > 0:
            transfer_type = "positive_pattern"
        elif numeric_delta < 0:
            transfer_type = "anti_pattern"
    title = _clean_text(item.get("title"))
    summary = _clean_text(item.get("summary"), default=title) or title
    takeaway = _clean_text(payload.get("takeaway"), default=summary) or summary
    version_before = _clean_text(payload.get("version_before"), default="unknown_before")
    version_after = _clean_text(payload.get("version_after"), default="unknown_after")
    return _build_canonical_pattern(
        pattern_label=_clean_identifier(title, default="case_study_tactic") or "case_study_tactic",
        pattern_statement=takeaway,
        transfer_type=transfer_type,
        applicability_reason=(
            f"Derived from same-skill comparison {version_before} -> {version_after}"
            if same_input_set_verified
            else "Derived from case-study evidence without verified same-input proof."
        ),
        mutation_leverage=takeaway,
        pattern_type_tactic=transfer_type,
        pattern_type_structure="heuristic",
        pattern_type_heuristic="heuristic",
    )


def _pattern_from_meta_learning_rule(item: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    title = _clean_text(item.get("title"))
    summary = _clean_text(item.get("summary"), default=title) or title
    rule_statement = _clean_text(payload.get("rule_statement"), default=summary) or summary
    return _build_canonical_pattern(
        pattern_label=_clean_identifier(title or rule_statement, default="meta_learning_rule") or "meta_learning_rule",
        pattern_statement=rule_statement,
        transfer_type="heuristic",
        applicability_reason=summary,
        mutation_leverage=rule_statement,
        pattern_type_tactic="heuristic",
        pattern_type_structure="heuristic",
        pattern_type_heuristic="heuristic",
    )


def _pattern_from_preference_signal(item: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    title = _clean_text(item.get("title"))
    summary = _clean_text(item.get("summary"), default=title) or title
    preference_key = _clean_text(payload.get("preference_key"))
    preference_value = _clean_text(payload.get("preference_value"))
    preference_statement = _clean_text(payload.get("preference_statement"), default=summary) or summary
    label_seed = "_".join(
        part for part in (preference_key, preference_value) if part
    ) or title or preference_statement
    return _build_canonical_pattern(
        pattern_label=_clean_identifier(label_seed, default="preference_signal") or "preference_signal",
        pattern_statement=preference_statement,
        transfer_type="heuristic",
        applicability_reason=_clean_text(payload.get("confirmation_state"), default=summary) or summary,
        mutation_leverage=preference_statement,
        pattern_type_tactic="heuristic",
        pattern_type_structure="heuristic",
        pattern_type_heuristic="heuristic",
    )


def _pattern_from_mutation_hypothesis(item: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    title = _clean_text(item.get("title"))
    summary = _clean_text(item.get("summary"), default=title) or title
    hypothesis_statement = _clean_text(payload.get("hypothesis_statement"), default=summary) or summary
    target_section = _clean_text(payload.get("target_section"), default=title) or title
    expected_effect = _clean_text(payload.get("expected_effect"), default=hypothesis_statement) or hypothesis_statement
    return _build_canonical_pattern(
        pattern_label=_clean_identifier(target_section, default="mutation_hypothesis") or "mutation_hypothesis",
        pattern_statement=hypothesis_statement,
        transfer_type="heuristic",
        applicability_reason=target_section,
        mutation_leverage=expected_effect,
        pattern_type_tactic="heuristic",
        pattern_type_structure="heuristic",
        pattern_type_heuristic="heuristic",
    )


def _extract_base_pattern(
    normalized_corpus_item: Mapping[str, Any],
    *,
    error_cls: type[ValueError],
) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(normalized_corpus_item, Mapping):
        raise error_cls("normalized_corpus_item must be a mapping")

    entry_id = _clean_text(normalized_corpus_item.get("entry_id"))
    if not entry_id:
        raise error_cls("normalized_corpus_item.entry_id is required")

    entry_type = _clean_text(normalized_corpus_item.get("entry_type"))
    if entry_type not in CANONICAL_PROJECTED_ENTRY_TYPES:
        raise error_cls(
            "normalized_corpus_item.entry_type must be one of "
            f"{CANONICAL_PROJECTED_ENTRY_TYPES}; received {entry_type!r}"
        )

    raw_payload = normalized_corpus_item.get("type_payload")
    payload = raw_payload if isinstance(raw_payload, Mapping) else {}
    if entry_type == "pattern_observation":
        pattern = _pattern_from_pattern_observation(normalized_corpus_item, payload)
    elif entry_type == "case_study":
        pattern = _pattern_from_case_study(normalized_corpus_item, payload)
    elif entry_type == "meta_learning_rule":
        pattern = _pattern_from_meta_learning_rule(normalized_corpus_item, payload)
    elif entry_type == "preference_signal":
        pattern = _pattern_from_preference_signal(normalized_corpus_item, payload)
    else:
        pattern = _pattern_from_mutation_hypothesis(normalized_corpus_item, payload)

    return entry_id, entry_type, pattern


def _project_pattern(base_pattern: Mapping[str, Any], *, projection_field: str) -> dict[str, Any]:
    if projection_field not in CANONICAL_PROJECTION_FIELDS:
        raise ValueError(
            f"projection_field must be one of {CANONICAL_PROJECTION_FIELDS}; received {projection_field!r}"
        )

    projected_pattern = _clone_json_value(base_pattern)
    default_transfer = _clean_text(projected_pattern.get("transfer_type"), default="heuristic")
    projected_pattern["transfer_type"] = _normalize_transfer_type(
        projected_pattern.get(projection_field),
        default=default_transfer,
    )
    return projected_pattern


def extract_projected_pattern(
    normalized_corpus_item: Mapping[str, Any],
    *,
    projection_field: str,
    pattern_id_prefix: str,
    schema_version: int,
    error_cls: type[ValueError],
) -> dict[str, Any]:
    entry_id, entry_type, base_pattern = _extract_base_pattern(
        normalized_corpus_item,
        error_cls=error_cls,
    )
    projected_pattern = _project_pattern(base_pattern, projection_field=projection_field)
    confidence_scoring = _score_pattern_confidence(normalized_corpus_item)
    evidence_reference = _build_projected_evidence_reference(normalized_corpus_item)
    origin_metadata = _build_projected_origin_metadata(
        normalized_corpus_item,
        evidence_reference=evidence_reference,
    )
    source_applicability = _clone_json_value(
        normalized_corpus_item.get("applicability")
        if isinstance(normalized_corpus_item.get("applicability"), Mapping)
        else {}
    )
    source_scoring_context = _clone_json_value(
        normalized_corpus_item.get("scoring_context")
        if isinstance(normalized_corpus_item.get("scoring_context"), Mapping)
        else {}
    )

    return {
        "schema_version": schema_version,
        "pattern_id": _stable_pattern_id(
            entry_id=entry_id,
            entry_type=entry_type,
            pattern=projected_pattern,
            pattern_id_prefix=pattern_id_prefix,
        ),
        "source_entry_id": entry_id,
        "source_entry_type": entry_type,
        "source_kind": _clean_text(normalized_corpus_item.get("source_kind"), default="unknown"),
        "confidence": _clean_text(normalized_corpus_item.get("confidence"), default="medium"),
        "confidence_score": confidence_scoring["score"],
        "confidence_scoring": confidence_scoring,
        "status": _clean_text(normalized_corpus_item.get("status"), default="candidate"),
        "derived_from_entry_ids": _clone_json_value(
            normalized_corpus_item.get("derived_from_entry_ids")
            if isinstance(normalized_corpus_item.get("derived_from_entry_ids"), list)
            else []
        ),
        "evidence_count": len(normalized_corpus_item.get("evidence") or []),
        "evidence_reference": evidence_reference,
        "origin_metadata": origin_metadata,
        "source_applicability": source_applicability,
        "source_scoring_context": source_scoring_context,
        "pattern": projected_pattern,
    }


def extract_projected_patterns(
    normalized_corpus_items: Iterable[Mapping[str, Any]],
    *,
    projection_field: str,
    pattern_id_prefix: str,
    schema_version: int,
    error_cls: type[ValueError],
) -> list[dict[str, Any]]:
    return [
        extract_projected_pattern(
            item,
            projection_field=projection_field,
            pattern_id_prefix=pattern_id_prefix,
            schema_version=schema_version,
            error_cls=error_cls,
        )
        for item in normalized_corpus_items
    ]


def extract_projected_patterns_from_corpus_bundle(
    normalized_corpus_bundle: Mapping[str, Any],
    *,
    projection_field: str,
    pattern_id_prefix: str,
    schema_version: int,
    error_cls: type[ValueError],
) -> list[dict[str, Any]]:
    if not isinstance(normalized_corpus_bundle, Mapping):
        raise error_cls("normalized_corpus_bundle must be a mapping")

    entries = normalized_corpus_bundle.get("entries")
    if entries is None:
        return []
    if not isinstance(entries, list):
        raise error_cls("normalized_corpus_bundle.entries must be a list")

    extracted: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, Mapping):
            raise error_cls(f"normalized_corpus_bundle.entries[{index}] must be a mapping")
        extracted.append(
            extract_projected_pattern(
                raw_entry,
                projection_field=projection_field,
                pattern_id_prefix=pattern_id_prefix,
                schema_version=schema_version,
                error_cls=error_cls,
            )
        )
    return extracted


def _pattern_store_record_sort_key(pattern_record: Mapping[str, Any]) -> tuple[str, int, str]:
    version = pattern_record.get("version")
    try:
        normalized_version = int(version)
    except (TypeError, ValueError):
        normalized_version = 0
    return (
        _clean_text(pattern_record.get("pattern_id")),
        normalized_version,
        _clean_text(pattern_record.get("pattern_version_id")),
    )


def _resolve_pattern_store_records(
    pattern_store_payload: Mapping[str, Any],
    *,
    pattern_id_prefix: str,
    error_cls: type[ValueError],
    latest_only: bool,
) -> list[dict[str, Any]]:
    if not isinstance(pattern_store_payload, Mapping):
        raise error_cls("pattern_store_payload must be a mapping")

    pattern_records = pattern_store_payload.get("pattern_records")
    if pattern_records is None:
        return []
    if not isinstance(pattern_records, list):
        raise error_cls("pattern_store_payload.pattern_records must be a list")

    filtered_records: list[dict[str, Any]] = []
    for index, raw_pattern_record in enumerate(pattern_records):
        if not isinstance(raw_pattern_record, Mapping):
            raise error_cls(
                f"pattern_store_payload.pattern_records[{index}] must be a mapping"
            )
        pattern_id = _clean_text(raw_pattern_record.get("pattern_id"))
        if not pattern_id:
            raise error_cls(
                f"pattern_store_payload.pattern_records[{index}].pattern_id is required"
            )
        if pattern_id_prefix and not pattern_id.startswith(f"{pattern_id_prefix}-"):
            continue
        filtered_records.append(_clone_json_value(raw_pattern_record))

    filtered_records.sort(key=_pattern_store_record_sort_key)
    if not latest_only:
        return filtered_records

    latest_records: dict[str, dict[str, Any]] = {}
    for pattern_record in filtered_records:
        pattern_id = _clean_text(pattern_record.get("pattern_id"))
        existing_record = latest_records.get(pattern_id)
        if existing_record is None or _pattern_store_record_sort_key(existing_record) < _pattern_store_record_sort_key(
            pattern_record
        ):
            latest_records[pattern_id] = pattern_record

    return sorted(latest_records.values(), key=_pattern_store_record_sort_key)


def _projected_pattern_from_store_record(
    pattern_record: Mapping[str, Any],
    *,
    schema_version: int,
) -> dict[str, Any]:
    contributors = (
        pattern_record.get("contributors")
        if isinstance(pattern_record.get("contributors"), list)
        else []
    )
    representative_contributor = (
        contributors[0]
        if contributors and isinstance(contributors[0], Mapping)
        else {}
    )
    evidence_references = (
        pattern_record.get("evidence_references")
        if isinstance(pattern_record.get("evidence_references"), list)
        else []
    )
    representative_evidence_reference = (
        pattern_record.get("primary_evidence_reference")
        if isinstance(pattern_record.get("primary_evidence_reference"), Mapping)
        else representative_contributor.get("evidence_reference")
        if isinstance(representative_contributor.get("evidence_reference"), Mapping)
        else None
    )
    evidence_count = representative_contributor.get("evidence_count")
    try:
        normalized_evidence_count = int(evidence_count)
    except (TypeError, ValueError):
        normalized_evidence_count = len(evidence_references)

    return {
        "schema_version": schema_version,
        "pattern_id": _clean_text(pattern_record.get("pattern_id")),
        "pattern_version_id": _clean_text(pattern_record.get("pattern_version_id")) or None,
        "pattern_version": (
            int(pattern_record.get("version"))
            if isinstance(pattern_record.get("version"), int)
            or (
                isinstance(pattern_record.get("version"), str)
                and _clean_text(pattern_record.get("version")).isdigit()
            )
            else None
        ),
        "source_entry_id": _clean_text(
            pattern_record.get("representative_source_entry_id"),
            default=representative_contributor.get("source_entry_id"),
        ),
        "source_entry_type": _clean_text(
            pattern_record.get("representative_source_entry_type"),
            default=representative_contributor.get("source_entry_type"),
        ),
        "source_kind": _clean_text(
            representative_contributor.get("source_kind"),
            default="unknown",
        ),
        "confidence": _clean_text(
            representative_contributor.get("confidence"),
            default="medium",
        ),
        "confidence_score": _coerce_numeric(
            representative_contributor.get("confidence_score")
        )
        or 0.0,
        "status": _clean_text(
            representative_contributor.get("status"),
            default="candidate",
        ),
        "derived_from_entry_ids": _normalize_string_list(
            pattern_record.get("derived_from_entry_ids")
        ),
        "evidence_count": normalized_evidence_count,
        "evidence_reference": _clone_json_value(representative_evidence_reference)
        if representative_evidence_reference is not None
        else None,
        "origin_metadata": _clone_json_value(representative_contributor.get("origin_metadata"))
        if isinstance(representative_contributor.get("origin_metadata"), Mapping)
        else None,
        "pattern": _clone_json_value(
            pattern_record.get("pattern")
            if isinstance(pattern_record.get("pattern"), Mapping)
            else {}
        ),
    }


def extract_projected_patterns_from_pattern_store(
    pattern_store_payload: Mapping[str, Any],
    *,
    projection_field: str | None = None,
    pattern_id_prefix: str,
    schema_version: int,
    error_cls: type[ValueError],
    latest_only: bool = True,
) -> list[dict[str, Any]]:
    """Load projected patterns from a persisted normalized pattern store."""

    if projection_field is not None and projection_field not in CANONICAL_PROJECTION_FIELDS:
        raise error_cls(
            f"projection_field must be one of {CANONICAL_PROJECTION_FIELDS}; received {projection_field!r}"
        )

    return [
        _projected_pattern_from_store_record(
            pattern_record,
            schema_version=schema_version,
        )
        for pattern_record in _resolve_pattern_store_records(
            pattern_store_payload,
            pattern_id_prefix=pattern_id_prefix,
            error_cls=error_cls,
            latest_only=latest_only,
        )
    ]
