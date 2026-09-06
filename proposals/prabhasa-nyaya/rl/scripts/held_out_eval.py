"""Independent held-out evaluation of an rl_candidate.

Deliberately does NOT import reward_function.py. The training reward and the
acceptance metric must be two different pieces of code reading the same
graph, or an inflated reward score during RL tells you nothing about
whether the objective was actually met (Goodhart's law applied to this
specific reward). Where the two implement a similar-sounding check (e.g.
"is this citation grounded"), they are written independently here and use
stricter tie-breaking so they are not the same test wearing two hats.

Usage (paths are placeholders -- point them at real artifacts):

    uv run python proposals/prabhasa-nyaya/rl/scripts/held_out_eval.py \\
        --held-out-corpus path/to/held_out.jsonl \\
        --candidate path/to/rl_candidate \\
        --baseline path/to/finetune_candidate \\
        --generate-fn my_module:generate

`--generate-fn` names a `module:function` callable with signature
`(model_ref: str, question: str, graph: dict) -> str` returning the model's
raw structured output text. This script ships without a real model runner
since none is named in this task's scope; wire it to whatever serves
finetune_candidate / rl_candidate.
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from data_contracts import GraphEdge, GraphNode, NyayaGraph, PreparedExample

ABSTAIN_MARKERS = ("i don't know", "i do not know", "cannot determine", "insufficient basis")


@dataclass
class EvalRow:
    example_id: str
    citation_precision: float
    citation_recall: float
    trace_faithful: bool
    abstained_correctly: bool | None  # None when not applicable
    hallucinated: bool


def load_held_out(path: Path) -> list[PreparedExample]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            graph = NyayaGraph(
                nodes=[GraphNode(**n) for n in obj["graph"]["nodes"]],
                edges=[GraphEdge(**e) for e in obj["graph"]["edges"]],
            )
            rows.append(
                PreparedExample(
                    id=obj["id"],
                    question=obj["question"],
                    graph=graph,
                    gold_citations=obj.get("gold_citations", []),
                    gold_answer=obj.get("gold_answer"),
                    answerable=obj["answerable"],
                )
            )
    return rows


def extract_citations(raw_text: str) -> list[str]:
    """Independent extraction: any bracketed [ID] token, not the training
    output schema's <citation> tags -- so a model that games the training
    parser's exact tag format still gets scored on substance here."""
    return re.findall(r"\[([^\[\]]+)\]", raw_text)


def is_abstention(raw_text: str) -> bool:
    lowered = raw_text.lower()
    return any(marker in lowered for marker in ABSTAIN_MARKERS)


def score_row(example: PreparedExample, raw_text: str) -> EvalRow:
    cited = extract_citations(raw_text)
    known = example.graph.node_ids()
    grounded = [c for c in cited if c in known]
    hallucinated = len(grounded) < len(cited)

    gold = set(example.gold_citations)
    precision = (len(set(grounded) & gold) / len(grounded)) if grounded else 0.0
    recall = (len(set(grounded) & gold) / len(gold)) if gold else 0.0

    # Trace faithfulness here is a coarse proxy independent of the training
    # trace parser: every cited, grounded node must appear in a sentence
    # that also mentions a node it is graph-adjacent to. This deliberately
    # does not require the model's own self-reported trace tags.
    adjacency: dict[str, set[str]] = {}
    for e in example.graph.edges:
        adjacency.setdefault(e.src, set()).add(e.dst)
        adjacency.setdefault(e.dst, set()).add(e.src)
    trace_faithful = True
    for node_id in grounded:
        neighbors = adjacency.get(node_id, set())
        if neighbors and not any(n in raw_text for n in neighbors):
            trace_faithful = False
            break

    abstained = is_abstention(raw_text)
    abstained_correctly = (not example.answerable) == abstained if not example.answerable or abstained else None

    return EvalRow(
        example_id=example.id,
        citation_precision=precision,
        citation_recall=recall,
        trace_faithful=trace_faithful,
        abstained_correctly=abstained_correctly,
        hallucinated=hallucinated,
    )


def summarize(rows: list[EvalRow]) -> dict:
    n = len(rows)
    if n == 0:
        return {}
    unanswerable = [r for r in rows if r.abstained_correctly is not None]
    return {
        "n": n,
        "mean_citation_precision": sum(r.citation_precision for r in rows) / n,
        "mean_citation_recall": sum(r.citation_recall for r in rows) / n,
        "trace_faithful_rate": sum(1 for r in rows if r.trace_faithful) / n,
        "hallucination_rate": sum(1 for r in rows if r.hallucinated) / n,
        "abstention_accuracy_on_unanswerable": (
            sum(1 for r in unanswerable if r.abstained_correctly) / len(unanswerable)
            if unanswerable
            else None
        ),
    }


def resolve_generate_fn(spec: str):
    module_name, func_name = spec.split(":")
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


def run(model_ref: str, examples: list[PreparedExample], generate_fn) -> list[EvalRow]:
    rows = []
    for ex in examples:
        graph_payload = {
            "nodes": [n.__dict__ for n in ex.graph.nodes],
            "edges": [e.__dict__ for e in ex.graph.edges],
        }
        raw_text = generate_fn(model_ref, ex.question, graph_payload)
        rows.append(score_row(ex, raw_text))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--held-out-corpus", required=True, type=Path)
    parser.add_argument("--candidate", required=True, help="model ref for rl_candidate")
    parser.add_argument("--baseline", required=True, help="model ref for finetune_candidate (pre-RL)")
    parser.add_argument("--generate-fn", required=True, help="module:function that runs the model")
    args = parser.parse_args()

    examples = load_held_out(args.held_out_corpus)
    generate_fn = resolve_generate_fn(args.generate_fn)

    candidate_rows = run(args.candidate, examples, generate_fn)
    baseline_rows = run(args.baseline, examples, generate_fn)

    result = {
        "candidate": summarize(candidate_rows),
        "baseline": summarize(baseline_rows),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
