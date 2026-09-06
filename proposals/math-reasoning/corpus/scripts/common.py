"""Shared types and helpers for the math-reasoning corpus scripts.

Kept dependency-light (stdlib only) so it can be imported by every stage
without pulling in the heavier optional dependencies (datasets, datasketch)
that only fetch_sources.py and dedupe.py actually need.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class ManifestRow:
    """One curated problem, with enough provenance to trace it back to its
    origin dataset/split and to decide train-vs-heldout membership.
    """

    source_id: str          # which dataset (e.g. "gsm8k")
    origin_split: str       # the split it was fetched from (e.g. "train", "test")
    item_id: str            # stable id within source_id+origin_split
    question: str
    answer: str
    sha256: str              # sha256 of normalize_text(question), for exact-dup grouping
    sha256_template: str     # sha256 of normalize_text(question) with numbers masked
    is_external_heldout: bool  # True if origin_split matches sources.yaml heldout_split


def normalize_text(text: str) -> str:
    """Collapse whitespace and lowercase, for stable hashing/shingling."""
    return _WHITESPACE_RE.sub(" ", text.strip().lower())


def mask_numbers(text: str) -> str:
    """Replace numeric literals with a placeholder.

    Used to build sha256_template: two problems that share a story template
    but differ only in the numbers plugged into it (a common source of
    near-duplication across the datasets in sources.yaml) hash identically
    under this normalization even when their exact text does not match.
    """
    return _NUMBER_RE.sub("<NUM>", text)


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shingles(text: str, n: int = 5) -> set[str]:
    """Word n-gram shingles, for MinHash/LSH near-duplicate detection."""
    words = normalize_text(text).split()
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def read_manifest(path: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(ManifestRow(**json.loads(line)))
    return rows


def write_manifest(path: Path, rows: list[ManifestRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), sort_keys=True))
            handle.write("\n")


def classify_topic(question: str, topic_buckets: dict) -> str:
    """Keyword-heuristic topic classifier for the domain-coverage report.

    Deliberately simple and auditable (grep-able keyword lists come straight
    from domain_coverage.yaml) rather than a learned classifier, since this
    is the scaffold a human reviewer checks before trusting the coverage
    numbers it produces - see README.md "Domain coverage".
    """
    text = normalize_text(question)
    for bucket, spec in topic_buckets.items():
        for keyword in spec.get("examples", []):
            if keyword in text:
                return bucket
    return "other_elementary_arithmetic"


def classify_step_count(answer: str) -> str:
    """Approximate reasoning-depth bucket from the number of arithmetic
    operations recorded in a GSM8K-style `answer` field (lines starting with
    `<<...=...>>` calculator annotations). Datasets without that annotation
    fall back to counting numeric literals in the answer as a proxy.
    """
    calc_steps = len(re.findall(r"<<[^>]+>>", answer))
    steps = calc_steps if calc_steps else max(1, len(_NUMBER_RE.findall(answer)) - 1)
    if steps <= 1:
        return "single_step"
    if steps <= 4:
        return "multi_step_2_to_4"
    return "multi_step_5_plus"
