#!/usr/bin/env python3
"""
Plan an AutoRefine Phase 7 campaign across multiple prepared skill workspaces.

The CLI is intentionally thin: campaign planning lives in
``autorefine.lib.campaign_planning`` and this script only handles files and
command-line arguments.
"""

import argparse
import json
import sys
from pathlib import Path

BUNDLE_PARENT = Path(__file__).resolve().parents[2]
if str(BUNDLE_PARENT) not in sys.path:
    sys.path.insert(0, str(BUNDLE_PARENT))

from autorefine.lib import campaign_planning as _planning


def write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_html_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_planning.render_html_report(report), encoding="utf-8")


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
    report = _planning.build_campaign_report_from_manifest(
        _planning.load_json(manifest_path),
        base_dir=manifest_path.parent,
    )
    if args.output:
        write_json(report, Path(args.output))
    if args.html_output:
        write_html_report(report, Path(args.html_output))
    if args.output or args.html_output:
        return
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
