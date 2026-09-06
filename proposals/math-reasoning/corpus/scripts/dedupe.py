#!/usr/bin/env python3
"""Deduplicate the manifest: exact duplicates and near-duplicate clusters.

Three layers, in increasing order of recall:

1. Exact duplicate: identical `sha256` (normalized question text). Catches
   the same problem appearing verbatim in more than one source (e.g. MAWPS
   re-packaging an item that also exists standalone).
2. Template duplicate: identical `sha256_template` (numbers masked out).
   Catches the same story template with different numbers substituted in -
   common because SVAMP is explicitly built by perturbing ASDiv seeds, and
   several MAWPS-lineage sets recycle earlier word-problem templates.
3. Near duplicate: MinHash + LSH over 5-gram shingles, Jaccard threshold
   from config/sources.yaml (`holdout.near_dup_jaccard_threshold`), using the
   `datasketch` library (scripts/requirements.txt) - not vendored here.
   Catches paraphrases that layers 1-2 miss.

Output: one JSON object per line, {"cluster_id", "source_ids",
"canonical_source_id"}. `source_id` here means the manifest's `item_id`
(the join key split_holdout.py and validate_corpus.py use), not the dataset
name. A singleton cluster (an item with no duplicate) is still emitted so
downstream steps have a uniform join key.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from datasketch import MinHash, MinHashLSH  # extra dependency, not vendored here

from common import ManifestRow, read_manifest, shingles

MINHASH_NUM_PERM = 128


def group_by(rows: list[ManifestRow], key: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for row in rows:
        groups.setdefault(getattr(row, key), []).append(row.item_id)
    return groups


def merge_groups(*group_lists: dict[str, list[str]]) -> list[set[str]]:
    """Union-find style merge: two item_ids in the same group under *any*
    key end up in the same cluster.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for groups in group_lists:
        for members in groups.values():
            for member in members:
                parent.setdefault(member, member)
            for member in members[1:]:
                union(members[0], member)

    clusters: dict[str, set[str]] = {}
    for item_id in parent:
        clusters.setdefault(find(item_id), set()).add(item_id)
    return list(clusters.values())


def near_duplicate_groups(rows: list[ManifestRow], jaccard_threshold: float) -> dict[str, list[str]]:
    lsh = MinHashLSH(threshold=jaccard_threshold, num_perm=MINHASH_NUM_PERM)
    minhashes: dict[str, MinHash] = {}

    for row in rows:
        mh = MinHash(num_perm=MINHASH_NUM_PERM)
        for shingle in shingles(row.question):
            mh.update(shingle.encode("utf-8"))
        minhashes[row.item_id] = mh
        lsh.insert(row.item_id, mh)

    groups: dict[str, list[str]] = {}
    for row in rows:
        matches = sorted(lsh.query(minhashes[row.item_id]))
        groups[matches[0]] = matches
    return groups


def pick_canonical(item_ids: list[str], rows_by_id: dict[str, ManifestRow]) -> str:
    """Prefer the external-heldout copy if one exists (so a cluster spanning
    train and heldout is visible to split_holdout.py via its members, while
    still naming a deterministic canonical); otherwise the lexicographically
    first item_id, for reproducibility.
    """

    def rank(item_id: str) -> tuple[int, str]:
        row = rows_by_id[item_id]
        return (0 if row.is_external_heldout else 1, item_id)

    return sorted(item_ids, key=rank)[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    threshold = config["holdout"]["near_dup_jaccard_threshold"]

    rows = read_manifest(args.manifest)
    rows_by_id = {row.item_id: row for row in rows}

    exact_groups = group_by(rows, "sha256")
    template_groups = group_by(rows, "sha256_template")
    near_dup_groups = near_duplicate_groups(rows, threshold)

    clusters = merge_groups(exact_groups, template_groups, near_dup_groups)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for i, cluster in enumerate(sorted(clusters, key=lambda c: sorted(c)[0])):
            item_ids = sorted(cluster)
            handle.write(
                json.dumps(
                    {
                        "cluster_id": f"cluster-{i:06d}",
                        "source_ids": item_ids,
                        "canonical_source_id": pick_canonical(item_ids, rows_by_id),
                    },
                    sort_keys=True,
                )
            )
            handle.write("\n")

    print(f"Wrote {len(clusters)} clusters to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
