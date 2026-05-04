"""Campaign readiness assessment for AutoRefine Gulf-stage workspaces."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


CampaignStageStatus = Literal["ready", "blocked", "needs_human_gate", "complete"]

GULF1_EXPECTED_OUTPUTS = [
    "contract/success-examples.jsonl",
    "contract/failure-examples.jsonl",
    "contract/do-not-trigger-examples.jsonl",
    "design-audit.md",
    "eval-suite.md",
    "gate-report-gulf-1.md",
]
GULF2_EXPECTED_OUTPUTS = [
    "fixtures-manifest.md",
    "judges/",
    "gate-report-gulf-2.md",
]
GULF3_EXPECTED_OUTPUTS = [
    "runs/run_*/experiment-contract.json",
    "runs/run_*/iteration_000/eval_results.json",
    "results.json",
    "session-log.json",
    "session_close_holdout/variant_results.json",
]
VALID_TRUST_GATE_OUTCOMES = {"promote", "review_required", "block"}


@dataclass(frozen=True)
class CampaignReadinessStage:
    stage: str
    status: CampaignStageStatus
    blocked_by: tuple[str, ...]
    inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    gate: dict[str, Any] | None
    mode: str
    trust_level: str
    next_action: str | None
    trust_gate: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "stage": self.stage,
            "status": self.status,
            "blocked_by": list(self.blocked_by),
            "inputs": list(self.inputs),
            "expected_outputs": list(self.expected_outputs),
            "gate": copy.deepcopy(self.gate),
            "mode": self.mode,
            "trust_level": self.trust_level,
            "next_action": self.next_action,
        }
        if self.trust_gate is not None:
            payload["trust_gate"] = copy.deepcopy(self.trust_gate)
        return payload


@dataclass(frozen=True)
class CampaignReadiness:
    target_id: str
    workspace_path: str
    overall_status: CampaignStageStatus
    stages: tuple[CampaignReadinessStage, ...]

    def to_stage_dicts(self) -> list[dict[str, Any]]:
        return [stage.to_dict() for stage in self.stages]

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "workspace_path": self.workspace_path,
            "overall_status": self.overall_status,
            "stages": self.to_stage_dicts(),
        }


def assess_campaign_readiness(target: dict[str, Any]) -> CampaignReadiness:
    workspace_path = Path(target["workspace_path"])
    state = _read_workspace_state(workspace_path)
    if state["error"]:
        stages = (
            _blocked_stage("gulf1_comprehension", state["error"], GULF1_EXPECTED_OUTPUTS),
            _blocked_stage("gulf2_specification", state["error"], GULF2_EXPECTED_OUTPUTS),
            _blocked_stage("gulf3_generalization", state["error"], GULF3_EXPECTED_OUTPUTS),
        )
    else:
        stages = (
            _build_gulf1_stage(workspace_path, state),
            _build_gulf2_stage(workspace_path, state),
            _build_gulf3_stage(workspace_path, state),
        )

    return CampaignReadiness(
        target_id=str(target.get("target_id", "")),
        workspace_path=str(workspace_path),
        overall_status=_derive_overall_status(stages),
        stages=stages,
    )


def blocked_stage(
    stage_name: str,
    reason: str,
    expected_outputs: list[str],
) -> dict[str, Any]:
    return _blocked_stage(stage_name, reason, expected_outputs).to_dict()


def build_gulf1_stage(
    target: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    return _build_gulf1_stage(Path(target["workspace_path"]), state).to_dict()


def build_gulf2_stage(
    target: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    return _build_gulf2_stage(Path(target["workspace_path"]), state).to_dict()


def build_gulf3_stage(
    target: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    return _build_gulf3_stage(Path(target["workspace_path"]), state).to_dict()


def read_workspace_state(workspace_path: Path | str) -> dict[str, Any]:
    return _read_workspace_state(workspace_path)


def gate_status_from_state(state: dict[str, Any], gate_name: str) -> str:
    return _gate_status_from_state(state, gate_name)


def gate_status(workspace_path: Path | str, gate_name: str) -> str:
    return gate_status_from_state(read_workspace_state(workspace_path), gate_name)


def artifact_exists(workspace_path: Path | str, relative_path: str) -> bool:
    return _artifact_exists(workspace_path, relative_path)


def read_trust_gate(workspace_path: Path | str) -> dict[str, Any]:
    return _read_trust_gate(workspace_path)


def _derive_overall_status(
    stages: tuple[CampaignReadinessStage, ...],
) -> CampaignStageStatus:
    statuses = [stage.status for stage in stages]
    if "blocked" in statuses:
        return "blocked"
    if "needs_human_gate" in statuses:
        return "needs_human_gate"
    if "ready" in statuses:
        return "ready"
    return "complete"


def _blocked_stage(
    stage_name: str,
    reason: str,
    expected_outputs: list[str],
) -> CampaignReadinessStage:
    return CampaignReadinessStage(
        stage=stage_name,
        status="blocked",
        blocked_by=(reason,),
        inputs=("skill-under-test/SKILL.md",),
        expected_outputs=tuple(expected_outputs),
        gate=None,
        mode="full",
        trust_level="untrusted",
        next_action="repair_workspace_state",
    )


def _build_gulf1_stage(
    workspace_path: Path,
    state: dict[str, Any],
) -> CampaignReadinessStage:
    gate = _gate_status_from_state(state, "gulf_1")
    outputs_exist = all(
        _artifact_exists(workspace_path, output)
        for output in GULF1_EXPECTED_OUTPUTS
    )
    if gate == "approved":
        status: CampaignStageStatus = "complete"
        next_action = None
        blocked_by: tuple[str, ...] = ()
    elif outputs_exist:
        status = "needs_human_gate"
        next_action = "request_gulf1_gate_review"
        blocked_by = ("state.json.gates.gulf_1",)
    else:
        status = "ready"
        next_action = "prepare_gulf1_workspace"
        blocked_by = ()

    return CampaignReadinessStage(
        stage="gulf1_comprehension",
        status=status,
        blocked_by=blocked_by,
        inputs=("skill-under-test/SKILL.md",),
        expected_outputs=tuple(GULF1_EXPECTED_OUTPUTS),
        gate={
            "name": "gulf_1",
            "required": True,
            "approval_source": "state.json.gates.gulf_1",
            "status": gate,
        },
        mode="full",
        trust_level="trusted_after_gate",
        next_action=next_action,
    )


def _build_gulf2_stage(
    workspace_path: Path,
    state: dict[str, Any],
) -> CampaignReadinessStage:
    gulf1_gate = _gate_status_from_state(state, "gulf_1")
    gulf2_gate = _gate_status_from_state(state, "gulf_2")
    outputs_exist = all(
        _artifact_exists(workspace_path, output)
        for output in GULF2_EXPECTED_OUTPUTS
    )
    if gulf1_gate != "approved":
        status: CampaignStageStatus = "blocked"
        next_action = "wait_for_gulf1_gate"
        blocked_by: tuple[str, ...] = ("state.json.gates.gulf_1",)
    elif gulf2_gate == "approved":
        status = "complete"
        next_action = None
        blocked_by = ()
    elif outputs_exist:
        status = "needs_human_gate"
        next_action = "request_gulf2_gate_review"
        blocked_by = ("state.json.gates.gulf_2",)
    else:
        status = "ready"
        next_action = "prepare_gulf2_specification"
        blocked_by = ()

    return CampaignReadinessStage(
        stage="gulf2_specification",
        status=status,
        blocked_by=blocked_by,
        inputs=("contract/", "design-audit.md", "eval-suite.md"),
        expected_outputs=tuple(GULF2_EXPECTED_OUTPUTS),
        gate={
            "name": "gulf_2",
            "required": True,
            "approval_source": "state.json.gates.gulf_2",
            "status": gulf2_gate,
        },
        mode="full",
        trust_level="trusted_after_gate",
        next_action=next_action,
    )


def _build_gulf3_stage(
    workspace_path: Path,
    state: dict[str, Any],
) -> CampaignReadinessStage:
    trust_gate = _read_trust_gate(workspace_path)
    if trust_gate["status"] in {"malformed", "invalid_outcome"}:
        return CampaignReadinessStage(
            stage="gulf3_generalization",
            status="blocked",
            blocked_by=(trust_gate["error"],),
            inputs=("eval-suite.md", "judges/", "domain-eval/"),
            expected_outputs=tuple(GULF3_EXPECTED_OUTPUTS),
            gate={
                "name": "session_close_trust_gate",
                "required": True,
                "approval_source": "session_close_holdout/variant_results.json#trust_gate",
            },
            mode="full",
            trust_level="untrusted",
            next_action="repair_session_close_holdout",
        )
    if trust_gate["status"] == "valid":
        return CampaignReadinessStage(
            stage="gulf3_generalization",
            status="complete",
            blocked_by=(),
            inputs=("eval-suite.md", "judges/", "domain-eval/"),
            expected_outputs=tuple(GULF3_EXPECTED_OUTPUTS),
            gate={
                "name": "session_close_trust_gate",
                "required": True,
                "approval_source": "session_close_holdout/variant_results.json#trust_gate",
            },
            mode="full",
            trust_level="trusted",
            trust_gate=trust_gate["trust_gate"],
            next_action=None,
        )

    gulf1_gate = _gate_status_from_state(state, "gulf_1")
    gulf2_gate = _gate_status_from_state(state, "gulf_2")
    quick_start_completed = bool(
        state["data"].get("quick_start", {}).get("completed")
    )
    if gulf1_gate == "approved" and gulf2_gate == "approved":
        status: CampaignStageStatus = "ready"
        mode = "full"
        trust_level = "untrusted"
        next_action = "run_phase7_full"
        blocked_by: tuple[str, ...] = ()
    elif quick_start_completed and gulf1_gate == "pending" and gulf2_gate == "pending":
        status = "ready"
        mode = "mini"
        trust_level = "directional"
        next_action = "run_phase7_mini"
        blocked_by = ()
    else:
        status = "blocked"
        mode = "full"
        trust_level = "untrusted"
        next_action = "wait_for_gulf2_gate"
        blocked_by = ("state.json.gates.gulf_2",)
        if gulf1_gate != "approved":
            next_action = "wait_for_gulf1_gate"
            blocked_by = ("state.json.gates.gulf_1",)

    return CampaignReadinessStage(
        stage="gulf3_generalization",
        status=status,
        blocked_by=blocked_by,
        inputs=("eval-suite.md", "judges/", "domain-eval/"),
        expected_outputs=tuple(GULF3_EXPECTED_OUTPUTS),
        gate={
            "name": "session_close_trust_gate",
            "required": True,
            "approval_source": "session_close_holdout/variant_results.json#trust_gate",
        },
        mode=mode,
        trust_level=trust_level,
        next_action=next_action,
    )


def _read_workspace_state(workspace_path: Path | str) -> dict[str, Any]:
    workspace_path = Path(workspace_path)
    state_path = workspace_path / "state.json"
    if not state_path.exists():
        return {"exists": False, "data": {}, "error": None}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "exists": True,
            "data": {},
            "error": f"state.json invalid JSON: {exc}",
        }
    if not isinstance(state, dict):
        return {
            "exists": True,
            "data": {},
            "error": "state.json must contain an object",
        }
    return {"exists": True, "data": state, "error": None}


def _gate_status_from_state(state: dict[str, Any], gate_name: str) -> str:
    gates = state["data"].get("gates", {})
    if not isinstance(gates, dict):
        return "pending"
    value = gates.get(gate_name, "pending")
    return value if value in {"approved", "pending", "rejected"} else "pending"


def _artifact_exists(workspace_path: Path | str, relative_path: str) -> bool:
    workspace_path = Path(workspace_path)
    if "*" in relative_path:
        return bool(list(workspace_path.glob(relative_path)))
    path = workspace_path / relative_path
    return path.exists()


def _read_trust_gate(workspace_path: Path | str) -> dict[str, Any]:
    workspace_path = Path(workspace_path)
    path = workspace_path / "session_close_holdout" / "variant_results.json"
    if not path.exists():
        return {"status": "missing", "trust_gate": None, "error": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "malformed",
            "trust_gate": None,
            "error": f"session_close_holdout/variant_results.json invalid JSON: {exc}",
        }
    if not isinstance(payload, dict) or not isinstance(payload.get("trust_gate"), dict):
        return {
            "status": "malformed",
            "trust_gate": None,
            "error": "session_close_holdout/variant_results.json missing trust_gate object",
        }
    trust_gate = payload["trust_gate"]
    outcome = trust_gate.get("outcome")
    if outcome not in VALID_TRUST_GATE_OUTCOMES:
        return {
            "status": "invalid_outcome",
            "trust_gate": trust_gate,
            "error": "trust_gate.outcome must be promote, review_required, or block",
        }
    return {"status": "valid", "trust_gate": trust_gate, "error": None}
