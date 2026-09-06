"""Track H: a fixed model, a mutable harness, MBPP+ hidden tests scored in the sandbox. Same ledger, same boundary."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from pravrudhi.application.deliberate import DecorativeAbort, deliberate
from pravrudhi.application.discordance import discordance
from pravrudhi.application.propose import next_candidate_id, propose_generic, strategy_switch_rate
from pravrudhi.application.spine import IMAGE, resolve_model_snapshot
from pravrudhi.models.proposer import proposer_client
from pravrudhi.targets.harness_grammar import BASELINE, H_GRAMMAR_DOC, HarnessRecipe, harness_array_schema, parse_harness
from pravrudhi_kernel.ledger import LedgerWriter, replay
from pravrudhi_kernel.metrics import PoolExhausted, Rotation, draw_rotation, record_exposure
from pravrudhi_kernel.metrics.pool import read_item
from pravrudhi_kernel.sandbox import JobSpec, KernelState, admit_observation, ensure_kernel_state, run_job
from pravrudhi_kernel.sandbox.observe import KernelHashes, kernel_hashes, sha256_file
from pravrudhi_kernel.sandbox.runner import docker_available
from pravrudhi_kernel.sandbox.state import read_secret
from pravrudhi_kernel.stats import Variance, sequential_boundary

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
                    "min_n_confirm": int(b.get("min_n_confirm", 1)),
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
    incumbent_scores: dict[str, int],
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
        cost_gpu_h=float(extra.get("wall_s_candidate") or 0.0) / 3600,
        wall_s=float(extra.get("wall_s_candidate") or 0.0),
        peak_gib=None,
        isolation=ctx.state.isolation,
        stage="screen",
        extra={
            "arm": "candidate",
            "track": "harness",
            "discordance": asdict(discordance(incumbent_scores, cscores)),
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


def harness_noise_floor(root: Path, *, rotations: int, seeds: int, k: int, night: int, log: Log = print) -> dict[str, Any]:
    """A/A of the baseline harness on the MBPP+ pool: sigma_seed for the harness track's boundary."""
    import math

    cfg = yaml.safe_load((root / "research" / "prereg" / "harness_night.yaml").read_text())
    ctx = HarnessContext(root, cfg, night, log)
    w = LedgerWriter.open(root / "research" / "ledger.jsonl", "0.1.0")
    w.append(
        "audit",
        "kernel",
        {
            "kind": "study_start",
            "severity": "info",
            "study": "harness_noise_floor",
            "design": {"rotations": rotations, "seeds": seeds, "k": k, "model": cfg["model"], "bench": cfg["bench"]},
        },
        epoch=0,
        night=night,
    )
    values: dict[str, list[float]] = {}
    ref: float | None = None
    for r in range(rotations):
        rot = draw_rotation(
            ctx.pool_dir,
            night,
            f"{BASELINE_ID}-h{r}",
            read_secret(ctx.state),
            k=k,
            exposure_cap=int(cfg["evaluation"]["exposure_cap"]),
        )
        record_exposure(ctx.pool_dir, rot)
        for s in range(seeds):
            jd, res, meta = run_agent(ctx, BASELINE, rot, s, f"nf-r{r}-s{s}")
            if res.exit_code != 0 or meta is None:
                log(f"rotation {r} seed {s}: agent FAILED {res.stderr_tail[-300:]}")
                continue
            scores, sref, sres = score_agent(ctx, jd, rot)
            h = _hashes(ctx, jd, BASELINE)
            meta["items_sha256"] = h.items
            _, obs = admit_observation(
                w,
                expected=h,
                job_meta=meta,
                per_item_scores=scores,
                per_item_ref=str(sref),
                run_id=jd.name,
                candidate_id=BASELINE_ID,
                surface="H3.prompt",
                bucket=ctx.bucket,
                epoch=0,
                night=night,
                cycle=None,
                seed=s,
                rotation_id=rot.rotation_id,
                value_ref=ref,
                cost_gpu_h=res.wall_s / 3600,
                wall_s=res.wall_s,
                peak_gib=res.peak_gib_smi,
                isolation=ctx.state.isolation,
                stage="screen",
                extra={"study": "harness_noise_floor", "track": "harness", "rotation_index": r},
            )
            v = obs.payload["observed"]["value"]
            ref = v if ref is None else ref
            values.setdefault(rot.rotation_id, []).append(v)
            log(f"rotation {r} seed {s}: plus_pass={v:.4f} n={k} seq={obs.seq} wall={res.wall_s:.0f}s")
    allv = [x for vs in values.values() for x in vs]
    within = [math.sqrt(sum((x - sum(vs) / len(vs)) ** 2 for x in vs) / (len(vs) - 1)) for vs in values.values() if len(vs) >= 2]
    sigma_seed = math.sqrt(sum(x * x for x in within) / len(within)) if within else 0.0
    means = [sum(vs) / len(vs) for vs in values.values()]
    sigma_rot = math.sqrt(sum((m - sum(means) / len(means)) ** 2 for m in means) / (len(means) - 1)) if len(means) > 1 else 0.0
    out = {
        "bench": cfg["bench"],
        "model": cfg["model"],
        "study": "harness_noise_floor",
        "n_runs": len(allv),
        "mean_plus_pass": sum(allv) / max(1, len(allv)),
        "sigma_seed": sigma_seed,
        "sigma_rot": sigma_rot,
        "k_items": k,
        "labels": "model-measured, screen tier, baseline harness A/A",
    }
    (root / "research" / "prereg" / "variance_harness.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    w.append(
        "audit",
        "kernel",
        {"kind": "study_end", "severity": "info", "study": "harness_noise_floor", "summary": out},
        epoch=0,
        night=night,
    )
    return out


