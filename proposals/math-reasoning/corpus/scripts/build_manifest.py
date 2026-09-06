#!/usr/bin/env python3
"""Build the provenance manifest from the raw per-source JSONL files.

Reads config/sources.yaml (to know which split is the external heldout split
per source) and every `<source_id>.jsonl` file under --raw-dir, and writes
one ManifestRow per item to --out. A row not present here is not part of the
corpus - this is the mechanism that keeps every downstream item traceable to
a named dataset and split, never an invented or unsourced example.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from common import ManifestRow, mask_numbers, normalize_text, sha256_of, write_manifest


def build_rows(source_id: str, heldout_split: str | None, raw_path: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    with raw_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            normalized = normalize_text(item["question"])
            rows.append(
                ManifestRow(
                    source_id=source_id,
                    origin_split=item["split"],
                    item_id=item["item_id"],
                    question=item["question"],
                    answer=item["answer"],
                    sha256=sha256_of(normalized),
                    sha256_template=sha256_of(mask_numbers(normalized)),
                    is_external_heldout=(item["split"] == heldout_split),
                )
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    all_rows: list[ManifestRow] = []

    for source in config["sources"]:
        source_id = source["source_id"]
        raw_path = args.raw_dir / f"{source_id}.jsonl"
        if not raw_path.exists():
            print(f"warning: {raw_path} not found, skipping {source_id}", file=sys.stderr)
            continue
        all_rows.extend(build_rows(source_id, source.get("heldout_split"), raw_path))

    write_manifest(args.out, all_rows)
    n_heldout = sum(1 for row in all_rows if row.is_external_heldout)
    print(f"Wrote {len(all_rows)} rows to {args.out} ({n_heldout} already marked external-heldout)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
