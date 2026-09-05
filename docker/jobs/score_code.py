"""Kernel-launched scorer for the harness track: executes EvalPlus hidden tests (base + plus) for MBPP+ solutions.
Reads /in/samples.jsonl (id, solution) and /in/answers.jsonl (id, task_id); writes /out/scores.jsonl (id, base, plus, score).
Runs with no network; EvalPlus data is read from the mounted cache. CPU-only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default="/in/samples.jsonl")
    ap.add_argument("--answers", default="/in/answers.jsonl")
    ap.add_argument("--out", default="/out")
    ap.add_argument("--dataset", default="mbpp")
    a = ap.parse_args()
    os.environ.setdefault("HF_HOME", "/cache")
    from evalplus.data import get_mbpp_plus, get_mbpp_plus_hash
    from evalplus.evaluate import check_correctness, get_groundtruth
    from evalplus.eval._special_oracle import MBPP_OUTPUT_NOT_NONE_TASKS

    problems = get_mbpp_plus()
    expected = get_groundtruth(problems, get_mbpp_plus_hash(), MBPP_OUTPUT_NOT_NONE_TASKS)
    id2task = {
        json.loads(line)["id"]: json.loads(line)["task_id"] for line in Path(a.answers).read_text().splitlines() if line.strip()
    }
    rows = []
    for line in Path(a.samples).read_text().splitlines():
        if not line.strip():
            continue
        s = json.loads(line)
        tid = id2task[s["id"]]
        res = check_correctness(
            a.dataset,
            0,
            problems[tid],
            s["solution"],
            expected[tid],
            base_only=False,
            fast_check=True,
            identifier=s["id"],
            min_time_limit=1.0,
            gt_time_limit_factor=4.0,
        )
        base_ok = res["base"][0] == "pass"
        plus_ok = base_ok and res["plus"][0] == "pass"
        rows.append({"id": s["id"], "base": int(base_ok), "plus": int(plus_ok), "score": int(plus_ok)})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    out.joinpath("scores.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    n = len(rows)
    print(
        json.dumps(
            {"n": n, "base_pass": sum(r["base"] for r in rows) / max(1, n), "plus_pass": sum(r["plus"] for r in rows) / max(1, n)}
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
