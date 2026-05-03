"""Tests for autorefine/scripts/render-phase7-status.py.

24 tests per design §5 (T1-T24). Stdlib unittest, fixtures inline.
Each test creates its own tempdir workspace, writes the JSON state files,
invokes the renderer, and asserts on the output (markdown body or exit code).
"""

import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


# Same loader pattern as test_campaign_orchestrator_py.py: load the script as
# a module via importlib because the filename has hyphens.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "render_phase7_status",
    SCRIPTS_DIR / "render-phase7-status.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["render_phase7_status"] = _mod
_spec.loader.exec_module(_mod)


def _minimal_state(**overrides):
    """Default schema_version=4 state.json with no active run."""
    state = {
        "schema_version": 4,
        "skill_name": "test-skill",
        "skill_path": "/tmp/skill",
        "original_skill_path": "/tmp/skill",
        "workspace_path": "/tmp/workspace",
        "started": "2026-05-02",
        "current_phase": 7,
        "current_gulf": 3,
        "phases": {},
        "gates": {"gulf_1": "pending", "gulf_2": "pending"},
        "hamel_available": False,
        "loop_iteration": 0,
        "locked_judges": [],
        "memory_path": None,
        "checkpoint": None,
        "consecutive_discards": 0,
        "circuit_breaker": None,
        "current_run_id": None,
        "current_run_path": None,
        "current_experiment": None,
        "iteration_state": None,
        "completion_cadence": None,
        "active_experiment_contract_path": None,
    }
    state.update(overrides)
    return state


