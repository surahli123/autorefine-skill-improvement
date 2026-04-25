#!/usr/bin/env python3
"""
Build a synthetic silver set for AutoRefine search adapter dogfood.

Input corpus JSONL rows must contain:
  {"doc_id": "...", "text": "...", "title": "... optional", "metadata": {... optional}}

Output rows follow the minimum viable search adapter contract:
  {"query": "...", "doc_id": "...", "grade": 0..3, "metadata": {...}}

This script intentionally uses deterministic lexical heuristics instead of an
LLM call. Treat its output as silver data until a human reviews a holdout slice.
"""

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "should",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "with",
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL row: {exc}") from exc
            rows.append(normalize_corpus_row(row, str(path), lineno))
    return rows


def normalize_corpus_row(row: dict, filepath: str, lineno: int) -> dict:
    doc_id = row.get("doc_id")
    text = row.get("text")
    if not isinstance(doc_id, str) or not doc_id.strip():
        raise ValueError(f"{filepath}:{lineno}: row requires non-empty string doc_id")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{filepath}:{lineno}: row requires non-empty string text")

    title = row.get("title")
    metadata = row.get("metadata", {})
    if title is not None and not isinstance(title, str):
        raise ValueError(f"{filepath}:{lineno}: title must be a string when present")
    if not isinstance(metadata, dict):
        raise ValueError(f"{filepath}:{lineno}: metadata must be an object when present")

    return {
        "doc_id": doc_id.strip(),
        "title": title.strip() if isinstance(title, str) else "",
        "text": text.strip(),
        "metadata": metadata,
    }


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if token.lower() not in STOPWORDS and len(token) > 1
    ]


def extract_headings(text: str) -> list[str]:
    headings = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def extract_key_sentences(text: str, limit: int = 3) -> list[str]:
    clean_text = re.sub(r"\s+", " ", text.replace("#", " ")).strip()
    sentences = [s.strip() for s in SENTENCE_RE.split(clean_text) if s.strip()]
    scored = sorted(
        sentences,
        key=lambda sentence: (len(set(tokenize(sentence))), len(sentence)),
        reverse=True,
    )
    return scored[:limit]


