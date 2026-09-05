"""Pool paired McNemar discordance across datasets (HumanEval+, MBPP+, ...).

A single external benchmark leaves the harness track's win/loss count too small to be statistically distinguishable
from chance (see `application/discordance.py`). Pooling every dataset's paired pass/fail vectors into one binomial
test uses the same held-out items more fully without inventing evidence: each pair is still base vs. candidate on
the same item and seed, just drawn from more than one benchmark. Task ids are prefixed by dataset before pooling so
that HumanEval's "HumanEval/2" and a hypothetical dataset's own "2" can never be merged into the same key.

usage: uv run python scripts/pool_discordance.py <dataset> <base_eval_results.json> <candidate_eval_results.json> [...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pravrudhi.application.discordance import Discordance, discordance


def _pass_vector(path: Path) -> dict[str, int]:
    """Read an EvalPlus `*_eval_results.json`; plus-pass is base pass AND plus pass, per `application/external.py`."""
    rows = json.loads(path.read_text())["eval"]
    return {
        task_id: int(v[0]["base_status"] == "pass" and v[0]["plus_status"] == "pass") for task_id, v in rows.items()
    }


def _prefixed(dataset: str, vector: dict[str, int]) -> dict[str, int]:
    return {f"{dataset}:{task_id}": v for task_id, v in vector.items()}


def pool(pairs: list[tuple[str, Path, Path]]) -> Discordance:
    """Pool per-item pass vectors from every (dataset, base_results, candidate_results) triple into one Discordance."""
    incumbent: dict[str, int] = {}
    candidate: dict[str, int] = {}
    for dataset, base_path, candidate_path in pairs:
        incumbent.update(_prefixed(dataset, _pass_vector(base_path)))
        candidate.update(_prefixed(dataset, _pass_vector(candidate_path)))
    return discordance(incumbent, candidate)


def per_dataset(pairs: list[tuple[str, Path, Path]]) -> dict[str, Discordance]:
    """The same pairs, scored one dataset at a time, for the breakdown alongside the pooled total."""
    return {
        dataset: discordance(_pass_vector(base_path), _pass_vector(candidate_path))
        for dataset, base_path, candidate_path in pairs
    }


def _render(label: str, d: Discordance) -> str:
    return (
        f"{label}: n={d.n} concordant={d.concordant} wins={d.wins} losses={d.losses} "
        f"delta={d.delta:+.4f} p_mcnemar={d.p_mcnemar:.4f} or=[{d.or_lower:.4f}, {d.or_upper:.4f}]"
    )


def main(argv: list[str]) -> int:
    if len(argv) < 3 or len(argv) % 3 != 0:
        print(__doc__, file=sys.stderr)
        return 2
    pairs = [
        (argv[i], Path(argv[i + 1]), Path(argv[i + 2])) for i in range(0, len(argv), 3)
    ]
    for dataset, d in per_dataset(pairs).items():
        print(_render(dataset, d))
    print(_render("pooled", pool(pairs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
