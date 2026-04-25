import importlib.util
import json
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "eval_search_metric",
    SCRIPTS_DIR / "eval-search-metric.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["eval_search_metric"] = _mod
_spec.loader.exec_module(_mod)

_silver_spec = importlib.util.spec_from_file_location(
    "build_search_silver_for_metric_test",
    SCRIPTS_DIR / "build-search-silver.py",
)
_silver_mod = importlib.util.module_from_spec(_silver_spec)
sys.modules["build_search_silver_for_metric_test"] = _silver_mod
_silver_spec.loader.exec_module(_silver_mod)


def test_ndcg_at_k_scores_perfect_and_misordered_rankings():
    judgments = {
        "adapter assets": {
            "adapter_resolution": 3,
            "domain_eval_config": 2,
            "unrelated": 0,
        }
    }

    perfect = _mod.score_query(
        "adapter assets",
        ["adapter_resolution", "domain_eval_config", "unrelated"],
        judgments["adapter assets"],
        k=5,
    )
    misordered = _mod.score_query(
        "adapter assets",
        ["unrelated", "domain_eval_config", "adapter_resolution"],
        judgments["adapter assets"],
        k=5,
    )

    assert perfect["ndcg_at_5"] == 1.0
    assert 0 < misordered["ndcg_at_5"] < 1.0
    assert perfect["recall_at_5"] == 1.0


def test_score_predictions_emits_evidence_and_false_pass_status():
    gold_rows = [
        {"query": "adapter assets", "doc_id": "adapter_resolution", "grade": 3, "metadata": {}},
        {"query": "adapter assets", "doc_id": "domain_eval_config", "grade": 2, "metadata": {}},
        {"query": "phase 7", "doc_id": "phase7", "grade": 3, "metadata": {}},
    ]
    predictions = [
        {
            "query": "adapter assets",
            "results": [{"doc_id": "domain_eval_config"}, {"doc_id": "adapter_resolution"}],
            "judge_diagnostic": "pass",
        },
        {
            "query": "phase 7",
            "results": [{"doc_id": "unrelated"}],
            "judge_diagnostic": "pass",
        },
    ]

    result = _mod.score_predictions(gold_rows, predictions, k=5, threshold_pass=0.65)

    assert result["metric_name"] == "ndcg_at_5"
    assert result["query_count"] == 2
    assert result["status"] == "fail"
    assert result["false_pass_count"] == 1
    assert result["evidence"][0]["kind"] == "metric"
    assert result["per_query"][1]["trust_diagnostic"] == "judge_pass_metric_fail"


def test_cli_writes_json_report(tmp_path):
    gold_path = tmp_path / "golden-set.jsonl"
    predictions_path = tmp_path / "predictions.jsonl"
    output_path = tmp_path / "metric-results.json"
    report_path = tmp_path / "metric-report.md"

    gold_path.write_text(
        "\n".join(
            [
                json.dumps({"query": "trust gate", "doc_id": "trust_gate", "grade": 3}),
                json.dumps({"query": "trust gate", "doc_id": "holdout", "grade": 2}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    predictions_path.write_text(
        json.dumps({"query": "trust gate", "doc_ids": ["trust_gate", "holdout"]}) + "\n",
        encoding="utf-8",
    )

    _mod.main(
        [
            "--gold",
            str(gold_path),
            "--predictions",
            str(predictions_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")

    assert payload["status"] == "pass"
    assert payload["continuous_score"] == 1.0
    assert "Search Metric Report" in report
    assert "NDCG@5" in report


def test_silver_builder_rows_score_with_metric_runner():
    corpus = [
        {
            "doc_id": "search_adapter",
            "title": "Search Adapter",
            "text": "Search adapter scores ranked doc_id output with NDCG@5.",
        },
        {
            "doc_id": "trust_gate",
            "title": "Trust Gate",
            "text": "Trust gate uses holdout evidence for promotion.",
        },
    ]
    silver_rows = _silver_mod.build_silver_rows(
        corpus,
        queries_per_doc=1,
        negatives_per_query=1,
    )
    predictions = []
    for query in sorted({row["query"] for row in silver_rows}):
        positive = next(row for row in silver_rows if row["query"] == query and row["grade"] == 3)
        predictions.append({"query": query, "doc_ids": [positive["doc_id"]]})

    result = _mod.score_predictions(silver_rows, predictions)

    assert result["status"] == "pass"
    assert result["query_count"] == 2
    assert result["continuous_score"] == 1.0
