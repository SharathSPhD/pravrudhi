"""Headline-drift check: every number that names a measurement in README, paper or docs must appear in a gate JSON
or a prereg file. Reports the offending line; exit 1 on any drift. Numbers inside code fences and citations are ignored."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = re.compile(r"(pass rate|pass_rate|sigma|Wilson|GiB|tokens/s|tok/s|tok_s|delta|Hedges|interval|VRAM)", re.I)
NUM = re.compile(r"(?<![\w.])(\d+\.\d{2,})(?![\w.])")


def known_numbers(root: Path) -> set[str]:
    out: set[str] = set()
    sources = (
        list((root / "gates").glob("gate_*.json"))
        + list((root / "research" / "prereg").glob("*.json"))
        + list((root / "docs" / "evidence").glob("*.md"))  # reproduced from the ledger by `make reproduce`
    )
    for p in sources:
        if p.exists():
            out |= set(NUM.findall(p.read_text()))
    return out


def scan(root: Path, paths: list[Path], known: set[str]) -> list[str]:
    bad: list[str] = []
    for p in paths:
        if not p.exists():
            continue
        fence = False
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if line.strip().startswith("```"):
                fence = not fence
            if fence or line.lstrip().startswith("%") or not KEYWORDS.search(line):
                continue
            for n in NUM.findall(line):
                if n not in known and not any(n.startswith(k[: len(n)]) for k in known):
                    bad.append(f"{p.relative_to(root)}:{i}: {n} not in any gate or prereg file")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    root = ap.parse_args().root.resolve()
    known = known_numbers(root)
    targets = [
        root / "README.md",
        *sorted((root / "paper" / "sections").glob("*.tex")),
        *sorted((root / "docs").glob("*.md")),
    ]
    bad = scan(root, targets, known)
    for b in bad:
        print(b)
    print(f"headline-check: {len(bad)} drift(s); {len(known)} known numbers")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
