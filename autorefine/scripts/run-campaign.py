#!/usr/bin/env python3
"""
Plan an AutoRefine Phase 7 campaign across multiple prepared skill workspaces.

The CLI is intentionally thin: campaign planning lives in
``autorefine.lib.campaign_planning`` and this script only handles files,
rendering output, and command-line arguments.
"""

import argparse
import html
import json
import sys
from pathlib import Path

BUNDLE_PARENT = Path(__file__).resolve().parents[2]
if str(BUNDLE_PARENT) not in sys.path:
    sys.path.insert(0, str(BUNDLE_PARENT))

from autorefine.lib.campaign_planning import (
    ADJACENCY_FIELDS,
    GULF_REQUIRED_INPUTS,
    MUTABLE_PATH_FIELDS,
    REQUIRED_SKILL_FIELDS,
    TOKEN_STOP_WORDS,
    analyze_gulf_work,
    analyze_skill_pair_for_gulf,
    assert_no_dependency_cycle,
    audit_skill_adjacency,
    build_campaign_targets,
    build_candidate_target,
    build_execution_plan,
    build_individual_work_order,
    build_pair_gulf1_packet,
    build_pair_gulf2_packet,
    build_pair_gulf3_order,
    build_single_skill_target,
    build_target_stage_plan,
    campaign_report,
    classify_skill_pair,
    collect_mutable_paths,
    common_campaign_workspace,
    execution_plan_summary,
    has_same_domain_trigger,
    load_json,
    normalize_command,
    normalize_path,
    normalize_skill,
    normalize_string_list,
    parse_frontmatter,
    read_skill_profile,
    recommend_pair_action,
    schedule_campaign,
    schedule_ready_stages,
    schedule_step,
    skill_terms,
    target_id_for,
    token_set,
    unique_skill_terms,
    validate_campaign_manifest,
)
from autorefine.lib.campaign_readiness import (
    GULF1_EXPECTED_OUTPUTS,
    GULF2_EXPECTED_OUTPUTS,
    GULF3_EXPECTED_OUTPUTS,
    artifact_exists,
    blocked_stage,
    build_gulf1_stage,
    build_gulf2_stage,
    build_gulf3_stage,
    gate_status,
    gate_status_from_state,
    read_trust_gate,
    read_workspace_state,
)


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
