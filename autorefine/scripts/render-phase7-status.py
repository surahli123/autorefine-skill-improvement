#!/usr/bin/env python3
"""Render a Phase 7 status snapshot from a workspace's state.json + run artifacts.

Manual debugging tool. The user runs this when they get lost mid-run; it writes
[workspace]/phase7-status.md (overwriting any prior copy) summarizing what the
active run is doing and where to look. No agent integration.

Design: design_phase7_status_ledger_v0.5.md
Stdlib only.

Exit codes (informational; the user reads any error directly):
    0 = success
    2 = bad workspace (missing or not a directory)
    3 = malformed state.json / results.json / active contract JSON
    4 = cannot write phase7-status.md (disk full / read-only)
    5 = path escape (absolute ref OR resolves outside the workspace)
"""

# Why stdlib-only: this is a v0.5 manual debug tool that ships inside the
# autorefine bundle. Adding deps for a 250-line script the user runs by hand
# would be over-engineering, and would also block running it from a fresh
# clone with nothing installed.
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Human-readable label maps for runner state strings (per design §3d). These
# turn opaque internal enum values into one-glance labels for the ledger.
NEXT_ACTION_LABELS = {
    "phase7_baseline_eval": "Run baseline evaluation",
    "phase7_mutation_analysis": "Analyze and propose next mutation",
    "phase7_test_phase": "Test the mutated skill on the eval set",
    "phase7_session_close": "Close the session - run holdout validation",
    None: "Loop terminal - see Stage status",
}

LAST_MUTATION_STATUS_LABELS = {
    "completed": "Completed -> advancing to test",
    "skipped": "Skipped -> re-targeting",
    "invalid": "Invalid -> rejected before scoring",
    "blocked": "Blocked -> see session-log.json",
    None: "First attempt",
}

SUMMARY_TRUNCATE = 280  # characters; per design §3c "Last Verdict" block


def _exit(code, message):
    """Exit with a code + a clear stderr message. Centralized so the user
    always sees a single-line reason before any non-zero exit."""
    print(message, file=sys.stderr)
    sys.exit(code)


def resolve_workspace_ref(workspace, ref):
    """Resolve a workspace-relative reference safely.

    Per CONCERN from prior reviews: state.json could be corrupted or buggy
    and contain absolute paths or `../` escapes. Both must be rejected.

    Python gotcha: `Path("/a") / "/b"` returns `/b` (the absolute child
    silently discards the parent), and `..` segments only escape if you
    don't bounds-check. We do both.
    """
    ref_path = Path(ref)
    if ref_path.is_absolute():
        _exit(5, f"Path escape: {ref} is absolute, refusing.")
    workspace_resolved = workspace.resolve()
    candidate = (workspace / ref).resolve()
    # On macOS, /tmp resolves to /private/tmp, so .resolve() both sides before
    # comparing. Use is_relative_to via try/except for python <3.9 compat-safety
    # (we still target stdlib but this is the most explicit form).
    try:
        candidate.relative_to(workspace_resolved)
    except ValueError:
        _exit(5, f"Path escape: {ref} resolves outside workspace, refusing.")
    return candidate


