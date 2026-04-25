import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "run_campaign",
    SCRIPTS_DIR / "run-campaign.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["run_campaign"] = _mod
_spec.loader.exec_module(_mod)


def _skill(
    skill_id,
    tmp_path,
    *,
    depends_on=None,
    cluster_id=None,
    triggers=None,
    scripts=None,
    failure_modes=None,
    result_refs=None,
):
    workspace_path = tmp_path / "workspaces" / skill_id
    return {
        "skill_id": skill_id,
        "skill_path": str(tmp_path / "skills" / skill_id / "SKILL.md"),
        "workspace_path": str(workspace_path),
        "depends_on": depends_on or [],
        "cluster_id": cluster_id,
        "phase7_command": ["python3", "-m", "autorefine.phase7", skill_id],
        "result_refs": result_refs or [str(workspace_path / "results.json")],
        "triggers": triggers or [],
        "scripts": scripts or [],
        "failure_modes": failure_modes or [],
    }


def _write_skill(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _validated_campaign(tmp_path, skills):
    return _mod.validate_campaign_manifest(
        {
            "campaign_id": "campaign_a",
            "skills": skills,
        }
    )


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_mod.json.dumps(payload), encoding="utf-8")


def _target(plan, target_id):
    return next(target for target in plan["targets"] if target["target_id"] == target_id)


def _stage(target, stage_name):
    return next(stage for stage in target["stages"] if stage["stage"] == stage_name)


def test_validate_manifest_rejects_shared_mutable_paths(tmp_path):
    manifest = {
        "campaign_id": "campaign_a",
        "skills": [
            _skill(
                "calendar_recall",
                tmp_path,
                result_refs=[str(tmp_path / "shared" / "holdout.jsonl")],
            ),
            _skill(
                "calendar_check",
                tmp_path,
                result_refs=[str(tmp_path / "shared" / "holdout.jsonl")],
            ),
        ],
    }

    with pytest.raises(ValueError, match="shared mutable path"):
        _mod.validate_campaign_manifest(manifest)


def test_schedule_campaign_parallelizes_independent_nodes_and_orders_dependencies(tmp_path):
    manifest = {
        "campaign_id": "campaign_a",
        "skills": [
            _skill("search", tmp_path),
            _skill("ranker", tmp_path, depends_on=["search"]),
            _skill("calendar", tmp_path),
            _skill("billing_a", tmp_path, cluster_id="billing"),
            _skill("billing_b", tmp_path, cluster_id="billing"),
        ],
    }

    validated = _mod.validate_campaign_manifest(manifest)
    schedule = _mod.schedule_campaign(validated)

    search_step = next(step for step in schedule if "search" in step["skill_ids"])
    ranker_step = next(step for step in schedule if "ranker" in step["skill_ids"])
    calendar_step = next(step for step in schedule if "calendar" in step["skill_ids"])
    billing_steps = [step for step in schedule if step["lock_id"] == "cluster:billing"]

    assert search_step["mode"] == "parallel"
    assert calendar_step["mode"] == "parallel"
    assert schedule.index(search_step) < schedule.index(ranker_step)
    assert len(billing_steps) == 2
    assert all(step["mode"] == "sequential" for step in billing_steps)
    assert billing_steps[0]["skill_ids"] == ["billing_a"]
    assert billing_steps[1]["skill_ids"] == ["billing_b"]


def test_dry_audit_classifies_adjacent_and_parametric_parent_candidates(tmp_path):
    manifest = {
        "campaign_id": "campaign_a",
        "skills": [
            _skill(
                "calendar_recall",
                tmp_path,
                triggers=["calendar", "historical", "event lookup"],
                scripts=["scripts/calendar-recall.mjs"],
                failure_modes=["wrong_time_source", "api_first"],
            ),
            _skill(
                "calendar_check",
                tmp_path,
                triggers=["calendar", "future", "event lookup"],
                scripts=["scripts/calendar-check.mjs"],
                failure_modes=["wrong_time_source", "double_booking"],
            ),
            _skill(
                "invoice_search",
                tmp_path,
                triggers=["invoice", "payment", "lookup"],
                scripts=["scripts/invoice-search.mjs"],
                failure_modes=["missing_receipt"],
            ),
        ],
    }

    validated = _mod.validate_campaign_manifest(manifest)
    audit = _mod.audit_skill_adjacency(validated)

    assert audit["summary"]["pair_count"] == 3
    adjacent = [
        pair for pair in audit["pairs"]
        if pair["skill_ids"] == ["calendar_check", "calendar_recall"]
    ][0]
    unrelated = [
        pair for pair in audit["pairs"]
        if pair["skill_ids"] == ["calendar_recall", "invoice_search"]
    ][0]

    assert adjacent["classification"] == "parametric_parent_candidate"
    assert "calendar" in adjacent["overlap"]["triggers"]
    assert unrelated["classification"] == "independent"


