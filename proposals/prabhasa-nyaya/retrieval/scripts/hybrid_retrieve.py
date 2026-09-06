"""Recipe entry point for the `retrieval` step.

Consumes `objective`, `rl_candidate`, `prepared_corpus`; produces
`retrieval_candidate`. Writes only to the local `--out` path given on the
command line — never to a ledger, `research/`, `gates/`, or
`pravrudhi_kernel/`. This is a proposal artifact, not a validated recipe.

Usage:
    uv run python hybrid_retrieve.py \
        --objective objective.json \
        --rl-candidate rl_candidate.json \
        --prepared-corpus prepared_corpus.json \
        --config ../configs/retrieval.yaml \
        --queries held_out_queries.json \
        --out /tmp/retrieval_candidate.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import load_simple_yaml
from graph_index import GraphIndex
from schemas import (
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    PreparedCorpus,
    RetrievalCandidate,
    RetrievalHit,
)


def naive_embed(text: str, dim: int) -> tuple[float, ...]:
    """Deterministic bag-of-hash-buckets embedding.

    This is a placeholder so the recipe is runnable end-to-end for wiring
    smoke-tests. It is NOT a semantic embedder and must be replaced with
    whatever model produced the corpus's stored node embeddings before any
    real evaluation of this recipe.
    """
    vec = [0.0] * dim
    for word in text.lower().split():
        digest = hashlib.sha256(word.encode("utf-8")).hexdigest()
        idx = int(digest, 16) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return tuple(x / norm for x in vec)


def load_prepared_corpus(path: str) -> PreparedCorpus:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    nodes = tuple(
        GraphNode(
            node_id=n["node_id"],
            node_type=NodeType(n["node_type"]),
            source_id=n["source_id"],
            text=n["text"],
            embedding=tuple(n["embedding"]),
        )
        for n in payload["nodes"]
    )
    edges = tuple(
        GraphEdge(
            src_id=e["src_id"],
            dst_id=e["dst_id"],
            edge_type=EdgeType(e["edge_type"]),
        )
        for e in payload["edges"]
    )
    citation_registry = frozenset(payload["citation_registry"])
    return PreparedCorpus(nodes=nodes, edges=edges, citation_registry=citation_registry)


def build_decomposer(rl_candidate_path: str):
    """Builds a query -> [sub-queries] callable from the rl_candidate artifact.

    The real `rl_candidate` is a reasoning-policy candidate; asking it to
    decompose a question is a model call this proposal does not have access
    to. As a stand-in, this reads an optional list of syllogism-member hints
    from the artifact (e.g. ["Hetu", "Udaharana"]) and appends each as a
    sub-query suffix. With no hints, decomposition is the identity function.
    """
    payload = json.loads(Path(rl_candidate_path).read_text(encoding="utf-8"))
    hints: list[str] = payload.get("decomposition_hints", [])

    def decompose(query: str) -> list[str]:
        if not hints:
            return [query]
        return [f"{query} ({hint})" for hint in hints]

    return decompose


def reciprocal_rank_fusion(ranked_lists: list[list[str]], rrf_k: int) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked_ids in ranked_lists:
        for rank, node_id in enumerate(ranked_ids, start=1):
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (rrf_k + rank)
    return scores


def run_query(query: str, decompose, index: GraphIndex, cfg: dict) -> RetrievalCandidate:
    sub_queries = decompose(query)

    dim = len(index.all_nodes()[0].embedding) if index.all_nodes() else 0
    best_score_by_id: dict[str, float] = {}
    best_raw_score = 0.0

    for sub_query in sub_queries:
        embedding = naive_embed(sub_query, dim)
        for node, score in index.dense_search(embedding, cfg["dense_top_k"]):
            best_score_by_id[node.node_id] = max(best_score_by_id.get(node.node_id, -1.0), score)
            best_raw_score = max(best_raw_score, score)

    dense_ranked_ids = sorted(best_score_by_id, key=lambda nid: best_score_by_id[nid], reverse=True)

    expansion_edge_types = [EdgeType(t) for t in cfg["expansion_edge_types"]]
    expanded_nodes = index.expand(dense_ranked_ids, expansion_edge_types, cfg["max_hops"])
    graph_ranked_ids = [node.node_id for node in expanded_nodes]

    fused = reciprocal_rank_fusion([dense_ranked_ids, graph_ranked_ids], cfg["rrf_k"])

    citable_types = [NodeType(t) for t in cfg["citable_node_types"]]
    citable_scored = sorted(
        (
            (node_id, score)
            for node_id, score in fused.items()
            if index.node(node_id).node_type in citable_types
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )

    top = citable_scored[: cfg["retrieval_count"]]
    abstain = best_raw_score < cfg["min_support_score"] or not top

    hits = (
        []
        if abstain
        else [
            RetrievalHit(
                node_id=node_id,
                node_type=index.node(node_id).node_type,
                source_id=index.node(node_id).source_id,
                text=index.node(node_id).text,
                fused_score=score,
            )
            for node_id, score in top
        ]
    )

    return RetrievalCandidate(
        query=query,
        sub_queries=sub_queries,
        hits=hits,
        abstain=abstain,
        config_snapshot=cfg,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--rl-candidate", required=True)
    parser.add_argument("--prepared-corpus", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--queries", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    # Read for provenance only; the objective does not otherwise steer this
    # step's retrieval logic (query decomposition comes from rl_candidate).
    json.loads(Path(args.objective).read_text(encoding="utf-8"))

    cfg = load_simple_yaml(args.config)
    corpus = load_prepared_corpus(args.prepared_corpus)
    index = GraphIndex(corpus)
    decompose = build_decomposer(args.rl_candidate)

    queries_payload = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    queries = [item["query"] for item in queries_payload]

    candidates = [run_query(query, decompose, index, cfg) for query in queries]

    out_payload = [
        {
            **asdict(candidate),
            "hits": [
                {**asdict(hit), "node_type": hit.node_type.value} for hit in candidate.hits
            ],
        }
        for candidate in candidates
    ]

    Path(args.out).write_text(json.dumps(out_payload, indent=2), encoding="utf-8")
    print(f"wrote {len(out_payload)} retrieval_candidate entries to {args.out}")


if __name__ == "__main__":
    main()