def load_seed_recipes(paths: Iterable[Path]) -> tuple[HarnessRecipe, ...]:
    """Operator-supplied harness recipes, parsed through the same grammar gate a proposer candidate must pass."""
    recipes: list[HarnessRecipe] = []
    for path in paths:
        parsed = parse_harness(json.loads(Path(path).read_text()))
        if isinstance(parsed, str):
            raise ValueError(f"{path}: {parsed}")
        recipes.append(parsed)
    return tuple(recipes)


def _admit_seed(
    w: LedgerWriter, night: int, cid: str, rec: HarnessRecipe, incumbent_id: str, bucket: dict[str, str], surface: str
) -> None:
    """The propose row a seed recipe needs to enter paired eval like any proposer candidate (never promoted here)."""
    key = json.dumps(rec.model_dump(exclude={"rationale"}), sort_keys=True)
    w.append(
        "propose",
        "human:operator",
        {
            "op": "harness",
            "source": "operator-seed",
            "rationale": rec.rationale,
            "recipe": rec.model_dump(),
            "strategy": rec.strategy,
            "edit_family": rec.execution_family,
            "vak": {"para": rec.rationale[:400], "pasyanti": key[:600]},
            "diff": {"sha256": hashlib.sha256(key.encode()).hexdigest()},
            "cost_estimate": {"gpu_h": rec.cost_est_gpu_h()},
            "lineage": [incumbent_id],
        },
        epoch=0,
        night=night,
        candidate_id=cid,
        surface=surface,
        bucket=bucket,
        provenance="agama",
    )


