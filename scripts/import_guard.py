"""Import guard: the kernel never imports the engine or torch; the engine's domain layer never imports torch.

Exit 1 and print `path:line: message` for every violation. Usage: import_guard.py [--root DIR]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

RULES: list[tuple[str, frozenset[str], str]] = [
    ("pravrudhi_kernel/src", frozenset({"pravrudhi", "torch"}), "kernel must not import"),
    ("src/pravrudhi/domain", frozenset({"torch"}), "domain must not import"),
]


def _roots(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [a.name.split(".")[0] for a in node.names]
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return [node.module.split(".")[0]]
    return []


def check(root: Path) -> list[str]:
    out: list[str] = []
    for rel, banned, msg in RULES:
        base = root / rel
        if not base.exists():
            continue
        for py in sorted(base.rglob("*.py")):
            tree = ast.parse(py.read_text(), filename=str(py))
            for node in ast.walk(tree):
                for name in _roots(node):
                    if name in banned:
                        out.append(f"{py}:{node.lineno}: {msg} {name}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    violations = check(Path(ap.parse_args().root).resolve())
    for v in violations:
        print(v)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
