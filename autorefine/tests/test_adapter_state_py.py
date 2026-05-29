import json
import pytest

from autorefine.lib.adapter_state import validate_adapter_state


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_adapter_config(
    workspace_path,
    *,
    path="domain-eval/config.json",
    author_confirmed=True,
    eval_script_path="domain-eval/eval-metric.py",
    golden_set_path="domain-eval/golden-set.jsonl",
):
    config_path = workspace_path / path
    _write_json(
        config_path,
        {
            "domain_eval_version": "1.0",
            "adapter_id": "search_retrieval_v1",
            "metric_name": "ndcg_at_5",
            "threshold_pass": 0.65,
            "threshold_concern": 0.50,
            "weight_multiplier": 2.0,
            "eval_script_path": eval_script_path,
            "golden_set_path": golden_set_path,
            "author_confirmed": author_confirmed,
        },
    )
    return config_path


def test_optional_mode_allows_absent_config_without_writing_state(tmp_path):
    workspace_path = tmp_path / "workspace"

    result = validate_adapter_state(workspace_path, mode="optional")

    assert result.ok is True
    assert result.normalized is None
    assert result.errors == ()
    assert "adapter config not configured" in result.warnings
    assert not (workspace_path / "state.json").exists()

    with pytest.raises(AttributeError):
        result.warnings.append("mutated")


def test_strict_modes_require_config(tmp_path):
    workspace_path = tmp_path / "workspace"

    for mode in ["requires_config", "requires_golden_set"]:
        result = validate_adapter_state(workspace_path, mode=mode)

        assert result.ok is False
        assert result.normalized is None
        assert "domain-eval/config.json with author_confirmed=true is required" in result.errors
        assert "adapter config not configured" in result.warnings


