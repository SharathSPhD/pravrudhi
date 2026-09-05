"""One night: deliberation window (proposer resident) -> controller selection -> execution windows -> close."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from pravrudhi.application.deliberate import DecorativeAbort, deliberate
from pravrudhi.application.execute import NightContext, evaluate_and_dispose, train
from pravrudhi.application.propose import propose, strategy_switch_rate
from pravrudhi.application.spine import resolve_model_snapshot
from pravrudhi.models.proposer import proposer_client
from pravrudhi.targets import LoraRecipe
from pravrudhi_kernel.ledger import LedgerWriter
from pravrudhi_kernel.sandbox import ensure_kernel_state
from pravrudhi_kernel.sandbox.observe import model_dir_hash, sha256_tree
from pravrudhi_kernel.sandbox.runner import docker_available


def load_train_rows(parquet: Path) -> list[dict[str, str]]:
    import pyarrow.parquet as pq

    return [{"question": str(r["question"]), "answer": str(r["answer"])} for r in pq.read_table(parquet).to_pylist()]


def run_night(
    root: Path,
    *,
    night: int,
    budget_gpu_h: float | None,
    k: int | None,
    train_parquet: Path,
    gguf: Path,
    log: Callable[[str], None] = print,
    selection_policy: str | None = None,
    proposer_endpoint: str = "",
) -> dict[str, Any]:
    cfg = yaml.safe_load((root / "research" / "prereg" / "lora_night.yaml").read_text())
    policy = str(selection_policy or cfg.get("selection_policy", "efe"))
    var = json.loads((root / "research" / "prereg" / "variance.json").read_text())
    budget = float(budget_gpu_h if budget_gpu_h is not None else cfg["budget"]["night_gpu_h"])
    k = int(k if k is not None else cfg["proposer"]["k_candidates"])
    state = ensure_kernel_state(root, docker_available=docker_available())
    if state.isolation != "container":
        raise RuntimeError("a night requires container isolation")
    snap = resolve_model_snapshot(str(cfg["model"]))
    pool_dir = root / ".pravrudhi" / "kernel" / "pools" / str(cfg["bench"])
    ledger = root / "research" / "ledger.jsonl"
    w = LedgerWriter.open(ledger, "0.1.0")
    bucket = {
        "task_family": str(cfg["bench"]),
        "target_model": str(cfg["model"]),
        "corpus": f"{cfg['bench']}-train",
    }
    ctx = NightContext(root, state, snap, pool_dir, cfg, var, load_train_rows(train_parquet), night, log)
    w.append(
        "audit",
        "kernel",
        {
            "kind": "night_start",
            "severity": "info",
            "track": "lora",
            "selection_policy": policy,
            "budget_gpu_h": budget,
            "k": k,
            "incumbent": ctx.incumbent_id,
            "prereg_sha256": {
                "lora_night": _sha(root / "research" / "prereg" / "lora_night.yaml"),
                "variance": _sha(root / "research" / "prereg" / "variance.json"),
                "canaries": _sha(root / "research" / "prereg" / "canaries.md"),
            },
        },
        epoch=0,
        night=night,
    )
    # 1. deliberation window: proposer resident, nothing else (skipped when this night already holds >= k proposals,
    #    so a relaunch after a failure does not double the pool)
    from pravrudhi_kernel.ledger.verify import iter_events

    already = sum(1 for ev in iter_events(ledger) if ev.kind == "propose" and ev.night == night and ev.candidate_id != "c-0000")
    accepted: list[tuple[str, LoraRecipe]] = []
    endpoint = proposer_endpoint or str(cfg["proposer"].get("endpoint", ""))
    if already >= k:
        log(f"deliberation window: {already} proposals already in the ledger for night {night}; not proposing again")
    else:
        with proposer_client(
            gguf, ctx=int(cfg["proposer"]["max_tokens"]) * 2 + 8192, endpoint=endpoint, log=log
        ) as client:
            accepted = propose(
                root,
                w,
                client,
                night=night,
                k=k,
                model=str(cfg["model"]),
                bucket=bucket,
                prompts_dir=root / "harness" / "prompts",
                sealed_dir=root / ".pravrudhi" / "kernel" / "sealed" / "predictions",
                incumbent_id=ctx.incumbent_id,
                sigma_seed=ctx.sigma_seed,
                temperature=float(cfg["proposer"]["temperature"]),
                max_tokens=int(cfg["proposer"]["max_tokens"]),
                rethink_m=int(cfg["rethink_m"]),
                log=log,
            )
    recipes: dict[str, LoraRecipe] = dict(accepted)
    # 2 + 3. rounds of selection and execution until the budget or the pool is exhausted; a candidate that returned
    #        `continue` is live again in the next round and receives its next seed (adapter re-used, not retrained)
    outcomes: dict[str, str] = {}
    max_rounds = int(cfg.get("max_rounds", 4))
    for rnd in range(max_rounds):
        remaining = budget - ctx.spent_gpu_h
        if remaining <= 0.05:
            break
        try:
            order = deliberate(
                root,
                w,
                night=night,
                budget_gpu_h=remaining,
                sigma_seed=ctx.sigma_seed,
                incumbent_id=ctx.incumbent_id,
                harness_hash=sha256_tree(root / "harness"),
                model_hash=model_dir_hash(snap),
                rng_seed=night * 100 + rnd,
                log=log,
                round_index=rnd,
                selection_policy=policy,
            )
        except DecorativeAbort as e:
            log(f"night aborted: decorative controller ({e})")
            w.append(
                "audit",
                "kernel",
                {"kind": "night_end", "severity": "high", "reason": "decorative_controller"},
                epoch=0,
                night=night,
            )
            return {"night": night, "status": "aborted", "reason": str(e)}
        if not order:
            break
        log(f"round {rnd + 1}: {len(order)} selected, {remaining:.2f} GPU-h remaining")
        for cid in order:
            if ctx.spent_gpu_h >= budget:
                w.append(
                    "skip",
                    "executor",
                    {"reason": "budget", "detail": f"spent {ctx.spent_gpu_h:.2f} >= {budget}", "never_repropose": False},
                    epoch=0,
                    night=night,
                    candidate_id=cid,
                    surface="W3.adapter",
                )
                outcomes[cid] = "skipped:budget"
                continue
            rec = recipes.get(cid)
            if rec is None:
                from pravrudhi.application.citta_view import build_citta
                from pravrudhi.targets import parse_recipe

                _, meta = build_citta(
                    ledger, root / ".pravrudhi" / "kernel" / "sealed" / "predictions", sigma2_eval=1e-4, tau0_2=0.01
                )
                r = parse_recipe(meta[cid]["recipe"] or {})
                if isinstance(r, str):
                    outcomes[cid] = "skipped:bad_recipe"
                    continue
                rec = r
                recipes[cid] = rec
            adapter = train(ctx, w, cid, rec)
            if adapter is None:
                outcomes[cid] = "failed:train"
                continue
            outcomes[cid] = evaluate_and_dispose(ctx, w, cid, rec, adapter)
    # 4. close
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
            "spent_gpu_h": ctx.spent_gpu_h,
            "budget_gpu_h": budget,
            "outcomes": outcomes,
            "incumbent": ctx.incumbent_id,
        },
        epoch=0,
        night=night,
    )
    log(f"night {night} closed: spent {ctx.spent_gpu_h:.2f}/{budget} GPU-h; outcomes {outcomes}; incumbent {ctx.incumbent_id}")
    return {
        "night": night,
        "status": "closed",
        "spent_gpu_h": ctx.spent_gpu_h,
        "outcomes": outcomes,
        "incumbent": ctx.incumbent_id,
    }


def _sha(p: Path) -> str:
    import hashlib

    return hashlib.sha256(p.read_bytes()).hexdigest()


def inbox_listing(root: Path) -> list[dict[str, Any]]:
    from pravrudhi_kernel.ledger import replay

    st = replay(root / "research" / "ledger.jsonl")
    out = []
    for p in sorted((root / "research" / "inbox").glob("*/*/README.md")) if (root / "research" / "inbox").exists() else []:
        cid = p.parent.name
        out.append(
            {
                "pack": str(p.parent),
                "candidate": cid,
                "badge": st.badges.get(cid),
                "night": p.parent.parent.name,
                "signed": any(s.get("pack") == str(p.parent) for s in st.signoffs),
            }
        )
    return out
