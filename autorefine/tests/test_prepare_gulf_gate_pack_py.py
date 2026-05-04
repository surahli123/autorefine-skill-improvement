import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "prepare_gulf_gate_pack",
    SCRIPTS_DIR / "prepare-gulf-gate-pack.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["prepare_gulf_gate_pack"] = _mod
_spec.loader.exec_module(_mod)

_campaign_spec = importlib.util.spec_from_file_location(
    "run_campaign_for_gate_pack_test",
    SCRIPTS_DIR / "run-campaign.py",
)
_campaign_mod = importlib.util.module_from_spec(_campaign_spec)
sys.modules["run_campaign_for_gate_pack_test"] = _campaign_mod
_campaign_spec.loader.exec_module(_campaign_mod)


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _skill(skill_id, tmp_path):
    workspace_path = tmp_path / "workspaces" / skill_id
    skill_path = tmp_path / "skills" / skill_id / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(
        f"---\nname: {skill_id}\ndescription: Test skill.\n---\n\n# Test\n",
        encoding="utf-8",
    )
    return {
        "skill_id": skill_id,
        "skill_path": str(skill_path),
        "workspace_path": str(workspace_path),
        "phase7_command": ["python3", "-m", "autorefine.phase7", skill_id],
        "result_refs": [str(workspace_path / "results.json")],
    }


def _manifest(tmp_path, skills):
    return {"campaign_id": "campaign_a", "skills": skills}


DEFAULT_GOLDEN_ROWS = [{"query": "trust gate", "doc_id": "trust_gate", "grade": 3}]


def _write_adapter_evidence(
    workspace_path,
    *,
    config_path="domain-eval/config.json",
    eval_script_path="domain-eval/eval-metric.py",
    golden_set_path="domain-eval/golden-set.jsonl",
    eval_script_body="# metric\n",
    threshold_pass=0.65,
    threshold_concern=0.50,
    weight_multiplier=2.0,
    write_golden_set=True,
):
    _write_json(
        workspace_path / config_path,
        {
            "domain_eval_version": "1.0",
            "adapter_id": "search_retrieval_v1",
            "metric_name": "ndcg_at_5",
            "threshold_pass": threshold_pass,
            "threshold_concern": threshold_concern,
            "weight_multiplier": weight_multiplier,
            "eval_script_path": eval_script_path,
            "golden_set_path": golden_set_path,
            "author_confirmed": True,
        },
    )
    (workspace_path / eval_script_path).parent.mkdir(parents=True, exist_ok=True)
    (workspace_path / eval_script_path).write_text(
        eval_script_body,
        encoding="utf-8",
    )
    if write_golden_set:
        _write_jsonl(workspace_path / golden_set_path, DEFAULT_GOLDEN_ROWS)


