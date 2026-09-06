#!/usr/bin/env python3
"""Validate the corpus against this proposal's success criteria.

Exits non-zero (printing every violation, not just the first) if any of the
following fail - see README.md "What would count as success":

  1. Every manifest row has a non-empty question, answer, and source_id.
  2. Realized domain-topic coverage meets every `min_share` floor in
     config/domain_coverage.yaml, and step-count coverage respects both the
     floors and the single-step cap.
  3. train.jsonl, internal_dev.jsonl and heldout.jsonl are pairwise disjoint.
  4. No dedup cluster (dedupe.py output) has members split across
     heldout.jsonl and (train.jsonl union internal_dev.jsonl).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from common import ManifestRow, classify_step_count, classify_topic, read_manifest


def read_ids(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8") as handle:
        return {json.loads(line) for line in handle if line.strip()}


def read_clusters(path: Path) -> list[list[str]]:
    clusters = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                clusters.append(json.loads(line)["source_ids"])
    return clusters


def check_manifest_completeness(rows: list[ManifestRow]) -> list[str]:
    errors = []
    for row in rows:
        if not row.question.strip():
            errors.append(f"{row.item_id}: empty question")
        if not row.answer.strip():
            errors.append(f"{row.item_id}: empty answer")
        if not row.source_id.strip():
            errors.append(f"{row.item_id}: empty source_id")
    return errors


def check_domain_coverage(
    rows: list[ManifestRow], train_ids: set[str], domain_config: dict
) -> list[str]:
    errors = []
    train_rows = [row for row in rows if row.item_id in train_ids]
    if not train_rows:
        return ["no train rows to compute domain coverage over"]

    topic_buckets = domain_config["topic_buckets"]
    topic_counts: dict[str, int] = {bucket: 0 for bucket in topic_buckets}
    for row in train_rows:
        topic_counts[classify_topic(row.question, topic_buckets)] += 1
    for bucket, spec in topic_buckets.items():
        share = topic_counts[bucket] / len(train_rows)
        min_share = spec.get("min_share", 0.0)
        if share < min_share:
            errors.append(
                f"topic bucket {bucket!r}: realized share {share:.3f} < floor {min_share:.3f}"
            )

    step_buckets = domain_config["step_count_buckets"]
    step_counts: dict[str, int] = {bucket: 0 for bucket in step_buckets}
    for row in train_rows:
        step_counts[classify_step_count(row.answer)] += 1
    for bucket, spec in step_buckets.items():
        share = step_counts[bucket] / len(train_rows)
        min_share = spec.get("min_share", 0.0)
        max_share = spec.get("max_share", 1.0)
        if share < min_share:
            errors.append(
                f"step bucket {bucket!r}: realized share {share:.3f} < floor {min_share:.3f}"
            )
        if share > max_share:
            errors.append(
                f"step bucket {bucket!r}: realized share {share:.3f} > cap {max_share:.3f}"
            )
    return errors


def check_split_disjoint(train_ids: set[str], dev_ids: set[str], heldout_ids: set[str]) -> list[str]:
    errors = []
    for name_a, set_a, name_b, set_b in [
        ("train", train_ids, "internal_dev", dev_ids),
        ("train", train_ids, "heldout", heldout_ids),
        ("internal_dev", dev_ids, "heldout", heldout_ids),
    ]:
        overlap = set_a & set_b
        if overlap:
            errors.append(f"{name_a} and {name_b} overlap on {len(overlap)} item(s): {sorted(overlap)[:5]}...")
    return errors


def check_no_cluster_spans_holdout(
    clusters: list[list[str]], heldout_ids: set[str], non_heldout_ids: set[str]
) -> list[str]:
    errors = []
    for cluster in clusters:
        cluster_set = set(cluster)
        if cluster_set & heldout_ids and cluster_set & non_heldout_ids:
            errors.append(f"dedup cluster spans heldout and train/dev: {sorted(cluster_set)[:5]}...")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--domain-coverage", required=True, type=Path)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--internal-dev", required=True, type=Path)
    parser.add_argument("--heldout", required=True, type=Path)
    parser.add_argument("--dedup-clusters", required=True, type=Path)
    args = parser.parse_args(argv)

    rows = read_manifest(args.manifest)
    domain_config = yaml.safe_load(args.domain_coverage.read_text(encoding="utf-8"))
    train_ids = read_ids(args.train)
    dev_ids = read_ids(args.internal_dev)
    heldout_ids = read_ids(args.heldout)
    clusters = read_clusters(args.dedup_clusters)

    errors: list[str] = []
    errors += check_manifest_completeness(rows)
    errors += check_domain_coverage(rows, train_ids, domain_config)
    errors += check_split_disjoint(train_ids, dev_ids, heldout_ids)
    errors += check_no_cluster_spans_holdout(clusters, heldout_ids, train_ids | dev_ids)

    if errors:
        print(f"validate_corpus: {len(errors)} violation(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        f"validate_corpus: OK - train={len(train_ids)} internal_dev={len(dev_ids)} "
        f"heldout={len(heldout_ids)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
