"""Audits reward_function.compute_reward against the stated intent.

This is NOT a model evaluation. It is a set of hand-built probe cases that
pin down the *ordering* the reward function must respect for the objective
("cites what it relied on, says it does not know rather than inventing a
citation, and a wrong answer must be traceable to the inference step that
produced it") to actually be what gets optimized. Run this whenever the
reward function or its weights change, before trusting any training curve
that uses it.

    uv run python proposals/prabhasa-nyaya/rl/scripts/audit_reward.py

Exits non-zero if any probe fails.
"""
from __future__ import annotations

import sys

from data_contracts import GraphEdge, GraphNode, ModelOutput, NyayaGraph, PreparedExample
from reward_function import compute_reward


def _graph() -> NyayaGraph:
    return NyayaGraph(
        nodes=[
            GraphNode(id="fact:1", type="fact", text="A struck B without provocation."),
            GraphNode(id="IPC:319", type="statute", text="Hurt."),
            GraphNode(id="IPC:320", type="statute", text="Grievous hurt."),
            GraphNode(id="prec:Xv Y", type="precedent", text="X v. Y on intent."),
        ],
        edges=[
            GraphEdge(src="fact:1", dst="IPC:319", relation="applies_to"),
            GraphEdge(src="IPC:319", dst="prec:Xv Y", relation="interpreted_by"),
        ],
    )


def _answerable_example() -> PreparedExample:
    return PreparedExample(
        id="q1",
        question="What offense, if any, does A's act constitute?",
        graph=_graph(),
        gold_citations=["IPC:319"],
        gold_answer="Hurt under IPC 319.",
        answerable=True,
    )


def _unanswerable_example() -> PreparedExample:
    g = _graph()
    # No node/edge chain actually settles the question -- graph is too thin.
    return PreparedExample(
        id="q2",
        question="Does the doctrine of frustration apply here?",
        graph=NyayaGraph(nodes=g.nodes[:1], edges=[]),
        gold_citations=[],
        gold_answer=None,
        answerable=False,
    )


def _output(
    citations=None, trace_nodes=None, trace_edges=None, abstained=False
) -> ModelOutput:
    return ModelOutput(
        raw_text="",
        answer=None,
        citations=citations or [],
        trace_node_ids=trace_nodes or [],
        trace_edges=trace_edges or [],
        abstained=abstained,
    )


def build_probes() -> list[tuple[str, float, float]]:
    """Each probe is (description, reward_of_desired_behavior, reward_of_undesired_behavior).

    A passing audit requires desired > undesired for every probe.
    """
    ans = _answerable_example()
    unans = _unanswerable_example()

    grounded_traced = _output(
        citations=["IPC:319"], trace_nodes=["fact:1", "IPC:319"], trace_edges=[("fact:1", "IPC:319")]
    )
    abstain = _output(abstained=True)
    hallucinated = _output(citations=["IPC:999-does-not-exist"], trace_nodes=["IPC:999-does-not-exist"])
    grounded_wrong_traced = _output(
        citations=["IPC:320"], trace_nodes=["fact:1", "IPC:320"], trace_edges=[("fact:1", "IPC:319")]
    )
    fabricated_edge = _output(
        citations=["IPC:319"], trace_nodes=["fact:1", "IPC:319"], trace_edges=[("IPC:319", "fact:1")]
    )
    cited_no_trace = _output(citations=["IPC:319"])

    return [
        (
            "grounded+traced correct beats abstention on an answerable question",
            compute_reward(grounded_traced, ans),
            compute_reward(abstain, ans),
        ),
        (
            "abstention beats a hallucinated citation on an unanswerable question",
            compute_reward(abstain, unans),
            compute_reward(hallucinated, unans),
        ),
        (
            "a grounded-but-wrong citation beats a hallucinated one",
            compute_reward(grounded_wrong_traced, ans),
            compute_reward(hallucinated, ans),
        ),
        (
            "a valid trace beats a fabricated edge over the same real nodes",
            compute_reward(grounded_traced, ans),
            compute_reward(fabricated_edge, ans),
        ),
        (
            "a real citation with a valid trace beats the same citation with no trace",
            compute_reward(grounded_traced, ans),
            compute_reward(cited_no_trace, ans),
        ),
    ]


def main() -> int:
    probes = build_probes()
    failed = 0
    print(f"{'PROBE':<75} {'desired':>8} {'undesired':>10}  result")
    for name, desired, undesired in probes:
        ok = desired > undesired
        failed += 0 if ok else 1
        print(f"{name:<75} {desired:8.3f} {undesired:10.3f}  {'PASS' if ok else 'FAIL'}")

    if failed:
        print(f"\n{failed} probe(s) FAILED -- reward function does not match stated intent.")
        return 1
    print(f"\nAll {len(probes)} probes passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
