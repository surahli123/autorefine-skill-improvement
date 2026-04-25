#!/usr/bin/env python3
"""
Prepare preauthorized Gulf 1 / Gulf 2 gate packs for campaign workspaces.

This helper is intentionally narrow: it approves Gulf gates only when a
workspace already has explicit adapter-backed evidence. It does not fabricate
human-reviewed contract examples and it does not execute Phase 7.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path


APPROVAL_SOURCE = "preauthorized_adapter_metric_v1"
DEFAULT_CONFIG_PATH = "domain-eval/config.json"
DEFAULT_GOLDEN_SET_PATH = "domain-eval/golden-set.jsonl"


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


def load_campaign_module() -> object:
    script_path = Path(__file__).with_name("run-campaign.py")
    spec = importlib.util.spec_from_file_location("run_campaign_for_gate_pack", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_campaign_for_gate_pack"] = module
    spec.loader.exec_module(module)
    return module


def prepare_campaign_gate_pack(manifest: dict, campaign_module: object | None = None) -> dict:
    if campaign_module is None:
        targets = [
            {
                "target_id": skill["skill_id"],
                "target_type": "single_skill",
                "source_skill_ids": [skill["skill_id"]],
                "workspace_path": skill["workspace_path"],
            }
            for skill in manifest["skills"]
        ]
    else:
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
        source_evidence.append((skill_id, workspace_path, evidence["evidence"]))

    adapter_ids = {evidence["adapter_id"] for _skill_id, _workspace, evidence in source_evidence}
    metric_names = {evidence["metric_name"] for _skill_id, _workspace, evidence in source_evidence}
    if len(adapter_ids) != 1 or len(metric_names) != 1:
        return {
            "skill_id": target["target_id"],
            "workspace_path": target["workspace_path"],
            "status": "blocked",
            "reason": "candidate source skills must share one adapter_id and metric_name",
        }

    materialize_candidate_adapter_evidence(Path(target["workspace_path"]), source_evidence)
    return prepare_workspace_gate_pack(target["workspace_path"], target["target_id"])


def prepare_workspace_gate_pack(workspace_path: Path | str, skill_id: str) -> dict:
    workspace_path = Path(workspace_path)
    evidence = read_adapter_evidence(workspace_path)
    if evidence["status"] != "ready":
        return {
            "skill_id": skill_id,
            "workspace_path": str(workspace_path),
            "status": "blocked",
            "reason": evidence["reason"],
        }

    workspace_path.mkdir(parents=True, exist_ok=True)
    write_gate_pack_artifacts(workspace_path, skill_id, evidence)
    update_state(workspace_path, skill_id, evidence)
    return {
        "skill_id": skill_id,
        "workspace_path": str(workspace_path),
        "status": "approved",
        "approval_source": APPROVAL_SOURCE,
        "evidence": evidence["evidence"],
    }


def materialize_candidate_adapter_evidence(
    workspace_path: Path,
    source_evidence: list[tuple[str, Path, dict]],
) -> None:
    _first_skill_id, first_workspace, first_evidence = source_evidence[0]
    first_config = load_json(first_workspace / first_evidence["config_path"])
    config = dict(first_config)
    config.update(
        {
            "adapter_id": first_evidence["adapter_id"],
            "metric_name": first_evidence["metric_name"],
            "golden_set_path": DEFAULT_GOLDEN_SET_PATH,
            "author_confirmed": True,
            "source_skill_ids": [skill_id for skill_id, _workspace, _evidence in source_evidence],
        }
    )

    rows = []
    for skill_id, source_workspace, evidence in source_evidence:
        source_path = resolve_workspace_path(source_workspace, evidence["golden_set_path"])
        for row in load_jsonl_rows(source_path):
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            row["metadata"] = {**metadata, "source_skill_id": skill_id}
            rows.append(row)

    workspace_path.mkdir(parents=True, exist_ok=True)
    write_json(workspace_path / DEFAULT_CONFIG_PATH, config)
    write_jsonl(workspace_path / DEFAULT_GOLDEN_SET_PATH, rows)


def read_adapter_evidence(workspace_path: Path) -> dict:
    config_path = workspace_path / DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return blocked("domain-eval/config.json with author_confirmed=true is required")

    try:
        config = load_json(config_path)
    except ValueError as exc:
        return blocked(str(exc))

    if config.get("author_confirmed") is not True:
        return blocked("domain-eval/config.json author_confirmed=true is required")

    golden_set_ref = config.get("golden_set_path") or DEFAULT_GOLDEN_SET_PATH
    golden_set_path = resolve_workspace_path(workspace_path, golden_set_ref)
    try:
        golden_set_count = count_jsonl_rows(golden_set_path)
    except ValueError as exc:
        return blocked(str(exc))
    if golden_set_count == 0:
        return blocked(f"{golden_set_ref} must contain at least one JSONL row")

    adapter_id = config.get("adapter_id") or config.get("selected_adapter_id") or "domain_metric_v1"
    metric_name = config.get("metric_name") or "domain_metric"
    return {
        "status": "ready",
        "reason": None,
        "evidence": {
            "adapter_id": adapter_id,
            "config_path": DEFAULT_CONFIG_PATH,
            "golden_set_path": str(golden_set_ref),
            "golden_set_count": golden_set_count,
            "metric_name": metric_name,
            "threshold_pass": config.get("threshold_pass"),
        },
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


def write_gate_pack_artifacts(workspace_path: Path, skill_id: str, evidence: dict) -> None:
    gate_pack = {
        "schema_version": 1,
        "skill_id": skill_id,
        "status": "approved",
        "approval_source": APPROVAL_SOURCE,
        "gates": {"gulf_1": "approved", "gulf_2": "approved"},
        "evidence": evidence["evidence"],
        "limits": [
            "Preauthorization is accepted only for adapter-backed deterministic evidence.",
            "This gate pack does not create human-reviewed contract examples.",
            "Phase 7 remains plan/execution separated; final promotion still requires session_close_holdout/variant_results.json#trust_gate.",
        ],
    }
    write_json(workspace_path / "gulf-gate-pack.json", gate_pack)
    (workspace_path / "gate-report-gulf-1.md").write_text(
        render_gulf1_report(skill_id, evidence["evidence"]),
        encoding="utf-8",
    )
    (workspace_path / "gate-report-gulf-2.md").write_text(
        render_gulf2_report(skill_id, evidence["evidence"]),
        encoding="utf-8",
    )
    (workspace_path / "eval-suite.md").write_text(
        render_eval_suite(evidence["evidence"]),
        encoding="utf-8",
    )
    (workspace_path / "fixtures-manifest.md").write_text(
        render_fixtures_manifest(evidence["evidence"]),
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


def update_state(workspace_path: Path, skill_id: str, evidence: dict) -> None:
    state_path = workspace_path / "state.json"
    state = load_json(state_path) if state_path.exists() else {}
    gates = state.get("gates") if isinstance(state.get("gates"), dict) else {}
    gates.update({"gulf_1": "approved", "gulf_2": "approved"})
    state.update(
        {
            "schema_version": state.get("schema_version", 4),
            "skill_name": state.get("skill_name", skill_id),
            "workspace_path": state.get("workspace_path", str(workspace_path)),
            "gates": gates,
            "selected_adapter_id": evidence["evidence"]["adapter_id"],
            "adapter_config_path": DEFAULT_CONFIG_PATH,
            "domain_eval_config_path": DEFAULT_CONFIG_PATH,
            "gulf_gate_pack": {
                "status": "approved",
                "approval_source": APPROVAL_SOURCE,
                "artifact_path": "gulf-gate-pack.json",
            },
        }
    )
    write_json(state_path, state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare preauthorized Gulf 1/2 gate packs for campaign workspaces."
    )
    parser.add_argument("--manifest", required=True, help="Campaign manifest JSON path.")
    parser.add_argument("--summary-output", help="Optional JSON summary output path.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    manifest_path = Path(args.manifest)
    campaign = load_campaign_module()
    manifest = campaign.validate_campaign_manifest(
        load_json(manifest_path),
        base_dir=manifest_path.parent,
    )
    summary = prepare_campaign_gate_pack(manifest, campaign)
    if args.summary_output:
        write_json(Path(args.summary_output), summary)
        return
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
