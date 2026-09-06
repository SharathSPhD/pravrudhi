"""Assumed I/O contracts for the rl step.

This proposal was written without reading the actual `finetune_candidate` /
`prepared_corpus` producers (out of scope for this task). The shapes below
are the assumption this design is built on; reconcile them with the real
producer schemas before running anything for real. Nothing here writes to
the ledger, research/, gates/ or pravrudhi_kernel/ -- these are plain
dataclasses used by the other scripts in this proposal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GraphNode:
    """One typed node in a Nyaya meaning graph fragment."""

    id: str
    type: str  # e.g. "statute", "section", "precedent", "fact", "issue", "holding"
    text: str


@dataclass
class GraphEdge:
    """One typed edge (inference step) between two nodes."""

    src: str
    dst: str
    relation: str  # e.g. "applies_to", "distinguishes", "overrules", "supports"


@dataclass
class NyayaGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}

    def edge_pairs(self) -> set[tuple[str, str]]:
        return {(e.src, e.dst) for e in self.edges}


@dataclass
class PreparedExample:
    """One row of `prepared_corpus`: a question situated in a graph slice."""

    id: str
    question: str
    graph: NyayaGraph
    gold_citations: list[str]  # canonical citation ids, e.g. "IPC:302"
    gold_answer: Optional[str]  # None when the question is a "should abstain" probe
    answerable: bool


@dataclass
class ModelOutput:
    """Parsed structured output of the policy for one rollout."""

    raw_text: str
    answer: Optional[str]
    citations: list[str]
    trace_node_ids: list[str]
    trace_edges: list[tuple[str, str]]
    abstained: bool


@dataclass
class FinetuneCandidateRef:
    """Reference to the upstream `finetune_candidate` artifact."""

    base_model: str
    adapter_path: Optional[str]
    tokenizer_path: str


@dataclass
class RLCandidateRef:
    """Reference to the `rl_candidate` this step proposes to produce."""

    base_model: str
    adapter_path: str
    parent_finetune_candidate: FinetuneCandidateRef
    training_config_path: str
