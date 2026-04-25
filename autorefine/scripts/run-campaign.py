#!/usr/bin/env python3
"""
Plan an AutoRefine Phase 7 campaign across multiple prepared skill workspaces.

The v1 campaign runner is intentionally conservative: it validates that mutable
artifacts are isolated, computes a dependency-aware schedule, and reports
human-gated Gulf work packets before any phase command is executed. Use the JSON
report as the handoff surface for a later execution wrapper.
"""

import argparse
import html
import itertools
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


REQUIRED_SKILL_FIELDS = {
    "skill_id",
    "skill_path",
    "workspace_path",
    "phase7_command",
    "result_refs",
}
MUTABLE_PATH_FIELDS = ("skill_path", "workspace_path")
ADJACENCY_FIELDS = ("triggers", "scripts", "failure_modes", "result_refs")
TOKEN_STOP_WORDS = {
    "a",
    "an",
    "and",
    "after",
    "are",
    "as",
    "before",
    "be",
    "by",
    "common",
    "flags",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "name",
    "need",
    "needs",
    "of",
    "on",
    "open",
    "or",
    "overview",
    "phase",
    "process",
    "that",
    "the",
    "this",
    "to",
    "use",
    "using",
    "with",
}
GULF_REQUIRED_INPUTS = [
    "contract_success_examples",
    "contract_failure_examples",
    "do_not_trigger_examples",
    "human_reviewed_error_analysis",
]
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


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc


