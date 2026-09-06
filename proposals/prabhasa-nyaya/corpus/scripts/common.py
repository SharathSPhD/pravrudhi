"""Shared helpers for the Prabhasa-Nyaya corpus curation scripts.

These scripts are a runnable scaffold for the `corpus` step recipe
(corpus-curation). Nothing in this package writes outside the
proposals/prabhasa-nyaya/corpus/ tree it lives in.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Iterator


@dataclasses.dataclass(frozen=True)
class ManifestRow:
    """One curated document's provenance record.

    A document with no ManifestRow is not part of the corpus - this is the
    mechanism that keeps "no invented citation" true at the data layer.
    """

    source_id: str
    origin_url: str
    fetch_timestamp_utc: str
    sha256: str
    court_or_authority: str
    authority_kind: str
    domain: str
    decision_date: str | None
    mirror_used: bool
    license_note: str

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)

    @staticmethod
    def from_json(line: str) -> "ManifestRow":
        data = json.loads(line)
        return ManifestRow(**data)


def read_manifest(path: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(ManifestRow.from_json(line))
    return rows


def write_manifest(path: Path, rows: Iterable[ManifestRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row.to_json())
            handle.write("\n")


_WHITESPACE_RE = re.compile(r"\s+")
_CITATION_HEADER_RE = re.compile(
    r"^\s*(IN THE .*?COURT.*?\n)+", re.IGNORECASE | re.MULTILINE
)


def normalize_text(raw_text: str) -> str:
    """Normalize document text for hashing and shingling.

    Strips a leading citation/court header block (which varies by mirror and
    reprint even when the substantive text is identical) and collapses
    whitespace, so exact-duplicate detection is not defeated by formatting
    differences between an official portal render and a mirror render.
    """
    without_header = _CITATION_HEADER_RE.sub("", raw_text, count=1)
    return _WHITESPACE_RE.sub(" ", without_header).strip().lower()


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shingles(text: str, k: int = 5) -> Iterator[str]:
    """Yield k-word shingles used for MinHash near-duplicate detection."""
    words = text.split(" ")
    if len(words) < k:
        yield text
        return
    for i in range(len(words) - k + 1):
        yield " ".join(words[i : i + k])
