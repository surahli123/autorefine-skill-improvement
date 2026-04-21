from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autorefine.lib.exemplar_source_loader import (
    build_skill_version_snapshot_bundle,
    load_candidate_skill_records_from_state,
    resolve_exemplar_source_configs,
)


class ExemplarSourceLoaderTest(unittest.TestCase):
    def test_loads_repository_and_evaluation_result_store_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            repository_root = root / "reference-repo"
            skill_dir = repository_root / "skills" / "incident-playbook"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "description: Respond to incidents with a staged workflow.\n"
                "---\n"
                "# Incident Playbook\n"
                "\n"
                "1. Triage the alert.\n"
                "2. Capture evidence.\n",
                encoding="utf-8",
            )
            (skill_dir / "references.md").write_text(
                "# Incident Playbook References\n",
                encoding="utf-8",
            )

            results_root = root / "prior-run"
            iteration0 = results_root / "runs" / "run-001" / "iteration_000"
            iteration1 = results_root / "runs" / "run-001" / "iteration_001"
            iteration0.mkdir(parents=True)
            iteration1.mkdir(parents=True)
            baseline_skill_path = iteration0 / "skill_before.md"
            kept_skill_path = iteration1 / "skill_after.md"
            kept_version_id = "skill_version__run-001__exp_001"
            kept_version_dir = results_root / "skill-versions" / kept_version_id
            kept_version_dir.mkdir(parents=True)
            kept_version_snapshot = kept_version_dir / "SKILL.md"
            baseline_skill_path.write_text(
                "# Checkout Skill v0\n\nCollect bug details before changing code.\n",
                encoding="utf-8",
            )
            kept_skill_path.write_text(
                "# Checkout Skill v1\n\nCollect bug details and preserve rollback notes.\n",
                encoding="utf-8",
            )
            kept_version_snapshot.write_text(
                "# Checkout Skill v1\n\nCollect bug details and preserve rollback notes.\n",
                encoding="utf-8",
            )

            (results_root / "results.json").write_text(
                json.dumps(
                    {
                        "skill_name": "checkout-skill",
                        "experiments": [
                            {
                                "id": 0,
                                "status": "baseline",
                                "skill_snapshot": str(baseline_skill_path),
                                "weighted_score": 0.62,
                                "pass_rate": 0.67,
                            },
                            {
                                "id": 1,
                                "status": "keep",
                                "skill_snapshot": str(kept_skill_path),
                                "version_artifact": {
                                    "version_id": kept_version_id,
                                    "artifact_path": f"skill-versions/{kept_version_id}/",
                                    "snapshot_path": f"skill-versions/{kept_version_id}/SKILL.md",
                                    "snapshot_sha256": "sha256:test-version-artifact",
                                    "parent_version_id": "skill_version__run-001__exp_000",
                                    "created_at": "2026-04-11T09:05:00Z",
                                },
                                "weighted_score": 0.81,
                                "pass_rate": 0.84,
                            },
                            {
                                "id": 2,
                                "status": "discard",
                                "skill_snapshot": str(kept_skill_path),
                                "weighted_score": 0.51,
                                "pass_rate": 0.48,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            holdout_dir = results_root / "session_close_holdout"
            holdout_dir.mkdir(parents=True)
            (holdout_dir / "variant_results.json").write_text(
                json.dumps(
                    {
                        "source_results_ref": "results.json",
                        "selected_candidate_summary": {
                            "version": "v1",
                            "experiment_id": 1,
                            "holdout_score": 83.4,
                        },
                        "variant_results": [
                            {"experiment_id": 0, "version": "v0", "final_score": 67.1},
                            {"experiment_id": 1, "version": "v1", "final_score": 83.4},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            state = {
                "exemplar_sources": [
                    {
                        "source_id": "reference_repo",
                        "source_kind": "repository",
                        "location": str(repository_root),
                    },
                    {
                        "source_id": "prior_campaign",
                        "source_kind": "evaluation_result_store",
                        "location": str(results_root),
                    },
                ]
            }

            resolved_sources = resolve_exemplar_source_configs(state=state)
            self.assertEqual(
                [source["source_kind"] for source in resolved_sources],
                ["repository", "evaluation_result_store"],
            )

            bundle = load_candidate_skill_records_from_state(state=state)

            self.assertEqual(bundle["bundle_type"], "candidate_skill_record_bundle")
            self.assertEqual(bundle["source_count"], 2)
            self.assertEqual(len(bundle["records"]), 3)

            repository_record = next(
                record
                for record in bundle["records"]
                if record["source_id"] == "reference_repo"
            )
            self.assertEqual(repository_record["record_kind"], "repository_skill")
            self.assertEqual(repository_record["references_path"], str(skill_dir / "references.md"))
            self.assertEqual(repository_record["summary"], "Respond to incidents with a staged workflow.")

            baseline_record = next(
                record
                for record in bundle["records"]
                if record["source_id"] == "prior_campaign"
                and record["version_label"] == "v0"
            )
            kept_record = next(
                record
                for record in bundle["records"]
                if record["source_id"] == "prior_campaign"
                and record["version_label"] == "v1"
            )

            self.assertEqual(baseline_record["record_kind"], "evaluated_skill_version")
            self.assertEqual(baseline_record["evaluation_context"]["status"], "baseline")
            self.assertEqual(kept_record["evaluation_context"]["status"], "keep")
            self.assertEqual(kept_record["evaluation_context"]["final_score"], 83.4)
            self.assertEqual(kept_record["version_id"], kept_version_id)
            self.assertEqual(
                kept_record["parent_version_id"],
                "skill_version__run-001__exp_000",
            )
            self.assertEqual(kept_record["skill_path"], str(kept_version_snapshot))
            self.assertEqual(
                kept_record["version_artifact"]["snapshot_path"],
                f"skill-versions/{kept_version_id}/SKILL.md",
            )
            self.assertEqual(
                kept_record["provenance"]["variant_results_ref"],
                str(holdout_dir / "variant_results.json"),
            )
            self.assertEqual(
                kept_record["provenance"]["selected_candidate_summary"]["version"],
                "v1",
            )

            snapshot_bundle = build_skill_version_snapshot_bundle(bundle["records"])
            kept_snapshot = next(
                snapshot
                for snapshot in snapshot_bundle["version_snapshots"]
                if snapshot["version_id"] == kept_version_id
            )
            self.assertEqual(kept_snapshot["snapshot_id"], kept_version_id)
            self.assertEqual(
                kept_snapshot["parent_snapshot_id"],
                "skill_version__run-001__exp_000",
            )
            self.assertEqual(
                kept_snapshot["version_provenance"]["version_artifact"]["artifact_path"],
                f"skill-versions/{kept_version_id}/",
            )


if __name__ == "__main__":
    unittest.main()
