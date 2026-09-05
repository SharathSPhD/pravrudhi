"""Deterministic golden ledgers: 5 ledgers, >=200 events each, every kind. Regenerable byte-for-byte."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np

from pravrudhi_kernel.ledger import LedgerWriter, replay, write_state


def make_clock(start: int) -> Callable[[], str]:
    n = [start]

    def tick() -> str:
        n[0] += 1
        s = n[0]
        day, hh, mm, ss = (s // 86400) % 20 + 4, (s // 3600) % 24, (s // 60) % 60, s % 60
        return f"2026-09-{day:02d}T{hh:02d}:{mm:02d}:{ss:02d}.000Z"

    return tick


def build(path: Path, seed: int) -> None:
    rng = np.random.default_rng(seed)
    w = LedgerWriter.open(path, "0.1.0", clock=make_clock(seed * 1000), glossary_hash="0" * 64)
    w.append("audit", "kernel", {"kind": "theta_surprise", "value": 3.0, "severity": "info"}, epoch=0, night=0)
    bucket = {"task_family": "gsm8k", "target_model": "Qwen/Qwen3-4B", "corpus": "gsm8k-train"}
    surfaces = ["W3.adapter", "W2.data", "H3.prompt"]
    families = ["optimiser", "adapter", "data_mixture"]
    cid_n = 0
    for night in range(1, 5):
        for cycle in range(1, 13):
            cid_n += 1
            cid = f"c-{cid_n:04d}"
            surf = surfaces[cid_n % 3]
            w.append(
                "propose",
                "proposer",
                {"op": "patch", "edit_family": families[cid_n % 3], "cost_estimate": {"gpu_h": 0.2}},
                epoch=0,
                night=night,
                cycle=cycle,
                candidate_id=cid,
                surface=surf,
                bucket=bucket,
                provenance="agama",
            )
            w.append(
                "predict",
                "proposer",
                {"predictor": "v1", "hash": "1" * 64},
                epoch=0,
                night=night,
                cycle=cycle,
                candidate_id=cid,
                surface=surf,
                bucket=bucket,
                provenance="agama",
            )
            if cid_n % 9 == 0:
                w.append(
                    "skip",
                    "executor",
                    {"reason": "residency", "detail": "no window", "never_repropose": False},
                    epoch=0,
                    night=night,
                    cycle=cycle,
                    candidate_id=cid,
                    surface=surf,
                )
                continue
            w.append(
                "select",
                "controller",
                {"G": float(rng.normal()), "Q": 0.3, "decorative": {"verdict": "pass"}},
                epoch=0,
                night=night,
                cycle=cycle,
                candidate_id=cid,
                surface=surf,
                bucket=bucket,
            )
            n_seeds = int(rng.integers(1, 4))
            for k in range(n_seeds):
                w.append(
                    "spend",
                    "executor",
                    {"gpu_h": round(float(rng.uniform(0.05, 0.3)), 4), "run_id": f"r-{cid_n}-{k}"},
                    epoch=0,
                    night=night,
                    cycle=cycle,
                    candidate_id=cid,
                    surface=surf,
                )
                d = round(float(rng.normal(0.01 * (cid_n % 4), 0.02)), 5)
                surprise = round(float(abs(rng.normal(0, 1.5))), 3)
                last = k == n_seeds - 1
                boundary = "continue" if not last else ("confirm" if d > 0.02 else "prune")
                w.append(
                    "observe",
                    "kernel",
                    {
                        "run_id": f"r-{cid_n}-{k}",
                        "seed_index": k,
                        "observed": {"delta_in": d, "n_items": 100, "seeds": [k]},
                        "hashes": {"harness_parent": "a" * 64},
                        "stats": {"boundary": boundary},
                        "surprise": surprise,
                        "brier": round(float(rng.uniform(0, 0.5)), 3),
                        "isolation": "container",
                        "measure_class": "model-measured",
                    },
                    epoch=0,
                    night=night,
                    cycle=cycle,
                    candidate_id=cid,
                    surface=surf,
                    bucket=bucket,
                    provenance="pratyaksha",
                )
                if surprise > 3.0:
                    w.append(
                        "reflect",
                        "proposer",
                        {"trigger": "surprise", "khyativada": "akhyati", "disposition": "remeasure"},
                        epoch=0,
                        night=night,
                        cycle=cycle,
                        candidate_id=cid,
                        surface=surf,
                    )
            if cid_n % 4 == 0:
                pack = f"research/inbox/{night}/{cid}"
                w.append(
                    "promote",
                    "broker",
                    {"tier": "T2", "merge_commit": "b" * 64, "tau_after": 0.6, "inbox_pack": pack},
                    epoch=0,
                    night=night,
                    cycle=cycle,
                    candidate_id=cid,
                    surface=surf,
                )
                if cid_n % 8 == 0:
                    w.append(
                        "signoff",
                        "human:sharath",
                        {"pack": pack, "decision": "approve", "scope": "promote_T2"},
                        epoch=0,
                        night=night,
                        candidate_id=cid,
                    )
            elif cid_n % 4 == 1:
                w.append(
                    "prune",
                    "kernel",
                    {"hetvabhasa": "asiddha", "by": "sequential", "status": "pruned"},
                    epoch=0,
                    night=night,
                    cycle=cycle,
                    candidate_id=cid,
                    surface=surf,
                )
            elif cid_n % 4 == 2:
                w.append(
                    "audit",
                    "auditor",
                    {"kind": "diff_tamper", "severity": "high", "detail": {}},
                    epoch=0,
                    night=night,
                    cycle=cycle,
                    candidate_id=cid,
                    surface=surf,
                )
            if cid_n % 10 == 0:
                w.append(
                    "sublate",
                    "kernel",
                    {"target": {"kind": "claim", "ref": "x"}, "reason": "precision"},
                    epoch=0,
                    night=night,
                    cycle=cycle,
                    candidate_id=cid,
                    provenance="pratyaksha",
                )
            if cid_n % 6 == 0:
                w.append(
                    "sensor",
                    "executor",
                    {"sensor": "entropy_budget", "value": 0.1, "badge": "exploratory"},
                    epoch=0,
                    night=night,
                    cycle=cycle,
                    provenance="anumana",
                )
    if seed % 2 == 0:
        w.append("audit", "kernel", {"kind": "paused_by_operator", "severity": "info"}, epoch=0, night=4)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for k in range(5):
        lp = out / f"ledger_{k}.jsonl"
        head = out / f"ledger_{k}.jsonl.head"
        lp.unlink(missing_ok=True)
        head.unlink(missing_ok=True)
        build(lp, seed=k + 1)
        write_state(replay(lp), out / f"state_{k}.json")
        head.unlink(missing_ok=True)
    print("golden written to", out)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "golden")
