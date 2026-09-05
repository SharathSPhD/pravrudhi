"""Seal a benchmark pool from a parquet file into the kernel's pools directory (an operator act, done
once)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pravrudhi_kernel.metrics import seal_pool
from pravrudhi_kernel.sandbox import ensure_kernel_state
from pravrudhi_kernel.sandbox.runner import docker_available


def seal_gsm8k(root: Path, parquet: Path, bench: str = "gsm8k-test", offset: int = 0, count: int | None = None) -> dict[str, Any]:
    import pyarrow.parquet as pq

    state = ensure_kernel_state(root, docker_available=docker_available())
    rows = pq.read_table(parquet).to_pylist()
    rows = rows[offset : (offset + count) if count else None]
    src = {
        "file": parquet.name,
        "sha256": hashlib.sha256(parquet.read_bytes()).hexdigest(),
        "n_rows": len(rows),
        "origin": "https://huggingface.co/datasets/openai/gsm8k (MIT)",
    }
    return seal_pool(Path(state.pools_dir) / bench, bench, rows, src)


def seal_mbpp_plus(root: Path, cache: Path, bench: str = "mbppplus") -> dict[str, Any]:
    """Seal EvalPlus MBPP+ (378 problems) as a kernel pool from the exported JSONL in the external cache: question =
    the EvalPlus prompt (with its visible example assert), answer = JSON naming the task and entry point; hidden tests
    run only inside the sandbox scorer job."""
    import json

    src_file = Path(cache) / f"{bench}.jsonl"
    rows = []
    for line in src_file.read_text().splitlines():
        if line.strip():
            pr = json.loads(line)
            rows.append(
                {
                    "question": pr["prompt"],
                    "answer": json.dumps(
                        {k: pr[k] for k in ("task_id", "entry_point", "canonical_solution", "n_base", "n_plus")}
                    ),
                }
            )
    state = ensure_kernel_state(root, docker_available=docker_available())
    src = {
        "file": src_file.name,
        "sha256": hashlib.sha256(src_file.read_bytes()).hexdigest(),
        "n_rows": len(rows),
        "origin": "EvalPlus MBPP+ v0.2.0 (Apache-2.0), exported from the evalplus package",
    }
    return seal_pool(Path(state.pools_dir) / bench, bench, rows, src)
