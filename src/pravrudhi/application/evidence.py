"""Render evidence documents from the ledger alone (make reproduce).

Deterministic: same ledger, same bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pravrudhi_kernel.ledger.verify import iter_events
from pravrudhi_kernel.stats import wilson_ci


def render_noise_floor(ledger: Path, variance: Path | None) -> str:
    rows = []
    design = None
    for ev in iter_events(ledger):
        p = ev.payload
        if ev.kind == "audit" and p.get("kind") == "study_start" and p.get("study") == "noise_floor":
            design = p.get("design")
        if ev.kind == "observe" and p.get("study") == "noise_floor":
            o = p["observed"]
            rows.append(
                (
                    ev.seq,
                    p.get("rotation_id"),
                    p.get("seed_index"),
                    o["value"],
                    o["n_items"],
                    p["hashes"]["model"][:12],
                    p.get("isolation"),
                    p.get("job", {}).get("tok_s"),
                )
            )
    lines = [
        "# L3 noise floor — rendered from research/ledger.jsonl",
        "",
        "**Label: model-measured, screen tier, single model (unmodified Qwen/Qwen3-4B), A/A design, isolation container.**",
        "",
    ]
    if design:
        lines += ["Design: " + ", ".join(f"{k}={v}" for k, v in sorted(design.items())), ""]
    lines += [
        "| seq | rotation | seed | pass_rate | n | model hash | isolation | tok/s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for seq, rot, seed, v, n, mh, iso, tps in rows:
        lines.append(
            f"| {seq} | {rot} | {seed} | {v:.4f} | {n} | {mh} | {iso} | {tps:.1f} |"
            if tps
            else f"| {seq} | {rot} | {seed} | {v:.4f} | {n} | {mh} | {iso} | |"
        )
    if rows:
        n_tot = sum(r[4] for r in rows)
        k = round(sum(r[3] * r[4] for r in rows))
        lo, hi = wilson_ci(int(k), n_tot)
        lines += [
            "",
            f"Runs: {len(rows)}; items scored: {n_tot}; pooled pass rate {k / n_tot:.4f}, Wilson 95% [{lo:.4f}, {hi:.4f}].",
        ]
    if variance and variance.exists():
        v = json.loads(variance.read_text())
        lines += [
            "",
            f"variance.json: sigma_seed={v['sigma_seed']:.4f} sigma_rot={v['sigma_rot']:.4f} "
            f"sigma_total={v['sigma_total']:.4f} "
            f"theta_surprise(|z| p99)={v['theta_surprise_abs_z_p99']}",
        ]
    return "\n".join(lines) + "\n"


def render_first_night(ledger: Path, night: int) -> str:
    """Per-candidate account of one night, from the ledger alone."""
    from collections import Counter

    cands: dict[str, dict[str, Any]] = {}
    audits: list[dict[str, Any]] = []
    spent = 0.0
    for ev in iter_events(ledger):
        if ev.night != night:
            continue
        p, cid = ev.payload, ev.candidate_id
        if ev.kind == "propose" and cid and cid != "c-0000":
            cands[cid] = {
                "strategy": p.get("strategy"),
                "family": p.get("edit_family"),
                "selected": False,
                "deltas": [],
                "boundary": None,
                "canary": None,
                "outcome": "proposed",
                "hetvabhasa": None,
                "brier": None,
            }
        elif ev.kind == "select" and cid in cands:
            cands[cid]["selected"] = True
        elif ev.kind == "spend":
            spent += float(p.get("gpu_h") or 0.0)
        elif ev.kind == "observe" and cid in cands and p.get("arm") == "candidate":
            cands[cid]["deltas"].append(float(p["observed"]["delta_in"]))
            cands[cid]["boundary"] = (p.get("stats") or {}).get("boundary")
            cands[cid]["brier"] = p.get("brier")
            cands[cid]["outcome"] = "observed"
        elif ev.kind == "prune" and cid in cands:
            cands[cid]["outcome"] = "pruned"
            cands[cid]["hetvabhasa"] = p.get("hetvabhasa")
        elif ev.kind == "promote" and cid in cands:
            cands[cid]["outcome"] = "promoted"
        elif ev.kind == "skip" and cid in cands:
            cands[cid]["outcome"] = f"skipped:{p.get('reason')}"
        elif ev.kind == "audit":
            k = p.get("kind")
            if k == "canary" and cid in cands:
                cands[cid]["canary"] = "pass" if p.get("severity") == "info" else "fail"
            if k in (
                "strategy_switch_rate",
                "rethink_checkpoint",
                "rethink_declined",
                "night_end",
                "samples_verified",
                "job_failed",
                "decorative_controller",
            ):
                audits.append(
                    {
                        "kind": k,
                        **{
                            kk: vv
                            for kk, vv in p.items()
                            if kk
                            in (
                                "switches",
                                "n",
                                "wilson",
                                "spent_gpu_h",
                                "outcomes",
                                "n_kept",
                                "kept_rate",
                                "consecutive",
                                "reason",
                                "run_id",
                            )
                        },
                    }
                )
    lines = [
        f"# L4 first night (night {night}) — rendered from research/ledger.jsonl",
        "",
        "**Label: model-measured, screen tier, one loop seed, paired on the same rotation and sampling seed; "
        "isolation container.**",
        "",
        "| candidate | strategy | family | selected | paired deltas | boundary | canary | outcome | hetvābhāsa | Brier |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for cid, c in cands.items():
        d = ", ".join(f"{x:+.3f}" for x in c["deltas"])
        b = "" if c["brier"] is None else f"{c['brier']:.3f}"
        lines.append(
            f"| {cid} | {c['strategy']} | {c['family']} | {'yes' if c['selected'] else ''} | {d} | {c['boundary'] or ''} | "
            f"{c['canary'] or ''} | {c['outcome']} | {c['hetvabhasa'] or ''} | {b} |"
        )
    outcomes = Counter(str(c["outcome"]) for c in cands.values())
    lines += [
        "",
        f"Candidates proposed: {len(cands)}; selected: {sum(1 for c in cands.values() if c['selected'])}; outcomes: "
        + ", ".join(f"{k}={v}" for k, v in sorted(outcomes.items()))
        + f"; GPU-hours charged (spend rows): {spent:.2f}.",
        "",
        "Audits:",
        "",
    ]
    for a in audits:
        lines.append("- " + ", ".join(f"{k}={v}" for k, v in a.items()))
    return "\n".join(lines) + "\n"