def run_harness_night(
    root: Path, *, night: int, k: int | None, budget_gpu_h: float | None, gguf: Path, log: Log = print,
    selection_policy: str | None = None,
    proposer_endpoint: str = "",
    seed_recipes: tuple[HarnessRecipe, ...] = (),
) -> dict[str, Any]:
    cfg = yaml.safe_load((root / "research" / "prereg" / "harness_night.yaml").read_text())
    ctx = HarnessContext(root, cfg, night, log)
    if ctx.variance is None:
        raise RuntimeError("run the harness noise floor first (research/prereg/variance_harness.json)")
    budget = float(budget_gpu_h if budget_gpu_h is not None else cfg["budget"]["night_gpu_h"])
    kk = int(k if k is not None else cfg["proposer"]["k_candidates"])
    policy = str(selection_policy or cfg.get("selection_policy", "efe"))
    ledger = root / "research" / "ledger.jsonl"
    w = LedgerWriter.open(ledger, "0.1.0")
    # incumbent = latest promoted harness on this surface whose promotion was not withdrawn, else baseline
    from pravrudhi_kernel.ledger.replay import withdrawn_observations
    from pravrudhi_kernel.ledger.verify import iter_events

    withdrawn = withdrawn_observations(ledger)
    for ev in iter_events(ledger):
        if ev.kind == "promote" and ev.surface == "H3.prompt" and ev.payload.get("harness") and ev.seq not in withdrawn:
            inc_parsed = parse_harness(ev.payload["harness"])
            if not isinstance(inc_parsed, str):
                ctx.incumbent, ctx.incumbent_id = inc_parsed, str(ev.candidate_id)
    w.append(
        "audit",
        "kernel",
        {
            "kind": "night_start",
            "severity": "info",
            "track": "harness",
            "selection_policy": policy,
            "budget_gpu_h": budget,
            "k": kk,
            "incumbent": ctx.incumbent_id,
            "prereg_sha256": {
                "harness_night": sha256_file(root / "research" / "prereg" / "harness_night.yaml"),
                "variance_harness": sha256_file(root / "research" / "prereg" / "variance_harness.json"),
            },
        },
        epoch=0,
        night=night,
    )
    recipes: dict[str, HarnessRecipe] = {}
    for seed_rec in seed_recipes:
        cid = next_candidate_id(ledger)
        _admit_seed(w, night, cid, seed_rec, ctx.incumbent_id, ctx.bucket, "H3.prompt")
        recipes[cid] = seed_rec
    already = sum(1 for ev in iter_events(ledger) if ev.kind == "propose" and ev.night == night and ev.surface == "H3.prompt")
    remaining_k = kk - len(seed_recipes)
    if remaining_k > 0 and already < kk:
        endpoint = proposer_endpoint or str(cfg["proposer"].get("endpoint", ""))
        with proposer_client(
            gguf, ctx=int(cfg["proposer"]["max_tokens"]) * 2 + 8192, endpoint=endpoint, log=log
        ) as client:
            acc = propose_generic(
                root,
                w,
                client,
                night=night,
                k=remaining_k,
                model=str(cfg["model"]),
                bucket=ctx.bucket,
                prompts_dir=root / "harness" / "prompts",
                sealed_dir=root / ".pravrudhi" / "kernel" / "sealed" / "predictions",
                incumbent_id=ctx.incumbent_id,
                sigma_seed=ctx.variance.sigma_seed,
                temperature=float(cfg["proposer"]["temperature"]),
                max_tokens=int(cfg["proposer"]["max_tokens"]),
                rethink_m=int(cfg["rethink_m"]),
                log=log,
                grammar_doc=H_GRAMMAR_DOC,
                parse_fn=parse_harness,
                prompt_file="harness_proposer/v1.md",
                surface="H3.prompt",
                op="harness",
                json_schema=harness_array_schema(remaining_k),
                extra_context="Incumbent harness (the reference every candidate is paired against):\n"
                + json.dumps(ctx.incumbent.harness_json(), indent=1, sort_keys=True),
            )
            recipes.update(dict(acc))
    outcomes: dict[str, str] = {}
    from pravrudhi.application.citta_view import build_citta

    for rnd in range(int(cfg.get("max_rounds", 4))):
        remaining = budget - ctx.spent_gpu_h
        if remaining <= 0.05:
            break
        try:
            order = deliberate(
                root,
                w,
                night=night,
                budget_gpu_h=remaining,
                sigma_seed=ctx.variance.sigma_seed,
                incumbent_id=ctx.incumbent_id,
                harness_hash=hashlib.sha256(json.dumps(ctx.incumbent.harness_json(), sort_keys=True).encode()).hexdigest(),
                model_hash="0" * 64,
                rng_seed=night * 100 + rnd,
                log=log,
                round_index=rnd,
                selection_policy=policy,
                surface="H3.prompt",
                target_model=str(cfg["model"]),
            )
        except DecorativeAbort as e:
            w.append(
                "audit",
                "kernel",
                {"kind": "night_end", "severity": "high", "reason": "decorative_controller", "track": "harness"},
                epoch=0,
                night=night,
            )
            return {"night": night, "status": "aborted", "reason": str(e)}
        if not order:
            break
        log(f"round {rnd + 1}: {len(order)} selected, {remaining:.2f} GPU-h remaining")
        _, meta = build_citta(ledger, root / ".pravrudhi" / "kernel" / "sealed" / "predictions", sigma2_eval=1e-4, tau0_2=0.01)
        for cid in order:
            if ctx.spent_gpu_h >= budget:
                outcomes[cid] = "skipped:budget"
                continue
            rec = recipes.get(cid)
            if rec is None:
                parsed = parse_harness(meta[cid]["recipe"] or {})
                if isinstance(parsed, str):
                    outcomes[cid] = "skipped:bad_recipe"
                    continue
                rec = parsed
                recipes[cid] = parsed
            try:
                outcomes[cid] = _execute_one(ctx, w, cid, rec, int(cfg["evaluation"]["k_items"]))
            except PoolExhausted as e:
                w.append(
                    "audit",
                    "kernel",
                    {"kind": "pool_exhausted", "severity": "high", "detail": str(e)},
                    epoch=0,
                    night=night,
                    candidate_id=cid,
                    surface="H3.prompt",
                )
                outcomes[cid] = "skipped:pool_exhausted"
                break
            except RuntimeError as e:
                outcomes[cid] = f"failed:{e}"
    sw, n, ci = strategy_switch_rate(ledger)
    w.append(
        "audit",
        "controller",
        {"kind": "strategy_switch_rate", "severity": "info", "switches": sw, "n": n, "wilson": list(ci)},
        epoch=0,
        night=night,
    )
    w.append(
        "audit",
        "kernel",
        {
            "kind": "night_end",
            "severity": "info",
            "track": "harness",
            "spent_gpu_h": ctx.spent_gpu_h,
            "budget_gpu_h": budget,
            "outcomes": outcomes,
            "incumbent": ctx.incumbent_id,
            "incumbent_harness": ctx.incumbent.harness_json(),
        },
        epoch=0,
        night=night,
    )
    log(f"harness night {night} closed: spent {ctx.spent_gpu_h:.2f}/{budget}; outcomes {outcomes}; incumbent {ctx.incumbent_id}")
    return {
        "night": night,
        "status": "closed",
        "spent_gpu_h": ctx.spent_gpu_h,
        "outcomes": outcomes,
        "incumbent": ctx.incumbent_id,
    }