def test_legacy_domain_eval_config_path_becomes_effective_config_path(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_json(
        workspace_path / "state.json",
        {
            "selected_adapter_id": "search_retrieval_v1",
            "domain_eval_config_path": "custom/domain-config.json",
            "active_experiment_contract_path": "runs/run_1/experiment-contract.json",
        },
    )
    _write_adapter_config(
        workspace_path,
        path="custom/domain-config.json",
        golden_set_path="custom/golden-set.jsonl",
        eval_script_path="custom/eval-metric.py",
    )
    (workspace_path / "custom" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")
    _write_jsonl(
        workspace_path / "custom" / "golden-set.jsonl",
        [{"query": "trust gate", "doc_id": "trust_gate", "grade": 3}],
    )

    result = validate_adapter_state(workspace_path, mode="requires_golden_set")

    assert result.ok is True
    assert result.errors == ()
    assert result.normalized.selected_adapter_id == "search_retrieval_v1"
    assert result.normalized.adapter_config_path is None
    assert result.normalized.domain_eval_config_path == "custom/domain-config.json"
    assert result.normalized.effective_config_path == "custom/domain-config.json"
    assert result.normalized.domain_eval_version == "1.0"
    assert result.normalized.metric_name == "ndcg_at_5"
    assert result.normalized.golden_set_path == "custom/golden-set.jsonl"
    assert result.normalized.golden_set_count == 1
    assert result.normalized.eval_script_path == "custom/eval-metric.py"
    assert result.normalized.active_experiment_contract_path == "runs/run_1/experiment-contract.json"
    assert result.normalized.threshold_concern == 0.50
    assert result.normalized.weight_multiplier == 2.0


def test_stale_adapter_config_path_falls_back_to_valid_domain_eval_config_path(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_json(
        workspace_path / "state.json",
        {
            "selected_adapter_id": "search_retrieval_v1",
            "adapter_config_path": "stale/missing-config.json",
            "domain_eval_config_path": "custom/domain-config.json",
        },
    )
    _write_adapter_config(
        workspace_path,
        path="custom/domain-config.json",
        golden_set_path="custom/golden-set.jsonl",
        eval_script_path="custom/eval-metric.py",
    )
    (workspace_path / "custom" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")
    _write_jsonl(
        workspace_path / "custom" / "golden-set.jsonl",
        [{"query": "trust gate", "doc_id": "trust_gate", "grade": 3}],
    )

    result = validate_adapter_state(workspace_path, mode="requires_golden_set")

    assert result.ok is True
    assert result.errors == ()
    assert result.normalized.adapter_config_path == "stale/missing-config.json"
    assert result.normalized.domain_eval_config_path == "custom/domain-config.json"
    assert result.normalized.effective_config_path == "custom/domain-config.json"
    assert any("adapter_config_path" in warning for warning in result.warnings)


def test_author_confirmation_is_required_when_config_is_required(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_adapter_config(workspace_path, author_confirmed=False)

    result = validate_adapter_state(workspace_path, mode="requires_config")

    assert result.ok is False
    assert "domain-eval/config.json author_confirmed=true is required" in result.errors


def test_eval_script_must_be_readable_when_config_is_required(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_adapter_config(workspace_path)

    result = validate_adapter_state(workspace_path, mode="requires_config")

    assert result.ok is False
    assert "domain-eval/eval-metric.py must exist and be readable" in result.errors


def test_missing_golden_set_warns_in_requires_config_and_errors_when_required(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_adapter_config(workspace_path)
    (workspace_path / "domain-eval" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")

    config_result = validate_adapter_state(workspace_path, mode="requires_config")
    strict_result = validate_adapter_state(workspace_path, mode="requires_golden_set")

    assert config_result.ok is True
    assert config_result.normalized.golden_set_count == 0
    assert "domain-eval/golden-set.jsonl must contain at least one JSONL row" in config_result.warnings
    assert strict_result.ok is False
    assert "domain-eval/golden-set.jsonl must contain at least one JSONL row" in strict_result.errors


def test_empty_golden_set_warns_in_requires_config_and_errors_when_required(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_adapter_config(workspace_path)
    (workspace_path / "domain-eval" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")
    (workspace_path / "domain-eval" / "golden-set.jsonl").parent.mkdir(parents=True, exist_ok=True)
    (workspace_path / "domain-eval" / "golden-set.jsonl").write_text("", encoding="utf-8")

    config_result = validate_adapter_state(workspace_path, mode="requires_config")
    strict_result = validate_adapter_state(workspace_path, mode="requires_golden_set")

    assert config_result.ok is True
    assert "domain-eval/golden-set.jsonl must contain at least one JSONL row" in config_result.warnings
    assert strict_result.ok is False
    assert "domain-eval/golden-set.jsonl must contain at least one JSONL row" in strict_result.errors


def test_validation_does_not_write_aligned_state_fields(tmp_path):
    workspace_path = tmp_path / "workspace"
    original_state = {
        "domain_eval_config_path": "custom/domain-config.json",
    }
    _write_json(workspace_path / "state.json", original_state)
    _write_adapter_config(
        workspace_path,
        path="custom/domain-config.json",
        golden_set_path="custom/golden-set.jsonl",
        eval_script_path="custom/eval-metric.py",
    )
    (workspace_path / "custom" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")
    _write_jsonl(
        workspace_path / "custom" / "golden-set.jsonl",
        [{"query": "trust gate", "doc_id": "trust_gate", "grade": 3}],
    )

    result = validate_adapter_state(workspace_path, mode="requires_golden_set")

    assert result.ok is True
    assert json.loads((workspace_path / "state.json").read_text(encoding="utf-8")) == original_state


def test_state_and_config_adapter_id_mismatch_is_error(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_json(
        workspace_path / "state.json",
        {
            "selected_adapter_id": "code_verification_v1",
        },
    )
    _write_adapter_config(workspace_path)
    (workspace_path / "domain-eval" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")
    _write_jsonl(
        workspace_path / "domain-eval" / "golden-set.jsonl",
        [{"query": "trust gate", "doc_id": "trust_gate", "grade": 3}],
    )

    result = validate_adapter_state(workspace_path, mode="requires_golden_set")

    assert result.ok is False
    assert "state.json selected_adapter_id must match adapter config adapter_id" in result.errors


def test_directory_config_path_returns_validation_error(tmp_path):
    workspace_path = tmp_path / "workspace"
    (workspace_path / "domain-eval" / "config.json").mkdir(parents=True)

    result = validate_adapter_state(workspace_path, mode="requires_config")

    assert result.ok is False
    assert any(error.endswith("domain-eval/config.json: must be a file") for error in result.errors)


def test_directory_golden_set_path_returns_validation_error(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_adapter_config(workspace_path)
    (workspace_path / "domain-eval" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")
    (workspace_path / "domain-eval" / "golden-set.jsonl").mkdir(parents=True)

    result = validate_adapter_state(workspace_path, mode="requires_golden_set")

    assert result.ok is False
    assert any(error.endswith("domain-eval/golden-set.jsonl: must be a file") for error in result.errors)


def test_requires_golden_set_requires_domain_eval_config_fields(tmp_path):
    workspace_path = tmp_path / "workspace"
    config_path = _write_adapter_config(workspace_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.pop("threshold_concern")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    (workspace_path / "domain-eval" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")
    _write_jsonl(
        workspace_path / "domain-eval" / "golden-set.jsonl",
        [{"query": "trust gate", "doc_id": "trust_gate", "grade": 3}],
    )

    result = validate_adapter_state(workspace_path, mode="requires_golden_set")

    assert result.ok is False
    assert "domain-eval/config.json threshold_concern must be a number" in result.errors


def test_requires_config_requires_adapter_id(tmp_path):
    workspace_path = tmp_path / "workspace"
    config_path = _write_adapter_config(workspace_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.pop("adapter_id")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    (workspace_path / "domain-eval" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")

    result = validate_adapter_state(workspace_path, mode="requires_config")

    assert result.ok is False
    assert "domain-eval/config.json adapter_id is required" in result.errors


def test_search_golden_set_rows_match_adapter_schema(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_adapter_config(workspace_path)
    (workspace_path / "domain-eval" / "eval-metric.py").write_text("# metric\n", encoding="utf-8")
    _write_jsonl(
        workspace_path / "domain-eval" / "golden-set.jsonl",
        [{"id": "generic", "input": "query", "expected_output": "doc"}],
    )

    result = validate_adapter_state(workspace_path, mode="requires_golden_set")

    assert result.ok is False
    assert any("search_retrieval_v1 row requires query" in error for error in result.errors)
    assert any("search_retrieval_v1 row requires doc_id" in error for error in result.errors)
    assert any("search_retrieval_v1 row requires non-negative integer grade" in error for error in result.errors)
