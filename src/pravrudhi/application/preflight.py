"""`pravrudhi preflight`: measure, never quote. Writes research/prereg/measured_stack.json from one real
job."""

from __future__ import annotations

import json
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pravrudhi.application.spine import (
    IMAGE,
    image_digest,
    resolve_model_snapshot,
    run_eval_job,
    write_job_inputs,
)
from pravrudhi_kernel.metrics import draw_rotation
from pravrudhi_kernel.sandbox import ensure_kernel_state
from pravrudhi_kernel.sandbox.runner import docker_available
from pravrudhi_kernel.sandbox.state import read_secret


def preflight(
    root: Path, *, model: str, bench_pool: Path, template: Path, n_items: int = 32, batch_size: int = 16
) -> dict[str, Any]:
    state = ensure_kernel_state(root, docker_available=docker_available())
    snap = resolve_model_snapshot(model)
    rot = draw_rotation(bench_pool, 0, "c-0000", read_secret(state), k=n_items, exposure_cap=10**6)
    job_dir = Path(state.jobs_dir) / f"preflight-{int(time.time())}"
    write_job_inputs(job_dir, bench_pool, rot, template)
    res, meta = run_eval_job(state, job_dir, snap, None, seed=0, temperature=0.0, max_new_tokens=256, batch_size=batch_size)
    if res.exit_code != 0 or meta is None:
        raise RuntimeError(f"preflight job failed (exit {res.exit_code}): {res.stderr_tail[-1500:]}")
    smi = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    out = {
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": platform.node(),
        "gpu": smi,
        "image": IMAGE,
        "image_digest": image_digest(),
        "model": model,
        "snapshot": snap.name,
        "dtype": meta["dtype"],
        "torch": meta["torch"],
        "cuda": meta["cuda"],
        "transformers": meta["transformers"],
        "n_items": meta["n_items"],
        "batch_size": batch_size,
        "max_new_tokens": 256,
        "temperature": 0.0,
        "peak_gib_torch_allocated": round(meta["peak_gib_torch"], 3),
        "peak_gib_nvidia_smi": round(res.peak_gib_smi, 3) if res.peak_gib_smi is not None else None,
        "load_s": round(meta["load_s"], 2),
        "gen_s": round(meta["gen_s"], 2),
        "tokens_generated": meta["tokens_generated"],
        "tok_s_batched": round(meta["tok_s"], 1) if meta["tok_s"] else None,
        "wall_s_container": round(res.wall_s, 2),
        "isolation": state.isolation,
        "job_dir": str(job_dir),
        "note": (
            "batched decode throughput at the stated batch size; single-stream tok/s is lower. Every field measured on this card."
        ),
    }
    dest = root / "research" / "prereg" / "measured_stack.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out
