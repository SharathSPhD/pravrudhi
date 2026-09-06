#!/usr/bin/env python3
"""Build/refresh the provenance manifest from fetched raw documents.

Walks --raw-dir (expected layout: <raw-dir>/<source_name>/<source_id>.json,
one JSON object per fetched document with at least `origin_url`, `raw_text`,
`fetch_timestamp_utc`, `court_or_authority`, `domain`, and optionally
`decision_date` / `mirror_used`) and writes one common.ManifestRow per
document, hashing the normalized text so downstream dedup and the
build-vs-fetch drift check both operate on the same content hash.

A document missing any required field is skipped with a warning rather than
silently entering the corpus without full provenance - see README.md
"Source provenance".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import ManifestRow, normalize_text, sha256_of, write_manifest

REQUIRED_FIELDS = (
    "origin_url",
    "raw_text",
    "fetch_timestamp_utc",
    "court_or_authority",
    "domain",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def build_rows(raw_dir: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    if not raw_dir.exists():
        print(f"warning: raw dir {raw_dir} does not exist yet; writing empty manifest",
              file=sys.stderr)
        return rows

    for doc_path in sorted(raw_dir.glob("*/*.json")):
        source_name = doc_path.parent.name
        with doc_path.open("r", encoding="utf-8") as handle:
            doc = json.load(handle)

        missing = [field for field in REQUIRED_FIELDS if field not in doc]
        if missing:
            print(f"warning: skipping {doc_path} - missing fields {missing}", file=sys.stderr)
            continue

        normalized = normalize_text(doc["raw_text"])
        rows.append(
            ManifestRow(
                source_id=f"{source_name}:{doc_path.stem}",
                origin_url=doc["origin_url"],
                fetch_timestamp_utc=doc["fetch_timestamp_utc"],
                sha256=sha256_of(normalized),
                court_or_authority=doc["court_or_authority"],
                authority_kind=doc.get("authority_kind", "unknown"),
                domain=doc["domain"],
                decision_date=doc.get("decision_date"),
                mirror_used=bool(doc.get("mirror_used", False)),
                license_note=doc.get("license_note", ""),
            )
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = build_rows(args.raw_dir)
    write_manifest(args.out, rows)
    print(f"Wrote {len(rows)} manifest rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