def test_prepare_workspace_auto_approves_adapter_backed_gulf_gates(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_adapter_evidence(workspace_path)

    result = _mod.prepare_workspace_gate_pack(workspace_path, "search")

    state = json.loads((workspace_path / "state.json").read_text(encoding="utf-8"))
    gate_pack = json.loads((workspace_path / "gulf-gate-pack.json").read_text(encoding="utf-8"))

    assert result["status"] == "approved"
    assert state["gates"] == {"gulf_1": "approved", "gulf_2": "approved"}
    assert state["selected_adapter_id"] == "search_retrieval_v1"
    assert state["adapter_config_path"] == "domain-eval/config.json"
    assert gate_pack["approval_source"] == "preauthorized_adapter_metric_v1"
    assert gate_pack["evidence"]["golden_set_count"] == 1
    assert "PREAUTHORIZED APPROVAL" in (
        workspace_path / "gate-report-gulf-1.md"
    ).read_text(encoding="utf-8")
    assert "domain-metric" in (workspace_path / "eval-suite.md").read_text(encoding="utf-8")


def test_prepare_workspace_blocks_without_adapter_evidence(tmp_path):
    workspace_path = tmp_path / "workspace"

    result = _mod.prepare_workspace_gate_pack(workspace_path, "subjective")

    assert result["status"] == "blocked"
    assert "author_confirmed" in result["reason"]
    assert not (workspace_path / "state.json").exists()
    assert not (workspace_path / "gulf-gate-pack.json").exists()


def test_prepare_workspace_blocks_configured_adapter_without_golden_set(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_adapter_evidence(workspace_path, write_golden_set=False)

    result = _mod.prepare_workspace_gate_pack(workspace_path, "search")

    assert result["status"] == "blocked"
    assert "domain-eval/golden-set.jsonl must contain at least one JSONL row" in result["reason"]
    assert not (workspace_path / "state.json").exists()
    assert not (workspace_path / "gulf-gate-pack.json").exists()


def test_prepare_workspace_uses_normalized_custom_adapter_config_path(tmp_path):
    workspace_path = tmp_path / "workspace"
    _write_json(
        workspace_path / "state.json",
        {
            "adapter_config_path": "custom/domain-config.json",
        },
    )
    _write_adapter_evidence(
        workspace_path,
        config_path="custom/domain-config.json",
        eval_script_path="custom/eval-metric.py",
        golden_set_path="custom/golden-set.jsonl",
    )

    result = _mod.prepare_workspace_gate_pack(workspace_path, "search")

    state = json.loads((workspace_path / "state.json").read_text(encoding="utf-8"))
    gate_pack = json.loads((workspace_path / "gulf-gate-pack.json").read_text(encoding="utf-8"))
    assert result["status"] == "approved"
    assert result["evidence"]["config_path"] == "custom/domain-config.json"
    assert state["adapter_config_path"] == "custom/domain-config.json"
    assert state["domain_eval_config_path"] == "custom/domain-config.json"
    assert gate_pack["evidence"]["config_path"] == "custom/domain-config.json"


def test_gate_pack_makes_campaign_orchestrator_ready_for_full_phase7(tmp_path):
    skill = _skill("search", tmp_path)
    workspace_path = Path(skill["workspace_path"])
    _write_adapter_evidence(workspace_path)
    _mod.prepare_workspace_gate_pack(workspace_path, "search")

    manifest = _campaign_mod.validate_campaign_manifest(_manifest(tmp_path, [skill]))
    report = _campaign_mod.campaign_report(manifest)
    target = report["execution_plan"]["targets"][0]
    gulf3 = next(stage for stage in target["stages"] if stage["stage"] == "gulf3_generalization")

    assert gulf3["status"] == "ready"
    assert gulf3["mode"] == "full"
    assert gulf3["next_action"] == "run_phase7_full"


def test_cli_prepares_manifest_workspaces_and_writes_summary(tmp_path):
    skill = _skill("search", tmp_path)
    workspace_path = Path(skill["workspace_path"])
    _write_adapter_evidence(workspace_path)
    manifest_path = tmp_path / "manifest.json"
    summary_path = tmp_path / "summary.json"
    _write_json(manifest_path, _manifest(tmp_path, [skill]))

    _mod.main(
        [
            "--manifest",
            str(manifest_path),
            "--summary-output",
            str(summary_path),
        ]
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    state = json.loads((workspace_path / "state.json").read_text(encoding="utf-8"))

    assert summary["approved_count"] == 1
    assert summary["blocked_count"] == 0
    assert state["gates"]["gulf_1"] == "approved"
    assert state["gates"]["gulf_2"] == "approved"


def test_direct_script_entrypoint_prepares_manifest_workspace(tmp_path):
    skill = _skill("search", tmp_path)
    workspace_path = Path(skill["workspace_path"])
    _write_adapter_evidence(workspace_path)
    manifest_path = tmp_path / "manifest.json"
    summary_path = tmp_path / "summary.json"
    _write_json(manifest_path, _manifest(tmp_path, [skill]))

    result = subprocess.run(
        [
            str(SCRIPTS_DIR / "prepare-gulf-gate-pack.py"),
            "--manifest",
            str(manifest_path),
            "--summary-output",
            str(summary_path),
        ],
        cwd=SCRIPTS_DIR.parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    state = json.loads((workspace_path / "state.json").read_text(encoding="utf-8"))
    assert summary["approved_count"] == 1
    assert summary["blocked_count"] == 0
    assert state["gates"]["gulf_1"] == "approved"
    assert state["gates"]["gulf_2"] == "approved"


def test_count_jsonl_rows_facade_preserves_legacy_counting_contract(tmp_path):
    jsonl_path = tmp_path / "rows.jsonl"
    jsonl_path.write_text('{"one": 1}\n\n["legacy", "accepted"]\n', encoding="utf-8")

    assert _mod.count_jsonl_rows(jsonl_path) == 2
    assert _mod.count_jsonl_rows(tmp_path / "missing.jsonl") == 0


def test_campaign_gate_pack_default_prepares_pairwise_candidate_targets(tmp_path):
    alpha = _skill("alpha", tmp_path)
    beta = _skill("beta", tmp_path)
    alpha["triggers"] = ["search", "rank"]
    beta["triggers"] = ["search", "rank"]
    eval_script_body = "# shared metric\n"
    _write_adapter_evidence(Path(alpha["workspace_path"]), eval_script_body=eval_script_body)
    _write_adapter_evidence(Path(beta["workspace_path"]), eval_script_body=eval_script_body)
    manifest = _campaign_mod.validate_campaign_manifest(_manifest(tmp_path, [alpha, beta]))

    summary = _mod.prepare_campaign_gate_pack(manifest)

    assert summary["approved_count"] == 3
    assert [result["skill_id"] for result in summary["results"]] == [
        "alpha",
        "alpha__beta",
        "beta",
    ]


def test_campaign_gate_pack_prepares_pairwise_candidate_targets(tmp_path):
    alpha = _skill("alpha", tmp_path)
    beta = _skill("beta", tmp_path)
    alpha["triggers"] = ["search", "rank"]
    beta["triggers"] = ["search", "rank"]
    eval_script_body = "# shared metric\n"
    _write_adapter_evidence(Path(alpha["workspace_path"]), eval_script_body=eval_script_body)
    _write_adapter_evidence(Path(beta["workspace_path"]), eval_script_body=eval_script_body)
    manifest = _campaign_mod.validate_campaign_manifest(_manifest(tmp_path, [alpha, beta]))

    summary = _mod.prepare_campaign_gate_pack(manifest, _campaign_mod)
    report = _campaign_mod.campaign_report(manifest)
    candidate = next(
        target for target in report["execution_plan"]["targets"]
        if target["target_id"] == "alpha__beta"
    )
    gulf3 = next(
        stage for stage in candidate["stages"]
        if stage["stage"] == "gulf3_generalization"
    )

    assert summary["approved_count"] == 3
    assert summary["blocked_count"] == 0
    assert candidate["target_type"] == "parametric_parent_candidate"
    assert gulf3["status"] == "ready"
    assert gulf3["mode"] == "full"
    candidate_eval_script = Path(candidate["workspace_path"]) / "domain-eval" / "eval-metric.py"
    assert candidate_eval_script.read_text(encoding="utf-8") == eval_script_body


def test_candidate_gate_pack_ignores_stale_candidate_state_config_refs(tmp_path):
    alpha = _skill("alpha", tmp_path)
    beta = _skill("beta", tmp_path)
    alpha["triggers"] = ["search", "rank"]
    beta["triggers"] = ["search", "rank"]
    eval_script_body = "# shared metric\n"
    _write_adapter_evidence(Path(alpha["workspace_path"]), eval_script_body=eval_script_body)
    _write_adapter_evidence(Path(beta["workspace_path"]), eval_script_body=eval_script_body)
    manifest = _campaign_mod.validate_campaign_manifest(_manifest(tmp_path, [alpha, beta]))
    report = _campaign_mod.campaign_report(manifest)
    candidate = next(
        target for target in report["execution_plan"]["targets"]
        if target["target_id"] == "alpha__beta"
    )
    candidate_workspace = Path(candidate["workspace_path"])
    _write_json(
        candidate_workspace / "state.json",
        {
            "schema_version": 4,
            "adapter_config_path": "stale/config.json",
            "domain_eval_config_path": "stale/config.json",
            "selected_adapter_id": "stale_adapter_v1",
        },
    )

    summary = _mod.prepare_campaign_gate_pack(manifest, _campaign_mod)

    candidate_result = next(
        result for result in summary["results"]
        if result["skill_id"] == "alpha__beta"
    )
    state = json.loads((candidate_workspace / "state.json").read_text(encoding="utf-8"))
    assert candidate_result["status"] == "approved"
    assert state["adapter_config_path"] == "domain-eval/config.json"
    assert state["domain_eval_config_path"] == "domain-eval/config.json"
    assert state["selected_adapter_id"] == "search_retrieval_v1"


def test_candidate_gate_pack_resolves_expanded_source_config_path(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))
    alpha = _skill("alpha", tmp_path)
    beta = _skill("beta", tmp_path)
    alpha["triggers"] = ["search", "rank"]
    beta["triggers"] = ["search", "rank"]
    eval_script_body = "# shared metric\n"
    for skill in [alpha, beta]:
        skill_id = skill["skill_id"]
        workspace_path = Path(skill["workspace_path"])
        _write_json(
            workspace_path / "state.json",
            {
                "adapter_config_path": f"~/{skill_id}-config.json",
            },
        )
        _write_json(
            fake_home / f"{skill_id}-config.json",
            {
                "domain_eval_version": "1.0",
                "adapter_id": "search_retrieval_v1",
                "metric_name": "ndcg_at_5",
                "threshold_pass": 0.65,
                "threshold_concern": 0.50,
                "weight_multiplier": 2.0,
                "eval_script_path": "domain-eval/eval-metric.py",
                "golden_set_path": "domain-eval/golden-set.jsonl",
                "author_confirmed": True,
            },
        )
        (workspace_path / "domain-eval").mkdir(parents=True, exist_ok=True)
        (workspace_path / "domain-eval" / "eval-metric.py").write_text(
            eval_script_body,
            encoding="utf-8",
        )
        _write_jsonl(workspace_path / "domain-eval" / "golden-set.jsonl", DEFAULT_GOLDEN_ROWS)
    manifest = _campaign_mod.validate_campaign_manifest(_manifest(tmp_path, [alpha, beta]))

    summary = _mod.prepare_campaign_gate_pack(manifest, _campaign_mod)

    candidate = next(
        result for result in summary["results"]
        if result["skill_id"] == "alpha__beta"
    )
    assert candidate["status"] == "approved"
    assert summary["approved_count"] == 3


def test_candidate_gate_pack_blocks_mismatched_eval_script_content(tmp_path):
    alpha = _skill("alpha", tmp_path)
    beta = _skill("beta", tmp_path)
    alpha["triggers"] = ["search", "rank"]
    beta["triggers"] = ["search", "rank"]
    _write_adapter_evidence(Path(alpha["workspace_path"]), eval_script_body="# alpha metric\n")
    _write_adapter_evidence(Path(beta["workspace_path"]), eval_script_body="# beta metric\n")
    manifest = _campaign_mod.validate_campaign_manifest(_manifest(tmp_path, [alpha, beta]))

    summary = _mod.prepare_campaign_gate_pack(manifest, _campaign_mod)
    candidate = next(
        result for result in summary["results"]
        if result["skill_id"] == "alpha__beta"
    )

    assert candidate["status"] == "blocked"
    assert "compatible eval_script_path content" in candidate["reason"]


def test_candidate_gate_pack_blocks_mismatched_scoring_config(tmp_path):
    alpha = _skill("alpha", tmp_path)
    beta = _skill("beta", tmp_path)
    alpha["triggers"] = ["search", "rank"]
    beta["triggers"] = ["search", "rank"]
    _write_adapter_evidence(Path(alpha["workspace_path"]), threshold_pass=0.65)
    _write_adapter_evidence(Path(beta["workspace_path"]), threshold_pass=0.75)
    manifest = _campaign_mod.validate_campaign_manifest(_manifest(tmp_path, [alpha, beta]))

    summary = _mod.prepare_campaign_gate_pack(manifest, _campaign_mod)
    candidate = next(
        result for result in summary["results"]
        if result["skill_id"] == "alpha__beta"
    )

    assert candidate["status"] == "blocked"
    assert "compatible adapter scoring config" in candidate["reason"]
