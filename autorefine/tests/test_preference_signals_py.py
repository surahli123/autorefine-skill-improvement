from __future__ import annotations

import pytest

from autorefine.lib.preference_signals import (
    _normalize_preference_signal_payload,
    build_preference_signal_payload_from_override_scan,
    derive_preference_signal_candidates_from_override_scan,
    normalize_preference_signal_payload,
)
from autorefine.lib.research_corpus import (
    CANONICAL_PREFERENCE_KEYS,
    build_preference_signal_payload_from_override_scan as facade_build_preference_signal_payload,
)


def _override_row(
    experiment_id: int,
    *,
    changed_locations: list[str],
    mutation_types: list[str],
    agent_verdict: str = "keep",
    user_verdict: str = "discard",
) -> dict[str, object]:
    return {
        "experiment_id": experiment_id,
        "agent_verdict": agent_verdict,
        "user_verdict": user_verdict,
        "override_detected": agent_verdict != user_verdict,
        "override_direction": f"{agent_verdict}_to_{user_verdict}"
        if agent_verdict != user_verdict
        else None,
        "changed_locations": changed_locations,
        "mutation_types": mutation_types,
        "completion_cadence": {"completed_experiments": experiment_id},
    }


def _scan_task(*rows: dict[str, object]) -> dict[str, object]:
    return {
        "task_type": "user_override_scan",
        "completed_experiment_slot": 6,
        "trigger_experiment_id": 6,
        "experiment_window": list(rows),
    }


def test_build_preference_signal_payload_from_override_scan_normalizes_support_and_confidence() -> None:
    scan_task = _scan_task(
        _override_row(4, changed_locations=["## Gotchas"], mutation_types=["added"]),
        _override_row(5, changed_locations=["## Gotchas"], mutation_types=["added"]),
    )

    payload = build_preference_signal_payload_from_override_scan(
        scan_task,
        preference_key="mutation_operation",
        preference_value="avoid_add",
        supporting_entries=scan_task["experiment_window"],
        confirmation_state="confirmed",
    )

    assert payload["preference_key"] == "mutation_operation"
    assert payload["preference_value"] == "avoid_add"
    assert payload["preference_statement"] == "Avoid additive mutations."
    assert payload["confirmation_state"] == "confirmed"
    assert payload["detected_from"]["source_ref"] == "checkpoint-tasks/exp6-user-override-scan.json"
    assert payload["detected_from"]["support_count"] == 2
    assert payload["detected_from"]["confidence_metadata"] == {
        "signal_confidence": "high",
        "source_confidence": "medium",
        "confidence_reason": (
            "Derived from 2 consistent keep_to_discard overrides supporting "
            "mutation_operation=avoid_add."
        ),
        "confirmation_bonus_applied": True,
        "support_count": 2,
    }
    assert [
        entry["source_ref"]
        for entry in payload["detected_from"]["normalized_override_entries"]
    ] == [
        "checkpoint-tasks/exp6-user-override-scan.json#experiment-4",
        "checkpoint-tasks/exp6-user-override-scan.json#experiment-5",
    ]


def test_normalize_preference_signal_payload_is_public_api() -> None:
    scan_task = _scan_task(
        _override_row(4, changed_locations=["## Gotchas"], mutation_types=["added"]),
        _override_row(5, changed_locations=["## Gotchas"], mutation_types=["added"]),
    )
    payload = build_preference_signal_payload_from_override_scan(
        scan_task,
        preference_key="mutation_operation",
        preference_value="avoid_add",
        supporting_entries=scan_task["experiment_window"],
    )

    assert normalize_preference_signal_payload(payload) == payload
    assert _normalize_preference_signal_payload(payload) == payload


def test_derive_preference_signal_candidates_returns_mutation_operation_and_section_focus() -> None:
    scan_task = _scan_task(
        _override_row(4, changed_locations=["## Gotchas"], mutation_types=["added"]),
        _override_row(5, changed_locations=["## Gotchas"], mutation_types=["added"]),
        _override_row(
            6,
            changed_locations=["## Examples"],
            mutation_types=["modified"],
            agent_verdict="keep",
            user_verdict="keep",
        ),
    )

    candidates = derive_preference_signal_candidates_from_override_scan(
        scan_task,
        confirmation_state="confirmed",
    )

    candidate_index = {
        (candidate["preference_key"], candidate["preference_value"]): candidate
        for candidate in candidates
    }
    assert set(candidate_index) == {
        ("mutation_operation", "avoid_add"),
        ("section_focus", "avoid"),
    }
    assert candidate_index[("section_focus", "avoid")]["preference_scope"] == {
        "section_ids": ["## Gotchas"]
    }
    assert (
        candidate_index[("section_focus", "avoid")]["detected_from"][
            "normalized_override_entries"
        ][0]["preference_key"]
        == "section_focus"
    )


def test_derive_preference_signal_candidates_requires_two_override_rows() -> None:
    scan_task = _scan_task(
        _override_row(4, changed_locations=["## Gotchas"], mutation_types=["added"]),
        _override_row(
            5,
            changed_locations=["## Examples"],
            mutation_types=["modified"],
            agent_verdict="keep",
            user_verdict="keep",
        ),
    )

    assert derive_preference_signal_candidates_from_override_scan(scan_task) == []


def test_section_focus_without_shared_section_or_scope_raises_existing_validation_error() -> None:
    scan_task = _scan_task(
        _override_row(4, changed_locations=["## Gotchas"], mutation_types=["added"]),
        _override_row(5, changed_locations=["## Examples"], mutation_types=["added"]),
    )

    with pytest.raises(
        ValueError,
        match=r"preference_scope\.section_ids is required when preference_key = section_focus",
    ):
        build_preference_signal_payload_from_override_scan(
            scan_task,
            preference_key="section_focus",
            preference_value="avoid",
            supporting_entries=scan_task["experiment_window"],
        )


def test_research_corpus_facade_still_reexports_preference_signal_api() -> None:
    scan_task = _scan_task(
        _override_row(4, changed_locations=["## Gotchas"], mutation_types=["added"]),
        _override_row(5, changed_locations=["## Gotchas"], mutation_types=["added"]),
    )

    payload = facade_build_preference_signal_payload(
        scan_task,
        preference_key="mutation_operation",
        preference_value="avoid_add",
    )

    assert "mutation_operation" in CANONICAL_PREFERENCE_KEYS
    assert payload["preference_key"] == "mutation_operation"
