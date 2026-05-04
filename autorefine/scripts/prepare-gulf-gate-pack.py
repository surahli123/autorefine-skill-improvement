#!/usr/bin/env python3
"""
Prepare preauthorized Gulf 1 / Gulf 2 gate packs for campaign workspaces.

The CLI is intentionally narrow: Gate Pack preparation lives in
``autorefine.lib.gate_pack`` and this script handles command-line arguments.
"""

import argparse
import json
import sys
from pathlib import Path

BUNDLE_PARENT = Path(__file__).resolve().parents[2]
if str(BUNDLE_PARENT) not in sys.path:
    sys.path.insert(0, str(BUNDLE_PARENT))

from autorefine.lib import campaign_planning
from autorefine.lib.gate_pack import (
    APPROVAL_SOURCE,
    CANDIDATE_COMPATIBILITY_FIELDS,
    DEFAULT_CONFIG_PATH,
    DEFAULT_EVAL_SCRIPT_PATH,
    DEFAULT_GOLDEN_SET_PATH,
    blocked,
    candidate_compatibility_error,
    clear_candidate_adapter_state_refs,
    count_jsonl_rows,
    load_json,
    load_jsonl_rows,
    materialize_candidate_adapter_evidence,
    prepare_campaign_gate_pack,
    prepare_candidate_gate_pack,
    prepare_target_gate_pack,
    prepare_workspace_gate_pack,
    read_adapter_evidence,
    render_eval_suite,
    render_fixtures_manifest,
    render_gulf1_report,
    render_gulf2_report,
    resolve_workspace_path,
    update_state,
    write_gate_pack_artifacts,
    write_json,
    write_jsonl,
)


def load_campaign_module() -> object:
    return campaign_planning


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
