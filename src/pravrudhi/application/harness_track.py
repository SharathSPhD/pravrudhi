"""Track H: a fixed model, a mutable harness, MBPP+ hidden tests scored in the sandbox. Same ledger, same boundary."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from pravrudhi_kernel.ledger import LedgerWriter, replay
from pravrudhi_kernel.metrics import PoolExhausted, Rotation, draw_rotation, record_exposure
from pravrudhi_kernel.metrics.pool import read_item
from pravrudhi_kernel.sandbox import JobSpec, KernelState, admit_observation, ensure_kernel_state, run_job
from pravrudhi_kernel.sandbox.observe import KernelHashes, kernel_hashes, sha256_file
from pravrudhi_kernel.sandbox.runner import docker_available
from pravrudhi_kernel.sandbox.state import read_secret
from pravrudhi_kernel.stats import Variance, sequential_boundary

from pravrudhi.application.deliberate import DecorativeAbort, deliberate
from pravrudhi.application.propose import propose_generic, strategy_switch_rate
from pravrudhi.application.spine import IMAGE, resolve_model_snapshot
from pravrudhi.models.llama_server import LlamaServer
from pravrudhi.targets.harness_grammar import BASELINE, H_GRAMMAR_DOC, HarnessRecipe, parse_harness

EXT_IMAGE = "pravrudhi/ext-scorers:latest"
SCORER_SOURCE = Path(__file__).resolve().parents[3] / "docker" / "jobs" / "score_code.py"
Log = Callable[[str], None]
BASELINE_ID = "c-0000"


class HarnessContext:
    def __init__(self, root: Path, cfg: dict[str, Any], night: int, log: Log) -> None:
        self.root, self.cfg, self.night, self.log = root, cfg, night, log
        self.state: KernelState = ensure_kernel_state(root, docker_available=docker_available())
        self.snapshot = resolve_model_snapshot(str(cfg["model"]))
        self.hf_home = self.snapshot.parents[3]
        self.pool_dir = root / ".pravrudhi" / "kernel" / "pools" / str(cfg["bench"])
        self.incumbent_id = BASELINE_ID
        self.incumbent: HarnessRecipe = BASELINE
        self.spent_gpu_h = 0.0
        self.sealed = _load_sealed(root / ".pravrudhi" / "kernel" / "sealed" / "predictions")
        vf = root / "research" / "prereg" / "variance_harness.json"
        self.variance: Variance | None = None
        if vf.exists():
            v = json.loads(vf.read_text())
            b = cfg["boundary"]
            dm = max(2 * float(v["sigma_seed"]), float(b["delta_min_floor"]))
            self.variance = Variance.model_validate(
                {
                    "bench": str(v["bench"]),
                    "sigma_seed": max(float(v["sigma_seed"]), 1e-4),
                    "tau": dm,
                    "delta_min": dm,
                    "alpha_eff": float(b["alpha_eff"]),
                    "alpha_fut": float(b["alpha_fut"]),
                    "k_max": int(b["k_max"]),
                    "sigma_mode": str(b["sigma_mode"]),
                    "n0": int(b["n0"]),
                }
            )
        self.bucket = {"task_family": str(cfg["bench"]), "target_model": str(cfg["model"]), "corpus": "mbppplus"}

    def job_dir(self, tag: str) -> Path:
        d = Path(self.state.jobs_dir) / f"h{self.night}-{tag}-{int(time.time() * 1000) % 10**8}"
        (d / "in").mkdir(parents=True, exist_ok=True)
        (d / "out").mkdir(parents=True, exist_ok=True)
        return d


def _load_sealed(d: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if d.exists():
        for p in sorted(d.glob("*.jsonl")):
            for line in p.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    out[r["candidate_id"]] = r
    return out


def run_agent(
    ctx: HarnessContext, harness: HarnessRecipe, rot: Rotation, seed: int, tag: str
) -> tuple[Path, Any, dict[str, Any] | None]:
    jd = ctx.job_dir(f"agent-{tag}")
    with (jd / "in" / "items.jsonl").open("w") as fh:
        for i in rot.item_ids:
            it = read_item(ctx.pool_dir, i)
            fh.write(json.dumps({"id": it["id"], "question": it["question"]}) + "\n")
    (jd / "in" / "harness.json").write_text(json.dumps(harness.harness_json(), sort_keys=True))
    cont_model = "/models/" + str(ctx.snapshot.relative_to(ctx.hf_home))
    spec = JobSpec(
        image=IMAGE,
        command=["agent_code", "--model-dir", cont_model, "--seed", str(seed), "--batch-size", "16"],
        mounts_ro={str(jd / "in"): "/in", str(ctx.hf_home): "/models"},
        output_dir=str(jd / "out"),
        gpu=True,
        network=False,
        timeout_s=5400,
        user=f"{os.getuid()}:{os.getgid()}",
        env={"HF_HOME": "/models", "HF_HUB_OFFLINE": "1"},
    )
    res = run_job(spec)
    ctx.spent_gpu_h += res.wall_s / 3600.0
    meta_p = jd / "out" / "job_meta.json"
    return jd, res, (json.loads(meta_p.read_text()) if meta_p.exists() else None)


def score_agent(ctx: HarnessContext, jd: Path, rot: Rotation) -> tuple[dict[str, int], Path, Any]:
    """Kernel-launched hidden-test execution in the scorers image: no network, no GPU, disposable."""
    sd = ctx.job_dir(f"score-{jd.name[-8:]}")
    (sd / "in" / "samples.jsonl").write_text((jd / "out" / "samples.jsonl").read_text())
    with (sd / "in" / "answers.jsonl").open("w") as fh:
        for i in rot.item_ids:
            fh.write(json.dumps({"id": i, "task_id": json.loads(read_item(ctx.pool_dir, i)["answer"])["task_id"]}) + "\n")
    spec = JobSpec(
        image=EXT_IMAGE,
        command=["python", "/opt/pravrudhi/jobs/score_code.py"],
        mounts_ro={str(sd / "in"): "/in", str(ctx.root / ".pravrudhi" / "ext_cache"): "/cache"},
        output_dir=str(sd / "out"),
        gpu=False,
        network=False,
        timeout_s=1800,
        user=f"{os.getuid()}:{os.getgid()}",
        env={"HOME": "/cache", "HF_HOME": "/cache"},
    )
    res = run_job(spec)
    scores: dict[str, int] = {}
    sp = sd / "out" / "scores.jsonl"
    if sp.exists():
        for line in sp.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                scores[r["id"]] = int(r["score"])
    for i in rot.item_ids:
        scores.setdefault(i, 0)
    ref = sd / "out" / "per_item_scores.jsonl"
    ref.write_text("".join(json.dumps({"id": i, "score": s}) + "\n" for i, s in sorted(scores.items())))
    return scores, ref, res


def _hashes(ctx: HarnessContext, jd: Path, harness: HarnessRecipe) -> KernelHashes:
    h = kernel_hashes(
        jd / "in" / "items.jsonl", ctx.pool_dir / "manifest.json", SCORER_SOURCE, ctx.root / "harness", ctx.snapshot
    )
    return h.model_copy(
        update={"harness": hashlib.sha256(json.dumps(harness.harness_json(), sort_keys=True).encode()).hexdigest()}
    )


def paired_eval(
    ctx: HarnessContext, w: LedgerWriter, cid: str, cand: HarnessRecipe, seed: int, k: int, stage: str = "screen"
) -> tuple[float, float, int]:
    rot = draw_rotation(
        ctx.pool_dir,
        ctx.night,
        f"{cid}-s{seed}",
        read_secret(ctx.state),
        k=k,
        exposure_cap=int(ctx.cfg["evaluation"]["exposure_cap"]),
    )
    record_exposure(ctx.pool_dir, rot)
    ijd, ires, imeta = run_agent(ctx, ctx.incumbent, rot, seed, f"inc-{cid}")
    cjd, cres, cmeta = run_agent(ctx, cand, rot, seed, f"cand-{cid}")
    if ires.exit_code != 0 or cres.exit_code != 0 or imeta is None or cmeta is None:
        w.append(
            "audit",
            "kernel",
            {
                "kind": "job_failed",
                "severity": "high",
                "detail": "paired agent run failed",
                "inc_exit": ires.exit_code,
                "cand_exit": cres.exit_code,
                "stderr_tail": (cres.stderr_tail or ires.stderr_tail)[-800:],
            },
            epoch=0,
            night=ctx.night,
            candidate_id=cid,
            surface="H3.prompt",
        )
        raise RuntimeError("agent run failed")
    iscores, iref, isres = score_agent(ctx, ijd, rot)
    cscores, cref, csres = score_agent(ctx, cjd, rot)
    iv = sum(iscores.values()) / len(iscores)
    cv = sum(cscores.values()) / len(cscores)
    ih, ch = _hashes(ctx, ijd, ctx.incumbent), _hashes(ctx, cjd, cand)
    imeta["items_sha256"], cmeta["items_sha256"] = ih.items, ch.items
    admit_observation(
        w,
        expected=ih,
        job_meta=imeta,
        per_item_scores=iscores,
        per_item_ref=str(iref),
        run_id=ijd.name,
        candidate_id=ctx.incumbent_id,
        surface="H3.prompt",
        bucket=ctx.bucket,
        epoch=0,
        night=ctx.night,
        cycle=None,
        seed=seed,
        rotation_id=rot.rotation_id,
        value_ref=None,
        cost_gpu_h=ires.wall_s / 3600,
        wall_s=ires.wall_s,
        peak_gib=ires.peak_gib_smi,
        isolation=ctx.state.isolation,
        stage=stage,
        extra={"arm": "incumbent", "paired_with": cid, "track": "harness", "score_job": isres.exit_code},
    )
    return iv, cv, len(cscores)  # candidate row is written by the caller once the boundary is known


def admit_candidate(
    ctx: HarnessContext,
    w: LedgerWriter,
    cid: str,
    cand: HarnessRecipe,
    cjd_scores: tuple[dict[str, int], Path, Any, dict[str, Any], Path],
    seed: int,
    rot_id: str,
    iv: float,
    br: Any,
    extra: dict[str, Any],
) -> None:
    cscores, cref, csres, cmeta, cjd = cjd_scores
    ch = _hashes(ctx, cjd, cand)
    cmeta["items_sha256"] = ch.items
    admit_observation(
        w,
        expected=ch,
        job_meta=cmeta,
        per_item_scores=cscores,
        per_item_ref=str(cref),
        run_id=cjd.name,
        candidate_id=cid,
        surface="H3.prompt",
        bucket=ctx.bucket,
        epoch=0,
        night=ctx.night,
        cycle=None,
        seed=seed,
        rotation_id=rot_id,
        value_ref=iv,
        cost_gpu_h=0.0,
        wall_s=0.0,
        peak_gib=None,
        isolation=ctx.state.isolation,
        stage="screen",
        extra={
            "arm": "candidate",
            "track": "harness",
            "stats": {
                "boundary": br.decision,
                "e_value": br.e_value,
                "xbar": br.xbar,
                "halfwidth": br.halfwidth,
                "sigma_used": br.sigma_used,
                "n": br.n,
            },
            **extra,
        },
    )
