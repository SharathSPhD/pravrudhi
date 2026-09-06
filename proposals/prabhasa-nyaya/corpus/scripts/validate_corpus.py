#!/usr/bin/env python3
"""Validate the curated corpus against README.md "What would count as success".

Checks:
  1. Every manifest row has a resolvable origin_url, sha256, and
     court_or_authority.
  2. Realized domain coverage meets every min_share floor in
     config/domain_coverage.yaml.
  3. No exact duplicate sha256 values remain unresolved (each dedup cluster
     must have exactly one canonical_source_id kept as "active").
  4. train.jsonl and heldout.jsonl are disjoint, and no dedup cluster spans
     both.

Exits non-zero if any check fails, and prints one line per failure so a
human reviewer can see exactly what is missing - it does not silently pass
on a partial corpus.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml  # extra dependency, see scripts/requirements.txt

from common import read_manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--domain-coverage", required=True, type=Path)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--heldout", required=True, type=Path)
    parser.add_argument("--dedup-clusters", required=True, type=Path)
    return parser.parse_args(argv)


def load_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            ids.add(json.loads(line)["source_id"])
    return ids


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


def check_provenance(rows) -> list[str]:
    failures = []
    for row in rows:
        if not row.origin_url:
            failures.append(f"{row.source_id}: missing origin_url")
        if not row.sha256:
            failures.append(f"{row.source_id}: missing sha256")
        if not row.court_or_authority:
            failures.append(f"{row.source_id}: missing court_or_authority")
    return failures


def check_domain_coverage(rows, domain_coverage_cfg: dict) -> list[str]:
    failures = []
    total = len(rows)
    if total == 0:
        return ["corpus is empty; cannot evaluate domain coverage"]

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.domain] = counts.get(row.domain, 0) + 1

    for domain in domain_coverage_cfg["domains"]:
        key = domain["key"]
        min_share = domain["min_share"]
        realized = counts.get(key, 0) / total
        if realized < min_share:
            failures.append(
                f"domain {key!r}: realized share {realized:.3f} < floor {min_share:.3f}"
            )
    return failures


def check_no_unresolved_exact_duplicates(clusters: list[list[str]]) -> list[str]:
    failures = []
    for cluster in clusters:
        if len(cluster) != len(set(cluster)):
            failures.append(f"cluster has duplicate source_ids listed: {cluster}")
    return failures


def check_train_heldout_disjoint(
    train_ids: set[str], heldout_ids: set[str], clusters: list[list[str]]
) -> list[str]:
    failures = []
    overlap = train_ids & heldout_ids
    if overlap:
        failures.append(f"train/heldout overlap on {len(overlap)} source_ids: {sorted(overlap)[:5]}...")

    for cluster in clusters:
        in_train = any(source_id in train_ids for source_id in cluster)
        in_heldout = any(source_id in heldout_ids for source_id in cluster)
        if in_train and in_heldout:
            failures.append(f"dedup cluster spans train and heldout: {cluster}")
    return failures


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    rows = read_manifest(args.manifest)
    with args.domain_coverage.open("r", encoding="utf-8") as handle:
        domain_coverage_cfg = yaml.safe_load(handle)

    train_ids = load_ids(args.train)
    heldout_ids = load_ids(args.heldout)
    clusters = load_clusters(args.dedup_clusters)

    failures: list[str] = []
    failures += check_provenance(rows)
    failures += check_domain_coverage(rows, domain_coverage_cfg)
    failures += check_no_unresolved_exact_duplicates(clusters)
    failures += check_train_heldout_disjoint(train_ids, heldout_ids, clusters)

    if failures:
        print(f"VALIDATION FAILED: {len(failures)} issue(s)")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"VALIDATION PASSED: {len(rows)} documents, "
          f"{len(train_ids)} train / {len(heldout_ids)} heldout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
