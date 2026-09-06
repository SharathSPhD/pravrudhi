#!/usr/bin/env python3
"""Fetch raw legal documents per config/sources.yaml.

This is a runnable scaffold for the corpus-curation recipe's fetch step. It
enumerates the configured sources and rate limits, and shows exactly where a
real HTTP client would be plugged in - it does not itself claim network
access has been exercised. See README.md "Explicit non-goals of this step".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml  # extra dependency, see scripts/requirements.txt


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the fetch plan without performing any network requests.",
    )
    return parser.parse_args(argv)


def load_sources(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def fetch_one(source_name: str, source_cfg: dict, out_dir: Path, dry_run: bool) -> int:
    """Fetch documents for a single configured source.

    Returns the number of documents fetched. Real implementation would page
    through the source's search/listing endpoint, respecting
    `rate_limit_per_minute`, and write one raw file per document under
    `out_dir / source_name /`.
    """
    print(f"[{source_name}] base_url={source_cfg['base_url']!r} "
          f"authority_kind={source_cfg['authority_kind']!r} "
          f"rate_limit_per_minute={source_cfg['rate_limit_per_minute']}")
    if source_name == "indian_kanoon":
        print(f"[{source_name}] NOTE: {source_cfg.get('rate_limit_notice', '').strip()}")

    if dry_run:
        return 0

    out_dir.joinpath(source_name).mkdir(parents=True, exist_ok=True)
    delay_seconds = 60.0 / max(source_cfg["rate_limit_per_minute"], 1)
    _ = delay_seconds  # a real fetch loop would `time.sleep(delay_seconds)` between requests
    raise NotImplementedError(
        f"Real fetch for source {source_name!r} is not implemented in this proposal; "
        "run with --dry-run to see the planned sources, or plug in an HTTP client here."
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_sources(args.config)
    sources = config.get("sources", {})

    total_planned = 0
    for source_name, source_cfg in sources.items():
        total_planned += fetch_one(source_name, source_cfg, args.out, args.dry_run)

    if args.dry_run:
        print(f"Dry run complete. {len(sources)} sources configured; "
              f"target_counts={config.get('target_counts')}")
        return 0

    print(f"Fetched {total_planned} documents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
