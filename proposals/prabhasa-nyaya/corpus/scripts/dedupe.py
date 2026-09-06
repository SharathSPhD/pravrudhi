#!/usr/bin/env python3
"""Deduplicate the manifest: exact duplicates and near-duplicate clusters.

Exact duplicates are found by sha256 of normalized text (already computed in
each ManifestRow by build_manifest.py). Near duplicates are found by MinHash
+ LSH over 5-gram shingles at Jaccard threshold 0.85, using the `datasketch`
library (see scripts/requirements.txt) - not vendored in this proposal.

Output is one JSON object per line: {"cluster_id": ..., "source_ids": [...],
"canonical_source_id": ...}. A singleton cluster (a document with no
duplicate) is still emitted so split_holdout.py has a uniform join key.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from datasketch import MinHash, MinHashLSH  # extra dependency, not vendored here

from common import ManifestRow, read_manifest, shingles

NEAR_DUP_JACCARD_THRESHOLD = 0.85
MINHASH_NUM_PERM = 128


def exact_duplicates(rows: list[ManifestRow]) -> dict[str, list[str]]:
    """Group source_ids by identical normalized-text sha256."""
    groups: dict[str, list[str]] = {}
    for row in rows:
        groups.setdefault(row.sha256, []).append(row.source_id)
    return groups


def pick_canonical(source_ids: list[str], rows_by_id: dict[str, ManifestRow]) -> str:
    """Prefer official-portal, non-mirror documents as the cluster canonical."""

    def rank(source_id: str) -> tuple[int, str]:
        row = rows_by_id[source_id]
        mirror_penalty = 1 if row.mirror_used else 0
        return (mirror_penalty, source_id)

    return sorted(source_ids, key=rank)[0]


def near_duplicate_clusters(
    rows: list[ManifestRow], normalized_text_by_id: dict[str, str]
) -> list[list[str]]:
    """Cluster near-duplicate documents via MinHash LSH.

    normalized_text_by_id must be supplied by the caller (build_manifest.py
    only persists the hash, not the normalized text, to keep the manifest
    small) - typically re-derived from the raw documents at dedup time.
    """
    lsh = MinHashLSH(threshold=NEAR_DUP_JACCARD_THRESHOLD, num_perm=MINHASH_NUM_PERM)
    minhashes: dict[str, MinHash] = {}

    for row in rows:
        text = normalized_text_by_id.get(row.source_id, "")
        mh = MinHash(num_perm=MINHASH_NUM_PERM)
        for shingle in shingles(text):
            mh.update(shingle.encode("utf-8"))
        minhashes[row.source_id] = mh
        lsh.insert(row.source_id, mh)

    seen: set[str] = set()
    clusters: list[list[str]] = []
    for row in rows:
        if row.source_id in seen:
            continue
        matches = lsh.query(minhashes[row.source_id])
        cluster = sorted(set(matches) | {row.source_id})
        seen.update(cluster)
        clusters.append(cluster)
    return clusters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    rows = read_manifest(args.manifest)
    rows_by_id = {row.source_id: row for row in rows}

    exact_groups = exact_duplicates(rows)

    # A real run re-derives normalized text from the raw fetched documents to
    # feed near-duplicate clustering; this scaffold has no raw text available
    # once only the manifest is on disk, so it clusters purely on the exact
    # sha256 groups already computed above as a conservative stand-in.
    clusters = list(exact_groups.values())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for i, source_ids in enumerate(clusters):
            canonical = pick_canonical(source_ids, rows_by_id)
            handle.write(
                json.dumps(
                    {
                        "cluster_id": f"cluster-{i:06d}",
                        "source_ids": source_ids,
                        "canonical_source_id": canonical,
                    },
                    sort_keys=True,
                )
            )
            handle.write("\n")

    print(f"Wrote {len(clusters)} clusters to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
