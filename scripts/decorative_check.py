"""Decorative-controller check over the last `select` batch (or a candidates file).

Thresholds come from research/prereg/controller.yaml.

Usage:
  decorative_check.py --batch research/last_select.json        # {"scores": {id: G}, "selection": {id: Q}}
  decorative_check.py --hypotheses cycle_candidates.json       # game-llm efe_rank lineage format
Exit 0 pass, 2 fail (the night must not proceed on a ranking that means nothing).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from pravrudhi_kernel.efe import decorative_check, rank_hypothesis_candidates, selection_probabilities


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", type=Path)
    ap.add_argument("--hypotheses", type=Path)
    ap.add_argument("--prereg", type=Path, default=Path("research/prereg/controller.yaml"))
    a = ap.parse_args()
    cfg = yaml.safe_load(a.prereg.read_text())
    cv_min, mi_min = float(cfg["decorative"]["cv_min"]), float(cfg["decorative"]["mi_min_bits"])
    if a.hypotheses:
        spec = json.loads(a.hypotheses.read_text())
        r = rank_hypothesis_candidates(spec)
        scores = {s["name"]: s["total"] for s in r["ranking"]}
        sel = selection_probabilities(scores, {k: 1.0 for k in scores})
        for s in r["ranking"]:
            print(
                f"  {s['name']:<32} G={s['total']:+.4f} epistemic {s['epistemic']:.4f} pragmatic {s['pragmatic']:.4f} cost {s['cost']:.4f}"
            )
        if r["degenerate"]:
            print("REFUSED: every candidate scored identically (efe_rank verdict)", file=sys.stderr)
            return 2
    elif a.batch:
        b = json.loads(a.batch.read_text())
        scores, sel = b["scores"], b["selection"]
    else:
        ap.error("give --batch or --hypotheses")
    v = decorative_check(scores, sel, cv_min, mi_min)
    print(
        f"decorative_check: {v.verdict} cv_G={v.cv_G:.4f} mi_bits={v.mi_bits:.4f} thresholds cv>={cv_min} mi>={mi_min}"
        + (f" reason={v.reason}" if v.reason else "")
    )
    return 0 if v.verdict == "pass" else 2


if __name__ == "__main__":
    sys.exit(main())