def _load_json(path, label):
    """Load JSON. Bad parse -> exit 3 (malformed); missing -> caller decides.

    `label` shows up in the error so the user knows which file to check.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        _exit(3, f"Cannot parse {label}")


def _truncate(text, limit=SUMMARY_TRUNCATE):
    """Truncate to `limit` chars + ellipsis suffix when over."""
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"  # the literal ellipsis char (...)


def _render_success_contract(workspace, state):
    """Render the Success Contract section.

    Source priority (per design §3c):
      1. Active contract JSON via state.active_experiment_contract_path
      2. Markdown fallback at contract/inferred-contract.md
      3. "No contract on file."
    """
    lines = ["## Success Contract"]
    contract_ref = state.get("active_experiment_contract_path")

    if contract_ref:
        contract_path = resolve_workspace_ref(workspace, contract_ref)
        if not contract_path.exists():
            lines.append(f"Active contract referenced but not found: {contract_ref}")
            return "\n".join(lines)
        contract = _load_json(contract_path, "active experiment contract")
        # Required fields per references.md schema. Render each; emit a
        # non-fatal "incomplete" notice when missing. Users can still get
        # partial info even if the contract writer skipped a field.
        objective = contract.get("objective")
        if objective is None:
            lines.append("Active contract incomplete: missing objective")
        else:
            lines.append(f"- Objective: {objective}")
        primary = contract.get("primary_metric") or {}
        metric_name = primary.get("metric_name")
        threshold_pass = primary.get("threshold_pass")
        if metric_name is None or threshold_pass is None:
            lines.append("Active contract incomplete: missing primary_metric")
        else:
            lines.append(
                f"- Primary metric: {metric_name} (threshold_pass: {threshold_pass})"
            )
        thresholds = contract.get("thresholds") or {}
        combined_score = thresholds.get("combined_score")
        if combined_score is None:
            lines.append("Active contract incomplete: missing thresholds.combined_score")
        else:
            lines.append(f"- Combined score threshold: {combined_score}")
        hard_fail = contract.get("hard_fail_dimensions") or []
        if hard_fail:
            lines.append(f"- Hard-fail dims: {', '.join(hard_fail)}")
        return "\n".join(lines)

    # Markdown fallback path
    md_path = workspace / "contract" / "inferred-contract.md"
    if md_path.exists():
        text = md_path.read_text(encoding="utf-8")
        marker = "## Success Criterion"
        idx = text.find(marker)
        if idx == -1:
            lines.append("Contract file exists but missing Success Criterion section")
            return "\n".join(lines)
        # Take the 2 lines immediately after the heading. Skip blank lines
        # right under the heading so we land on actual content.
        after = text[idx + len(marker):].splitlines()
        body = []
        for raw in after:
            stripped = raw.strip()
            if not stripped:
                if body:
                    break
                continue
            body.append(stripped)
            if len(body) >= 2:
                break
        if body:
            for b in body:
                lines.append(b)
        else:
            lines.append("Contract file exists but Success Criterion section is empty")
        return "\n".join(lines)

    lines.append("No contract on file.")
    return "\n".join(lines)


def _find_finalized_experiment(results, experiment_id):
    """Return the experiments[] row matching experiment_id, or None.

    results.json may be missing entirely or have an empty experiments[] list
    while the run is mid-flight. Both are normal in-flight states.
    """
    if results is None:
        return None
    experiments = results.get("experiments") or []
    for exp in experiments:
        if exp.get("id") == experiment_id and exp.get("status"):
            return exp
    return None


def _render_last_verdict(workspace, state, results):
    """Render the Last Verdict section.

    Two branches per design §3c:
      - Finalized: results.json#experiments[id] has a `status`
      - In-flight: read decision_breakdown / decision_explanation from the
        most recent eval_results.json (via iteration_state.last_eval_results_ref)
    """
    lines = ["## Last Verdict"]
    iteration_state = state.get("iteration_state") or {}
    experiment_id = iteration_state.get("experiment_id")
    last_eval_ref = iteration_state.get("last_eval_results_ref")

    # Special case: experiment 0 + no eval ref yet = baseline still running.
    if experiment_id == 0 and not last_eval_ref:
        lines.append("Baseline in progress (no eval results yet)")
        return "\n".join(lines)

    # No eval ref at all and we're past baseline -> just say so.
    if not last_eval_ref:
        lines.append("No verdict yet")
        return "\n".join(lines)

    # Resolve + load the latest eval_results.json (in-flight reasoning lives there).
    eval_path = resolve_workspace_ref(workspace, last_eval_ref)
    eval_data = None
    if not eval_path.exists():
        lines.append(f"Last eval file referenced but not found: {last_eval_ref}")
        return "\n".join(lines)
    try:
        with open(eval_path, "r", encoding="utf-8") as fh:
            eval_data = json.load(fh)
    except json.JSONDecodeError:
        # Mid-write race or genuine corruption: don't kill the whole render;
        # the user still benefits from the rest of the ledger.
        lines.append("Last eval file unreadable (parse error) - possibly mid-write")
        return "\n".join(lines)

    decision_breakdown = eval_data.get("decision_breakdown") or {}
    decision_explanation = eval_data.get("decision_explanation") or {}
    proposed = decision_breakdown.get("proposed_decision")
    combined = decision_breakdown.get("combined_score")
    summary = decision_explanation.get("summary")

    # Multi-judge disagreement guard: a null combined_score means the judges
    # disagreed and we have no aggregate to render. Don't crash on int(None).
    if combined is None or proposed == "disagreement":
        lines.append("Multi-judge disagreement, awaiting human review")
        if last_eval_ref:
            lines.append(f"- Full reasoning: see {last_eval_ref}")
        return "\n".join(lines)

    # Branch on whether we have a finalized record matching this experiment.
    finalized = _find_finalized_experiment(results, experiment_id)
    if finalized:
        status = finalized.get("status")
        score = finalized.get("score")
        max_score = finalized.get("max_score")
        pass_rate = finalized.get("pass_rate")
        lines.append(f"- **Final decision:** {status}")
        if score is not None and max_score is not None and pass_rate is not None:
            lines.append(f"- **Score:** {score}/{max_score} ({pass_rate}%)")
        if summary:
            lines.append(f"- **Why:** {_truncate(summary)}")
        lines.append(f"- **Full reasoning:** see {last_eval_ref}")
        if proposed and proposed != status:
            lines.append(
                f"- **Note:** user overrode agent's proposed `{proposed}` to `{status}`."
            )
        return "\n".join(lines)

    # In-flight branch: render the agent's proposal awaiting accept/override.
    threshold = decision_breakdown.get("threshold")
    pct = decision_breakdown.get("combined_score_pct")
    threshold_pct = threshold * 100 if isinstance(threshold, (int, float)) else None
    if pct is not None and threshold_pct is not None:
        lines.append(
            f"- **Proposed:** {proposed} ({pct}% vs threshold {threshold_pct}%) "
            "- awaiting user accept/override"
        )
    else:
        lines.append(f"- **Proposed:** {proposed} - awaiting user accept/override")
    if summary:
        lines.append(f"- **Why:** {_truncate(summary)}")
    lines.append(f"- **Full reasoning:** see {last_eval_ref}")

    # Non-fatal note when results.json is absent: the user should know
    # the verdict is provisional, not finalized.
    if results is None:
        lines.append("- _Note: results.json missing - finalized status unknown_")
    return "\n".join(lines)


def _render_you_are_here(state):
    """Render the You Are Here section + STALE-MISMATCH warning when applicable."""
    lines = []
    iteration_state = state.get("iteration_state") or {}
    current_run_id = state.get("current_run_id")
    current_run_path = state.get("current_run_path")
    iter_run_path = iteration_state.get("run_path")

    # Stale mismatch: a corrupted writer or partial resume can leave
    # state.current_run_path pointing at one place while iteration_state
    # points elsewhere. Surface that loudly at the top.
    stale_warning = None
    if (
        iteration_state
        and iter_run_path
        and current_run_path
        and current_run_path != iter_run_path
    ):
        stale_warning = (
            f"⚠ STALE-MISMATCH: state.json says current_run_path={current_run_path} "
            f"but iteration_state.run_path={iter_run_path}"
        )

    lines.append("## You Are Here")
    lines.append(f"- Run: {current_run_id} ({current_run_path})")
    if iteration_state:
        lines.append(
            f"- Experiment: {iteration_state.get('experiment_id')} "
            f"(slot: {state.get('current_experiment')})"
        )
        lines.append(
            f"- Stage: {iteration_state.get('active_phase')} "
            f"(status: {iteration_state.get('phase_status')})"
        )
        last_mut_status = iteration_state.get("last_mutation_status")
        last_mut_ref = iteration_state.get("last_mutation_results_ref")
        last_mut_label = LAST_MUTATION_STATUS_LABELS.get(
            last_mut_status, last_mut_status
        )
        if last_mut_ref:
            lines.append(f"- Last mutation: {last_mut_label} ({last_mut_ref})")
        else:
            lines.append(f"- Last mutation: {last_mut_label}")
        next_action = iteration_state.get("next_action")
        next_label = NEXT_ACTION_LABELS.get(next_action, next_action)
        lines.append(f"- Next action: {next_label}")
        # Terminal signposts: when next_action is null AND phase_status says
        # the run finished or got blocked, point at the right artifact.
        phase_status = iteration_state.get("phase_status")
        if next_action is None and phase_status == "completed":
            lines.append("✅ Run finished - see session_close_holdout/")
        elif next_action is None and phase_status == "blocked":
            lines.append("❌ Run blocked - see session-log.json")
    return stale_warning, "\n".join(lines)


def _render_files_to_look_at(state):
    """Render the Files To Look At pointer block."""
    iteration_state = state.get("iteration_state") or {}
    contract_ref = state.get("active_experiment_contract_path") or "contract/inferred-contract.md"
    lines = ["## Files To Look At"]
    lines.append("- State:           state.json")
    lines.append("- Results:         results.json")
    lines.append(f"- Active run:      {state.get('current_run_path')}/")
    lines.append(
        f"- Last eval:       {iteration_state.get('last_eval_results_ref')}"
    )
    last_mut_ref = iteration_state.get("last_mutation_results_ref")
    if last_mut_ref:
        lines.append(f"- Last mutation:   {last_mut_ref}")
    lines.append(f"- Contract:        {contract_ref}")
    lines.append(
        "- Holdout (terminal): session_close_holdout/variant_results.json (if completed)"
    )
    lines.append("- Errors (terminal):  session-log.json (if blocked)")
    return "\n".join(lines)


def render_status(workspace_path):
    """Top-level renderer: read state, dispatch to section renderers, write file.

    Returns the markdown body too, mostly so tests can inspect it without
    re-reading the on-disk file.
    """
    workspace = Path(workspace_path)
    if not workspace.exists():
        _exit(2, f"Workspace not found at {workspace}")
    if not workspace.is_dir():
        _exit(2, f"Workspace path is not a directory: {workspace}")

    state_path = workspace / "state.json"
    if not state_path.exists():
        _exit(2, f"Workspace not found at {workspace} (missing state.json)")
    state = _load_json(state_path, "state.json")

    skill_name = state.get("skill_name", "<unknown>")
    timestamp = datetime.now(timezone.utc).isoformat()
    header = [
        f"# Phase 7 Status - {skill_name}",
        "",
        f"_Generated: {timestamp} by render-phase7-status.py (v0.5)_",
    ]

    # Truncated/legacy state guard: if required top-level keys are missing,
    # render a minimal header + warning. Don't try to keep going with a
    # half-initialized state object.
    if "phases" not in state or "gates" not in state:
        body = "\n".join(
            header
            + [
                "",
                "_state.json appears truncated/legacy: missing required top-level keys (`phases`, `gates`)._",
            ]
        )
        return _write_output(workspace, body)

    # Load results.json if present. Missing -> non-fatal; malformed -> exit 3
    # because that signals real corruption the user needs to know about.
    results_path = workspace / "results.json"
    results = None
    if results_path.exists():
        results = _load_json(results_path, "results.json")

    sections = list(header)
    sections.append("")

    # Stale mismatch warning goes immediately under the header per design.
    stale_warning, you_are_here_block = _render_you_are_here(state)
    if stale_warning:
        sections.append(stale_warning)
        sections.append("")

    # No active run? Render only the minimal pointer + bail.
    current_run_path = state.get("current_run_path")
    if current_run_path is None:
        sections.append("## You Are Here")
        sections.append("No active Phase 7 run")
        body = "\n".join(sections)
        return _write_output(workspace, body)

    # Active run but no iteration_state yet (phase 7 hasn't actually started).
    iteration_state = state.get("iteration_state")
    if iteration_state is None:
        sections.append("## You Are Here")
        sections.append(f"- Run: {state.get('current_run_id')} ({current_run_path})")
        sections.append("Phase 7 not yet started for this run")
        body = "\n".join(sections)
        return _write_output(workspace, body)

    # Full ledger render: You Are Here + Success Contract + Last Verdict + Files
    sections.append(you_are_here_block)
    sections.append("")
    sections.append(_render_success_contract(workspace, state))
    sections.append("")
    sections.append(_render_last_verdict(workspace, state, results))
    sections.append("")
    sections.append(_render_files_to_look_at(state))

    body = "\n".join(sections)
    return _write_output(workspace, body)


def _write_output(workspace, body):
    """Write phase7-status.md, exiting with code 4 on any OSError."""
    out_path = workspace / "phase7-status.md"
    try:
        out_path.write_text(body + "\n", encoding="utf-8")
    except OSError as exc:
        _exit(4, f"Cannot write to {out_path}: {exc}")
    return body


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Render a Phase 7 status snapshot from a workspace's state.json + "
            "run artifacts. Manual debug tool; v0.5 ships script-only."
        )
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace directory (default: current directory)",
    )
    args = parser.parse_args(argv)
    render_status(args.workspace)


if __name__ == "__main__":
    main()
