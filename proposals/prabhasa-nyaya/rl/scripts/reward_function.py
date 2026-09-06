"""Reward function for RL post-training of the Nyaya-graph legal assistant.

Design intent (mirrors the objective, not just task accuracy):
  1. Never reward a citation that is not grounded in the supplied graph/corpus
     slice for that question ("no invented citations").
  2. Reward answers whose citation is reachable by a *valid* path through the
     typed Nyaya graph, so a wrong answer can be traced to the inference step
     that produced it -- an ungrounded or disconnected trace is a defect
     regardless of whether the final text happens to be correct.
  3. Reward correct abstention ("I don't know") on questions the graph does
     not support, and penalize abstention less harshly than hallucination
     on questions that *are* supported.
  4. Only let task correctness contribute once grounding + trace validity
     have passed -- otherwise a lucky/hallucinated correct string could
     out-score a properly-traced answer.

This module is intentionally free of any dependency on pravrudhi_kernel or
the ledger. It is pure functions over the dataclasses in data_contracts.py
so it can be unit-audited (see audit_reward.py) independently of any model.
"""
from __future__ import annotations

from dataclasses import dataclass

from data_contracts import ModelOutput, NyayaGraph, PreparedExample


@dataclass(frozen=True)
class RewardWeights:
    grounding: float = 1.0
    trace_validity: float = 1.0
    abstention: float = 1.0
    task_correctness: float = 1.0
    hallucination_penalty: float = 2.0  # applied on top of, not instead of, the above


DEFAULT_WEIGHTS = RewardWeights()


def citation_grounding_score(output: ModelOutput, example: PreparedExample) -> float:
    """Fraction of cited ids that exist as nodes in the question's graph slice.

    A citation is "grounded" only if it names a node actually present in the
    graph handed to the model for this question -- not merely a real-sounding
    statute id. This is the hard anti-hallucination check.
    """
    if not output.citations:
        return 0.0
    known = example.graph.node_ids()
    grounded = [c for c in output.citations if c in known]
    return len(grounded) / len(output.citations)


def has_hallucinated_citation(output: ModelOutput, example: PreparedExample) -> bool:
    known = example.graph.node_ids()
    return any(c not in known for c in output.citations)


def trace_validity_score(output: ModelOutput, example: PreparedExample) -> float:
    """Checks the claimed inference trace is a real path in the typed graph.

    Every node the model claims to have used must exist, and every edge it
    claims to have traversed must exist with that relation direction in the
    graph. A trace of length zero when citations are non-empty is invalid
    (an answer with no supporting inference path is not traceable).
    """
    if not output.trace_node_ids:
        return 0.0
    known_nodes = example.graph.node_ids()
    known_edges = example.graph.edge_pairs()

    nodes_ok = all(n in known_nodes for n in output.trace_node_ids)
    if not nodes_ok:
        return 0.0

    if not output.trace_edges:
        # A single-node trace is only valid if it directly cites that node.
        return 1.0 if set(output.trace_node_ids) & set(output.citations) else 0.0

    edges_ok = [1.0 if pair in known_edges else 0.0 for pair in output.trace_edges]
    return sum(edges_ok) / len(edges_ok)


def abstention_score(output: ModelOutput, example: PreparedExample) -> float:
    """Rewards abstaining exactly when the graph does not support an answer."""
    if example.answerable:
        # Abstaining on an answerable question forfeits task credit but is not
        # a hallucination -- mild penalty only, per the objective's own
        # framing ("says it does not know rather than inventing a citation").
        return -0.2 if output.abstained else 0.0
    return 1.0 if output.abstained else -1.0


def task_correctness_score(output: ModelOutput, example: PreparedExample) -> float:
    """Soft correctness against gold, gated on the caller having already
    verified grounding + trace validity (see `compute_reward`)."""
    if output.abstained or example.gold_answer is None:
        return 0.0
    gold_citations = set(example.gold_citations)
    cited = set(output.citations)
    if not gold_citations:
        return 0.0
    overlap = len(gold_citations & cited) / len(gold_citations)
    return overlap


def compute_reward(
    output: ModelOutput,
    example: PreparedExample,
    weights: RewardWeights = DEFAULT_WEIGHTS,
) -> float:
    """Combine the components with the anti-hallucination gate applied.

    Returns a value nominally in roughly [-3, 3]; callers doing GRPO/PPO
    should normalize within-group as usual, this function only defines the
    *ordering* the training signal must respect.
    """
    if output.abstained:
        return weights.abstention * abstention_score(output, example)

    grounding = citation_grounding_score(output, example)
    trace = trace_validity_score(output, example)

    reward = weights.grounding * grounding + weights.trace_validity * trace
    reward += weights.abstention * abstention_score(output, example)

    # Task correctness is gated: an ungrounded or untraced "correct-looking"
    # citation earns no correctness credit, only the (already low) grounding
    # and trace terms above.
    if grounding >= 1.0 and trace >= 1.0:
        reward += weights.task_correctness * task_correctness_score(output, example)

    if has_hallucinated_citation(output, example):
        reward -= weights.hallucination_penalty

    return reward
