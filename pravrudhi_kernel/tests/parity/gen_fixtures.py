"""Generate parity fixtures ONCE from the source implementations.

Usage (throwaway venv):
    python gen_fixtures.py --core-module prabodha.stats.core \
        --prayoga-metrics /path/to/metrics.py --out fixtures/
CI never runs this; it compares the vendored functions to the committed JSON.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np


def _cases(rng: np.random.Generator) -> list[dict]:
    cases: list[dict] = []
    for n in (2, 3, 5, 10, 30, 100):
        for k in range(8):
            x = rng.normal(0.02 * k, 1.0, n)
            y = rng.normal(0.0, 1.0, n)
            cases.append({"cls": f"normal_n{n}", "x": x.tolist(), "y": y.tolist()})
    cases.append({"cls": "all_equal", "x": [1.0] * 6, "y": [1.0] * 6})
    cases.append({"cls": "zero_var_x", "x": [2.0] * 5, "y": rng.normal(0, 1, 5).tolist()})
    cases.append({"cls": "huge", "x": (rng.normal(0, 1, 8) * 1e9).tolist(), "y": (rng.normal(0, 1, 8) * 1e9).tolist()})
    cases.append(
        {
            "cls": "tiny",
            "x": (rng.normal(0, 1, 8) * 1e-9).tolist(),
            "y": (rng.normal(0, 1, 8) * 1e-9).tolist(),
        }
    )
    cases.append({"cls": "n1", "x": [0.5], "y": [0.2]})
    cases.append({"cls": "negative", "x": rng.normal(-3, 0.1, 7).tolist(), "y": rng.normal(3, 0.1, 7).tolist()})
    cases.append({"cls": "nan", "x": [0.1, float("nan"), 0.3], "y": [0.2, 0.2, 0.2]})
    return cases


def _enc(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return {"__float__": repr(v)}
    if isinstance(v, (list, tuple)):
        return [_enc(i) for i in v]
    if isinstance(v, dict):
        return {k: _enc(i) for k, i in v.items()}
    if isinstance(v, np.generic):
        return _enc(v.item())
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core-module", default="prabodha.stats.core")
    ap.add_argument("--prayoga-metrics", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    core = importlib.import_module(a.core_module)
    spec = importlib.util.spec_from_file_location("prayoga_metrics", a.prayoga_metrics)
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)  # type: ignore[union-attr]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260904)
    cases = _cases(rng)
    fx: dict[str, list[dict]] = {
        "permutation_p": [],
        "hedges_g": [],
        "boot_ci_g": [],
        "holm": [],
        "screen": [],
    }
    for c in cases:
        x, y = np.asarray(c["x"]), np.asarray(c["y"])
        for paired in (True, False):
            if paired and x.size != y.size:
                continue
            fx["permutation_p"].append(
                {
                    **c,
                    "paired": paired,
                    "n_resamples": 2000,
                    "seed": 7,
                    "out": core.permutation_p(x, y, 2000, 7, paired),
                }
            )
        fx["hedges_g"].append({**c, "out": core.hedges_g(x, y)})
        fx["boot_ci_g"].append({**c, "n_boot": 300, "seed": 11, "out": list(core.boot_ci_g(x, y, 300, 0.05, 11))})
        fx["screen"].append(
            {
                **c,
                "cfg": {"permutation_resamples": 500, "seed": 3},
                "out": core.screen(x, y, {"permutation_resamples": 500, "seed": 3}),
            }
        )
    for k in range(60):
        m = int(rng.integers(1, 9))
        names = [f"h{i}" for i in range(m)]
        p = {nm: float(rng.uniform(0, 0.2)) for nm in names}
        if k % 7 == 0:
            p[names[0]] = 0.0
        if k % 11 == 0 and m > 1:
            p[names[1]] = p[names[0]]
        fx["holm"].append({"cls": f"m{m}", "pvals": p, "alpha": 0.05, "out": core.holm(p, 0.05)})
    ls = []
    for k in range(50):
        n, d = int(rng.integers(6, 40)), int(rng.integers(1, 5))
        X = rng.normal(0, 1, (n, d))
        w = rng.normal(0, 1, d)
        y = (X @ w + rng.normal(0, 0.5 + k * 0.05, n) > 0).astype(int)
        res = pm.label_shuffle_null(
            lambda A, b, w=w: float(np.mean((A @ w > 0).astype(int) == b)),
            X,
            y,
            n_shuffle=100,
            random_state=k,
        )
        ls.append(
            {
                "X": X.tolist(),
                "y": y.tolist(),
                "w": w.tolist(),
                "n_shuffle": 100,
                "random_state": k,
                "out": res,
            }
        )
    fx["label_shuffle_null"] = ls
    for name, rows in fx.items():
        (out / f"{name}.json").write_text(json.dumps(_enc(rows), indent=0) + "\n")
        print(name, len(rows))


if __name__ == "__main__":
    main()
