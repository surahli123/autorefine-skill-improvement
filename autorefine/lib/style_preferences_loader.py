from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from .research_corpus import _clean_text, _normalize_preference_signal_payload


STYLE_PREFERENCES_PAYLOAD_SCHEMA_VERSION = 1
STYLE_PREFERENCES_PAYLOAD_TYPE = "style_preferences"
DEFAULT_STYLE_PREFERENCES_FILENAME = "preferences.md"
CANONICAL_STYLE_PREFERENCE_STATUSES = (
    "not_detected",
    "pending_confirmation",
    "confirmed",
    "applied",
    "skipped",
)
ACTIVE_STYLE_PREFERENCE_STATUSES = ("confirmed", "applied")


def _coerce_optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _normalize_optional_text(value: Any) -> str | None:
    normalized_value = _clean_text(value)
    return normalized_value or None


def _normalize_status(value: Any) -> str | None:
    normalized_value = _normalize_optional_text(value)
    if normalized_value not in CANONICAL_STYLE_PREFERENCE_STATUSES:
        return None
    return normalized_value


def _normalize_experiment_id_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    return [
        item
        for item in (_coerce_optional_int(entry) for entry in value)
        if item is not None
    ]


def _normalize_signal_rows(
    value: Any,
    *,
    strict: bool,
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        if strict:
            raise ValueError("mid_session_preference_signals.signals must be a list")
        return []

    normalized_signals: list[dict[str, Any]] = []
    for index, raw_signal in enumerate(value):
        try:
            normalized_signals.append(_normalize_preference_signal_payload(raw_signal))
        except (TypeError, ValueError) as exc:
            if strict:
                raise ValueError(
                    f"mid_session_preference_signals.signals[{index}] is invalid"
                ) from exc
    return normalized_signals


def _normalize_detected_signal_count(
    value: Any,
    *,
    signals: list[dict[str, Any]],
) -> int:
    normalized_value = _coerce_optional_int(value)
    if normalized_value is not None:
        return normalized_value
    return len(signals)


def _normalize_confirmed_signal_count(
    value: Any,
    *,
    signals: list[dict[str, Any]],
) -> int:
    normalized_value = _coerce_optional_int(value)
    if normalized_value is not None:
        return normalized_value
    return sum(
        1
        for signal in signals
        if _normalize_optional_text(signal.get("confirmation_state"))
        in ACTIVE_STYLE_PREFERENCE_STATUSES
    )


def _normalize_mid_session_preference_signals(
    value: Any,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    if value is None:
        return {
            "status": None,
            "source_task_ref": None,
            "source_window_experiment_ids": [],
            "signals": [],
            "detected_signal_count": 0,
            "confirmed_signal_count": 0,
            "last_detected_at": None,
            "last_confirmed_experiment_id": None,
        }

    if not isinstance(value, Mapping):
        if strict:
            raise ValueError("mid_session_preference_signals must be a mapping")
        return _normalize_mid_session_preference_signals(None, strict=strict)

    normalized_signals = _normalize_signal_rows(value.get("signals"), strict=strict)
    return {
        "status": _normalize_status(value.get("status")),
        "source_task_ref": _normalize_optional_text(value.get("source_task_ref")),
        "source_window_experiment_ids": _normalize_experiment_id_list(
            value.get("source_window_experiment_ids")
        ),
        "signals": normalized_signals,
        "detected_signal_count": _normalize_detected_signal_count(
            value.get("detected_signal_count"),
            signals=normalized_signals,
        ),
        "confirmed_signal_count": _normalize_confirmed_signal_count(
            value.get("confirmed_signal_count"),
            signals=normalized_signals,
        ),
        "last_detected_at": _normalize_optional_text(value.get("last_detected_at")),
        "last_confirmed_experiment_id": _coerce_optional_int(
            value.get("last_confirmed_experiment_id")
        ),
    }


def _normalize_workspace_root(
    *,
    state: Mapping[str, Any] | None,
    workspace_path: str | Path | None,
) -> Path | None:
    explicit_workspace_path = (
        Path(workspace_path).expanduser() if workspace_path is not None else None
    )
    if explicit_workspace_path is not None:
        return explicit_workspace_path

    if not isinstance(state, Mapping):
        return None

    stored_workspace_path = _normalize_optional_text(state.get("workspace_path"))
    if not stored_workspace_path:
        return None
    return Path(stored_workspace_path).expanduser()


def _normalize_path_reference(
    *,
    state: Mapping[str, Any] | None,
    workspace_root: Path | None,
    default_filename: str,
) -> str | None:
    raw_path = None
    if isinstance(state, Mapping):
        raw_path = _normalize_optional_text(state.get("mid_session_preference_signals_path"))

    if raw_path:
        return raw_path

    if workspace_root is None:
        return None

    return str((workspace_root / default_filename).resolve())


def resolve_style_preferences_path(
    state: Mapping[str, Any] | None,
    *,
    workspace_path: str | Path | None = None,
    default_filename: str = DEFAULT_STYLE_PREFERENCES_FILENAME,
) -> str | None:
    workspace_root = _normalize_workspace_root(
        state=state,
        workspace_path=workspace_path,
    )
    path_reference = _normalize_path_reference(
        state=state,
        workspace_root=workspace_root,
        default_filename=default_filename,
    )
    if not path_reference:
        return None

    if path_reference.startswith("[workspace]/"):
        if workspace_root is None:
            return path_reference
        relative_suffix = path_reference[len("[workspace]/") :]
        return str((workspace_root / relative_suffix).resolve())

    resolved_path = Path(path_reference).expanduser()
    if not resolved_path.is_absolute() and workspace_root is not None:
        resolved_path = workspace_root / resolved_path
    if resolved_path.is_absolute() or workspace_root is not None:
        return str(resolved_path.resolve())
    return path_reference


def _normalize_state_write_path_reference(
    *,
    state: Mapping[str, Any] | None,
    workspace_root: Path | None,
    path_reference: str | Path | None,
    default_filename: str,
) -> str | None:
    normalized_path_reference = _normalize_optional_text(path_reference)
    if normalized_path_reference:
        if normalized_path_reference.startswith("[workspace]/"):
            return normalized_path_reference

        if workspace_root is not None:
            candidate_path = Path(normalized_path_reference).expanduser()
            if not candidate_path.is_absolute():
                candidate_path = workspace_root / candidate_path
            try:
                relative_candidate = candidate_path.resolve().relative_to(
                    workspace_root.resolve()
                )
            except ValueError:
                return normalized_path_reference
            return f"[workspace]/{relative_candidate.as_posix()}"

        return normalized_path_reference

    existing_path_reference = None
    if isinstance(state, Mapping):
        existing_path_reference = _normalize_optional_text(
            state.get("mid_session_preference_signals_path")
        )
    if existing_path_reference:
        return _normalize_state_write_path_reference(
            state=None,
            workspace_root=workspace_root,
            path_reference=existing_path_reference,
            default_filename=default_filename,
        )

    if workspace_root is None:
        return None
    return f"[workspace]/{default_filename}"


def persist_style_preferences_detection_to_run_state(
    state: Mapping[str, Any] | None,
    *,
    detected_signals: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
    detection_status: str,
    source_task_ref: str | None = None,
    source_window_experiment_ids: list[Any] | tuple[Any, ...] | None = None,
    last_detected_at: str | None = None,
    last_confirmed_experiment_id: int | None = None,
    workspace_path: str | Path | None = None,
    path_reference: str | Path | None = None,
    default_filename: str = DEFAULT_STYLE_PREFERENCES_FILENAME,
    strict: bool = True,
) -> dict[str, Any]:
    """Persist a completed preference-detection batch into the active run state.

    Detection callers should invoke this immediately after scan completion so
    the refreshed session state exposes both the persisted ledger and the
    canonical in-memory ``style_preferences`` payload without waiting for a
    reload/resume cycle.
    """

    normalized_status = _normalize_status(detection_status)
    if strict and normalized_status is None:
        raise ValueError(
            "detection_status must be one of "
            f"{CANONICAL_STYLE_PREFERENCE_STATUSES}; received {detection_status!r}"
        )

    normalized_state = deepcopy(dict(state)) if isinstance(state, Mapping) else {}
    if workspace_path is not None:
        normalized_state["workspace_path"] = str(Path(workspace_path).expanduser())

    normalized_ledger = _normalize_mid_session_preference_signals(
        {
            "status": normalized_status,
            "source_task_ref": source_task_ref,
            "source_window_experiment_ids": list(source_window_experiment_ids or []),
            "signals": list(detected_signals or []),
            "last_detected_at": last_detected_at,
            "last_confirmed_experiment_id": last_confirmed_experiment_id,
        },
        strict=strict,
    )
    normalized_state["mid_session_preference_signals"] = normalized_ledger

    normalized_workspace_root = _normalize_workspace_root(
        state=normalized_state,
        workspace_path=workspace_path,
    )
    normalized_state["mid_session_preference_signals_path"] = (
        _normalize_state_write_path_reference(
            state=normalized_state,
            workspace_root=normalized_workspace_root,
            path_reference=path_reference,
            default_filename=default_filename,
        )
    )
    normalized_state["style_preferences"] = build_style_preferences_payload_from_state(
        normalized_state,
        workspace_path=workspace_path,
        default_filename=default_filename,
        strict=strict,
    )
    return normalized_state


def build_style_preferences_payload_from_state(
    state: Mapping[str, Any] | None,
    *,
    workspace_path: str | Path | None = None,
    default_filename: str = DEFAULT_STYLE_PREFERENCES_FILENAME,
    strict: bool = False,
) -> dict[str, Any]:
    normalized_ledger = _normalize_mid_session_preference_signals(
        state.get("mid_session_preference_signals") if isinstance(state, Mapping) else None,
        strict=strict,
    )
    normalized_status = normalized_ledger["status"]
    is_active_status = normalized_status in ACTIVE_STYLE_PREFERENCE_STATUSES
    active_signals = (
        deepcopy(normalized_ledger["signals"])
        if is_active_status
        else []
    )

    workspace_root = _normalize_workspace_root(
        state=state,
        workspace_path=workspace_path,
    )
    path_reference = _normalize_path_reference(
        state=state,
        workspace_root=workspace_root,
        default_filename=default_filename,
    )

    return {
        "schema_version": STYLE_PREFERENCES_PAYLOAD_SCHEMA_VERSION,
        "payload_type": STYLE_PREFERENCES_PAYLOAD_TYPE,
        "status": normalized_status,
        "source_task_ref": normalized_ledger["source_task_ref"],
        "source_window_experiment_ids": normalized_ledger["source_window_experiment_ids"],
        "signals": deepcopy(normalized_ledger["signals"]),
        "active_signals": active_signals,
        "detected_signal_count": normalized_ledger["detected_signal_count"],
        "confirmed_signal_count": normalized_ledger["confirmed_signal_count"],
        "last_detected_at": normalized_ledger["last_detected_at"],
        "last_confirmed_experiment_id": normalized_ledger["last_confirmed_experiment_id"],
        "mid_session_preference_signals_path": path_reference,
        "resolved_preferences_path": resolve_style_preferences_path(
            state,
            workspace_path=workspace_path,
            default_filename=default_filename,
        ),
    }


def load_style_preferences_payload_from_state(
    state: Mapping[str, Any] | None,
    *,
    workspace_path: str | Path | None = None,
    default_filename: str = DEFAULT_STYLE_PREFERENCES_FILENAME,
    strict: bool = False,
) -> dict[str, Any]:
    """Build the active loop style-preferences envelope from persisted state.

    Phase 7 and Session Close consumers should carry this normalized payload in
    the loaded run context so every mid-loop stage reads the same explainable
    preference bundle across eval, mutate, test, and closeout iterations.
    """

    return build_style_preferences_payload_from_state(
        state,
        workspace_path=workspace_path,
        default_filename=default_filename,
        strict=strict,
    )


__all__ = [
    "ACTIVE_STYLE_PREFERENCE_STATUSES",
    "CANONICAL_STYLE_PREFERENCE_STATUSES",
    "DEFAULT_STYLE_PREFERENCES_FILENAME",
    "STYLE_PREFERENCES_PAYLOAD_SCHEMA_VERSION",
    "STYLE_PREFERENCES_PAYLOAD_TYPE",
    "build_style_preferences_payload_from_state",
    "load_style_preferences_payload_from_state",
    "persist_style_preferences_detection_to_run_state",
    "resolve_style_preferences_path",
]
