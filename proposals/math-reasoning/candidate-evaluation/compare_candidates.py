#!/usr/bin/env python3
"""Candidate-vs-baseline comparison for the 'candidate-evaluation' step.

PROPOSAL ONLY. This script never touches the ledger, research/, gates/, or
pravrudhi_kernel/; it reads the four declared inputs (objective, benchmarks,
baseline_results, rl_candidate) from plain JSON files given on the command
line and writes a candidate_comparison.json next to wherever the caller
points --out. Nothing it prints or writes is a measured result -- the
numbers under example_inputs/ are illustrative placeholders, not data from
an actual run.

Input contracts assumed by this script (see README.md "Input contracts"
for the reasoning -- these are proposed shapes, not read off an existing
schema, because this task is scoped to not survey the repository):

objective.json:
    {
      "id": "...",
      "uncertainty_rule": {
        "type": "wilson_diff" | "none",
        "confidence": 0.95
      }
    }

benchmarks.json:
    [
      {
        "name": "gsm8k",
        "metric": "accuracy",
        "direction": "maximize",   # or "minimize"
        "target": 0.02,            # optional
        "target_type": "delta"     # "delta" (candidate-baseline) or "absolute"
      },
      ...
    ]

baseline_results.json / rl_candidate.json:
    {
      "gsm8k": {"metric": "accuracy", "correct": 554, "n": 1319},
      ...
    }
    A benchmark entry may omit "correct"/"n" and give "value" directly;
    in that case no confidence interval can be computed for it and the
    comparison falls back to a point-estimate-only verdict, flagged as such.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from stats import newcombe_diff_interval, wilson_interval

SUPPORTED_UNCERTAINTY_RULES = {"wilson_diff", "none"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_value_and_counts(entry: dict) -> tuple[float, int | None, int | None]:
    if "correct" in entry and "n" in entry:
        n = int(entry["n"])
        correct = int(entry["correct"])
        return correct / n, correct, n
    if "value" in entry:
        return float(entry["value"]), None, None
    raise ValueError(f"result entry has neither value nor correct/n: {entry}")


def compare_benchmark(
    bench: dict, baseline_entry: dict, candidate_entry: dict, uncertainty_rule: dict
) -> dict:
    name = bench["name"]
    direction = bench["direction"]
    if direction not in ("maximize", "minimize"):
        raise ValueError(f"benchmark {name!r}: direction must be maximize/minimize")

    b_value, b_correct, b_n = resolve_value_and_counts(baseline_entry)
    c_value, c_correct, c_n = resolve_value_and_counts(candidate_entry)
    delta = c_value - b_value
    signed_delta = delta if direction == "maximize" else -delta

    result: dict[str, Any] = {
        "benchmark": name,
        "metric": bench["metric"],
        "direction": direction,
        "baseline_value": b_value,
        "candidate_value": c_value,
        "delta": delta,
        "improved_point_estimate": signed_delta > 0,
    }

    rule_type = uncertainty_rule.get("type", "none")
    confidence = uncertainty_rule.get("confidence", 0.95)
    if rule_type not in SUPPORTED_UNCERTAINTY_RULES:
        result["uncertainty_warning"] = (
            f"objective declared uncertainty_rule.type={rule_type!r}, which this "
            f"proposal script does not implement; falling back to 'wilson_diff' "
            f"if counts are available, else 'none'. Extend this script to add it."
        )
        rule_type = "wilson_diff" if (b_correct is not None and c_correct is not None) else "none"

    if rule_type == "wilson_diff" and b_correct is not None and c_correct is not None:
        diff_ci = newcombe_diff_interval(b_correct, b_n, c_correct, c_n, confidence)
        signed_low = diff_ci.low if direction == "maximize" else -diff_ci.high
        signed_high = diff_ci.high if direction == "maximize" else -diff_ci.low
        result["confidence"] = confidence
        result["diff_ci_low"] = diff_ci.low
        result["diff_ci_high"] = diff_ci.high
        result["baseline_ci"] = list(wilson_interval(b_correct, b_n, confidence).__dict__.values())
        result["candidate_ci"] = list(wilson_interval(c_correct, c_n, confidence).__dict__.values())
        # "Distinguishable" means the CI on the direction-aware delta excludes zero,
        # i.e. we can't explain the gap by noise at the declared confidence level.
        result["distinguishable_from_noise"] = signed_low > 0 or signed_high < 0
        result["improved_with_confidence"] = signed_low > 0
    else:
        result["uncertainty_note"] = (
            "no per-item correct/n counts supplied for this benchmark; "
            "reporting the point-estimate delta only, no confidence claim."
        )
        result["distinguishable_from_noise"] = None
        result["improved_with_confidence"] = None

    target = bench.get("target")
    if target is not None:
        target_type = bench.get("target_type", "delta")
        if target_type == "delta":
            result["meets_target"] = signed_delta >= target
        elif target_type == "absolute":
            candidate_signed = c_value if direction == "maximize" else -c_value
            target_signed = target if direction == "maximize" else -target
            result["meets_target"] = candidate_signed >= target_signed
        else:
            raise ValueError(f"benchmark {name!r}: unknown target_type {target_type!r}")
        result["target"] = target
        result["target_type"] = target_type
    else:
        result["meets_target"] = None

    return result


def build_comparison(objective: dict, benchmarks: list[dict], baseline: dict, candidate: dict) -> dict:
    uncertainty_rule = objective.get("uncertainty_rule", {"type": "none"})
    per_benchmark = []
    for bench in benchmarks:
        name = bench["name"]
        if name not in baseline:
            raise KeyError(f"baseline_results missing benchmark {name!r}")
        if name not in candidate:
            raise KeyError(f"rl_candidate missing benchmark {name!r}")
        per_benchmark.append(compare_benchmark(bench, baseline[name], candidate[name], uncertainty_rule))

    # A candidate only counts as strictly better if every declared benchmark
    # either improved (or held, for benchmarks without a target) and none
    # regressed with confidence -- this is what "without losing what it
    # already knew" cashes out to across a benchmark suite.
    any_regression_with_confidence = any(
        b["improved_with_confidence"] is False and b["distinguishable_from_noise"]
        for b in per_benchmark
    )
    all_targets_met = all(b["meets_target"] is not False for b in per_benchmark)
    overall_pass = all_targets_met and not any_regression_with_confidence

    return {
        "objective_id": objective.get("id"),
        "uncertainty_rule_applied": uncertainty_rule,
        "per_benchmark": per_benchmark,
        "any_regression_with_confidence": any_regression_with_confidence,
        "all_targets_met": all_targets_met,
        "overall_pass": overall_pass,
        "note": (
            "This is a PROPOSAL-generated comparison, not a ledger result. "
            "Every number above traces to whatever was in the input files "
            "given on the command line."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--objective", type=Path, required=True)
    parser.add_argument("--benchmarks", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Where to write candidate_comparison.json")
    args = parser.parse_args(argv)

    objective = load_json(args.objective)
    benchmarks = load_json(args.benchmarks)
    baseline = load_json(args.baseline)
    candidate = load_json(args.candidate)

    comparison = build_comparison(objective, benchmarks, baseline, candidate)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, sort_keys=True)

    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0 if comparison["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
