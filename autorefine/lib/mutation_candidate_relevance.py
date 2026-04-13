from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from ._shared_text import (
    clean_identifier as _clean_identifier,
    clean_text as _clean_text,
)
from .target_skill_scoring_context import (
    CANONICAL_TARGET_SKILL_SCORING_CONTEXT_TYPE,
    build_target_skill_scoring_context,
)


MUTATION_CANDIDATE_RELEVANCE_RUBRIC_SCHEMA_VERSION = 1
CANONICAL_MUTATION_CANDIDATE_RELEVANCE_ENGINE_ID = "deterministic_mutation_candidate_relevance_v1"
CANONICAL_MUTATION_CANDIDATE_RELEVANCE_DIMENSIONS = (
    "goal_alignment",
    "structural_fit",
    "domain_context_match",
)
DEFAULT_MUTATION_CANDIDATE_RELEVANCE_WEIGHTS = {
    "goal_alignment": 0.45,
    "structural_fit": 0.35,
    "domain_context_match": 0.20,
}
_CRITERION_DESCRIPTIONS = {
    "goal_alignment": (
        "Does the donor pattern directly improve the same target job, failure mode, "
        "or mutation objective that the current skill version is trying to improve?"
    ),
    "structural_fit": (
        "Can the donor pattern be transplanted into the target skill's pattern, "
        "section boundaries, and workflow shape without importing incompatible stage "
        "logic or hidden assumptions?"
    ),
    "domain_context_match": (
        "Do the donor and target operate in a similar agent, domain, and scenario "
        "context so the terminology, constraints, and reference expectations still "
        "transfer cleanly?"
    ),
}

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "do",
    "does",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "same",
    "so",
    "still",
    "that",
    "the",
    "their",
    "them",
    "to",
    "use",
    "when",
    "with",
}


class MutationCandidateRelevanceError(ValueError):
    """Raised when donor-pattern relevance scoring inputs are invalid."""


def _clone_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _clone_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_clone_json_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_clone_json_value(item) for item in value)
    return value


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _normalize_identifier_list(values: Any) -> list[str]:
    normalized: list[str] = []
    for item in _normalize_string_list(values):
        cleaned = _clean_identifier(item)
        if cleaned:
            normalized.append(cleaned)
    return _unique(normalized)


def _tokenize(values: Iterable[str]) -> list[str]:
    tokens: list[str] = []
    for value in values:
        cleaned = _clean_text(value).lower()
        if not cleaned:
            continue
        for token in _TOKEN_PATTERN.findall(cleaned):
            if token not in _STOPWORDS:
                tokens.append(token)
    return _unique(tokens)


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _matched_identifiers(source_values: Iterable[str], target_values: Iterable[str]) -> list[str]:
    target_lookup = set(target_values)
    return [value for value in _unique(source_values) if value in target_lookup]


def _matched_tokens(source_values: Iterable[str], target_values: Iterable[str]) -> list[str]:
    target_lookup = set(target_values)
    return [value for value in _unique(source_values) if value in target_lookup]


def _points_for_thresholds(match_count: int, thresholds: list[tuple[int, int]]) -> int:
    for minimum, points in thresholds:
        if match_count >= minimum:
            return points
    return 0


def _score_label(score: float) -> str:
    if score >= 0.75:
        return "strong_match"
    if score >= 0.40:
        return "partial_match"
    return "weak_match"


def _build_rule_result(
    *,
    rule_id: str,
    points_awarded: int,
    max_points: int,
    signal_value: Any,
    reason: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "points_awarded": points_awarded,
        "max_points": max_points,
        "signal_value": _clone_json_value(signal_value),
        "reason": reason,
    }


def _format_signal_list(values: Iterable[str], *, empty: str = "none") -> str:
    ordered = _unique(values)
    if not ordered:
        return empty
    return ", ".join(ordered)


