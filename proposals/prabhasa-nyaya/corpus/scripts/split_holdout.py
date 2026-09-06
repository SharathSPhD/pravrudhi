#!/usr/bin/env python3
"""Split the manifest into disjoint train / held-out sets.

Two holdout rules, both from config/sources.yaml `holdout:`:

1. Temporal: any document with decision_date >= cutoff (build date minus
   `temporal_cutoff_months_before_build`) goes to held-out.
2. Stratified: within each domain, a seeded `stratified_holdout_fraction` of
   the remaining (non-temporal-holdout) documents also goes to held-out, so
   evaluation coverage does not collapse onto whatever domain is most recent.

Held-out assignment is then propagated across dedup clusters (from
dedupe.py's output): if any member of a cluster is held out, the whole
cluster is held out, so a judgment and the near-duplicate text that quotes it
cannot land on opposite sides of the split.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import yaml  # extra dependency, see scripts/requirements.txt

from common import ManifestRow, read_manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dedup-clusters", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--build-date",
        default=None,
        help="ISO date to compute the temporal cutoff from; defaults to today.",
    )
    return parser.parse_args(argv)


def load_clusters(path: Path) -> list[list[str]]:
    clusters: list[list[str]] = []
    if not path.exists():
        return clusters
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            clusters.append(json.loads(line)["source_ids"])
    return clusters


def months_before(reference: dt.date, months: int) -> dt.date:
    year = reference.year
    month = reference.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(reference.day, 28)
    return dt.date(year, month, day)


def stratified_pick(source_id: str, seed: int, fraction: float) -> bool:
    """Deterministic seeded pick: True if source_id falls in the holdout fraction."""
    digest = hashlib.sha256(f"{seed}:{source_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return bucket < fraction


def assign_holdout(
    rows: list[ManifestRow], config: dict, build_date: dt.date
) -> dict[str, bool]:
    holdout_cfg = config["holdout"]
    cutoff = months_before(build_date, holdout_cfg["temporal_cutoff_months_before_build"])
    fraction = holdout_cfg["stratified_holdout_fraction"]
    seed = holdout_cfg["stratified_seed"]

    is_heldout: dict[str, bool] = {}
    for row in rows:
        temporal_hit = False
        if row.decision_date:
            try:
                decision_date = dt.date.fromisoformat(row.decision_date)
                temporal_hit = decision_date >= cutoff
            except ValueError:
                temporal_hit = False

        stratified_hit = stratified_pick(row.source_id, seed, fraction)
        is_heldout[row.source_id] = temporal_hit or stratified_hit
    return is_heldout


def propagate_across_clusters(
    is_heldout: dict[str, bool], clusters: list[list[str]]
) -> dict[str, bool]:
    result = dict(is_heldout)
    for cluster in clusters:
        if any(result.get(source_id, False) for source_id in cluster):
            for source_id in cluster:
                result[source_id] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    with args.config.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    build_date = (
        dt.date.fromisoformat(args.build_date) if args.build_date else dt.date.today()
    )

    rows = read_manifest(args.manifest)
    clusters = load_clusters(args.dedup_clusters)

    is_heldout = assign_holdout(rows, config, build_date)
    is_heldout = propagate_across_clusters(is_heldout, clusters)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    train_path = args.out_dir / "train.jsonl"
    heldout_path = args.out_dir / "heldout.jsonl"

    train_count = 0
    heldout_count = 0
    with train_path.open("w", encoding="utf-8") as train_f, heldout_path.open(
        "w", encoding="utf-8"
    ) as heldout_f:
        for row in rows:
            record = json.dumps({"source_id": row.source_id, "domain": row.domain})
            if is_heldout.get(row.source_id, False):
                heldout_f.write(record + "\n")
                heldout_count += 1
            else:
                train_f.write(record + "\n")
                train_count += 1

    print(f"train={train_count} heldout={heldout_count} (cutoff computed from build_date={build_date})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
