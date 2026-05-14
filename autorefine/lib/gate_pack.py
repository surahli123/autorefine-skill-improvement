"""Gate Pack preparation for AutoRefine campaign workspaces."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapter_state import (
    AdapterState,
    DEFAULT_CONFIG_PATH,
    DEFAULT_GOLDEN_SET_PATH,
    validate_adapter_state,
)


APPROVAL_SOURCE = "preauthorized_adapter_metric_v1"
DEFAULT_EVAL_SCRIPT_PATH = "domain-eval/eval-metric.py"
CANDIDATE_COMPATIBILITY_FIELDS = (
    "domain_eval_version",
    "adapter_id",
    "metric_name",
    "threshold_pass",
    "threshold_concern",
    "weight_multiplier",
)


@dataclass(frozen=True)
class AdapterEvidence:
    adapter_id: str
    config_path: str
    domain_eval_version: str | None
    eval_script_path: str | None
    golden_set_path: str
    golden_set_count: int
    metric_name: str
    threshold_pass: Any
    threshold_concern: Any
    weight_multiplier: Any

    @classmethod
    def from_adapter_state(cls, adapter_state: AdapterState) -> "AdapterEvidence":
        return cls(
            adapter_id=adapter_state.selected_adapter_id or "domain_metric_v1",
            config_path=adapter_state.effective_config_path,
            domain_eval_version=adapter_state.domain_eval_version,
            eval_script_path=adapter_state.eval_script_path,
            golden_set_path=adapter_state.golden_set_path,
            golden_set_count=adapter_state.golden_set_count,
            metric_name=adapter_state.metric_name,
            threshold_pass=adapter_state.threshold_pass,
            threshold_concern=adapter_state.threshold_concern,
            weight_multiplier=adapter_state.weight_multiplier,
        )

    @classmethod
    def from_summary(cls, summary: dict[str, Any]) -> "AdapterEvidence":
        return cls(
            adapter_id=summary["adapter_id"],
            config_path=summary["config_path"],
            domain_eval_version=summary.get("domain_eval_version"),
            eval_script_path=summary.get("eval_script_path"),
            golden_set_path=summary["golden_set_path"],
            golden_set_count=summary["golden_set_count"],
            metric_name=summary["metric_name"],
            threshold_pass=summary.get("threshold_pass"),
            threshold_concern=summary.get("threshold_concern"),
            weight_multiplier=summary.get("weight_multiplier"),
        )

    def to_summary(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "config_path": self.config_path,
            "domain_eval_version": self.domain_eval_version,
            "eval_script_path": self.eval_script_path,
            "golden_set_path": self.golden_set_path,
            "golden_set_count": self.golden_set_count,
            "metric_name": self.metric_name,
            "threshold_pass": self.threshold_pass,
            "threshold_concern": self.threshold_concern,
            "weight_multiplier": self.weight_multiplier,
        }


def load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON payload must be an object")
    return payload


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare_campaign_gate_pack(manifest: dict, campaign_module: object | None = None) -> dict:
    if campaign_module is None:
        from . import campaign_planning as campaign_module

    gulf_analysis = campaign_module.analyze_gulf_work(manifest)
    targets = campaign_module.build_campaign_targets(manifest, gulf_analysis)

    skills = {skill["skill_id"]: skill for skill in manifest["skills"]}
    results = [prepare_target_gate_pack(target, skills) for target in targets]
    return {
        "approval_source": APPROVAL_SOURCE,
        "target_count": len(results),
        "approved_count": sum(1 for result in results if result["status"] == "approved"),
        "blocked_count": sum(1 for result in results if result["status"] == "blocked"),
        "results": results,
    }


def prepare_target_gate_pack(target: dict, skills: dict[str, dict]) -> dict:
    if target["target_type"] == "single_skill":
        return prepare_workspace_gate_pack(target["workspace_path"], target["target_id"])
    return prepare_candidate_gate_pack(target, skills)


def prepare_candidate_gate_pack(target: dict, skills: dict[str, dict]) -> dict:
    source_evidence = []
    for skill_id in target["source_skill_ids"]:
        workspace_path = Path(skills[skill_id]["workspace_path"])
        evidence = read_adapter_evidence(workspace_path)
        if evidence["status"] != "ready":
            return {
                "skill_id": target["target_id"],
                "workspace_path": target["workspace_path"],
                "status": "blocked",
                "reason": f"{skill_id}: {evidence['reason']}",
            }
        source_evidence.append(
            (skill_id, workspace_path, AdapterEvidence.from_summary(evidence["evidence"]))
        )

    adapter_ids = {evidence.adapter_id for _skill_id, _workspace, evidence in source_evidence}
    metric_names = {evidence.metric_name for _skill_id, _workspace, evidence in source_evidence}
    if len(adapter_ids) != 1 or len(metric_names) != 1:
        return {
            "skill_id": target["target_id"],
            "workspace_path": target["workspace_path"],
            "status": "blocked",
            "reason": "candidate source skills must share one adapter_id and metric_name",
        }

    compatibility_error = candidate_compatibility_error(source_evidence)
    if compatibility_error:
        return {
            "skill_id": target["target_id"],
            "workspace_path": target["workspace_path"],
            "status": "blocked",
            "reason": compatibility_error,
        }

    materialize_candidate_adapter_evidence(Path(target["workspace_path"]), source_evidence)
    return prepare_workspace_gate_pack(target["workspace_path"], target["target_id"])


def prepare_workspace_gate_pack(workspace_path: Path | str, skill_id: str) -> dict:
    workspace_path = Path(workspace_path)
    evidence_result = read_adapter_evidence(workspace_path)
    if evidence_result["status"] != "ready":
        return {
            "skill_id": skill_id,
            "workspace_path": str(workspace_path),
            "status": "blocked",
            "reason": evidence_result["reason"],
        }

    evidence = AdapterEvidence.from_summary(evidence_result["evidence"])
    workspace_path.mkdir(parents=True, exist_ok=True)
    write_gate_pack_artifacts(workspace_path, skill_id, evidence)
    update_state(workspace_path, skill_id, evidence)
    return {
        "skill_id": skill_id,
        "workspace_path": str(workspace_path),
        "status": "approved",
        "approval_source": APPROVAL_SOURCE,
        "evidence": evidence.to_summary(),
    }


def materialize_candidate_adapter_evidence(
    workspace_path: Path,
    source_evidence: list[tuple[str, Path, AdapterEvidence]],
) -> None:
    _first_skill_id, first_workspace, first_evidence = source_evidence[0]
    first_config = load_json(
        resolve_workspace_path(first_workspace, first_evidence.config_path)
    )
    config = dict(first_config)
    config.update(
        {
            "adapter_id": first_evidence.adapter_id,
            "metric_name": first_evidence.metric_name,
            "eval_script_path": DEFAULT_EVAL_SCRIPT_PATH,
            "golden_set_path": DEFAULT_GOLDEN_SET_PATH,
            "author_confirmed": True,
            "source_skill_ids": [skill_id for skill_id, _workspace, _evidence in source_evidence],
        }
    )

    rows = []
    for skill_id, source_workspace, evidence in source_evidence:
        source_path = resolve_workspace_path(source_workspace, evidence.golden_set_path)
        for row in load_jsonl_rows(source_path):
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            row["metadata"] = {**metadata, "source_skill_id": skill_id}
            rows.append(row)

    workspace_path.mkdir(parents=True, exist_ok=True)
    clear_candidate_adapter_state_refs(workspace_path)
    source_eval_script_path = resolve_workspace_path(
        first_workspace,
        first_evidence.eval_script_path,
    )
    (workspace_path / DEFAULT_EVAL_SCRIPT_PATH).parent.mkdir(parents=True, exist_ok=True)
    (workspace_path / DEFAULT_EVAL_SCRIPT_PATH).write_bytes(
        source_eval_script_path.read_bytes(),
    )
    write_json(workspace_path / DEFAULT_CONFIG_PATH, config)
    write_jsonl(workspace_path / DEFAULT_GOLDEN_SET_PATH, rows)


def read_adapter_evidence(workspace_path: Path) -> dict:
    validation = validate_adapter_state(workspace_path, mode="requires_golden_set")
    if not validation.ok or validation.normalized is None:
        return blocked("; ".join(validation.errors or validation.warnings))

    evidence = AdapterEvidence.from_adapter_state(validation.normalized)
    return {
        "status": "ready",
        "reason": None,
        "evidence": evidence.to_summary(),
    }


def load_jsonl_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL row: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{lineno}: JSONL row must be an object")
            rows.append(row)
    return rows


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL row: {exc}") from exc
            count += 1
    return count


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def blocked(reason: str) -> dict:
    return {"status": "blocked", "reason": reason, "evidence": None}


def resolve_workspace_path(workspace_path: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        return workspace_path / DEFAULT_GOLDEN_SET_PATH
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return workspace_path / path


def candidate_compatibility_error(
    source_evidence: list[tuple[str, Path, AdapterEvidence]],
) -> str | None:
    signatures = []
    for skill_id, workspace_path, evidence in source_evidence:
        source_eval_script_path = resolve_workspace_path(
            workspace_path,
            evidence.eval_script_path,
        )
        try:
            eval_script_digest = hashlib.sha256(
                source_eval_script_path.read_bytes()
            ).hexdigest()
        except OSError as exc:
            return f"{skill_id}: unable to read eval script for candidate compatibility: {exc}"
        evidence_summary = evidence.to_summary()
        scoring_signature = {
            field: evidence_summary.get(field)
            for field in CANDIDATE_COMPATIBILITY_FIELDS
        }
        signatures.append(
            (skill_id, {**scoring_signature, "eval_script_sha256": eval_script_digest})
        )

    _first_skill_id, first_signature = signatures[0]
    for skill_id, signature in signatures[1:]:
        if signature["eval_script_sha256"] != first_signature["eval_script_sha256"]:
            return "candidate source skills must share compatible eval_script_path content"
        if {
            key: value
            for key, value in signature.items()
            if key != "eval_script_sha256"
        } != {
            key: value
            for key, value in first_signature.items()
            if key != "eval_script_sha256"
        }:
            return "candidate source skills must share compatible adapter scoring config"
    return None


def clear_candidate_adapter_state_refs(workspace_path: Path) -> None:
    state_path = workspace_path / "state.json"
    if not state_path.exists():
        return
    state = load_json(state_path)
    state.pop("adapter_config_path", None)
    state.pop("domain_eval_config_path", None)
    state.pop("selected_adapter_id", None)
    write_json(state_path, state)


def write_gate_pack_artifacts(workspace_path: Path, skill_id: str, evidence: AdapterEvidence) -> None:
    evidence_summary = evidence.to_summary()
    gate_pack = {
        "schema_version": 1,
        "skill_id": skill_id,
        "status": "approved",
        "approval_source": APPROVAL_SOURCE,
        "gates": {"gulf_1": "approved", "gulf_2": "approved"},
        "evidence": evidence_summary,
        "limits": [
            "Preauthorization is accepted only for adapter-backed deterministic evidence.",
            "This gate pack does not create human-reviewed contract examples.",
            "Phase 7 remains plan/execution separated; final promotion still requires session_close_holdout/variant_results.json#trust_gate.",
        ],
    }
    write_json(workspace_path / "gulf-gate-pack.json", gate_pack)
    (workspace_path / "gate-report-gulf-1.md").write_text(
        render_gulf1_report(skill_id, evidence_summary),
        encoding="utf-8",
    )
    (workspace_path / "gate-report-gulf-2.md").write_text(
        render_gulf2_report(skill_id, evidence_summary),
        encoding="utf-8",
    )
    (workspace_path / "eval-suite.md").write_text(
        render_eval_suite(evidence_summary),
        encoding="utf-8",
    )
    (workspace_path / "fixtures-manifest.md").write_text(
        render_fixtures_manifest(evidence_summary),
        encoding="utf-8",
    )


def render_gulf1_report(skill_id: str, evidence: dict) -> str:
    return f"""# Gulf 1 Gate Report

