"""Offline check for the step's stated success criterion:

    "Check retrieved source identifiers resolve and cited passages support
    answers on held-out queries."

This script only reads local files and prints/writes a report; it does not
write to a ledger, research/, gates/, or pravrudhi_kernel/, and nothing it
prints should be read as a measured result — there is no real prepared_corpus
or gold set behind it yet in this worktree.

Usage:
    uv run python eval_retrieval.py \
        --retrieval-candidate /tmp/retrieval_candidate.json \
        --prepared-corpus prepared_corpus.json \
        --gold held_out_queries_with_gold.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


def lexical_support_proxy(expected_answer: str, cited_text: str) -> bool:
    """Cheap stand-in for a real entailment/NLI check or human review.

    Flags whether the cited passage shares enough vocabulary with the
    expected answer to plausibly support it. This is NOT a substitute for
    expert legal review or a trained entailment model — see README.md,
    "What would count as success", point 2.
    """
    expected_kw = _keywords(expected_answer)
    if not expected_kw:
        return False
    cited_kw = _keywords(cited_text)
    overlap = expected_kw & cited_kw
    return len(overlap) / len(expected_kw) >= 0.5


def evaluate(retrieval_candidates: list[dict], corpus_registry: set[str], gold: list[dict]) -> dict:
    gold_by_query = {item["query"]: item for item in gold}

    total = 0
    resolved_ok = 0
    supported_ok = 0
    abstain_correct = 0
    abstain_expected = 0
    unresolved: list[str] = []
    unsupported: list[str] = []

    for candidate in retrieval_candidates:
        query = candidate["query"]
        gold_item = gold_by_query.get(query)
        if gold_item is None:
            continue
        total += 1

        if gold_item.get("unanswerable", False):
            abstain_expected += 1
            if candidate["abstain"]:
                abstain_correct += 1
            continue

        if candidate["abstain"]:
            # A query with a known answer that retrieval abstained on is
            # neither a resolution nor a support failure by itself, but it
            # is a miss worth surfacing separately from both counters.
            continue

        query_resolved = True
        query_supported = False
        expected_answer = gold_item.get("expected_answer", "")

        for hit in candidate["hits"]:
            if hit["source_id"] not in corpus_registry:
                query_resolved = False
                unresolved.append(f"{query} -> {hit['source_id']}")
            if lexical_support_proxy(expected_answer, hit["text"]):
                query_supported = True

        if query_resolved:
            resolved_ok += 1
        if query_supported:
            supported_ok += 1
        else:
            unsupported.append(query)

    return {
        "total_scored_queries": total,
        "resolved_ok": resolved_ok,
        "supported_ok": supported_ok,
        "unresolved_examples": unresolved,
        "unsupported_examples": unsupported,
        "abstain_expected": abstain_expected,
        "abstain_correct": abstain_correct,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-candidate", required=True)
    parser.add_argument("--prepared-corpus", required=True)
    parser.add_argument("--gold", required=True)
    args = parser.parse_args()

    retrieval_candidates = json.loads(Path(args.retrieval_candidate).read_text(encoding="utf-8"))
    corpus_payload = json.loads(Path(args.prepared_corpus).read_text(encoding="utf-8"))
    corpus_registry = set(corpus_payload["citation_registry"])
    gold = json.loads(Path(args.gold).read_text(encoding="utf-8"))

    report = evaluate(retrieval_candidates, corpus_registry, gold)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
