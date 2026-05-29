from pathlib import Path

from autorefine.lib.campaign_readiness import (
    GULF1_EXPECTED_OUTPUTS,
    GULF2_EXPECTED_OUTPUTS,
    GULF3_EXPECTED_OUTPUTS,
    assess_campaign_readiness,
)


def _target(workspace_path: Path) -> dict:
    return {
        "target_id": "search",
        "workspace_path": str(workspace_path),
    }


def _write_json(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def test_assess_campaign_readiness_returns_initial_stage_shapes(tmp_path):
    workspace = tmp_path / "workspace"

    readiness = assess_campaign_readiness(_target(workspace))

    assert readiness.overall_status == "blocked"
    assert readiness.to_dict() == {
        "target_id": "search",
        "workspace_path": str(workspace),
        "overall_status": "blocked",
        "stages": [
            {
                "stage": "gulf1_comprehension",
                "status": "ready",
                "blocked_by": [],
                "inputs": ["skill-under-test/SKILL.md"],
                "expected_outputs": GULF1_EXPECTED_OUTPUTS,
                "gate": {
                    "name": "gulf_1",
                    "required": True,
                    "approval_source": "state.json.gates.gulf_1",
                    "status": "pending",
                },
                "mode": "full",
                "trust_level": "trusted_after_gate",
                "next_action": "prepare_gulf1_workspace",
            },
            {
                "stage": "gulf2_specification",
                "status": "blocked",
                "blocked_by": ["state.json.gates.gulf_1"],
                "inputs": ["contract/", "design-audit.md", "eval-suite.md"],
                "expected_outputs": GULF2_EXPECTED_OUTPUTS,
                "gate": {
                    "name": "gulf_2",
                    "required": True,
                    "approval_source": "state.json.gates.gulf_2",
                    "status": "pending",
                },
                "mode": "full",
                "trust_level": "trusted_after_gate",
                "next_action": "wait_for_gulf1_gate",
            },
            {
                "stage": "gulf3_generalization",
                "status": "blocked",
                "blocked_by": ["state.json.gates.gulf_1"],
                "inputs": ["eval-suite.md", "judges/", "domain-eval/"],
                "expected_outputs": GULF3_EXPECTED_OUTPUTS,
                "gate": {
                    "name": "session_close_trust_gate",
                    "required": True,
                    "approval_source": "session_close_holdout/variant_results.json#trust_gate",
                },
                "mode": "full",
                "trust_level": "untrusted",
                "next_action": "wait_for_gulf1_gate",
            },
        ],
    }


def test_assess_campaign_readiness_preserves_quick_start_mini_mode(tmp_path):
    workspace = tmp_path / "workspace"
    _write_json(
        workspace / "state.json",
        """
        {
          "quick_start": {"completed": true},
          "gates": {"gulf_1": "pending", "gulf_2": "pending"}
        }
        """,
    )

    readiness = assess_campaign_readiness(_target(workspace))

    assert readiness.overall_status == "blocked"
    assert readiness.stages[2].to_dict() == {
        "stage": "gulf3_generalization",
        "status": "ready",
        "blocked_by": [],
        "inputs": ["eval-suite.md", "judges/", "domain-eval/"],
        "expected_outputs": GULF3_EXPECTED_OUTPUTS,
        "gate": {
            "name": "session_close_trust_gate",
            "required": True,
            "approval_source": "session_close_holdout/variant_results.json#trust_gate",
        },
        "mode": "mini",
        "trust_level": "directional",
        "next_action": "run_phase7_mini",
    }


def test_assess_campaign_readiness_marks_trusted_gulf3_complete(tmp_path):
    workspace = tmp_path / "workspace"
    _write_json(
        workspace / "state.json",
        """
        {"gates": {"gulf_1": "approved", "gulf_2": "approved"}}
        """,
    )
    _write_json(
        workspace / "session_close_holdout" / "variant_results.json",
        """
        {"trust_gate": {"outcome": "review_required", "reviewer": "human"}}
        """,
    )

    readiness = assess_campaign_readiness(_target(workspace))

    assert readiness.overall_status == "complete"
    assert [stage.status for stage in readiness.stages] == [
        "complete",
        "complete",
        "complete",
    ]
    assert readiness.stages[2].to_dict() == {
        "stage": "gulf3_generalization",
        "status": "complete",
        "blocked_by": [],
        "inputs": ["eval-suite.md", "judges/", "domain-eval/"],
        "expected_outputs": GULF3_EXPECTED_OUTPUTS,
        "gate": {
            "name": "session_close_trust_gate",
            "required": True,
            "approval_source": "session_close_holdout/variant_results.json#trust_gate",
        },
        "mode": "full",
        "trust_level": "trusted",
        "trust_gate": {"outcome": "review_required", "reviewer": "human"},
        "next_action": None,
    }


def test_assess_campaign_readiness_blocks_all_stages_on_invalid_state_json(tmp_path):
    workspace = tmp_path / "workspace"
    _write_json(workspace / "state.json", "{bad")

    readiness = assess_campaign_readiness(_target(workspace))

    assert readiness.overall_status == "blocked"
    assert [stage.status for stage in readiness.stages] == [
        "blocked",
        "blocked",
        "blocked",
    ]
    assert readiness.stages[0].blocked_by[0].startswith("state.json invalid JSON:")
    assert readiness.to_stage_dicts()[0]["next_action"] == "repair_workspace_state"