def test_campaign_report_builds_gulf_work_packets_from_skill_content(tmp_path):
    python_testing = _skill(
        "python_testing",
        tmp_path,
        triggers=["python", "pytest", "test"],
        failure_modes=["missing_regression_test"],
    )
    tdd = _skill(
        "test_driven_development",
        tmp_path,
        triggers=["python", "pytest", "test"],
        failure_modes=["implementation_without_failing_test"],
    )
    changelog = _skill(
        "changelog",
        tmp_path,
        triggers=["release notes"],
        failure_modes=["missing_user_facing_summary"],
    )
    _write_skill(
        Path(python_testing["skill_path"]),
        """---
name: python-testing
description: Python testing strategies using pytest, fixtures, and coverage.
---

# Python Testing

## Test-Driven Development

Use pytest regression tests, fixtures, parametrization, and coverage checks.
""",
    )
    _write_skill(
        Path(tdd["skill_path"]),
        """---
name: test-driven-development
description: Failing test first workflow for Python and pytest changes.
---

# Test Driven Development

## Red Green Refactor

Write the failing regression test before implementation and keep pytest green.
""",
    )
    _write_skill(
        Path(changelog["skill_path"]),
        """---
name: changelog
description: Write release notes and user-facing change summaries.
---

# Changelog

## Release Notes

Summarize shipped changes for users.
""",
    )

    report = _mod.campaign_report(
        _mod.validate_campaign_manifest(
            {
                "campaign_id": "campaign_a",
                "skills": [python_testing, tdd, changelog],
            }
        )
    )

    gulf = report["gulf_analysis"]
    assert gulf["summary"]["candidate_group_count"] == 1
    candidate = gulf["candidate_groups"][0]
    assert candidate["recommendation"] == "extract_parametric_parent"
    assert candidate["gulf1_comprehension"]["source_skill_ids"] == [
        "python_testing",
        "test_driven_development",
    ]
    assert "contract_success_examples" in candidate["gulf1_comprehension"]["required_human_inputs"]
    assert "routing_boundaries" in candidate["gulf2_specification"]["required_eval_categories"]
    assert candidate["gulf3_work_orders"][0]["human_gate_required"] is True

    separate_pair = [
        pair for pair in gulf["pair_analysis"]
        if pair["skill_ids"] == ["changelog", "python_testing"]
    ][0]
    assert separate_pair["recommendation"] == "keep_separate"
    assert {
        order["skill_id"] for order in gulf["individual_work_orders"]
    } == {"changelog", "python_testing", "test_driven_development"}


def test_write_html_report_renders_schedule_and_adjacency(tmp_path):
    manifest = {
        "campaign_id": "campaign_a",
        "skills": [
            _skill("search", tmp_path, triggers=["search", "rank"]),
            _skill("ranker", tmp_path, depends_on=["search"], triggers=["search", "rerank"]),
        ],
    }
    html_path = tmp_path / "campaign-report.html"

    report = _mod.campaign_report(_mod.validate_campaign_manifest(manifest))
    _mod.write_html_report(report, html_path)

    html = html_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    assert "campaign_a" in html
    assert "Schedule" in html
    assert "ranker" in html
    assert "parametric_parent_candidate" in html
    assert "Gulf 1" in html
    assert "Gulf 2" in html
    assert "Gulf 3" in html


def test_execution_plan_blocks_gulf2_until_gulf1_gate(tmp_path):
    manifest = _validated_campaign(tmp_path, [_skill("search", tmp_path)])
    plan = _mod.build_execution_plan(manifest, _mod.analyze_gulf_work(manifest))

    search = _target(plan, "search")
    gulf2 = _stage(search, "gulf2_specification")

    assert gulf2["status"] == "blocked"
    assert "state.json.gates.gulf_1" in gulf2["blocked_by"]
    assert gulf2["next_action"] == "wait_for_gulf1_gate"


def test_execution_plan_blocks_gulf3_until_gulf2_gate(tmp_path):
    skill = _skill("search", tmp_path)
    _write_json(
        Path(skill["workspace_path"]) / "state.json",
        {"gates": {"gulf_1": "approved", "gulf_2": "pending"}},
    )
    manifest = _validated_campaign(tmp_path, [skill])
    plan = _mod.build_execution_plan(manifest, _mod.analyze_gulf_work(manifest))

    search = _target(plan, "search")
    gulf3 = _stage(search, "gulf3_generalization")

    assert gulf3["status"] == "blocked"
    assert "state.json.gates.gulf_2" in gulf3["blocked_by"]
    assert gulf3["next_action"] == "wait_for_gulf2_gate"