def slug(value: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return raw[:80] or "query"


def stable_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return digest


def query_specs_for_doc(doc: dict, limit: int) -> list[dict]:
    candidates = []
    title = doc.get("title") or ""
    headings = extract_headings(doc["text"])
    sentences = extract_key_sentences(doc["text"])

    if title:
        candidates.append(
            {
                "query": f"How should I use {title}?",
                "query_type": "direct_lookup",
                "rationale": f"Generated from document title: {title}",
            }
        )

    for heading in headings:
        candidates.append(
            {
                "query": f"What does {heading} mean in this workflow?",
                "query_type": "conceptual",
                "rationale": f"Generated from heading: {heading}",
            }
        )

    for sentence in sentences:
        terms = tokenize(sentence)[:6]
        if terms:
            candidates.append(
                {
                    "query": f"How do I handle {' '.join(terms)}?",
                    "query_type": "troubleshooting",
                    "rationale": f"Generated from salient sentence: {sentence[:160]}",
                }
            )

    deduped = []
    seen = set()
    for candidate in candidates:
        key = candidate["query"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped[:limit]


def lexical_score(query: str, doc: dict) -> float:
    query_terms = Counter(tokenize(query))
    doc_terms = Counter(tokenize(f"{doc.get('title', '')} {doc['text']}"))
    if not query_terms or not doc_terms:
        return 0.0

    score = 0.0
    doc_len = sum(doc_terms.values())
    for term, q_count in query_terms.items():
        if term in doc_terms:
            score += q_count * (1.0 + math.log1p(doc_terms[term])) / math.log1p(doc_len)
    return score


def select_hard_negatives(
    query: str,
    positive_doc_id: str,
    corpus: list[dict],
    limit: int,
) -> list[dict]:
    scored = []
    for doc in corpus:
        if doc["doc_id"] == positive_doc_id:
            continue
        score = lexical_score(query, doc)
        scored.append((score, doc))
    scored.sort(key=lambda item: (-item[0], item[1]["doc_id"]))
    return [doc for _, doc in scored[:limit]]


def build_silver_rows(
    corpus: list[dict],
    queries_per_doc: int = 3,
    negatives_per_query: int = 3,
) -> list[dict]:
    rows = []
    for doc in corpus:
        for spec in query_specs_for_doc(doc, queries_per_doc):
            query = spec["query"]
            family_id = (
                f"synthetic:{doc['doc_id']}:{slug(query)}:"
                f"{stable_id(doc['doc_id'], query)}"
            )
            shared_metadata = {
                "metric_target": "search_retrieval_v1",
                "source_doc_id": doc["doc_id"],
                "query_family_id": family_id,
                "query_type": spec["query_type"],
                "split_hint": "split_by_query_family",
                "review_status": "silver",
                "review_note": "Synthetic label; promote to gold only after review.",
            }
            rows.append(
                {
                    "query": query,
                    "doc_id": doc["doc_id"],
                    "grade": 3,
                    "metadata": {
                        **shared_metadata,
                        "source": "synthetic_doc_to_query",
                        "rationale": spec["rationale"],
                    },
                }
            )

            for negative in select_hard_negatives(
                query,
                doc["doc_id"],
                corpus,
                negatives_per_query,
            ):
                rows.append(
                    {
                        "query": query,
                        "doc_id": negative["doc_id"],
                        "grade": 0,
                        "metadata": {
                            **shared_metadata,
                            "source": "synthetic_lexical_hard_negative",
                            "negative_for_doc_id": doc["doc_id"],
                            "rationale": (
                                "Lexically similar candidate included as a hard "
                                "negative for pooled review."
                            ),
                        },
                    }
                )
    return rows


def write_jsonl(rows: Iterable[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def write_report(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    query_count = len({row["query"] for row in rows})
    doc_count = len({row["doc_id"] for row in rows})
    positive_count = sum(1 for row in rows if row["grade"] == 3)
    negative_count = sum(
        1
        for row in rows
        if row["metadata"].get("source") == "synthetic_lexical_hard_negative"
    )
    body = f"""# Synthetic Search Silver Set Report

Rows: {len(rows)}
Queries: {query_count}
Docs referenced: {doc_count}
Positive rows: {positive_count}
Hard-negative rows: {negative_count}

## Human review next step

Treat this file as silver data. Review complete query families before using a
holdout split. Promote reviewed rows by changing `metadata.review_status` from
`silver` to `gold_reviewed`.

## Split guidance

Split by `metadata.query_family_id`, not by individual rows, so the positive
and hard negatives for one synthetic query never cross dev and holdout.
"""
    path.write_text(body, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build synthetic silver query/doc relevance rows for search_retrieval_v1."
    )
    parser.add_argument("--corpus", required=True, help="Input corpus JSONL.")
    parser.add_argument("--output", required=True, help="Output golden-set JSONL path.")
    parser.add_argument("--report", help="Optional markdown report path.")
    parser.add_argument("--queries-per-doc", type=int, default=3)
    parser.add_argument("--negatives-per-query", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.queries_per_doc < 1:
        raise ValueError("--queries-per-doc must be >= 1")
    if args.negatives_per_query < 0:
        raise ValueError("--negatives-per-query must be >= 0")

    corpus = load_jsonl(Path(args.corpus))
    rows = build_silver_rows(
        corpus,
        queries_per_doc=args.queries_per_doc,
        negatives_per_query=args.negatives_per_query,
    )
    write_jsonl(rows, Path(args.output))
    if args.report:
        write_report(rows, Path(args.report))


if __name__ == "__main__":
    main()
