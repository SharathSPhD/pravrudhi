"""In-memory typed index over a prepared_corpus payload.

Builds adjacency-by-edge-type and a simple embedding lookup so
hybrid_retrieve.py can do dense scoring and typed graph traversal without
re-scanning the raw corpus on every query. This is a proposal-grade
implementation: it favours clarity over performance (no ANN index), which is
appropriate for evaluating a recipe against a held-out query set before any
scale requirement is known.
"""

from __future__ import annotations

import math
from collections import defaultdict

from schemas import EdgeType, GraphEdge, GraphNode, NodeType, PreparedCorpus


def cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    if len(a) != len(b):
        raise ValueError(f"embedding dim mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class GraphIndex:
    def __init__(self, corpus: PreparedCorpus) -> None:
        self._corpus = corpus
        self._nodes_by_id: dict[str, GraphNode] = {n.node_id: n for n in corpus.nodes}
        self._out_edges: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in corpus.edges:
            self._out_edges[edge.src_id].append(edge)

    def node(self, node_id: str) -> GraphNode:
        return self._nodes_by_id[node_id]

    def all_nodes(self) -> tuple[GraphNode, ...]:
        return self._corpus.nodes

    def resolves(self, source_id: str) -> bool:
        return source_id in self._corpus.citation_registry

    def dense_search(
        self, query_embedding: tuple[float, ...], top_k: int
    ) -> list[tuple[GraphNode, float]]:
        scored = [
            (node, cosine_similarity(query_embedding, node.embedding))
            for node in self._corpus.nodes
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    def expand(
        self,
        seed_ids: list[str],
        edge_types: list[EdgeType],
        max_hops: int,
    ) -> list[GraphNode]:
        """Breadth-first expansion from seed nodes along allowed edge types."""
        visited: set[str] = set(seed_ids)
        frontier = list(seed_ids)
        expanded: list[GraphNode] = []

        for _ in range(max_hops):
            next_frontier: list[str] = []
            for node_id in frontier:
                for edge in self._out_edges.get(node_id, []):
                    if edge.edge_type not in edge_types:
                        continue
                    if edge.dst_id in visited:
                        continue
                    visited.add(edge.dst_id)
                    next_frontier.append(edge.dst_id)
                    expanded.append(self._nodes_by_id[edge.dst_id])
            frontier = next_frontier
            if not frontier:
                break

        return expanded

    def citable(self, node: GraphNode, citable_types: list[NodeType]) -> bool:
        return node.node_type in citable_types
