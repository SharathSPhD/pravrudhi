"""Seal a benchmark pool from a parquet file into the kernel's pools directory (an operator act, done
once)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pravrudhi_kernel.metrics import seal_pool
from pravrudhi_kernel.sandbox import ensure_kernel_state
from pravrudhi_kernel.sandbox.runner import docker_available


def seal_gsm8k(root: Path, parquet: Path, bench: str = "gsm8k-test") -> dict[str, Any]:
    import pyarrow.parquet as pq

    state = ensure_kernel_state(root, docker_available=docker_available())
    rows = pq.read_table(parquet).to_pylist()
    src = {
        "file": parquet.name,
        "sha256": hashlib.sha256(parquet.read_bytes()).hexdigest(),
        "n_rows": len(rows),
        "origin": "https://huggingface.co/datasets/openai/gsm8k (MIT)",
    }
    return seal_pool(Path(state.pools_dir) / bench, bench, rows, src)