def _write_state(workspace, state):
    (workspace / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _read_output(workspace):
    return (workspace / "phase7-status.md").read_text(encoding="utf-8")


def _run_and_catch(workspace_path):
    """Invoke main() under SystemExit guard so we can assert on exit codes."""
    try:
        _mod.main([str(workspace_path)])
    except SystemExit as exc:
        return exc.code
    return 0


class RenderPhase7StatusTests(unittest.TestCase):
    # ------- T1-T4: workspace + state.json basic guards -------

    def test_T1_workspace_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "does-not-exist"
            code = _run_and_catch(ws)
            self.assertEqual(code, 2)

    def test_T2_state_json_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "state.json").write_text("{not json", encoding="utf-8")
            code = _run_and_catch(ws)
            self.assertEqual(code, 3)

    def test_T3_workspace_path_is_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "file.txt"
            file_path.write_text("not a dir", encoding="utf-8")
            code = _run_and_catch(file_path)
            self.assertEqual(code, 2)

    def test_T4_state_missing_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Truncated/legacy: missing `phases` and `gates`
            (ws / "state.json").write_text(
                json.dumps({"schema_version": 4, "skill_name": "legacy-skill"}),
                encoding="utf-8",
            )
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("# Phase 7 Status - legacy-skill", body)
            self.assertIn("truncated/legacy", body)

    # ------- T5-T6: minimal / pre-eval rendering -------

    def test_T5_no_active_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _write_state(ws, _minimal_state())
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("No active Phase 7 run", body)

    def test_T6_mid_eval_no_eval_ref_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            iteration_state = {
                "run_id": "run_X",
                "run_path": "runs/run_X/",
                "experiment_id": 0,
                "active_phase": "eval",
                "phase_status": "running",
                "last_eval_status": None,
                "last_eval_results_ref": None,
                "last_mutation_status": None,
                "last_mutation_results_ref": None,
                "next_action": "phase7_baseline_eval",
            }
            state = _minimal_state(
                current_run_id="run_X",
                current_run_path="runs/run_X/",
                current_experiment=0,
                iteration_state=iteration_state,
            )
            _write_state(ws, state)
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Baseline in progress (no eval results yet)", body)

    # ------- T7-T9: in-flight verdict rendering -------

    def _make_inflight_workspace(self, tmp, *, proposed, summary, combined=0.787):
        ws = Path(tmp)
        run_dir = ws / "runs" / "run_Y" / "iteration_001"
        run_dir.mkdir(parents=True)
        eval_results = {
            "decision_breakdown": {
                "combined_score": combined,
                "combined_score_pct": combined * 100,
                "threshold": 0.8,
                "proposed_decision": proposed,
            },
            "decision_explanation": {"summary": summary},
        }
        (run_dir / "eval_results.json").write_text(
            json.dumps(eval_results), encoding="utf-8"
        )
        iteration_state = {
            "run_id": "run_Y",
            "run_path": "runs/run_Y/",
            "experiment_id": 1,
            "active_phase": "mutate",
            "phase_status": "ready",
            "last_eval_status": "completed",
            "last_eval_results_ref": "runs/run_Y/iteration_001/eval_results.json",
            "last_mutation_status": "completed",
            "last_mutation_results_ref": "runs/run_Y/iteration_001/mutation.md",
            "next_action": "phase7_mutation_analysis",
        }
        state = _minimal_state(
            current_run_id="run_Y",
            current_run_path="runs/run_Y/",
            current_experiment=1,
            iteration_state=iteration_state,
        )
        _write_state(ws, state)
        return ws

    def test_T7_full_decision_breakdown_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = "E2 withheld weight; E1 added; below threshold."
            ws = self._make_inflight_workspace(
                tmp, proposed="discard", summary=summary
            )
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Proposed:", body)
            self.assertIn("discard", body)
            self.assertIn(summary, body)  # quoted verbatim

    def test_T8_post_discard_in_flight(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_inflight_workspace(
                tmp, proposed="discard", summary="Too low."
            )
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Proposed:", body)
            self.assertIn("discard", body)
            self.assertIn("awaiting user accept/override", body)

    def test_T9_post_keep_in_flight(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_inflight_workspace(
                tmp, proposed="keep", summary="Above threshold."
            )
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Proposed:", body)
            self.assertIn("keep", body)
            self.assertIn("awaiting user accept/override", body)

    # ------- T10-T11: finalized verdict + override -------

    def _make_finalized_workspace(
        self, tmp, *, proposed, status, summary="Finalized."
    ):
        ws = Path(tmp)
        run_dir = ws / "runs" / "run_Z" / "iteration_001"
        run_dir.mkdir(parents=True)
        eval_results = {
            "decision_breakdown": {
                "combined_score": 0.79,
                "combined_score_pct": 79.0,
                "threshold": 0.8,
                "proposed_decision": proposed,
            },
            "decision_explanation": {"summary": summary},
        }
        (run_dir / "eval_results.json").write_text(
            json.dumps(eval_results), encoding="utf-8"
        )
        iteration_state = {
            "run_id": "run_Z",
            "run_path": "runs/run_Z/",
            "experiment_id": 2,
            "active_phase": "mutate",
            "phase_status": "ready",
            "last_eval_results_ref": "runs/run_Z/iteration_001/eval_results.json",
            "last_mutation_status": "completed",
            "last_mutation_results_ref": None,
            "next_action": "phase7_mutation_analysis",
        }
        state = _minimal_state(
            current_run_id="run_Z",
            current_run_path="runs/run_Z/",
            current_experiment=2,
            iteration_state=iteration_state,
        )
        _write_state(ws, state)
        results = {
            "skill_name": "test-skill",
            "experiments": [
                {
                    "id": 2,
                    "status": status,
                    "score": 79,
                    "max_score": 100,
                    "pass_rate": 79.0,
                }
            ],
        }
        (ws / "results.json").write_text(json.dumps(results), encoding="utf-8")
        return ws

    def test_T10_finalized_match_no_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_finalized_workspace(
                tmp, proposed="discard", status="discard"
            )
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Final decision:", body)
            self.assertIn("discard", body)
            self.assertNotIn("user overrode", body)

    def test_T11_finalized_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_finalized_workspace(
                tmp, proposed="discard", status="keep"
            )
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Final decision:", body)
            self.assertIn("keep", body)
            self.assertIn("user overrode agent's proposed `discard` to `keep`", body)

    # ------- T12-T13: results.json edge cases -------

    def test_T12_results_json_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_inflight_workspace(
                tmp, proposed="discard", summary="No results yet."
            )
            # results.json deliberately not written
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Proposed:", body)
            self.assertIn("results.json missing", body)

    def test_T13_results_json_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_inflight_workspace(
                tmp, proposed="discard", summary="Bad results."
            )
            (ws / "results.json").write_text("{not json", encoding="utf-8")
            code = _run_and_catch(ws)
            self.assertEqual(code, 3)

    # ------- T14-T15: degraded / large-input edge cases -------

    def test_T14_multi_judge_disagreement(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            run_dir = ws / "runs" / "run_D" / "iteration_001"
            run_dir.mkdir(parents=True)
            eval_results = {
                "decision_breakdown": {
                    "combined_score": None,
                    "proposed_decision": "disagreement",
                },
                "decision_explanation": {"summary": ""},
            }
            (run_dir / "eval_results.json").write_text(
                json.dumps(eval_results), encoding="utf-8"
            )
            iteration_state = {
                "run_id": "run_D",
                "run_path": "runs/run_D/",
                "experiment_id": 1,
                "active_phase": "mutate",
                "phase_status": "ready",
                "last_eval_results_ref": "runs/run_D/iteration_001/eval_results.json",
                "last_mutation_status": None,
                "last_mutation_results_ref": None,
                "next_action": "phase7_mutation_analysis",
            }
            state = _minimal_state(
                current_run_id="run_D",
                current_run_path="runs/run_D/",
                current_experiment=1,
                iteration_state=iteration_state,
            )
            _write_state(ws, state)
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Multi-judge disagreement", body)

    def test_T15_truncate_oversized_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            long_summary = "x" * 500
            ws = self._make_inflight_workspace(
                tmp, proposed="discard", summary=long_summary
            )
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            # full long summary must NOT appear; truncated form must
            self.assertNotIn("x" * 500, body)
            self.assertIn("…", body)
            self.assertIn("x" * 280, body)

    # ------- T16-T18: active contract path (JSON) -------

    def _make_workspace_with_contract(self, tmp, contract_payload):
        ws = Path(tmp)
        run_dir = ws / "runs" / "run_C"
        run_dir.mkdir(parents=True)
        if contract_payload is not None:
            (run_dir / "experiment-contract.json").write_text(
                contract_payload, encoding="utf-8"
            )
        iteration_state = {
            "run_id": "run_C",
            "run_path": "runs/run_C/",
            "experiment_id": 0,
            "active_phase": "eval",
            "phase_status": "running",
            "last_eval_results_ref": None,
            "last_mutation_status": None,
            "last_mutation_results_ref": None,
            "next_action": "phase7_baseline_eval",
        }
        state = _minimal_state(
            current_run_id="run_C",
            current_run_path="runs/run_C/",
            current_experiment=0,
            iteration_state=iteration_state,
            active_experiment_contract_path="runs/run_C/experiment-contract.json",
        )
        _write_state(ws, state)
        return ws

    def test_T16_contract_json_renders(self):
        contract = {
            "run_id": "run_C",
            "adapter_id": "search_retrieval_v1",
            "objective": "Improve NDCG@5 without regressing boundary checks.",
            "primary_metric": {
                "metric_name": "ndcg_at_5",
                "threshold_pass": 0.65,
            },
            "thresholds": {"combined_score": 0.8},
            "hard_fail_dimensions": [
                "primary_metric_below_threshold",
                "holdout_leakage",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_workspace_with_contract(tmp, json.dumps(contract))
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Improve NDCG@5", body)
            self.assertIn("ndcg_at_5", body)
            self.assertIn("0.65", body)
            self.assertIn("0.8", body)
            self.assertIn("primary_metric_below_threshold", body)
            self.assertIn("holdout_leakage", body)

    def test_T17_contract_json_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_workspace_with_contract(tmp, "{not json")
            code = _run_and_catch(ws)
            self.assertEqual(code, 3)

    def test_T18_contract_missing_objective(self):
        contract = {
            "run_id": "run_C",
            "primary_metric": {
                "metric_name": "ndcg_at_5",
                "threshold_pass": 0.65,
            },
            "thresholds": {"combined_score": 0.8},
        }
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_workspace_with_contract(tmp, json.dumps(contract))
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)  # non-fatal
            body = _read_output(ws)
            self.assertIn("Active contract incomplete: missing objective", body)

    # ------- T19-T20: markdown contract fallback -------

    def _make_workspace_with_inferred_contract(self, tmp, contract_md):
        ws = Path(tmp)
        contract_dir = ws / "contract"
        contract_dir.mkdir(parents=True)
        if contract_md is not None:
            (contract_dir / "inferred-contract.md").write_text(
                contract_md, encoding="utf-8"
            )
        iteration_state = {
            "run_id": "run_M",
            "run_path": "runs/run_M/",
            "experiment_id": 0,
            "active_phase": "eval",
            "phase_status": "running",
            "last_eval_results_ref": None,
            "last_mutation_status": None,
            "last_mutation_results_ref": None,
            "next_action": "phase7_baseline_eval",
        }
        state = _minimal_state(
            current_run_id="run_M",
            current_run_path="runs/run_M/",
            current_experiment=0,
            iteration_state=iteration_state,
            active_experiment_contract_path=None,
        )
        _write_state(ws, state)
        return ws

    def test_T19_inferred_contract_renders(self):
        md = (
            "# Inferred Contract\n\n"
            "## Success Criterion\n"
            "Output must include a Gotchas section.\n"
            "Output must list at least 3 concrete warnings.\n\n"
            "## Other section\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_workspace_with_inferred_contract(tmp, md)
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("Output must include a Gotchas section.", body)
            self.assertIn("Output must list at least 3 concrete warnings.", body)

    def test_T20_inferred_contract_missing_section(self):
        md = "# Inferred Contract\n\n## Some Other Heading\n\nbody\n"
        with tempfile.TemporaryDirectory() as tmp:
            ws = self._make_workspace_with_inferred_contract(tmp, md)
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("missing Success Criterion section", body)

    # ------- T21-T22: path escape -------

    def test_T21_eval_ref_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            iteration_state = {
                "run_id": "run_E",
                "run_path": "runs/run_E/",
                "experiment_id": 1,
                "active_phase": "mutate",
                "phase_status": "ready",
                "last_eval_results_ref": "/etc/passwd",
                "last_mutation_status": None,
                "last_mutation_results_ref": None,
                "next_action": "phase7_mutation_analysis",
            }
            state = _minimal_state(
                current_run_id="run_E",
                current_run_path="runs/run_E/",
                current_experiment=1,
                iteration_state=iteration_state,
            )
            _write_state(ws, state)
            code = _run_and_catch(ws)
            self.assertEqual(code, 5)

    def test_T22_eval_ref_dotdot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            iteration_state = {
                "run_id": "run_F",
                "run_path": "runs/run_F/",
                "experiment_id": 1,
                "active_phase": "mutate",
                "phase_status": "ready",
                "last_eval_results_ref": "../../etc/passwd",
                "last_mutation_status": None,
                "last_mutation_results_ref": None,
                "next_action": "phase7_mutation_analysis",
            }
            state = _minimal_state(
                current_run_id="run_F",
                current_run_path="runs/run_F/",
                current_experiment=1,
                iteration_state=iteration_state,
            )
            _write_state(ws, state)
            code = _run_and_catch(ws)
            self.assertEqual(code, 5)

    # ------- T23: stale mismatch -------

    def test_T23_stale_mismatch_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            iteration_state = {
                "run_id": "run_OLD",
                "run_path": "runs/run_OLD/",  # different from current_run_path
                "experiment_id": 1,
                "active_phase": "mutate",
                "phase_status": "ready",
                "last_eval_results_ref": None,
                "last_mutation_status": None,
                "last_mutation_results_ref": None,
                "next_action": "phase7_mutation_analysis",
            }
            state = _minimal_state(
                current_run_id="run_NEW",
                current_run_path="runs/run_NEW/",
                current_experiment=1,
                iteration_state=iteration_state,
            )
            _write_state(ws, state)
            code = _run_and_catch(ws)
            self.assertEqual(code, 0)
            body = _read_output(ws)
            self.assertIn("STALE-MISMATCH", body)
            self.assertIn("runs/run_NEW/", body)
            self.assertIn("runs/run_OLD/", body)

    # ------- T24: write OSError -------

    def test_T24_write_oserror_exits_4(self):
        # Patch Path.write_text on the output file path so we can simulate
        # OSError without messing with real file permissions (which behave
        # differently across platforms / when running as root).
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _write_state(ws, _minimal_state())
            real_write_text = Path.write_text

            def fake_write_text(self, *args, **kwargs):
                if self.name == "phase7-status.md":
                    raise OSError("Read-only file system")
                return real_write_text(self, *args, **kwargs)

            with mock.patch.object(Path, "write_text", new=fake_write_text):
                code = _run_and_catch(ws)
            self.assertEqual(code, 4)


if __name__ == "__main__":
    unittest.main()