def _execute_one(ctx: HarnessContext, w: LedgerWriter, cid: str, rec: HarnessRecipe, k: int) -> str:
    st = replay(ctx.root / "research" / "ledger.jsonl")
    xs_prev = list(st.candidates[cid].xs) if cid in st.candidates else []
    seed = len(xs_prev)
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
    cjd, cres, cmeta = run_agent(ctx, rec, rot, seed, f"cand-{cid}")
    if ires.exit_code != 0 or cres.exit_code != 0 or imeta is None or cmeta is None:
        w.append(
            "audit",
            "kernel",
            {"kind": "job_failed", "severity": "high", "stderr_tail": (cres.stderr_tail or ires.stderr_tail)[-800:]},
            epoch=0,
            night=ctx.night,
            candidate_id=cid,
            surface="H3.prompt",
        )
        raise RuntimeError("agent run failed")
    iscores, iref, _ = score_agent(ctx, ijd, rot)
    cscores, cref, csres = score_agent(ctx, cjd, rot)
    iv, cv = sum(iscores.values()) / len(iscores), sum(cscores.values()) / len(cscores)
    delta = cv - iv
    assert ctx.variance is not None
    br = sequential_boundary([*xs_prev, delta], ctx.variance)
    ih = _hashes(ctx, ijd, ctx.incumbent)
    imeta["items_sha256"] = ih.items
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
        stage="screen",
        extra={"arm": "incumbent", "paired_with": cid, "track": "harness"},
    )
    sealed = ctx.sealed.get(cid)
    brier = None
    predicted = None
    if sealed:
        predicted = {"delta_in": sealed["delta_in"], "delta_out": None, "conf": sealed["conf"], "hash": sealed["hash"]}
        brier = (sealed["conf"] - (1.0 if (sealed["delta_in"] >= 0) == (delta >= 0) else 0.0)) ** 2
    admit_candidate(
        ctx,
        w,
        cid,
        rec,
        (cscores, cref, csres, cmeta, cjd),
        seed,
        rot.rotation_id,
        iv,
        br,
        {"predicted": predicted, "brier": brier, "wall_s_candidate": cres.wall_s, "harness": rec.harness_json()},
        incumbent_scores=iscores,
    )
    ctx.log(
        f"{cid}: seed {seed} incumbent={iv:.3f} candidate={cv:.3f} delta={delta:+.3f} "
        f"boundary={br.decision} (n={br.n}, E={br.e_value:.2f})"
    )
    if br.decision == "prune":
        w.append(
            "prune",
            "kernel",
            {
                "hetvabhasa": br.hetvabhasa or "asiddha",
                "reason": f"sequential boundary at n={br.n}",
                "stage": "screen",
                "boundary": "prune",
                "by": "sequential",
                "status": "pruned",
            },
            epoch=0,
            night=ctx.night,
            candidate_id=cid,
            surface="H3.prompt",
        )
        return "pruned"
    if br.decision == "confirm":
        pack = ctx.root / "research" / "inbox" / f"harness-night{ctx.night}" / cid
        pack.mkdir(parents=True, exist_ok=True)
        (pack / "README.md").write_text(
            f"# Harness promotion {cid}\n\n```json\n{json.dumps(rec.harness_json(), indent=2)}\n```\n"
        )
        w.append(
            "promote",
            "broker",
            {
                "tier": "T2",
                "from_worktree": str(pack),
                "merge_commit": hashlib.sha256(json.dumps(rec.harness_json(), sort_keys=True).encode()).hexdigest(),
                "tag": f"harness-night{ctx.night}-{cid}",
                "lineage": [ctx.incumbent_id],
                "tau_before": 0.5,
                "tau_after": 0.6,
                "inbox_pack": str(pack),
                "harness": rec.harness_json(),
                "regression": {"pass3": None, "wilson_lo": None, "flips": 0},
                "holm": {"m": 1, "rank": 1, "p_adj": None},
            },
            epoch=0,
            night=ctx.night,
            candidate_id=cid,
            surface="H3.prompt",
        )
        ctx.incumbent, ctx.incumbent_id = rec, cid
        (ctx.root / "harness" / "agent").mkdir(parents=True, exist_ok=True)
        (ctx.root / "harness" / "agent" / "harness.json").write_text(
            json.dumps(rec.harness_json(), indent=2, sort_keys=True) + "\n"
        )
        ctx.log(f"{cid}: PROMOTED harness (T2); now the incumbent")
        return "promoted"
    return "continue"
