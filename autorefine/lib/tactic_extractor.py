from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ._projected_pattern_extractor import (
    CANONICAL_PROJECTED_ENTRY_TYPES,
    CANONICAL_PROJECTED_TRANSFER_TYPES,
    extract_projected_pattern,
    extract_projected_patterns,
    extract_projected_patterns_from_corpus_bundle,
    extract_projected_patterns_from_pattern_store,
)


CANONICAL_TACTIC_PATTERN_SCHEMA_VERSION = 1
CANONICAL_TACTIC_TRANSFER_TYPES = CANONICAL_PROJECTED_TRANSFER_TYPES
CANONICAL_TACTIC_ENTRY_TYPES = CANONICAL_PROJECTED_ENTRY_TYPES


class TacticExtractionError(ValueError):
    """Raised when a normalized corpus item cannot be converted to a tactic pattern."""


def extract_tactic_pattern(normalized_corpus_item: Mapping[str, Any]) -> dict[str, Any]:
    """Map one normalized corpus item to a canonical tactic pattern object."""

    return extract_projected_pattern(
        normalized_corpus_item,
        projection_field="pattern_type_tactic",
        pattern_id_prefix="tp",
        schema_version=CANONICAL_TACTIC_PATTERN_SCHEMA_VERSION,
        error_cls=TacticExtractionError,
    )


def extract_tactic_patterns(normalized_corpus_items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Map many normalized corpus items to canonical tactic pattern objects."""

    return extract_projected_patterns(
        normalized_corpus_items,
        projection_field="pattern_type_tactic",
        pattern_id_prefix="tp",
        schema_version=CANONICAL_TACTIC_PATTERN_SCHEMA_VERSION,
        error_cls=TacticExtractionError,
    )


def extract_tactic_patterns_from_corpus_bundle(
    normalized_corpus_bundle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Extract canonical tactic patterns from a normalized research corpus bundle."""

    return extract_projected_patterns_from_corpus_bundle(
        normalized_corpus_bundle,
        projection_field="pattern_type_tactic",
        pattern_id_prefix="tp",
        schema_version=CANONICAL_TACTIC_PATTERN_SCHEMA_VERSION,
        error_cls=TacticExtractionError,
    )


def extract_tactic_patterns_from_pattern_store(
    pattern_store_payload: Mapping[str, Any],
    *,
    latest_only: bool = True,
) -> list[dict[str, Any]]:
    """Load canonical tactic patterns from a persisted pattern store payload."""

    return extract_projected_patterns_from_pattern_store(
        pattern_store_payload,
        projection_field="pattern_type_tactic",
        pattern_id_prefix="tp",
        schema_version=CANONICAL_TACTIC_PATTERN_SCHEMA_VERSION,
        error_cls=TacticExtractionError,
        latest_only=latest_only,
    )


def map_normalized_corpus_item_to_tactic_pattern(
    normalized_corpus_item: Mapping[str, Any],
) -> dict[str, Any]:
    """Compatibility alias for deterministic single-item tactic extraction."""

    return extract_tactic_pattern(normalized_corpus_item)


def map_normalized_corpus_items_to_tactic_patterns(
    normalized_corpus_items: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Compatibility alias for deterministic multi-item tactic extraction."""

    return extract_tactic_patterns(normalized_corpus_items)
