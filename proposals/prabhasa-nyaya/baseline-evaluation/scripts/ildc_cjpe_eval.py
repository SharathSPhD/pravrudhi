"""Thin wrapper around the ILDC / CJPE official evaluation harness.

CJPE (Court Judgment Prediction with Explanation, Malik et al. 2021,
`Exploration-Lab/CJPE`, built on the ILDC corpus) defines its own
prediction-accuracy and explanation-overlap metrics. As with
`iltur_eval.py`, this wrapper passes those metrics through unchanged.

Install (pin the real version before running for real):
    uv pip install ildc-cjpe-eval==<PIN_ME>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import ToolResult, now_iso

PACKAGE_NAME = "ildc-cjpe-eval"


def run(
    tasks: list[str],
    base_model: str,
    sample_count: int,
    dataset_cache_dir: Path,
    seed: int,
) -> ToolResult:
    """Invoke the CJPE harness for each declared task and merge its metrics.

    As in iltur_eval.py, the actual package import/call is left as the
    implementation step for when this proposal is promoted — not faked here.
    """
    try:
        import ildc_cjpe_eval as cjpe  # type: ignore[import-not-found]
    except ImportError as exc:
        return ToolResult.failed(
            tool_name="ildc_cjpe",
            tool_version="unknown",
            base_model=base_model,
            sample_count=sample_count,
            error=f"ildc-cjpe-eval package not installed: {exc}",
        )

    metrics: dict[str, float] = {}
    for task in tasks:
        task_metrics = cjpe.evaluate(  # type: ignore[attr-defined]
            task=task,
            model=base_model,
            n_samples=sample_count,
            cache_dir=str(dataset_cache_dir),
            seed=seed,
        )
        for metric_name, value in task_metrics.items():
            metrics[f"{task}.{metric_name}"] = value

    return ToolResult(
        tool_name="ildc_cjpe",
        tool_version=getattr(cjpe, "__version__", "unknown"),
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