def normalize_path(value: object, base_dir: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path values must be non-empty strings")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return str(path.resolve(strict=False))


def normalize_string_list(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    normalized = []
    seen = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} entries must be non-empty strings")
        token = item.strip()
        if token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def normalize_command(value: object, skill_id: str) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if isinstance(value, list) and value:
        command = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{skill_id}: phase7_command entries must be strings")
            command.append(item.strip())
        return command
    raise ValueError(f"{skill_id}: phase7_command must be a string or non-empty list")


def read_skill_profile(skill_path: str, skill_id: str) -> dict:
    path = Path(skill_path)
    if path.is_dir():
        path = path / "SKILL.md"

    if not path.exists():
        return {
            "exists": False,
            "name": skill_id,
            "description": "",
            "headings": [],
            "script_refs": [],
            "terms": [],
        }

    text = path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    headings = [
        match.group(1).strip()
        for match in re.finditer(r"^#{1,4}\s+(.+)$", text, flags=re.MULTILINE)
    ]
    script_refs = sorted(set(re.findall(r"\bscripts/[A-Za-z0-9_./-]+", text)))
    description = frontmatter.get("description", "")
    terms = token_set(" ".join([description, *headings, *script_refs]))

    return {
        "exists": True,
        "name": frontmatter.get("name", skill_id),
        "description": description,
        "headings": headings[:12],
        "script_refs": script_refs,
        "terms": sorted(terms),
    }


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    try:
        block = text.split("---\n", 2)[1]
    except IndexError:
        return {}

    fields = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def token_set(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower()):
        normalized = token.replace("_", "-")
        if normalized in TOKEN_STOP_WORDS:
            continue
        tokens.add(normalized)
    return tokens


def normalize_skill(raw_skill: dict, base_dir: Path) -> dict:
    if not isinstance(raw_skill, dict):
        raise ValueError("each skill entry must be an object")

    missing = sorted(REQUIRED_SKILL_FIELDS - set(raw_skill))
    if missing:
        raise ValueError(f"skill entry missing required fields: {', '.join(missing)}")

    skill_id = raw_skill["skill_id"]
    if not isinstance(skill_id, str) or not skill_id.strip():
        raise ValueError("skill_id must be a non-empty string")
    skill_id = skill_id.strip()

    workspace_path = normalize_path(raw_skill["workspace_path"], base_dir)
    result_refs = [
        normalize_path(ref, base_dir)
        for ref in normalize_string_list(raw_skill.get("result_refs"), f"{skill_id}.result_refs")
    ]
    if not result_refs:
        raise ValueError(f"{skill_id}: result_refs must include at least one artifact path")

    cluster_id = raw_skill.get("cluster_id")
    if cluster_id is not None:
        if not isinstance(cluster_id, str) or not cluster_id.strip():
            raise ValueError(f"{skill_id}: cluster_id must be a non-empty string when present")
        cluster_id = cluster_id.strip()

    skill_path = normalize_path(raw_skill["skill_path"], base_dir)
    return {
        "skill_id": skill_id,
        "skill_path": skill_path,
        "workspace_path": workspace_path,
        "state_path": normalize_path(
            raw_skill.get("state_path") or str(Path(workspace_path) / "state.json"),
            base_dir,
        ),
        "holdout_refs": [
            normalize_path(ref, base_dir)
            for ref in normalize_string_list(
                raw_skill.get("holdout_refs"),
                f"{skill_id}.holdout_refs",
            )
        ],
        "depends_on": normalize_string_list(raw_skill.get("depends_on"), f"{skill_id}.depends_on"),
        "cluster_id": cluster_id,
        "phase7_command": normalize_command(raw_skill["phase7_command"], skill_id),
        "result_refs": result_refs,
        "triggers": normalize_string_list(raw_skill.get("triggers"), f"{skill_id}.triggers"),
        "scripts": normalize_string_list(raw_skill.get("scripts"), f"{skill_id}.scripts"),
        "failure_modes": normalize_string_list(
            raw_skill.get("failure_modes"),
            f"{skill_id}.failure_modes",
        ),
        "skill_profile": read_skill_profile(skill_path, skill_id),
    }


def validate_campaign_manifest(manifest: dict, base_dir: Path | None = None) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")

    campaign_id = manifest.get("campaign_id", "autorefine_campaign")
    if not isinstance(campaign_id, str) or not campaign_id.strip():
        raise ValueError("campaign_id must be a non-empty string")

    raw_skills = manifest.get("skills")
    if not isinstance(raw_skills, list) or not raw_skills:
        raise ValueError("manifest.skills must be a non-empty list")

    root = (base_dir or Path.cwd()).resolve(strict=False)
    skills = [normalize_skill(skill, root) for skill in raw_skills]
    skill_ids = [skill["skill_id"] for skill in skills]
    duplicate_ids = sorted(id_ for id_ in set(skill_ids) if skill_ids.count(id_) > 1)
    if duplicate_ids:
        raise ValueError(f"duplicate skill_id values: {', '.join(duplicate_ids)}")

    known_skill_ids = set(skill_ids)
    for skill in skills:
        unknown_dependencies = sorted(set(skill["depends_on"]) - known_skill_ids)
        if unknown_dependencies:
            raise ValueError(
                f"{skill['skill_id']}: unknown depends_on skill_id values: "
                f"{', '.join(unknown_dependencies)}"
            )

    mutable_paths_by_owner = collect_mutable_paths(skills)
    shared_paths = {
        path: owners
        for path, owners in mutable_paths_by_owner.items()
        if len({owner["skill_id"] for owner in owners}) > 1
    }
    if shared_paths:
        details = "; ".join(
            f"{path} used by {', '.join(sorted(owner['skill_id'] for owner in owners))}"
            for path, owners in sorted(shared_paths.items())
        )
        raise ValueError(f"shared mutable path detected: {details}")

    assert_no_dependency_cycle(skills)

    return {
        "campaign_id": campaign_id.strip(),
        "phase": "phase7_only",
        "skills": sorted(skills, key=lambda skill: skill["skill_id"]),
    }


def collect_mutable_paths(skills: Iterable[dict]) -> dict[str, list[dict]]:
    paths: dict[str, list[dict]] = defaultdict(list)
    for skill in skills:
        for field in MUTABLE_PATH_FIELDS:
            paths[skill[field]].append({"skill_id": skill["skill_id"], "field": field})
        paths[skill["state_path"]].append({"skill_id": skill["skill_id"], "field": "state_path"})
        for path in skill["holdout_refs"]:
            paths[path].append({"skill_id": skill["skill_id"], "field": "holdout_refs"})
        for path in skill["result_refs"]:
            paths[path].append({"skill_id": skill["skill_id"], "field": "result_refs"})
    return paths


def assert_no_dependency_cycle(skills: list[dict]) -> None:
    graph = {skill["skill_id"]: set(skill["depends_on"]) for skill in skills}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(skill_id: str, path: list[str]) -> None:
        if skill_id in visited:
            return
        if skill_id in visiting:
            cycle = " -> ".join(path + [skill_id])
            raise ValueError(f"dependency cycle detected: {cycle}")
        visiting.add(skill_id)
        for dependency in sorted(graph[skill_id]):
            visit(dependency, path + [skill_id])
        visiting.remove(skill_id)
        visited.add(skill_id)

    for skill_id in sorted(graph):
        visit(skill_id, [])


def schedule_campaign(manifest: dict) -> list[dict]:
    skills = {skill["skill_id"]: skill for skill in manifest["skills"]}
    remaining = set(skills)
    completed = set()
    schedule = []
    step_index = 1

    while remaining:
        ready = sorted(
            skill_id
            for skill_id in remaining
            if set(skills[skill_id]["depends_on"]).issubset(completed)
        )
        if not ready:
            raise ValueError("no schedulable skills remain; dependency cycle suspected")

        clustered = [skill_id for skill_id in ready if skills[skill_id]["cluster_id"]]
        cluster_groups: dict[str, list[str]] = defaultdict(list)
        for skill_id in clustered:
            cluster_groups[skills[skill_id]["cluster_id"]].append(skill_id)

        for cluster_id in sorted(cluster_groups):
            for skill_id in sorted(cluster_groups[cluster_id]):
                schedule.append(schedule_step(step_index, [skill_id], skills, "sequential"))
                step_index += 1
                remaining.remove(skill_id)
                completed.add(skill_id)

        independent = [
            skill_id
            for skill_id in ready
            if skill_id in remaining and not skills[skill_id]["cluster_id"]
        ]
        if independent:
            schedule.append(schedule_step(step_index, independent, skills, "parallel"))
            step_index += 1
            remaining.difference_update(independent)
            completed.update(independent)

    return schedule


def schedule_step(
    step_index: int,
    skill_ids: list[str],
    skills: dict[str, dict],
    mode: str,
) -> dict:
    first_skill = skills[skill_ids[0]]
    cluster_id = first_skill.get("cluster_id")
    return {
        "step": step_index,
        "mode": mode,
        "lock_id": f"cluster:{cluster_id}" if cluster_id else "parallel",
        "skill_ids": skill_ids,
        "commands": {skill_id: skills[skill_id]["phase7_command"] for skill_id in skill_ids},
    }


def audit_skill_adjacency(manifest: dict) -> dict:
    pairs = []
    skills = manifest["skills"]
    for left, right in itertools.combinations(skills, 2):
        pair = classify_skill_pair(left, right)
        pairs.append(pair)

    summary = {
        "pair_count": len(pairs),
        "merge_candidate_count": sum(
            1 for pair in pairs if pair["classification"] == "merge_candidate"
        ),
        "parametric_parent_candidate_count": sum(
            1 for pair in pairs if pair["classification"] == "parametric_parent_candidate"
        ),
    }
    return {"summary": summary, "pairs": pairs}


def classify_skill_pair(left: dict, right: dict) -> dict:
    overlap = {}
    union_size = 0
    overlap_size = 0
    for field in ADJACENCY_FIELDS:
        left_values = set(left[field])
        right_values = set(right[field])
        shared = sorted(left_values & right_values)
        overlap[field] = shared
        union_size += len(left_values | right_values)
        overlap_size += len(shared)

    score = round(overlap_size / union_size, 6) if union_size else 0.0
    if score >= 0.55:
        classification = "merge_candidate"
    elif score >= 0.18 or has_same_domain_trigger(left, right):
        classification = "parametric_parent_candidate"
    else:
        classification = "independent"

    return {
        "skill_ids": sorted([left["skill_id"], right["skill_id"]]),
        "adjacency_score": score,
        "classification": classification,
        "overlap": overlap,
    }


def has_same_domain_trigger(left: dict, right: dict) -> bool:
    left_triggers = {trigger.lower() for trigger in left["triggers"]}
    right_triggers = {trigger.lower() for trigger in right["triggers"]}
    return bool(left_triggers & right_triggers)


def analyze_gulf_work(manifest: dict) -> dict:
    pair_analysis = []
    candidate_groups = []
    for left, right in itertools.combinations(manifest["skills"], 2):
        analysis = analyze_skill_pair_for_gulf(left, right)
        pair_analysis.append(analysis)
        if analysis["recommendation"] != "keep_separate":
            candidate_groups.append(analysis)

    individual_work_orders = [build_individual_work_order(skill) for skill in manifest["skills"]]
    recommendation_counts: dict[str, int] = defaultdict(int)
    for pair in pair_analysis:
        recommendation_counts[pair["recommendation"]] += 1

    return {
        "summary": {
            "candidate_group_count": len(candidate_groups),
            "pair_count": len(pair_analysis),
            "recommendations": dict(sorted(recommendation_counts.items())),
            "limits": [
                "Gulf 1 error analysis still requires human review before trust claims.",
                "Gulf 2 judges and fixtures must be approved before Gulf 3 execution.",
                "Campaign output is a work packet, not an automatic skill rewrite.",
            ],
        },
        "candidate_groups": candidate_groups,
        "pair_analysis": pair_analysis,
        "individual_work_orders": individual_work_orders,
    }


def analyze_skill_pair_for_gulf(left: dict, right: dict) -> dict:
    adjacency = classify_skill_pair(left, right)
    shared_terms = sorted(skill_terms(left) & skill_terms(right))
    recommendation = recommend_pair_action(adjacency, shared_terms)
    skill_ids = sorted([left["skill_id"], right["skill_id"]])

    return {
        "skill_ids": skill_ids,
        "recommendation": recommendation,
        "adjacency_classification": adjacency["classification"],
        "shared_signals": {
            "terms": shared_terms[:16],
            "triggers": adjacency["overlap"]["triggers"],
            "scripts": adjacency["overlap"]["scripts"],
            "failure_modes": adjacency["overlap"]["failure_modes"],
        },
        "gulf1_comprehension": build_pair_gulf1_packet(left, right, shared_terms),
        "gulf2_specification": build_pair_gulf2_packet(recommendation),
        "gulf3_work_orders": [build_pair_gulf3_order(left, right, recommendation)],
    }


def skill_terms(skill: dict) -> set[str]:
    text_sources = [
        *skill["triggers"],
        *skill["scripts"],
        *skill["failure_modes"],
        skill["skill_profile"]["description"],
        *skill["skill_profile"]["headings"],
        *skill["skill_profile"]["script_refs"],
    ]
    return token_set(" ".join(text_sources)) | set(skill["skill_profile"]["terms"])


def recommend_pair_action(adjacency: dict, shared_terms: list[str]) -> str:
    if adjacency["classification"] == "merge_candidate" and len(shared_terms) >= 6:
        return "combine_skills"
    if adjacency["classification"] in {"merge_candidate", "parametric_parent_candidate"}:
        return "extract_parametric_parent"
    return "keep_separate"


def build_pair_gulf1_packet(left: dict, right: dict, shared_terms: list[str]) -> dict:
    return {
        "source_skill_ids": sorted([left["skill_id"], right["skill_id"]]),
        "shared_intent": shared_terms[:10],
        "distinct_responsibilities": {
            left["skill_id"]: unique_skill_terms(left, right),
            right["skill_id"]: unique_skill_terms(right, left),
        },
        "source_descriptions": {
            left["skill_id"]: left["skill_profile"]["description"],
            right["skill_id"]: right["skill_profile"]["description"],
        },
        "required_human_inputs": GULF_REQUIRED_INPUTS,
        "gate": "requires_gulf1_human_review",
    }


def unique_skill_terms(skill: dict, other: dict) -> list[str]:
    return sorted(skill_terms(skill) - skill_terms(other))[:10]


def build_pair_gulf2_packet(recommendation: str) -> dict:
    required_eval_categories = [
        "routing_boundaries",
        "behavior_parity",
        "negative_trigger_examples",
        "regression_suite",
    ]
    if recommendation in {"combine_skills", "extract_parametric_parent"}:
        required_eval_categories.extend(
            ["shared_fixture_coverage", "parametric_variant_coverage"]
        )

    return {
        "required_eval_categories": required_eval_categories,
        "primary_oracle": (
            "contract-example pass/fail plus adapter primary metric when configured"
        ),
        "secondary_oracles": [
            "explanation_quality",
            "scope_discipline",
            "user_facing_clarity",
        ],
        "judge_rule": (
            "secondary LLM explanation quality may diagnose regressions but must not "
            "override adapter primary metrics"
        ),
    }


def build_pair_gulf3_order(left: dict, right: dict, recommendation: str) -> dict:
    skill_ids = sorted([left["skill_id"], right["skill_id"]])
    return {
        "action": recommendation,
        "target_skill_ids": skill_ids,
        "status": "requires_gulf_gates",
        "human_gate_required": True,
        "workspace_hint": common_campaign_workspace(left, right),
        "steps": [
            "prepare copied skill-under-test workspaces",
            "complete Gulf 1 comprehension and human-reviewed error analysis",
            "approve Gulf 2 eval fixtures and judge oracles",
            "run Phase 7 only after gates pass",
        ],
    }


def common_campaign_workspace(left: dict, right: dict) -> str:
    left_parent = Path(left["workspace_path"]).parent
    name = "__".join(sorted([left["skill_id"], right["skill_id"]]))
    return str((left_parent / f"campaign-{name}").resolve(strict=False))


def build_individual_work_order(skill: dict) -> dict:
    return {
        "skill_id": skill["skill_id"],
        "recommendation": "improve_separate_skill",
        "gulf1_comprehension": {
            "description": skill["skill_profile"]["description"],
            "headings": skill["skill_profile"]["headings"],
            "required_human_inputs": GULF_REQUIRED_INPUTS,
        },
        "gulf2_specification": {
            "required_eval_categories": [
                "activation_contract",
                "failure_examples",
                "do_not_trigger_boundaries",
                "regression_suite",
            ],
            "primary_oracle": (
                "domain adapter metric when available, otherwise contract-example pass/fail"
            ),
        },
        "gulf3_work_order": {
            "action": "improve_separate_skill",
            "target_skill_ids": [skill["skill_id"]],
            "status": "requires_gulf_gates",
            "human_gate_required": True,
            "workspace_hint": skill["workspace_path"],
        },
    }


def target_id_for(skill_ids: list[str]) -> str:
    return "__".join(sorted(skill_ids))


def build_campaign_targets(manifest: dict, gulf_analysis: dict) -> list[dict]:
    skills = {skill["skill_id"]: skill for skill in manifest["skills"]}
    candidate_groups = [
        group for group in gulf_analysis["candidate_groups"]
        if len(group["skill_ids"]) == 2
    ]
    source_counts: dict[str, int] = defaultdict(int)
    for group in candidate_groups:
        for skill_id in group["skill_ids"]:
            source_counts[skill_id] += 1

    targets = [build_single_skill_target(skill) for skill in manifest["skills"]]
    for group in candidate_groups:
        targets.append(build_candidate_target(group, skills, source_counts))
    return sorted(targets, key=lambda target: target["target_id"])


def build_single_skill_target(skill: dict) -> dict:
    skill_id = skill["skill_id"]
    return {
        "target_id": skill_id,
        "target_type": "single_skill",
        "source_skill_ids": [skill_id],
        "overlap_group_id": None,
        "workspace_path": skill["workspace_path"],
        "lock_id": f"target:{skill_id}",
        "locks": [f"skill:{skill_id}"],
        "recommendation": "improve_separate_skill",
        "cluster_id": skill.get("cluster_id"),
        "phase7_command": skill["phase7_command"],
    }


def build_candidate_target(
    candidate_group: dict,
    skills: dict[str, dict],
    source_counts: dict[str, int],
) -> dict:
    skill_ids = sorted(candidate_group["skill_ids"])
    target_id = target_id_for(skill_ids)
    overlapping_sources = [
        skill_id for skill_id in skill_ids
        if source_counts[skill_id] > 1
    ]
    recommendation = candidate_group["recommendation"]
    target_type = {
        "combine_skills": "combine_candidate",
        "extract_parametric_parent": "parametric_parent_candidate",
    }.get(recommendation, recommendation)

    return {
        "target_id": target_id,
        "target_type": target_type,
        "source_skill_ids": skill_ids,
        "overlap_group_id": (
            f"overlap:{'__'.join(overlapping_sources)}"
            if overlapping_sources
            else None
        ),
        "workspace_path": common_campaign_workspace(
            skills[skill_ids[0]],
            skills[skill_ids[1]],
        ),
        "lock_id": f"target:{target_id}",
        "locks": [f"skill:{skill_id}" for skill_id in skill_ids],
        "recommendation": recommendation,
        "cluster_id": None,
        "preparation_steps": candidate_group["gulf3_work_orders"][0]["steps"],
    }


def build_execution_plan(manifest: dict, gulf_analysis: dict) -> dict:
    targets = build_campaign_targets(manifest, gulf_analysis)
    planned_targets = []
    for target in targets:
        planned_target = dict(target)
        planned_target["stages"] = build_target_stage_plan(planned_target)
        planned_targets.append(planned_target)

    plan = {
        "mode": "plan_only",
        "summary": execution_plan_summary(planned_targets),
        "targets": planned_targets,
        "stage_schedule": [],
    }
    plan["stage_schedule"] = schedule_ready_stages(plan)
    return plan


def execution_plan_summary(targets: list[dict]) -> dict:
    stages = [stage for target in targets for stage in target["stages"]]
    return {
        "target_count": len(targets),
        "ready_stage_count": sum(1 for stage in stages if stage["status"] == "ready"),
        "blocked_stage_count": sum(1 for stage in stages if stage["status"] == "blocked"),
        "human_gate_count": sum(
            1 for stage in stages if stage["status"] == "needs_human_gate"
        ),
    }


def build_target_stage_plan(target: dict) -> list[dict]:
    state = read_workspace_state(Path(target["workspace_path"]))
    if state["error"]:
        return [
            blocked_stage("gulf1_comprehension", state["error"], GULF1_EXPECTED_OUTPUTS),
            blocked_stage("gulf2_specification", state["error"], GULF2_EXPECTED_OUTPUTS),
            blocked_stage("gulf3_generalization", state["error"], GULF3_EXPECTED_OUTPUTS),
        ]
    return [
        build_gulf1_stage(target, state),
        build_gulf2_stage(target, state),
        build_gulf3_stage(target, state),
    ]


def blocked_stage(stage_name: str, reason: str, expected_outputs: list[str]) -> dict:
    return {
        "stage": stage_name,
        "status": "blocked",
        "blocked_by": [reason],
        "inputs": ["skill-under-test/SKILL.md"],
        "expected_outputs": expected_outputs,
        "gate": None,
        "mode": "full",
        "trust_level": "untrusted",
        "next_action": "repair_workspace_state",
    }


def build_gulf1_stage(target: dict, state: dict) -> dict:
    gate = gate_status_from_state(state, "gulf_1")
    outputs_exist = all(
        artifact_exists(Path(target["workspace_path"]), output)
        for output in GULF1_EXPECTED_OUTPUTS
    )
    if gate == "approved":
        status = "complete"
        next_action = None
        blocked_by = []
    elif outputs_exist:
        status = "needs_human_gate"
        next_action = "request_gulf1_gate_review"
        blocked_by = ["state.json.gates.gulf_1"]
    else:
        status = "ready"
        next_action = "prepare_gulf1_workspace"
        blocked_by = []

    return {
        "stage": "gulf1_comprehension",
        "status": status,
        "blocked_by": blocked_by,
        "inputs": ["skill-under-test/SKILL.md"],
        "expected_outputs": GULF1_EXPECTED_OUTPUTS,
        "gate": {
            "name": "gulf_1",
            "required": True,
            "approval_source": "state.json.gates.gulf_1",
            "status": gate,
        },
        "mode": "full",
        "trust_level": "trusted_after_gate",
        "next_action": next_action,
    }


def build_gulf2_stage(target: dict, state: dict) -> dict:
    gulf1_gate = gate_status_from_state(state, "gulf_1")
    gulf2_gate = gate_status_from_state(state, "gulf_2")
    outputs_exist = all(
        artifact_exists(Path(target["workspace_path"]), output)
        for output in GULF2_EXPECTED_OUTPUTS
    )
    if gulf1_gate != "approved":
        status = "blocked"
        next_action = "wait_for_gulf1_gate"
        blocked_by = ["state.json.gates.gulf_1"]
    elif gulf2_gate == "approved":
        status = "complete"
        next_action = None
        blocked_by = []
    elif outputs_exist:
        status = "needs_human_gate"
        next_action = "request_gulf2_gate_review"
        blocked_by = ["state.json.gates.gulf_2"]
    else:
        status = "ready"
        next_action = "prepare_gulf2_specification"
        blocked_by = []

    return {
        "stage": "gulf2_specification",
        "status": status,
        "blocked_by": blocked_by,
        "inputs": ["contract/", "design-audit.md", "eval-suite.md"],
        "expected_outputs": GULF2_EXPECTED_OUTPUTS,
        "gate": {
            "name": "gulf_2",
            "required": True,
            "approval_source": "state.json.gates.gulf_2",
            "status": gulf2_gate,
        },
        "mode": "full",
        "trust_level": "trusted_after_gate",
        "next_action": next_action,
    }


def build_gulf3_stage(target: dict, state: dict) -> dict:
    workspace_path = Path(target["workspace_path"])
    trust_gate = read_trust_gate(workspace_path)
    if trust_gate["status"] in {"malformed", "invalid_outcome"}:
        return {
            "stage": "gulf3_generalization",
            "status": "blocked",
            "blocked_by": [trust_gate["error"]],
            "inputs": ["eval-suite.md", "judges/", "domain-eval/"],
            "expected_outputs": GULF3_EXPECTED_OUTPUTS,
            "gate": {
                "name": "session_close_trust_gate",
                "required": True,
                "approval_source": "session_close_holdout/variant_results.json#trust_gate",
            },
            "mode": "full",
            "trust_level": "untrusted",
            "next_action": "repair_session_close_holdout",
        }
    if trust_gate["status"] == "valid":
        return {
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
            "trust_gate": trust_gate["trust_gate"],
            "next_action": None,
        }

    gulf1_gate = gate_status_from_state(state, "gulf_1")
    gulf2_gate = gate_status_from_state(state, "gulf_2")
    quick_start_completed = bool(
        state["data"].get("quick_start", {}).get("completed")
    )
    if gulf1_gate == "approved" and gulf2_gate == "approved":
        status = "ready"
        mode = "full"
        trust_level = "untrusted"
        next_action = "run_phase7_full"
        blocked_by = []
    elif quick_start_completed and gulf1_gate == "pending" and gulf2_gate == "pending":
        status = "ready"
        mode = "mini"
        trust_level = "directional"
        next_action = "run_phase7_mini"
        blocked_by = []
    else:
        status = "blocked"
        mode = "full"
        trust_level = "untrusted"
        next_action = "wait_for_gulf2_gate"
        blocked_by = ["state.json.gates.gulf_2"]
        if gulf1_gate != "approved":
            next_action = "wait_for_gulf1_gate"
            blocked_by = ["state.json.gates.gulf_1"]

    return {
        "stage": "gulf3_generalization",
        "status": status,
        "blocked_by": blocked_by,
        "inputs": ["eval-suite.md", "judges/", "domain-eval/"],
        "expected_outputs": GULF3_EXPECTED_OUTPUTS,
        "gate": {
            "name": "session_close_trust_gate",
            "required": True,
            "approval_source": "session_close_holdout/variant_results.json#trust_gate",
        },
        "mode": mode,
        "trust_level": trust_level,
        "next_action": next_action,
    }


def read_workspace_state(workspace_path: Path | str) -> dict:
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


def gate_status(workspace_path: Path | str, gate_name: str) -> str:
    return gate_status_from_state(read_workspace_state(workspace_path), gate_name)


def gate_status_from_state(state: dict, gate_name: str) -> str:
    gates = state["data"].get("gates", {})
    if not isinstance(gates, dict):
        return "pending"
    value = gates.get(gate_name, "pending")
    return value if value in {"approved", "pending", "rejected"} else "pending"


def artifact_exists(workspace_path: Path | str, relative_path: str) -> bool:
    workspace_path = Path(workspace_path)
    if "*" in relative_path:
        return bool(list(workspace_path.glob(relative_path)))
    path = workspace_path / relative_path
    return path.exists()


def read_trust_gate(workspace_path: Path | str) -> dict:
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


def schedule_ready_stages(execution_plan: dict) -> list[dict]:
    ready_items = []
    for target in execution_plan["targets"]:
        for stage in target["stages"]:
            if stage["status"] == "ready":
                ready_items.append((target, stage))

    schedule = []
    step_index = 1
    remaining = ready_items
    while remaining:
        used_locks: set[str] = set()
        parallel_targets = []
        next_remaining = []
        for target, stage in remaining:
            locks = set(target["locks"])
            if target.get("cluster_id"):
                locks.add(f"cluster:{target['cluster_id']}")
            if used_locks & locks:
                next_remaining.append((target, stage))
                continue
            used_locks.update(locks)
            parallel_targets.append((target, stage))

        if len(parallel_targets) == 1:
            target, stage = parallel_targets[0]
            lock_id = (
                f"cluster:{target['cluster_id']}"
                if target.get("cluster_id")
                else target["lock_id"]
            )
            mode = "sequential" if target.get("cluster_id") else "parallel"
            target_ids = [target["target_id"]]
            stage_name = stage["stage"]
        else:
            mode = "parallel"
            lock_id = "parallel"
            target_ids = [target["target_id"] for target, _stage in parallel_targets]
            stage_names = sorted({_stage["stage"] for _target, _stage in parallel_targets})
            stage_name = ",".join(stage_names)

        schedule.append(
            {
                "step": step_index,
                "mode": mode,
                "lock_id": lock_id,
                "target_ids": target_ids,
                "stage": stage_name,
            }
        )
        step_index += 1
        remaining = next_remaining

    return schedule


def campaign_report(manifest: dict) -> dict:
    gulf_analysis = analyze_gulf_work(manifest)
    return {
        "campaign_id": manifest["campaign_id"],
        "phase": manifest["phase"],
        "skills": manifest["skills"],
        "adjacency_audit": audit_skill_adjacency(manifest),
        "gulf_analysis": gulf_analysis,
        "schedule": schedule_campaign(manifest),
        "execution_plan": build_execution_plan(manifest, gulf_analysis),
    }


def write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_html_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html_report(report), encoding="utf-8")