def test_execution_plan_allows_mini_mode_when_quick_start_completed(tmp_path):
    skill = _skill("search", tmp_path)
    _write_json(
        Path(skill["workspace_path"]) / "state.json",
        {
            "quick_start": {"completed": True},
            "gates": {"gulf_1": "pending", "gulf_2": "pending"},
        },
    )
    manifest = _validated_campaign(tmp_path, [skill])
    plan = _mod.build_execution_plan(manifest, _mod.analyze_gulf_work(manifest))

    search = _target(plan, "search")
    gulf3 = _stage(search, "gulf3_generalization")

    assert gulf3["status"] == "ready"
    assert gulf3["mode"] == "mini"
    assert gulf3["trust_level"] == "directional"
    assert gulf3["next_action"] == "run_phase7_mini"


def test_execution_plan_computes_combination_target_workspace_path(tmp_path):
    alpha = _skill("alpha", tmp_path, triggers=["python", "pytest"])
    beta = _skill("beta", tmp_path, triggers=["python", "pytest"])
    manifest = _validated_campaign(tmp_path, [alpha, beta])
    plan = _mod.build_execution_plan(manifest, _mod.analyze_gulf_work(manifest))

    target = _target(plan, "alpha__beta")

    assert target["target_type"] == "parametric_parent_candidate"
    assert target["source_skill_ids"] == ["alpha", "beta"]
    assert target["workspace_path"] == str(tmp_path / "workspaces" / "campaign-alpha__beta")


def test_execution_plan_marks_overlapping_pair_targets(tmp_path):
    alpha = _skill("alpha", tmp_path, triggers=["alpha"])
    bridge = _skill("bridge", tmp_path, triggers=["alpha", "beta"])
    beta = _skill("beta", tmp_path, triggers=["beta"])
    manifest = _validated_campaign(tmp_path, [alpha, bridge, beta])
    plan = _mod.build_execution_plan(manifest, _mod.analyze_gulf_work(manifest))

    pair_targets = [
        target for target in plan["targets"]
        if target["target_type"] != "single_skill"
    ]

    assert {target["target_id"] for target in pair_targets} == {
        "alpha__bridge",
        "beta__bridge",
    }
    assert {target["overlap_group_id"] for target in pair_targets} == {"overlap:bridge"}
    assert all("skill:bridge" in target["locks"] for target in pair_targets)


def test_execution_plan_trusts_only_session_close_trust_gate_for_gulf3_completion(tmp_path):
    skill = _skill("search", tmp_path)
    workspace = Path(skill["workspace_path"])
    _write_json(
        workspace / "state.json",
        {
            "gates": {"gulf_1": "approved", "gulf_2": "approved"},
            "final_only_evaluation": {
                "status": "completed",
                "variant_results_ref": "session_close_holdout/variant_results.json",
            },
        },
    )
    manifest = _validated_campaign(tmp_path, [skill])
    plan = _mod.build_execution_plan(manifest, _mod.analyze_gulf_work(manifest))

    search = _target(plan, "search")
    gulf3 = _stage(search, "gulf3_generalization")

    assert gulf3["status"] == "ready"
    assert gulf3["trust_level"] == "untrusted"

    _write_json(
        workspace / "session_close_holdout" / "variant_results.json",
        {"trust_gate": {"outcome": "review_required"}},
    )
    plan = _mod.build_execution_plan(manifest, _mod.analyze_gulf_work(manifest))
    search = _target(plan, "search")
    gulf3 = _stage(search, "gulf3_generalization")

    assert gulf3["status"] == "complete"
    assert gulf3["trust_level"] == "trusted"
    assert gulf3["trust_gate"]["outcome"] == "review_required"


def test_html_report_renders_execution_plan_stage_status(tmp_path):
    manifest = _validated_campaign(tmp_path, [_skill("search", tmp_path)])
    html_path = tmp_path / "campaign-report.html"

    report = _mod.campaign_report(manifest)
    _mod.write_html_report(report, html_path)

    html = html_path.read_text(encoding="utf-8")
    assert "Execution Plan" in html
    assert "gulf1_comprehension" in html
    assert "gulf2_specification" in html
    assert "blocked" in html
    assert "wait_for_gulf1_gate" in html
