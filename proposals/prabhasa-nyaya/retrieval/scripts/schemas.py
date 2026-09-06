"""Typed contract for the `retrieval` recipe's consumed and produced artifacts.

This is a proposal: it defines the shape the recipe expects `prepared_corpus`
and `rl_candidate` to already have, and the shape it promises for
`retrieval_candidate`. It does not fabricate or validate real corpus data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeType(str, Enum):
    STATUTE = "Statute"
    PRECEDENT = "Precedent"
    FACT = "Fact"
    PRATIJNA = "Pratijna"
    HETU = "Hetu"
    UDAHARANA = "Udaharana"
    UPANAYA = "Upanaya"
    NIGAMANA = "Nigamana"


class EdgeType(str, Enum):
    CITES = "cites"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    APPLIES_TO = "applies_to"
    DERIVED_FROM = "derived_from"


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: NodeType
    source_id: str
    text: str
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class GraphEdge:
    src_id: str
    dst_id: str
    edge_type: EdgeType


@dataclass(frozen=True)
class PreparedCorpus:
    """Expected shape of the `prepared_corpus` artifact this recipe consumes."""

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    citation_registry: frozenset[str]  # every resolvable source_id


@dataclass(frozen=True)
class RLCandidate:
    """Expected shape of the `rl_candidate` artifact this recipe consumes.

    `rl_candidate` is the reasoning-policy candidate under evaluation. This
    recipe only asks it to decompose a question into sub-queries; it does not
    otherwise inspect or score the policy.
    """

    candidate_id: str
    decompose: "QueryDecomposer"


# A decomposer is any callable question -> list[sub-query strings]. Kept as a
# Protocol-like alias rather than a concrete class because the real
# rl_candidate artifact will supply its own implementation (e.g. a model call);
# this module only needs the call signature to type-check the recipe.
from typing import Callable  # noqa: E402

QueryDecomposer = Callable[[str], list[str]]


@dataclass(frozen=True)
class RetrievalHit:
    node_id: str
    node_type: NodeType
    source_id: str
    text: str
    fused_score: float


@dataclass(frozen=True)
class RetrievalCandidate:
    """Produced artifact: `retrieval_candidate`."""

    query: str
    sub_queries: list[str]
    hits: list[RetrievalHit]
    abstain: bool
    config_snapshot: dict = field(default_factory=dict)