def _normalize_target_context(target_context_or_scoring_context: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if target_context_or_scoring_context is None:
        raise MutationCandidateRelevanceError("target context is required for donor-pattern relevance scoring")
    if not isinstance(target_context_or_scoring_context, Mapping):
        raise MutationCandidateRelevanceError("target context must be a mapping")

    if (
        _clean_text(target_context_or_scoring_context.get("payload_type"))
        == CANONICAL_TARGET_SKILL_SCORING_CONTEXT_TYPE
    ):
        return target_context_or_scoring_context

    normalized = build_target_skill_scoring_context(target_context_or_scoring_context)
    if not normalized:
        raise MutationCandidateRelevanceError(
            "target context must include enough signal content to build a target_skill_scoring_context payload"
        )
    return normalized


def _extract_pattern_payload(projected_pattern: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    if not isinstance(projected_pattern, Mapping):
        raise MutationCandidateRelevanceError("projected_pattern must be a mapping")

    pattern = projected_pattern.get("pattern")
    if not isinstance(pattern, Mapping):
        raise MutationCandidateRelevanceError("projected_pattern.pattern is required")

    return (
        pattern,
        _mapping_or_empty(projected_pattern.get("source_applicability")),
        _mapping_or_empty(projected_pattern.get("source_scoring_context")),
        _mapping_or_empty(projected_pattern.get("evidence_reference")),
    )


def _donor_text_terms(pattern: Mapping[str, Any], evidence_reference: Mapping[str, Any]) -> list[str]:
    source_location = _mapping_or_empty(evidence_reference.get("source_location"))
    heading_path = _normalize_string_list(source_location.get("heading_path"))
    donor_texts = [
        _clean_text(pattern.get("pattern_label")),
        _clean_text(pattern.get("pattern_statement")),
        _clean_text(pattern.get("applicability_reason")),
        _clean_text(pattern.get("mutation_leverage")),
        _clean_text(source_location.get("section_id")),
        *heading_path,
        _clean_text(evidence_reference.get("quote")),
    ]
    return _tokenize(donor_texts)


def _goal_alignment_dimension(
    *,
    pattern: Mapping[str, Any],
    evidence_reference: Mapping[str, Any],
    target_scoring_context: Mapping[str, Any],
) -> dict[str, Any]:
    donor_terms = _donor_text_terms(pattern, evidence_reference)
    goals = _mapping_or_empty(target_scoring_context.get("goals"))
    target_goal_terms = _tokenize(_normalize_string_list(goals.get("comparison_terms")))
    target_primary_goal_terms = _tokenize([_clean_text(goals.get("primary_goal"))])
    target_failure_terms = _tokenize(_normalize_string_list(goals.get("failure_focus")))

    matched_goal_terms = _matched_tokens(donor_terms, target_goal_terms)
    matched_primary_terms = _matched_tokens(donor_terms, target_primary_goal_terms)
    matched_failure_terms = _matched_tokens(donor_terms, target_failure_terms)

    goal_term_points = _points_for_thresholds(
        len(matched_goal_terms),
        [(3, 45), (2, 30), (1, 15)],
    )
    primary_goal_points = _points_for_thresholds(
        len(matched_primary_terms),
        [(2, 30), (1, 15)],
    )
    failure_focus_points = _points_for_thresholds(
        len(matched_failure_terms),
        [(2, 25), (1, 10)],
    )

    rule_results = [
        _build_rule_result(
            rule_id="goal_term_overlap",
            points_awarded=goal_term_points,
            max_points=45,
            signal_value={
                "matched_terms": matched_goal_terms,
                "matched_count": len(matched_goal_terms),
            },
            reason="Matched donor terms against the target goal and mutation-objective comparison terms.",
        ),
        _build_rule_result(
            rule_id="primary_goal_overlap",
            points_awarded=primary_goal_points,
            max_points=30,
            signal_value={
                "matched_terms": matched_primary_terms,
                "matched_count": len(matched_primary_terms),
            },
            reason="Checked whether donor language overlaps the current primary goal statement.",
        ),
        _build_rule_result(
            rule_id="failure_focus_overlap",
            points_awarded=failure_focus_points,
            max_points=25,
            signal_value={
                "matched_terms": matched_failure_terms,
                "matched_count": len(matched_failure_terms),
            },
            reason="Checked whether donor language targets the active failure-focus terms.",
        ),
    ]

    awarded_points = goal_term_points + primary_goal_points + failure_focus_points
    score = round(awarded_points / 100, 3)

    if matched_goal_terms or matched_primary_terms or matched_failure_terms:
        evidence_summary = (
            "Matched goal terms: "
            f"{_format_signal_list(matched_goal_terms)}; primary-goal overlap: "
            f"{_format_signal_list(matched_primary_terms)}; failure-focus overlap: "
            f"{_format_signal_list(matched_failure_terms)}."
        )
    else:
        evidence_summary = "No donor terms overlap the current goal or failure-focus signals."

    return {
        "dimension": "goal_alignment",
        "weight": DEFAULT_MUTATION_CANDIDATE_RELEVANCE_WEIGHTS["goal_alignment"],
        "criterion_description": _CRITERION_DESCRIPTIONS["goal_alignment"],
        "score": score,
        "score_label": _score_label(score),
        "awarded_points": awarded_points,
        "max_points": 100,
        "evidence_summary": evidence_summary,
        "subscore_components": rule_results,
    }


def _structural_fit_dimension(
    *,
    pattern: Mapping[str, Any],
    source_applicability: Mapping[str, Any],
    source_scoring_context: Mapping[str, Any],
    evidence_reference: Mapping[str, Any],
    target_scoring_context: Mapping[str, Any],
) -> dict[str, Any]:
    target_structure = _mapping_or_empty(target_scoring_context.get("structure_signals"))
    source_structure = _mapping_or_empty(source_scoring_context.get("structure_signals"))
    source_location = _mapping_or_empty(evidence_reference.get("source_location"))

    target_skill_pattern = _clean_identifier(target_structure.get("skill_pattern"))
    source_skill_patterns = _unique(
        [
            *_normalize_identifier_list(source_applicability.get("skill_patterns")),
            _clean_identifier(source_structure.get("skill_pattern")),
        ]
    )
    donor_text_terms = _donor_text_terms(pattern, evidence_reference)

    if target_skill_pattern and target_skill_pattern in source_skill_patterns:
        skill_pattern_points = 40
        skill_pattern_signal = "exact_match"
    elif target_skill_pattern and target_skill_pattern in donor_text_terms:
        skill_pattern_points = 20
        skill_pattern_signal = "text_inference"
    elif source_skill_patterns:
        skill_pattern_points = 0
        skill_pattern_signal = "explicit_non_match"
    else:
        skill_pattern_points = 0
        skill_pattern_signal = "missing"

    target_section = _clean_text(target_structure.get("target_section"))
    target_section_identifier = _clean_identifier(target_section)
    donor_section_identifiers = _unique(
        [
            _clean_identifier(source_structure.get("target_section")),
            _clean_identifier(source_location.get("section_id")),
            *_normalize_identifier_list(source_location.get("heading_path")),
            _clean_identifier(source_applicability.get("scope_ref")),
        ]
    )
    donor_section_terms = _tokenize(
        [
            _clean_text(source_structure.get("target_section")),
            _clean_text(source_location.get("section_id")),
            *_normalize_string_list(source_location.get("heading_path")),
            _clean_text(source_applicability.get("scope_ref")),
        ]
    )
    target_section_terms = _tokenize([target_section])

    if target_section_identifier and target_section_identifier in donor_section_identifiers:
        section_points = 35
        section_signal = "exact_match"
    elif _matched_tokens(donor_section_terms + donor_text_terms, target_section_terms):
        section_points = 20
        section_signal = "token_overlap"
    else:
        section_points = 0
        section_signal = "no_match"

    target_signal_tags = _unique(
        [
            *_normalize_identifier_list(target_structure.get("signal_tags")),
            _clean_identifier(target_structure.get("selected_eval_strategy_id")),
        ]
    )
    donor_signal_tags = _unique(
        [
            *_normalize_identifier_list(source_structure.get("signal_tags")),
            _clean_identifier(source_structure.get("selected_eval_strategy_id")),
            _clean_identifier(source_applicability.get("scope_type")),
            _clean_identifier(source_applicability.get("scope_ref")),
        ]
    )
    matched_signal_tags = _matched_identifiers(donor_signal_tags, target_signal_tags)
    signal_overlap_points = _points_for_thresholds(
        len(matched_signal_tags),
        [(3, 25), (2, 15), (1, 8)],
    )

    rule_results = [
        _build_rule_result(
            rule_id="skill_pattern_match",
            points_awarded=skill_pattern_points,
            max_points=40,
            signal_value={
                "target_skill_pattern": target_skill_pattern or None,
                "source_skill_patterns": source_skill_patterns,
                "match_state": skill_pattern_signal,
            },
            reason="Compared the donor pattern's declared source skill pattern against the target skill pattern.",
        ),
        _build_rule_result(
            rule_id="target_section_alignment",
            points_awarded=section_points,
            max_points=35,
            signal_value={
                "target_section": target_section or None,
                "donor_sections": donor_section_identifiers,
                "match_state": section_signal,
            },
            reason="Checked whether donor evidence and applicability land in the same section boundary as the target.",
        ),
        _build_rule_result(
            rule_id="structure_signal_overlap",
            points_awarded=signal_overlap_points,
            max_points=25,
            signal_value={
                "matched_signal_tags": matched_signal_tags,
                "matched_count": len(matched_signal_tags),
            },
            reason="Compared donor structure tags and strategy hints against the target workflow signals.",
        ),
    ]

    awarded_points = skill_pattern_points + section_points + signal_overlap_points
    score = round(awarded_points / 100, 3)
    evidence_summary = (
        f"Skill-pattern state: {skill_pattern_signal}; section state: {section_signal}; "
        f"matched structure signals: {_format_signal_list(matched_signal_tags)}."
    )

    return {
        "dimension": "structural_fit",
        "weight": DEFAULT_MUTATION_CANDIDATE_RELEVANCE_WEIGHTS["structural_fit"],
        "criterion_description": _CRITERION_DESCRIPTIONS["structural_fit"],
        "score": score,
        "score_label": _score_label(score),
        "awarded_points": awarded_points,
        "max_points": 100,
        "evidence_summary": evidence_summary,
        "subscore_components": rule_results,
    }


def _domain_context_match_dimension(
    *,
    source_applicability: Mapping[str, Any],
    source_scoring_context: Mapping[str, Any],
    target_scoring_context: Mapping[str, Any],
) -> dict[str, Any]:
    target_domain = _mapping_or_empty(target_scoring_context.get("domain_tags"))
    source_domain = _mapping_or_empty(source_scoring_context.get("domain_tags"))

    target_agent = _clean_identifier(target_domain.get("agent_target"))
    source_agents = _unique(
        [
            *_normalize_identifier_list(source_applicability.get("agent_targets")),
            _clean_identifier(source_domain.get("agent_target")),
        ]
    )
    if target_agent and target_agent in source_agents:
        agent_points = 35
        agent_signal = "exact_match"
    elif source_agents:
        agent_points = 0
        agent_signal = "explicit_non_match"
    else:
        agent_points = 10
        agent_signal = "missing"

    target_scenario = _clean_identifier(target_domain.get("scenario_target"))
    source_scenarios = _unique(
        [
            *_normalize_identifier_list(source_applicability.get("scenario_targets")),
            _clean_identifier(source_domain.get("scenario_target")),
        ]
    )
    if target_scenario and target_scenario in source_scenarios:
        scenario_points = 35
        scenario_signal = "exact_match"
    elif source_scenarios:
        scenario_points = 0
        scenario_signal = "explicit_non_match"
    else:
        scenario_points = 10
        scenario_signal = "missing"

    target_domain_tags = _normalize_identifier_list(target_domain.get("tags"))
    source_domain_tags = _normalize_identifier_list(source_domain.get("tags"))
    matched_domain_tags = _matched_identifiers(source_domain_tags, target_domain_tags)
    domain_tag_points = _points_for_thresholds(
        len(matched_domain_tags),
        [(3, 30), (2, 20), (1, 10)],
    )

    rule_results = [
        _build_rule_result(
            rule_id="agent_target_match",
            points_awarded=agent_points,
            max_points=35,
            signal_value={
                "target_agent": target_agent or None,
                "source_agents": source_agents,
                "match_state": agent_signal,
            },
            reason="Compared donor applicability and source-domain agent targets to the current target agent.",
        ),
        _build_rule_result(
            rule_id="scenario_target_match",
            points_awarded=scenario_points,
            max_points=35,
            signal_value={
                "target_scenario": target_scenario or None,
                "source_scenarios": source_scenarios,
                "match_state": scenario_signal,
            },
            reason="Compared donor applicability and source-domain scenario targets to the current scenario target.",
        ),
        _build_rule_result(
            rule_id="domain_tag_overlap",
            points_awarded=domain_tag_points,
            max_points=30,
            signal_value={
                "matched_domain_tags": matched_domain_tags,
                "matched_count": len(matched_domain_tags),
            },
            reason="Compared donor source-domain tags against the target domain-tag surface.",
        ),
    ]

    awarded_points = agent_points + scenario_points + domain_tag_points
    score = round(awarded_points / 100, 3)
    evidence_summary = (
        f"Agent state: {agent_signal}; scenario state: {scenario_signal}; "
        f"matched domain tags: {_format_signal_list(matched_domain_tags)}."
    )

    return {
        "dimension": "domain_context_match",
        "weight": DEFAULT_MUTATION_CANDIDATE_RELEVANCE_WEIGHTS["domain_context_match"],
        "criterion_description": _CRITERION_DESCRIPTIONS["domain_context_match"],
        "score": score,
        "score_label": _score_label(score),
        "awarded_points": awarded_points,
        "max_points": 100,
        "evidence_summary": evidence_summary,
        "subscore_components": rule_results,
    }


def build_mutation_candidate_relevance_rubric(
    projected_pattern: Mapping[str, Any],
    target_context_or_scoring_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Score one extracted donor pattern against the current target-skill context."""

    target_scoring_context = _normalize_target_context(target_context_or_scoring_context)
    pattern, source_applicability, source_scoring_context, evidence_reference = _extract_pattern_payload(
        projected_pattern
    )

    dimensions = [
        _goal_alignment_dimension(
            pattern=pattern,
            evidence_reference=evidence_reference,
            target_scoring_context=target_scoring_context,
        ),
        _structural_fit_dimension(
            pattern=pattern,
            source_applicability=source_applicability,
            source_scoring_context=source_scoring_context,
            evidence_reference=evidence_reference,
            target_scoring_context=target_scoring_context,
        ),
        _domain_context_match_dimension(
            source_applicability=source_applicability,
            source_scoring_context=source_scoring_context,
            target_scoring_context=target_scoring_context,
        ),
    ]

    weighted_score = round(
        sum(dimension["score"] * dimension["weight"] for dimension in dimensions),
        3,
    )
    for dimension in dimensions:
        dimension["weighted_contribution"] = round(
            dimension["score"] * dimension["weight"],
            3,
        )

    return {
        "schema_version": MUTATION_CANDIDATE_RELEVANCE_RUBRIC_SCHEMA_VERSION,
        "engine_id": CANONICAL_MUTATION_CANDIDATE_RELEVANCE_ENGINE_ID,
        "pattern_id": _clean_text(projected_pattern.get("pattern_id")) or None,
        "aggregation_formula": "weighted_sum(dimension.score * dimension.weight)",
        "dimensions": dimensions,
        "weighted_score": weighted_score,
        "weighted_score_pct": round(weighted_score * 100, 1),
    }


def build_mutation_candidate_relevance_rubrics(
    projected_patterns: Iterable[Mapping[str, Any]],
    target_context_or_scoring_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Score many extracted donor patterns against the same target-skill context."""

    target_scoring_context = _normalize_target_context(target_context_or_scoring_context)
    return [
        build_mutation_candidate_relevance_rubric(projected_pattern, target_scoring_context)
        for projected_pattern in projected_patterns
    ]


__all__ = [
    "CANONICAL_MUTATION_CANDIDATE_RELEVANCE_DIMENSIONS",
    "CANONICAL_MUTATION_CANDIDATE_RELEVANCE_ENGINE_ID",
    "DEFAULT_MUTATION_CANDIDATE_RELEVANCE_WEIGHTS",
    "MUTATION_CANDIDATE_RELEVANCE_RUBRIC_SCHEMA_VERSION",
    "MutationCandidateRelevanceError",
    "build_mutation_candidate_relevance_rubric",
    "build_mutation_candidate_relevance_rubrics",
]
