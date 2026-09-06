#!/usr/bin/env python3
"""Print the metrics lm-evaluation-harness itself reported for the
math-reasoning baseline-evaluation proposal.

Reads the JSON files lm_eval writes under a results directory and prints each
task's metric name/value exactly as the harness computed it. Does not
recompute, round-and-forget, or rename anything — this is a read-only view
onto the external tool's own output.

Proposal-stage only: the numbers printed here are not a ledger entry.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_result_files(results_dir: Path) -> list[Path]:
    return sorted(results_dir.rglob("results.json")) or sorted(
        results_dir.rglob("*.json")
    )


def iter_task_metrics(result_file: Path):
    with result_file.open() as f:
        payload = json.load(f)
    results = payload.get("results", {})
    for task_name, metrics in results.items():
        for metric_name, value in metrics.items():
            if metric_name.endswith("_stderr") or not isinstance(
                value, (int, float)
            ):
                continue
            yield task_name, metric_name, value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_dir",
        type=Path,
        help="Directory produced by run_baseline_eval.py (contains lm_eval JSON output)",
    )
    args = parser.parse_args()

    if not args.results_dir.exists():
        print(f"No such directory: {args.results_dir}", file=sys.stderr)
        return 1

    result_files = find_result_files(args.results_dir)
    if not result_files:
        print(f"No lm_eval JSON output found under {args.results_dir}", file=sys.stderr)
        return 1

    print("PROPOSAL-STAGE SUMMARY (not a ledger entry) — as reported by lm_eval:\n")
    for result_file in result_files:
        for task_name, metric_name, value in iter_task_metrics(result_file):
            print(f"  {task_name:12s} {metric_name:20s} {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
