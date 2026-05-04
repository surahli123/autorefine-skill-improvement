"""Read-only validation for AutoRefine adapter workspace state."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VALIDATION_MODES = {"optional", "requires_config", "requires_golden_set"}
DEFAULT_CONFIG_PATH = "domain-eval/config.json"
DEFAULT_GOLDEN_SET_PATH = "domain-eval/golden-set.jsonl"


@dataclass(frozen=True)
class AdapterState:
    selected_adapter_id: str | None
    adapter_config_path: str | None
    domain_eval_config_path: str | None
    effective_config_path: str
    domain_eval_version: str | None
    metric_name: str
    golden_set_path: str
    golden_set_count: int
    eval_script_path: str | None
    active_experiment_contract_path: str | None
    threshold_pass: Any = None
    threshold_concern: Any = None
    weight_multiplier: Any = None


@dataclass(frozen=True)
class AdapterStateValidation:
    ok: bool
    normalized: AdapterState | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def validate_adapter_state(
    workspace_path: Path | str,
    *,
    mode: str = "optional",
) -> AdapterStateValidation:
    if mode not in VALIDATION_MODES:
        raise ValueError(f"mode must be one of {', '.join(sorted(VALIDATION_MODES))}")

    workspace_path = Path(workspace_path)
    errors: list[str] = []
    warnings: list[str] = []
    state = _read_state(workspace_path, errors)
    if errors:
        return _validation(False, None, errors, warnings)

    adapter_config_ref = _non_empty_string(state.get("adapter_config_path"))
    domain_eval_config_ref = _non_empty_string(state.get("domain_eval_config_path"))
    effective_config_ref, config_path = _resolve_effective_config_path(
        workspace_path,
        adapter_config_ref,
        domain_eval_config_ref,
        warnings,
    )
    if not config_path.exists():
        if adapter_config_ref and effective_config_ref == adapter_config_ref:
            warnings.append(f"adapter_config_path {adapter_config_ref} not found")
        elif domain_eval_config_ref and effective_config_ref == domain_eval_config_ref:
            warnings.append(f"domain_eval_config_path {domain_eval_config_ref} not found")
        warnings.append("adapter config not configured")
        if mode in {"requires_config", "requires_golden_set"}:
            errors.append("domain-eval/config.json with author_confirmed=true is required")
        return _validation(not errors, None, errors, warnings)

    config = _read_json_object(config_path, "adapter config", errors)
    if config is None:
        return _validation(False, None, errors, warnings)

    if config.get("author_confirmed") is not True:
        message = "domain-eval/config.json author_confirmed=true is required"
        if mode in {"requires_config", "requires_golden_set"}:
            errors.append(message)
        else:
            warnings.append(message)

    eval_script_ref = _non_empty_string(config.get("eval_script_path"))
    if eval_script_ref:
        eval_script_path = _resolve_workspace_path(workspace_path, eval_script_ref)
        if not _is_readable_file(eval_script_path):
            message = f"{eval_script_ref} must exist and be readable"
            if mode in {"requires_config", "requires_golden_set"}:
                errors.append(message)
            else:
                warnings.append(message)
    elif mode in {"requires_config", "requires_golden_set"}:
        errors.append("domain-eval/config.json eval_script_path is required")

    state_adapter_id = _non_empty_string(state.get("selected_adapter_id"))
    config_adapter_id = _non_empty_string(config.get("adapter_id")) or _non_empty_string(
        config.get("selected_adapter_id")
    )
    if state_adapter_id and config_adapter_id and state_adapter_id != config_adapter_id:
        errors.append(
            "state.json selected_adapter_id must match adapter config adapter_id"
        )
    adapter_id = state_adapter_id or config_adapter_id
    if mode in {"requires_config", "requires_golden_set"} and not adapter_id:
        errors.append("domain-eval/config.json adapter_id is required")
    if mode == "requires_golden_set":
        _validate_required_domain_eval_config(config, errors)

    golden_set_ref = _non_empty_string(config.get("golden_set_path")) or DEFAULT_GOLDEN_SET_PATH
    golden_set_path = _resolve_workspace_path(workspace_path, golden_set_ref)
    golden_set_count = _count_jsonl_rows(golden_set_path, adapter_id, errors)
    if golden_set_count == 0:
        message = f"{golden_set_ref} must contain at least one JSONL row"
        if mode == "requires_golden_set":
            errors.append(message)
        else:
            warnings.append(message)

    metric_name = _non_empty_string(config.get("metric_name")) or "domain_metric"
    normalized = AdapterState(
        selected_adapter_id=adapter_id,
        adapter_config_path=adapter_config_ref,
        domain_eval_config_path=domain_eval_config_ref,
        effective_config_path=effective_config_ref,
        domain_eval_version=_non_empty_string(config.get("domain_eval_version")),
        metric_name=metric_name,
        golden_set_path=golden_set_ref,
        golden_set_count=golden_set_count,
        eval_script_path=eval_script_ref,
        active_experiment_contract_path=_non_empty_string(
            state.get("active_experiment_contract_path")
        ),
        threshold_pass=config.get("threshold_pass"),
        threshold_concern=config.get("threshold_concern"),
        weight_multiplier=config.get("weight_multiplier"),
    )
    return _validation(not errors, normalized, errors, warnings)


def _validation(
    ok: bool,
    normalized: AdapterState | None,
    errors: list[str],
    warnings: list[str],
) -> AdapterStateValidation:
    return AdapterStateValidation(
        ok=ok,
        normalized=normalized,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _read_state(workspace_path: Path, errors: list[str]) -> dict[str, Any]:
    state_path = workspace_path / "state.json"
    if not state_path.exists():
        return {}
    state = _read_json_object(state_path, "state.json", errors)
    return state or {}


def _read_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{path}: must be a file")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return None
    except OSError as exc:
        errors.append(f"{path}: unable to read: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label} must contain an object")
        return None
    return payload


def _non_empty_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _resolve_workspace_path(workspace_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return workspace_path / path


def _resolve_effective_config_path(
    workspace_path: Path,
    adapter_config_ref: str | None,
    domain_eval_config_ref: str | None,
    warnings: list[str],
) -> tuple[str, Path]:
    candidates: list[tuple[str, str]] = []
    if adapter_config_ref:
        candidates.append(("adapter_config_path", adapter_config_ref))
    if domain_eval_config_ref and domain_eval_config_ref != adapter_config_ref:
        candidates.append(("domain_eval_config_path", domain_eval_config_ref))
    if not candidates:
        candidates.append(("default_config_path", DEFAULT_CONFIG_PATH))

    selected_field, selected_ref = candidates[0]
    selected_path = _resolve_workspace_path(workspace_path, selected_ref)
    if selected_path.exists():
        return selected_ref, selected_path

    for fallback_field, fallback_ref in candidates[1:]:
        fallback_path = _resolve_workspace_path(workspace_path, fallback_ref)
        if fallback_path.exists():
            warnings.append(
                f"{selected_field} {selected_ref} not found; "
                f"using {fallback_field} {fallback_ref}"
            )
            return fallback_ref, fallback_path

    return selected_ref, selected_path


def _is_readable_file(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open("rb"):
            return True
    except OSError:
        return False


def _validate_required_domain_eval_config(config: dict[str, Any], errors: list[str]) -> None:
    required_strings = {
        "domain_eval_version": config.get("domain_eval_version"),
        "adapter_id": config.get("adapter_id"),
        "metric_name": config.get("metric_name"),
        "eval_script_path": config.get("eval_script_path"),
        "golden_set_path": config.get("golden_set_path"),
    }
    for field, value in required_strings.items():
        if not _non_empty_string(value):
            errors.append(f"domain-eval/config.json {field} is required")

    for field in ("threshold_pass", "threshold_concern", "weight_multiplier"):
        value = config.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"domain-eval/config.json {field} must be a number")


def _count_jsonl_rows(path: Path, adapter_id: str | None, errors: list[str]) -> int:
    if not path.exists():
        return 0
    if not path.is_file():
        errors.append(f"{path}: must be a file")
        return 0
    count = 0
    try:
        with path.open(encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"{path}:{lineno}: invalid JSONL row: {exc}")
                    continue
                if not isinstance(payload, dict):
                    errors.append(f"{path}:{lineno}: JSONL row must be an object")
                    continue
                _validate_golden_set_row(path, lineno, payload, adapter_id, errors)
                count += 1
    except OSError as exc:
        errors.append(f"{path}: unable to read: {exc}")
    return count


def _validate_golden_set_row(
    path: Path,
    lineno: int,
    payload: dict[str, Any],
    adapter_id: str | None,
    errors: list[str],
) -> None:
    if adapter_id != "search_retrieval_v1":
        return
    if not _non_empty_string(payload.get("query")):
        errors.append(f"{path}:{lineno}: search_retrieval_v1 row requires query")
    if not _non_empty_string(payload.get("doc_id")):
        errors.append(f"{path}:{lineno}: search_retrieval_v1 row requires doc_id")
    grade = payload.get("grade")
    if not isinstance(grade, int) or isinstance(grade, bool) or grade < 0:
        errors.append(
            f"{path}:{lineno}: search_retrieval_v1 row requires non-negative integer grade"
        )
