import importlib.util
import json
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "build_search_silver",
    SCRIPTS_DIR / "build-search-silver.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["build_search_silver"] = _mod
_spec.loader.exec_module(_mod)


def test_build_rows_generates_positive_and_hard_negative():
    corpus = [
        {
            "doc_id": "adapter_resolution",
            "title": "Adapter Resolution Rules",
            "text": "# Adapter Resolution Rules\nMissing adapter assets must stop the run.",
        },
        {
            "doc_id": "domain_eval_config",
            "title": "Domain Eval Config",
            "text": "The domain eval config names the metric and golden set path.",
        },
        {
            "doc_id": "unrelated",
            "title": "Unrelated Install Notes",
            "text": "Scratch installs validate package shape.",
        },
    ]

    rows = _mod.build_silver_rows(corpus, queries_per_doc=1, negatives_per_query=1)

    positives = [row for row in rows if row["grade"] == 3]
    negatives = [row for row in rows if row["grade"] == 0]
    assert positives
    assert negatives
    assert {"query", "doc_id", "grade", "metadata"} <= set(rows[0])
    assert all(row["metadata"]["review_status"] == "silver" for row in rows)
    assert any(row["metadata"]["source"] == "synthetic_doc_to_query" for row in positives)
    assert any(row["metadata"]["source"] == "synthetic_lexical_hard_negative" for row in negatives)


def test_rows_use_stable_query_family_ids():
    corpus = [
        {
            "doc_id": "trust_gate",
            "title": "Trust Gate",
            "text": "Trust gate outcomes are promote, review_required, and block.",
        },
        {
            "doc_id": "holdout",
            "title": "Holdout Evaluation",
            "text": "Holdout evaluation runs only at Session Close.",
        },
    ]

    rows = _mod.build_silver_rows(corpus, queries_per_doc=2, negatives_per_query=1)
    family_ids = {row["metadata"]["query_family_id"] for row in rows}

    assert family_ids
    assert all(family_id.startswith("synthetic:") for family_id in family_ids)
    for row in rows:
        assert row["metadata"]["source_doc_id"] in {"trust_gate", "holdout"}
        assert row["metadata"]["split_hint"] == "split_by_query_family"


def test_cli_writes_jsonl_and_report(tmp_path):
    corpus_path = tmp_path / "corpus.jsonl"
    output_path = tmp_path / "golden-set.jsonl"
    report_path = tmp_path / "report.md"
    corpus_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "doc_id": "search_adapter",
                        "title": "Search Adapter",
                        "text": "Search adapter scores ranked doc_id output with NDCG@5.",
                    }
                ),
                json.dumps(
                    {
                        "doc_id": "phase7",
                        "title": "Phase 7",
                        "text": "Phase 7 records evidence and decision breakdowns.",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _mod.main(
        [
            "--corpus",
            str(corpus_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--queries-per-doc",
            "1",
            "--negatives-per-query",
            "1",
        ]
    )

    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    report = report_path.read_text(encoding="utf-8")

    assert len(rows) == 4
    assert all(row["metadata"]["metric_target"] == "search_retrieval_v1" for row in rows)
    assert "Synthetic Search Silver Set Report" in report
    assert "Human review next step" in report
    assert "Hard-negative rows: 2" in report
