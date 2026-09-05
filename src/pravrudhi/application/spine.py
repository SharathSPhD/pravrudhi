"""Shared execution-spine pieces for the engine: paths, model resolution, one kernel-launched eval job."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from pravrudhi_kernel.metrics import Rotation, score_completions
from pravrudhi_kernel.metrics.pool import read_item
from pravrudhi_kernel.sandbox import JobResult, JobSpec, KernelState, kernel_hashes, run_job
from pravrudhi_kernel.sandbox.observe import KernelHashes

IMAGE = "pravrudhi/exec-5090:latest"
SCORER_SOURCE = Path(__file__).resolve().parents[3] / "pravrudhi_kernel" / "src" / "pravrudhi_kernel" / "metrics" / "gsm8k.py"


def resolve_model_snapshot(repo_id: str, hf_home: Path | None = None) -> Path:
    """Local snapshot directory of a downloaded HF model (no network here; the container has none either)."""
    home = hf_home or Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    base = home / "hub" / f"models--{repo_id.replace('/', '--')}" / "snapshots"
    snaps = sorted(p for p in base.glob("*") if p.is_dir())
    if not snaps:
        raise FileNotFoundError(f"no local snapshot for {repo_id} under {base}; download it first")
    return snaps[-1]


def image_digest(image: str = IMAGE) -> str:
    out = subprocess.run(["docker", "images", "--no-trunc", "--format", "{{.ID}}", image], capture_output=True, text=True)
    return out.stdout.strip().splitlines()[0] if out.stdout.strip() else "unknown"


def write_job_inputs(job_dir: Path, pool_dir: Path, rot: Rotation, template: Path) -> tuple[Path, Path]:
    """Questions only. Gold answers stay in the kernel pool."""
    inp = job_dir / "in"
    inp.mkdir(parents=True, exist_ok=True)
    items = inp / "items.jsonl"
    with items.open("w") as fh:
        for i in rot.item_ids:
            it = read_item(pool_dir, i)
            fh.write(json.dumps({"id": it["id"], "question": it["question"]}) + "\n")
    tpl = inp / "template.txt"
    tpl.write_text(template.read_text())
    return items, tpl


def run_eval_job(
    state: KernelState,
    job_dir: Path,
    model_snapshot: Path,
    adapter_dir: Path | None,
    *,
    seed: int,
    temperature: float,
    max_new_tokens: int,
    batch_size: int,
    limit: int = 0,
    timeout_s: int = 3600,
) -> tuple[JobResult, dict[str, Any] | None]:
    hf_home = model_snapshot.parents[3]
    mounts = {str(job_dir / "in"): "/in", str(hf_home): "/models"}
    cont_model = "/models/" + str(model_snapshot.relative_to(hf_home))
    cmd = [
        "--model-dir",
        cont_model,
        "--seed",
        str(seed),
        "--temperature",
        str(temperature),
        "--max-new-tokens",
        str(max_new_tokens),
        "--batch-size",
        str(batch_size),
    ]
    if adapter_dir is not None:
        mounts[str(adapter_dir)] = "/adapter"
        cmd += ["--adapter-dir", "/adapter"]
    if limit:
        cmd += ["--limit", str(limit)]
    spec = JobSpec(
        image=IMAGE,
        command=cmd,
        mounts_ro=mounts,
        output_dir=str(job_dir / "out"),
        gpu=True,
        network=False,
        timeout_s=timeout_s,
        user=f"{os.getuid()}:{os.getgid()}",
        env={"HF_HOME": "/models", "HF_HUB_OFFLINE": "1"},
    )
    res = run_job(spec)
    meta_path = job_dir / "out" / "job_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
    return res, meta


def score_job(job_dir: Path, pool_dir: Path, rot: Rotation) -> tuple[dict[str, int], Path]:
    from pravrudhi_kernel.metrics import gold_answer

    comps: dict[str, str] = {}
    for line in (job_dir / "out" / "completions.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            comps[r["id"]] = r["completion"]
    golds = {i: gold_answer(read_item(pool_dir, i)["answer"]) for i in rot.item_ids}
    scores = score_completions(comps, golds)
    ref = job_dir / "out" / "per_item_scores.jsonl"
    ref.write_text("".join(json.dumps({"id": i, "score": s}) + "\n" for i, s in sorted(scores.items())))
    return scores, ref


def expected_hashes(job_dir: Path, pool_dir: Path, harness_dir: Path, model_snapshot: Path) -> KernelHashes:
    return kernel_hashes(job_dir / "in" / "items.jsonl", pool_dir / "manifest.json", SCORER_SOURCE, harness_dir, model_snapshot)
