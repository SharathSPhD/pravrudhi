#!/usr/bin/env python3
"""Candidate-vs-baseline comparison for the candidate-evaluation step.

This is a PROPOSAL script. Nothing it prints or writes is a measured
result: it only becomes one once the pravrudhi_kernel/gates pipeline runs
it against real objective/benchmark/result artifacts and records the
output through the ledger. Any numbers in the example configs under
../configs/ are fabricated for the purpose of exercising this script.

Input contract (see ../README.md for the full schema description):

  objective.json
    {
      "objective_id": str,
      "uncertainty_rule": {
        "hard_constraint_metrics": [str, ...],   # candidate may never regress these
        "confidence_level": float,               # e.g. 0.95
        "min_sample_count": int                  # informational, see README
      }
    }

  benchmarks.json
    {
      "benchmarks": [
        {
          "name": str,
          "metrics": [
            {"name": str, "direction": "maximize" | "minimize", "target": float | null}
          ]
        },
        ...
      ]
    }

  baseline_results.json / retrieval_candidate.json (same shape)
    {
      "benchmark_results": {
        "<benchmark_name>": {
          "<metric_name>": {"value": float, "n": int}
        }
      }
    }

Output: candidate_comparison.json written to --out, structured as
described in ../README.md.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def wilson_interval(value: float, n: int, confidence_level: float) -> tuple[float, float]:
    """Wilson score interval for a proportion metric.

    Non-proportion metrics (value outside [0, 1] or n <= 0) fall back to a
    zero-width interval, which makes the CI-overlap check degrade to a
    plain not-equal comparison rather than silently mis-treating them as
    proportions.
    """
    if n <= 0 or not (0.0 <= value <= 1.0):
        return (value, value)
    z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(round(confidence_level, 2), 1.96)
    denom = 1 + z * z / n
    centre = value + z * z / (2 * n)
    half = z * math.sqrt((value * (1 - value) + z * z / (4 * n)) / n)
    lo = (centre - half) / denom
    hi = (centre + half) / denom
    return (max(0.0, lo), min(1.0, hi))


def intervals_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def compare_metric(
    metric_name: str,
    direction: str,
    target: float | None,
    baseline: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    confidence_level: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "metric": metric_name,
        "direction": direction,
        "target": target,
    }

    if baseline is None or candidate is None:
        result["verdict"] = "missing_data"
        result["baseline_value"] = baseline.get("value") if baseline else None
        result["candidate_value"] = candidate.get("value") if candidate else None
        return result

    b_val, b_n = baseline["value"], baseline.get("n", 0)
    c_val, c_n = candidate["value"], candidate.get("n", 0)
    result["baseline_value"] = b_val
    result["candidate_value"] = c_val
    result["delta"] = c_val - b_val

    sign = 1.0 if direction == "maximize" else -1.0
    favored_delta = sign * (c_val - b_val)

    b_ci = wilson_interval(b_val, b_n, confidence_level)
    c_ci = wilson_interval(c_val, c_n, confidence_level)
    overlap = intervals_overlap(b_ci, c_ci)
    result["baseline_ci"] = list(b_ci)
    result["candidate_ci"] = list(c_ci)

    if overlap:
        result["verdict"] = "inconclusive"
    elif favored_delta > 0:
        result["verdict"] = "improved"
    else:
        result["verdict"] = "regressed"

    if target is not None:
        meets_target = (c_val >= target) if direction == "maximize" else (c_val <= target)
        result["meets_target"] = meets_target

    return result


def evaluate(
    objective: dict,
    benchmarks: dict,
    baseline_results: dict,
    candidate_results: dict,
) -> dict:
    uncertainty_rule = objective.get("uncertainty_rule", {})
    confidence_level = uncertainty_rule.get("confidence_level", 0.95)
    hard_constraints = set(uncertainty_rule.get("hard_constraint_metrics", []))

    per_benchmark = []
    hard_constraint_violations = []
    improved_count = 0
    regressed_count = 0

    for bench in benchmarks.get("benchmarks", []):
        bname = bench["name"]
        b_bench = baseline_results.get("benchmark_results", {}).get(bname, {})
        c_bench = candidate_results.get("benchmark_results", {}).get(bname, {})

        metric_rows = []
        for metric in bench.get("metrics", []):
            mname = metric["name"]
            row = compare_metric(
                mname,
                metric["direction"],
                metric.get("target"),
                b_bench.get(mname),
                c_bench.get(mname),
                confidence_level,
            )
            row["is_hard_constraint"] = mname in hard_constraints
            metric_rows.append(row)

            if row.get("verdict") == "improved":
                improved_count += 1
            elif row.get("verdict") == "regressed":
                regressed_count += 1
                if mname in hard_constraints:
                    hard_constraint_violations.append({"benchmark": bname, "metric": mname})

        per_benchmark.append({"benchmark": bname, "metrics": metric_rows})

    if hard_constraint_violations:
        overall_verdict = "reject_candidate_hard_constraint"
    elif improved_count > 0 and regressed_count == 0:
        overall_verdict = "prefer_candidate"
    elif regressed_count > 0 and improved_count == 0:
        overall_verdict = "prefer_baseline"
    elif improved_count > 0 and regressed_count > 0:
        overall_verdict = "mixed_inconclusive"
    else:
        overall_verdict = "inconclusive"

    return {
        "_disclaimer": (
            "PROPOSAL OUTPUT: not a ledger result. Produced by "
            "proposals/prabhasa-nyaya/candidate-evaluation/scripts/evaluate.py."
        ),
        "objective_id": objective.get("objective_id"),
        "confidence_level": confidence_level,
        "hard_constraint_metrics": sorted(hard_constraints),
        "per_benchmark": per_benchmark,
        "hard_constraint_violations": hard_constraint_violations,
        "improved_metric_count": improved_count,
        "regressed_metric_count": regressed_count,
        "overall_verdict": overall_verdict,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--benchmarks", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    objective = load_json(args.objective)
    benchmarks = load_json(args.benchmarks)
    baseline_results = load_json(args.baseline)
    candidate_results = load_json(args.candidate)

    comparison = evaluate(objective, benchmarks, baseline_results, candidate_results)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(comparison, fh, indent=2)
        fh.write("\n")

    print(f"wrote {args.out} (overall_verdict={comparison['overall_verdict']})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
