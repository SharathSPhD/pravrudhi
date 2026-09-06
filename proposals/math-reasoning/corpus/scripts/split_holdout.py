#!/usr/bin/env python3
"""Split the deduplicated manifest into train / internal-dev / heldout.

Order of operations (each step can only move items into a more-held-out
bucket, never back into train):

1. Any item with `is_external_heldout=True` (GSM8K/SVAMP/MAWPS official test
   split, per sources.yaml) goes to `heldout.jsonl` unconditionally.
2. Any item whose dedup cluster (dedupe.py output) contains at least one
   external-heldout item also goes to `heldout.jsonl` - this is what keeps a
   paraphrased or number-substituted copy of a test-set problem out of
   training, not just the exact test-set copy itself (see README.md
   "Separation from held-out evaluation").
3. From what remains, a stratified `internal_dev_fraction` (config:
   holdout.internal_dev_fraction, seeded by holdout.internal_dev_seed) is
   carved out per dedup-cluster-representative into `internal_dev.jsonl`,
   for early-stopping/model-selection during fine-tuning without ever
   touching the external test splits.
4. Everything else is `train.jsonl`.

All three output files list `item_id` only (one per line, JSON string), not
full document bodies - the manifest remains the single source of truth for
content.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import yaml

from common import ManifestRow, read_manifest


def load_clusters(path: Path) -> list[dict]:
    clusters = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                clusters.append(json.loads(line))
    return clusters


def write_ids(path: Path, item_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item_id in sorted(item_ids):
            handle.write(json.dumps(item_id))
            handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dedup-clusters", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    rows = read_manifest(args.manifest)
    rows_by_id: dict[str, ManifestRow] = {row.item_id: row for row in rows}
    clusters = load_clusters(args.dedup_clusters)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    holdout_cfg = config["holdout"]

    heldout: set[str] = {row.item_id for row in rows if row.is_external_heldout}

    # Step 2: propagate heldout status across dedup clusters.
    for cluster in clusters:
        members = cluster["source_ids"]
        if any(m in heldout for m in members):
            heldout.update(members)

    remaining_clusters = [c for c in clusters if not set(c["source_ids"]) & heldout]

    # Step 3: stratified internal-dev sample, one decision per cluster (so a
    # cluster's members - which are near-duplicates of each other - always
    # land on the same side of the train/internal-dev line).
    rng = random.Random(holdout_cfg["internal_dev_seed"])
    dev_fraction = holdout_cfg["internal_dev_fraction"]
    internal_dev: set[str] = set()
    train: set[str] = set()
    for cluster in sorted(remaining_clusters, key=lambda c: c["cluster_id"]):
        members = cluster["source_ids"]
        if rng.random() < dev_fraction:
            internal_dev.update(members)
        else:
            train.update(members)

    write_ids(args.out_dir / "heldout.jsonl", sorted(heldout))
    write_ids(args.out_dir / "internal_dev.jsonl", sorted(internal_dev))
    write_ids(args.out_dir / "train.jsonl", sorted(train))

    print(
        f"train={len(train)} internal_dev={len(internal_dev)} heldout={len(heldout)} "
        f"(of {len(rows_by_id)} manifest rows)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