Status: PREAUTHORIZED APPROVAL
Skill: `{skill_id}`
Approval source: `{APPROVAL_SOURCE}`

## Evidence

- Adapter: `{evidence['adapter_id']}`
- Metric: `{evidence['metric_name']}`
- Golden-set rows: {evidence['golden_set_count']}

## Limits

This report does not claim live human-reviewed error analysis. It records a
preauthorized deterministic gate based on adapter evidence so the campaign
orchestrator can enter Phase 7 Full mode without a live approval prompt.
"""


def render_gulf2_report(skill_id: str, evidence: dict) -> str:
    return f"""# Gulf 2 Gate Report

Status: PREAUTHORIZED APPROVAL
Skill: `{skill_id}`
Approval source: `{APPROVAL_SOURCE}`

## Evaluation Surface

- Eval type: `domain-metric`
- Adapter: `{evidence['adapter_id']}`
- Metric: `{evidence['metric_name']}`
- Golden set: `{evidence['golden_set_path']}`
- Golden-set rows: {evidence['golden_set_count']}

## Limits

Secondary judge quality may diagnose regressions, but this preauthorization is
grounded in the adapter primary metric. It must not override final Session Close
trust-gate semantics.
"""


def render_eval_suite(evidence: dict) -> str:
    return f"""# Eval Suite

