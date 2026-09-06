"""Thin wrapper around the IL-TUR official evaluation harness.

IL-TUR (Indian Legal Text Understanding and Reasoning benchmark,
Kapoor et al. 2024, `Exploration-Lab/IL-TUR`) already defines its own
per-task metrics. This wrapper's job is to call the official harness and
pass its reported numbers through unchanged — it must not recompute or
rename any metric, or the point of using an external tool as a check is
lost.

Install (pin the real version before running for real):
    uv pip install il-tur==<PIN_ME>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import ToolResult, now_iso

PACKAGE_NAME = "il-tur"


def run(
    tasks: list[str],
    base_model: str,
    sample_count: int,
    dataset_cache_dir: Path,
    seed: int,
) -> ToolResult:
    """Invoke the IL-TUR harness for each declared task and merge its metrics.

    Left unimplemented in this proposal: the actual import of the `il_tur`
    package and its harness entry point. Filling this in is implementation
    work for when this step leaves proposal status, not something to fake
    here with placeholder numbers.
    """
    try:
        import il_tur  # type: ignore[import-not-found]
    except ImportError as exc:
        return ToolResult.failed(
            tool_name="il_tur",
            tool_version="unknown",
            base_model=base_model,
            sample_count=sample_count,
            error=f"il-tur package not installed: {exc}",
        )

    metrics: dict[str, float] = {}
    for task in tasks:
        task_metrics = il_tur.evaluate(  # type: ignore[attr-defined]
            task=task,
            model=base_model,
            n_samples=sample_count,
            cache_dir=str(dataset_cache_dir),
            seed=seed,
        )
        for metric_name, value in task_metrics.items():
            metrics[f"{task}.{metric_name}"] = value

    return ToolResult(
        tool_name="il_tur",
        tool_version=getattr(il_tur, "__version__", "unknown"),
        base_model=base_model,
        sample_count=sample_count,
        metrics=metrics,
        timestamp=now_iso(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", action="append", dest="tasks", required=True)
    parser.add_argument("--base-model", type=str, required=True)
    parser.add_argument("--sample-count", type=int, default=200)
    parser.add_argument("--dataset-cache-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = run(
        tasks=args.tasks,
        base_model=args.base_model,
        sample_count=args.sample_count,
        dataset_cache_dir=args.dataset_cache_dir,
        seed=args.seed,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
