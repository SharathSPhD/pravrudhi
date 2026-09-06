#!/usr/bin/env python3
"""Proposal-stage orchestrator for the math-reasoning baseline-evaluation step.

Shells out to the external `lm_eval` CLI (lm-evaluation-harness) once per task
declared in tasks.yaml, against $BASE_MODEL. Writes each task's own JSON output
under ./results/. Does not recompute, rename, or otherwise touch the metrics
that lm_eval reports.

This script produces a PROPOSAL artifact only: nothing it writes may be cited
as a measured result, and it never touches the ledger, research/, gates/ or
pravrudhi_kernel/.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TASKS_FILE = HERE / "tasks.yaml"
DEFAULT_RESULTS_DIR = HERE / "results"


def load_tasks(tasks_file: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            "PyYAML is required to read tasks.yaml (pip install pyyaml)."
        ) from exc
    with tasks_file.open() as f:
        return yaml.safe_load(f)


def build_lm_eval_command(
    *,
    base_model: str,
    task_name: str,
    num_fewshot: int,
    limit: int | None,
    seed: int,
    output_path: Path,
    model_args_extra: str,
) -> list[str]:
    model_args = f"pretrained={base_model}"
    if model_args_extra:
        model_args = f"{model_args},{model_args_extra}"
    cmd = [
        "lm_eval",
        "--model",
        "hf",
        "--model_args",
        model_args,
        "--tasks",
        task_name,
        "--num_fewshot",
        str(num_fewshot),
        "--seed",
        str(seed),
        "--output_path",
        str(output_path),
    ]
    if limit is not None:
        cmd += ["--limit", str(limit)]
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-model", default=os.environ.get("BASE_MODEL"))
    parser.add_argument("--tasks-file", type=Path, default=DEFAULT_TASKS_FILE)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument(
        "--model-args-extra",
        default=os.environ.get("LM_EVAL_MODEL_ARGS_EXTRA", ""),
        help="Extra comma-separated hf model_args, e.g. dtype=bfloat16",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the lm_eval commands that would run without executing them.",
    )
    args = parser.parse_args()

    if not args.base_model:
        parser.error("--base-model or $BASE_MODEL must be set")

    if shutil.which("lm_eval") is None and not args.dry_run:
        print(
            "lm_eval (lm-evaluation-harness) was not found on PATH.\n"
            "Install the declared external evaluation tool with:\n"
            "  pip install lm-eval\n",
            file=sys.stderr,
        )
        return 1

    config = load_tasks(args.tasks_file)
    seed = config.get("seed", 1234)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    exit_code = 0
    for task in config["tasks"]:
        output_path = args.results_dir / task["name"]
        cmd = build_lm_eval_command(
            base_model=args.base_model,
            task_name=task["name"],
            num_fewshot=task.get("num_fewshot", 0),
            limit=task.get("limit"),
            seed=seed,
            output_path=output_path,
            model_args_extra=args.model_args_extra,
        )
        print(f"[{task['name']}] {' '.join(cmd)}")
        if args.dry_run:
            continue
        result = subprocess.run(cmd)
        if result.returncode != 0:
            exit_code = result.returncode

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