def render_html_report(report: dict) -> str:
    schedule_rows = "\n".join(render_schedule_row(step) for step in report["schedule"])
    adjacency_rows = "\n".join(
        render_adjacency_row(pair)
        for pair in report["adjacency_audit"]["pairs"]
        if pair["classification"] != "independent"
    )
    if not adjacency_rows:
        adjacency_rows = (
            "<tr><td colspan=\"4\" class=\"muted\">"
            "No merge or parametric-parent candidates detected."
            "</td></tr>"
        )

    summary = report["adjacency_audit"]["summary"]
    gulf = report["gulf_analysis"]
    gulf_candidate_rows = "\n".join(
        render_gulf_candidate_row(candidate)
        for candidate in gulf["candidate_groups"]
    )
    if not gulf_candidate_rows:
        gulf_candidate_rows = (
            "<tr><td colspan=\"5\" class=\"muted\">"
            "No combine or shared-parent work packets detected."
            "</td></tr>"
        )
    individual_rows = "\n".join(
        render_individual_work_order_row(order)
        for order in gulf["individual_work_orders"]
    )
    execution_plan = report["execution_plan"]
    execution_rows = "\n".join(
        render_execution_plan_row(target)
        for target in execution_plan["targets"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AutoRefine Campaign Report - {escape(report["campaign_id"])}</title>
  <style>
    :root {{
      color-scheme: light;
      --text: #1d252c;
      --muted: #62707c;
      --line: #d8dee4;
      --surface: #f7f9fb;
      --accent: #1f7a8c;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      margin: 0;
      background: #fff;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    h1, h2 {{
      letter-spacing: 0;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin: 24px 0;
    }}
    .metric {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .metric strong {{
      display: block;
      font-size: 24px;
      margin-bottom: 4px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0 28px;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      background: var(--surface);
    }}
    code {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 1px 4px;
      font-size: 13px;
    }}
    .badge {{
      color: #fff;
      background: var(--accent);
      border-radius: 999px;
      display: inline-block;
      padding: 2px 8px;
      font-size: 12px;
      white-space: nowrap;
    }}
    .muted {{
      color: var(--muted);
    }}
  </style>
</head>
<body>
<main>
  <h1>AutoRefine Campaign Report</h1>
  <p class="muted">Campaign <code>{escape(report["campaign_id"])}</code> is a
  planning-first Phase 7 schedule. Commands are reported, not executed.</p>

  <section class="summary" aria-label="Campaign summary">
    <div class="metric"><strong>{len(report["skills"])}</strong><span>Skills</span></div>
    <div class="metric"><strong>{len(report["schedule"])}</strong><span>Schedule steps</span></div>
    <div class="metric"><strong>{summary["pair_count"]}</strong><span>Skill pairs audited</span></div>
    <div class="metric"><strong>{summary["parametric_parent_candidate_count"]}</strong><span>Parametric candidates</span></div>
    <div class="metric"><strong>{summary["merge_candidate_count"]}</strong><span>Merge candidates</span></div>
    <div class="metric"><strong>{gulf["summary"]["candidate_group_count"]}</strong><span>Gulf work packets</span></div>
    <div class="metric"><strong>{execution_plan["summary"]["ready_stage_count"]}</strong><span>Ready stages</span></div>
  </section>

  <h2>Schedule</h2>
  <table>
    <thead><tr><th>Step</th><th>Mode</th><th>Lock</th><th>Skills</th><th>Commands</th></tr></thead>
    <tbody>
      {schedule_rows}
    </tbody>
  </table>

  <h2>Adjacency / DRY Audit</h2>
  <table>
    <thead><tr><th>Classification</th><th>Score</th><th>Skills</th><th>Shared signals</th></tr></thead>
    <tbody>
      {adjacency_rows}
    </tbody>
  </table>

  <h2>Gulf 1 / Gulf 2 / Gulf 3 Work Packets</h2>
  <p class="muted">These packets identify where skills may combine, share a
  parametric parent, or improve separately. They do not replace Gulf 1 human
  error analysis or Gulf 2 judge approval.</p>
  <table>
    <thead>
      <tr>
        <th>Recommendation</th>
        <th>Skills</th>
        <th>Gulf 1 comprehension</th>
        <th>Gulf 2 specification</th>
        <th>Gulf 3 work order</th>
      </tr>
    </thead>
    <tbody>
      {gulf_candidate_rows}
    </tbody>
  </table>

  <h2>Separate Skill Improvement Orders</h2>
  <table>
    <thead><tr><th>Skill</th><th>Gulf 1</th><th>Gulf 2</th><th>Gulf 3</th></tr></thead>
    <tbody>
      {individual_rows}
    </tbody>
  </table>

  <h2>Execution Plan</h2>
  <p class="muted">Plan-only Gulf stage status. These next actions are
  computed for handoff and are not executed by this report.</p>
  <table>
    <thead>
      <tr>
        <th>Target</th>
        <th>Type</th>
        <th>Workspace</th>
        <th>Stages</th>
        <th>Next actions</th>
      </tr>
    </thead>
    <tbody>
      {execution_rows}
    </tbody>
  </table>
</main>
</body>
</html>
"""


def render_schedule_row(step: dict) -> str:
    command_list = [
        f"<code>{escape(skill_id)}: {escape(' '.join(command))}</code>"
        for skill_id, command in sorted(step["commands"].items())
    ]
    return (
        "<tr>"
        f"<td>{step['step']}</td>"
        f"<td><span class=\"badge\">{escape(step['mode'])}</span></td>"
        f"<td><code>{escape(step['lock_id'])}</code></td>"
        f"<td>{escape(', '.join(step['skill_ids']))}</td>"
        f"<td>{'<br>'.join(command_list)}</td>"
        "</tr>"
    )


def render_adjacency_row(pair: dict) -> str:
    shared_signals = []
    for field, values in pair["overlap"].items():
        if values:
            shared_signals.append(f"{escape(field)}: {escape(', '.join(values))}")
    shared_text = (
        "<br>".join(shared_signals)
        if shared_signals
        else '<span class="muted">none</span>'
    )
    return (
        "<tr>"
        f"<td><span class=\"badge\">{escape(pair['classification'])}</span></td>"
        f"<td>{pair['adjacency_score']}</td>"
        f"<td>{escape(', '.join(pair['skill_ids']))}</td>"
        f"<td>{shared_text}</td>"
        "</tr>"
    )


def render_gulf_candidate_row(candidate: dict) -> str:
    gulf1 = candidate["gulf1_comprehension"]
    gulf2 = candidate["gulf2_specification"]
    gulf3 = candidate["gulf3_work_orders"][0]
    return (
        "<tr>"
        f"<td><span class=\"badge\">{escape(candidate['recommendation'])}</span></td>"
        f"<td>{escape(', '.join(candidate['skill_ids']))}</td>"
        f"<td>Gulf 1: shared intent "
        f"<code>{escape(', '.join(gulf1['shared_intent']) or 'none')}</code><br>"
        f"Gate: {escape(gulf1['gate'])}</td>"
        f"<td>Gulf 2: {escape(', '.join(gulf2['required_eval_categories']))}<br>"
        f"Primary: {escape(gulf2['primary_oracle'])}</td>"
        f"<td>Gulf 3: {escape(gulf3['action'])}<br>"
        f"Status: {escape(gulf3['status'])}<br>"
        f"Workspace: <code>{escape(gulf3['workspace_hint'])}</code></td>"
        "</tr>"
    )


def render_individual_work_order_row(order: dict) -> str:
    gulf1 = order["gulf1_comprehension"]
    gulf2 = order["gulf2_specification"]
    gulf3 = order["gulf3_work_order"]
    return (
        "<tr>"
        f"<td>{escape(order['skill_id'])}</td>"
        f"<td>Gulf 1: {escape(gulf1['description'] or 'description missing')}<br>"
        f"Inputs: {escape(', '.join(gulf1['required_human_inputs']))}</td>"
        f"<td>Gulf 2: {escape(', '.join(gulf2['required_eval_categories']))}<br>"
        f"Primary: {escape(gulf2['primary_oracle'])}</td>"
        f"<td>Gulf 3: {escape(gulf3['action'])}<br>"
        f"Status: {escape(gulf3['status'])}<br>"
        f"Workspace: <code>{escape(gulf3['workspace_hint'])}</code></td>"
        "</tr>"
    )


def render_execution_plan_row(target: dict) -> str:
    stages = []
    actions = []
    for stage in target["stages"]:
        blocked_by = (
            f" blocked by {', '.join(stage['blocked_by'])}"
            if stage["blocked_by"]
            else ""
        )
        trust = f" ({stage['trust_level']})" if stage.get("trust_level") else ""
        stages.append(
            f"{escape(stage['stage'])}: "
            f"<span class=\"badge\">{escape(stage['status'])}</span>"
            f"{escape(trust)}{escape(blocked_by)}"
        )
        if stage.get("next_action"):
            actions.append(
                f"{escape(stage['stage'])}: <code>{escape(stage['next_action'])}</code>"
            )

    actions_text = (
        "<br>".join(actions)
        if actions
        else '<span class="muted">none</span>'
    )
    return (
        "<tr>"
        f"<td><code>{escape(target['target_id'])}</code><br>"
        f"<span class=\"muted\">{escape(', '.join(target['source_skill_ids']))}</span></td>"
        f"<td>{escape(target['target_type'])}</td>"
        f"<td><code>{escape(target['workspace_path'])}</code></td>"
        f"<td>{'<br>'.join(stages)}</td>"
        f"<td>{actions_text}</td>"
        "</tr>"
    )


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and schedule an AutoRefine Phase 7 skill campaign."
    )
    parser.add_argument("--manifest", required=True, help="Campaign manifest JSON path.")
    parser.add_argument("--output", help="Optional JSON report path.")
    parser.add_argument("--html-output", help="Optional HTML report path.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    manifest_path = Path(args.manifest)
    validated = validate_campaign_manifest(
        load_json(manifest_path),
        base_dir=manifest_path.parent,
    )
    report = campaign_report(validated)
    if args.output:
        write_json(report, Path(args.output))
    if args.html_output:
        write_html_report(report, Path(args.html_output))
    if args.output or args.html_output:
        return
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
