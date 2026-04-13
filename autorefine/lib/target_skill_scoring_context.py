from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any

if __package__:
    from ._shared_text import (
        clean_identifier as _clean_identifier,
        clean_text as _clean_text,
    )
else:
    _CURRENT_DIR = Path(__file__).resolve().parent
    if str(_CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(_CURRENT_DIR))
    from _shared_text import (
        clean_identifier as _clean_identifier,
        clean_text as _clean_text,
    )

TARGET_SKILL_SCORING_CONTEXT_SCHEMA_VERSION = 1
CANONICAL_TARGET_SKILL_SCORING_CONTEXT_TYPE = "target_skill_scoring_context"

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return [cleaned] if cleaned else []
    if isinstance(value, (list, tuple, set)):
        normalized: list[str] = []
        for item in value:
            cleaned = _clean_text(item)
            if cleaned:
                normalized.append(cleaned)
        return normalized
    cleaned = _clean_text(value)
    return [cleaned] if cleaned else []


def _normalize_tag_list(value: Any) -> list[str]:
    raw_items = _normalize_string_list(value)
    normalized: list[str] = []
    for item in raw_items:
        for part in re.split(r"[;,|]", item):
            cleaned = _clean_identifier(part)
            if cleaned:
                normalized.append(cleaned)
    return _unique(normalized)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _collect_phrase_fields(target_context: Mapping[str, Any], field_names: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for field_name in field_names:
        values.extend(_normalize_string_list(target_context.get(field_name)))
    return _unique(values)


def _collect_tag_fields(target_context: Mapping[str, Any], field_names: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for field_name in field_names:
        values.extend(_normalize_tag_list(target_context.get(field_name)))
    return _unique(values)


def _extract_skill_metadata(target_context: Mapping[str, Any]) -> Mapping[str, Any]:
    skill_metadata = target_context.get("skill_metadata")
    if isinstance(skill_metadata, Mapping):
        return skill_metadata
    selected_skill = target_context.get("selected_skill")
    if isinstance(selected_skill, Mapping):
        return selected_skill
    fixture_skill = target_context.get("fixture_skill")
    if isinstance(fixture_skill, Mapping):
        return fixture_skill
    return {}


def _build_goal_signals(target_context: Mapping[str, Any]) -> dict[str, Any]:
    skill_metadata = _extract_skill_metadata(target_context)
    goal_statements = _collect_phrase_fields(
        target_context,
        (
            "campaign_objective",
            "objective",
            "analysis_goal",
            "goal",
            "goal_statement",
            "goal_statements",
            "goals",
            "objectives",
        ),
    )
    if not goal_statements:
        goal_statements = _collect_phrase_fields(
            skill_metadata,
            ("summary", "description", "objective"),
        )

    failure_focus = _collect_phrase_fields(
        target_context,
        ("failure_focus", "failure_modes", "pain_points", "mutation_targets"),
    )
    comparison_terms = _unique(
        _tokenize_phrases(goal_statements + failure_focus)
    )

    primary_goal = (
        _clean_text(_first_present(target_context, "campaign_objective", "objective", "analysis_goal", "goal"))
        or (goal_statements[0] if goal_statements else None)
    )

    return {
        "primary_goal": primary_goal or None,
        "goal_statements": goal_statements,
        "failure_focus": failure_focus,
        "comparison_terms": comparison_terms,
    }


def _build_structure_signals(target_context: Mapping[str, Any]) -> dict[str, Any]:
    phase1_context = (
        target_context.get("phase1_context")
        if isinstance(target_context.get("phase1_context"), Mapping)
        else {}
    )
    skill_pattern = _clean_text(
        _first_present(target_context, "skill_pattern")
        or _first_present(phase1_context, "selected_skill_pattern")
    )
    selected_eval_strategy_id = _clean_text(
        _first_present(
            target_context,
            "selected_eval_strategy_id",
            "eval_strategy_id",
            "strategy_id",
        )
        or _first_present(phase1_context, "selected_eval_strategy_id")
    )
    target_section = _clean_text(
        _first_present(
            target_context,
            "target_section",
            "section_focus",
            "section",
            "target_location",
        )
    )

    explicit_signals = _collect_tag_fields(
        target_context,
        (
            "structure_signals",
            "structure_tags",
            "workflow_signals",
            "workflow_shape_tags",
        ),
    )
    if target_section:
        explicit_signals.extend(_normalize_tag_list(target_section))
    if skill_pattern:
        explicit_signals.append(_clean_identifier(skill_pattern))
    if selected_eval_strategy_id:
        explicit_signals.append(_clean_identifier(selected_eval_strategy_id))

    scope_type = _clean_text(target_context.get("scope_type"))
    scope_ref = _clean_text(target_context.get("scope_ref"))
    if scope_type:
        explicit_signals.append(_clean_identifier(scope_type))
    if scope_ref:
        explicit_signals.append(_clean_identifier(scope_ref))

    return {
        "skill_pattern": skill_pattern or None,
        "selected_eval_strategy_id": selected_eval_strategy_id or None,
        "target_section": target_section or None,
        "signal_tags": _unique(explicit_signals),
        "comparison_terms": _unique(
            _tokenize_phrases(
                [
                    skill_pattern,
                    selected_eval_strategy_id,
                    target_section,
                    scope_type,
                    scope_ref,
                    *explicit_signals,
                ]
            )
        ),
    }


def _build_domain_tags(target_context: Mapping[str, Any]) -> dict[str, Any]:
    skill_metadata = _extract_skill_metadata(target_context)

    agent_target = _clean_text(target_context.get("agent_target"))
    scenario_target = _clean_text(target_context.get("scenario_target"))
    target_domain = _clean_text(
        _first_present(target_context, "target_domain", "domain", "domain_context")
    )

    tags = _collect_tag_fields(
        target_context,
        ("domain_tags", "tags"),
    )
    tags.extend(_collect_tag_fields(skill_metadata, ("tags",)))
    if target_domain:
        tags.append(_clean_identifier(target_domain))
    if agent_target:
        tags.append(_clean_identifier(agent_target))
    if scenario_target:
        tags.append(_clean_identifier(scenario_target))

    return {
        "agent_target": agent_target or None,
        "scenario_target": scenario_target or None,
        "target_domain": target_domain or None,
        "tags": _unique(tags),
        "comparison_terms": _unique(
            _tokenize_phrases(
                [
                    agent_target,
                    scenario_target,
                    target_domain,
                    *tags,
                ]
            )
        ),
    }


def _tokenize_phrases(values: list[str | None]) -> list[str]:
    tokens: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        tokens.extend(_TOKEN_PATTERN.findall(cleaned.lower()))
    return tokens


def build_target_skill_scoring_context(
    target_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a consistent scoring envelope for the current skill-under-test."""

    if target_context is None:
        return {}
    if not isinstance(target_context, Mapping):
        raise TypeError("target_context must be a mapping when provided")

    goals = _build_goal_signals(target_context)
    structure_signals = _build_structure_signals(target_context)
    domain_tags = _build_domain_tags(target_context)

    has_signal_content = any(
        (
            goals["primary_goal"],
            goals["goal_statements"],
            goals["failure_focus"],
            structure_signals["skill_pattern"],
            structure_signals["selected_eval_strategy_id"],
            structure_signals["target_section"],
            structure_signals["signal_tags"],
            domain_tags["agent_target"],
            domain_tags["scenario_target"],
            domain_tags["target_domain"],
            domain_tags["tags"],
        )
    )
    if not has_signal_content:
        return {}

    return {
        "schema_version": TARGET_SKILL_SCORING_CONTEXT_SCHEMA_VERSION,
        "payload_type": CANONICAL_TARGET_SKILL_SCORING_CONTEXT_TYPE,
        "goals": goals,
        "structure_signals": structure_signals,
        "domain_tags": domain_tags,
    }


__all__ = [
    "CANONICAL_TARGET_SKILL_SCORING_CONTEXT_TYPE",
    "TARGET_SKILL_SCORING_CONTEXT_SCHEMA_VERSION",
    "build_target_skill_scoring_context",
]
