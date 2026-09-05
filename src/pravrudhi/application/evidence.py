"""Render evidence documents from the ledger alone (make reproduce).

Deterministic: same ledger, same bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

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
        "**Label: model-measured, screen tier, single model (unmodified Qwen/Qwen3-4B), "
        "A/A design, isolation container.**",
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
            f"Runs: {len(rows)}; items scored: {n_tot}; pooled pass rate {k / n_tot:.4f}, "
            f"Wilson 95% [{lo:.4f}, {hi:.4f}].",
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
