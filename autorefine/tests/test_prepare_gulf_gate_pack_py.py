import importlib.util
import json
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


def _write_adapter_evidence(workspace_path):
    _write_json(
        workspace_path / "domain-eval" / "config.json",
        {
            "domain_eval_version": "1.0",
            "adapter_id": "search_retrieval_v1",
            "metric_name": "ndcg_at_5",
            "threshold_pass": 0.65,
            "eval_script_path": "domain-eval/eval-metric.py",
            "golden_set_path": "domain-eval/golden-set.jsonl",
            "author_confirmed": True,
        },
    )
    _write_jsonl(
        workspace_path / "domain-eval" / "golden-set.jsonl",
        [{"query": "trust gate", "doc_id": "trust_gate", "grade": 3}],
    )


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


def test_campaign_gate_pack_prepares_pairwise_candidate_targets(tmp_path):
    alpha = _skill("alpha", tmp_path)
    beta = _skill("beta", tmp_path)
    alpha["triggers"] = ["search", "rank"]
    beta["triggers"] = ["search", "rank"]
    _write_adapter_evidence(Path(alpha["workspace_path"]))
    _write_adapter_evidence(Path(beta["workspace_path"]))
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