## E1: Adapter Primary Metric

- Type: domain-metric
- Adapter: `{evidence['adapter_id']}`
- Metric: `{evidence['metric_name']}`
- Config: `{evidence['config_path']}`
- Golden set: `{evidence['golden_set_path']}`
- Active: true

Secondary explanation-quality checks may be added as diagnostics, but the
adapter primary metric remains the quality gate for this preauthorization.
"""


def render_fixtures_manifest(evidence: dict) -> str:
    return f"""# Fixtures Manifest

## Adapter Golden Set

- Source: `{evidence['golden_set_path']}`
- Row count: {evidence['golden_set_count']}
- Mutation-stage access: dev-only scoring surface

This manifest is generated by `{APPROVAL_SOURCE}` so Phase 7 can restore the
adapter-backed eval surface without re-running Gulf 1 or Gulf 2 interactively.
"""


def update_state(workspace_path: Path, skill_id: str, evidence: AdapterEvidence) -> None:
    state_path = workspace_path / "state.json"
    state = load_json(state_path) if state_path.exists() else {}
    gates = state.get("gates") if isinstance(state.get("gates"), dict) else {}
    gates.update({"gulf_1": "approved", "gulf_2": "approved"})
    evidence_summary = evidence.to_summary()
    state.update(
        {
            "schema_version": state.get("schema_version", 4),
            "skill_name": state.get("skill_name", skill_id),
            "workspace_path": state.get("workspace_path", str(workspace_path)),
            "gates": gates,
            "selected_adapter_id": evidence_summary["adapter_id"],
            "adapter_config_path": evidence_summary["config_path"],
            "domain_eval_config_path": evidence_summary["config_path"],
            "gulf_gate_pack": {
                "status": "approved",
                "approval_source": APPROVAL_SOURCE,
                "artifact_path": "gulf-gate-pack.json",
            },
        }
    )
    write_json(state_path, state)
