"""Vendored verbatim from prabodha.stats.core (house rule: never a third statistics library).

Parity against the source is proven by committed fixtures in tests/parity/fixtures, generated once.
Do not edit to taste; a mismatch above tolerance is an ADR request, not a fix.
"""

from __future__ import annotations

import numpy as np


def permutation_p(
    x: np.ndarray, y: np.ndarray, n_resamples: int = 10_000, seed: int = 42, paired: bool = True
) -> float:
    """Two-sided paired (sign-flip) or unpaired (shuffle) permutation p-value for mean difference."""
    rng = np.random.default_rng(seed)
    x, y = np.asarray(x, float), np.asarray(y, float)
    if paired:
        d = x - y
        obs = abs(d.mean())
        signs = rng.choice([-1.0, 1.0], size=(n_resamples, d.size))
        null = np.abs((signs * d).mean(axis=1))
    else:
        pooled = np.concatenate([x, y])
        nx = x.size
        obs = abs(x.mean() - y.mean())
        null = np.empty(n_resamples)
        for i in range(n_resamples):
            p = rng.permutation(pooled)
            null[i] = abs(p[:nx].mean() - p[nx:].mean())
    return float((1 + (null >= obs).sum()) / (1 + n_resamples))


def hedges_g(x: np.ndarray, y: np.ndarray) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    nx, ny = x.size, y.size
    sp = np.sqrt(((nx - 1) * x.var(ddof=1) + (ny - 1) * y.var(ddof=1)) / (nx + ny - 2))
    if sp == 0:
        return 0.0
    d = (x.mean() - y.mean()) / sp
    J = 1 - 3 / (4 * (nx + ny) - 9)
    return float(J * d)


def boot_ci_g(
    x: np.ndarray, y: np.ndarray, n_boot: int = 2000, alpha: float = 0.05, seed: int = 42
) -> tuple[float, float]:
    """Percentile bootstrap CI for Hedges' g (numpy-only; BCa upgrade tracked in journal)."""
    rng = np.random.default_rng(seed)
    x, y = np.asarray(x, float), np.asarray(y, float)
    boots = np.array([hedges_g(rng.choice(x, x.size), rng.choice(y, y.size)) for _ in range(n_boot)])
    lo, hi = np.quantile(boots, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def holm(pvals: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    """Holm-Bonferroni: name -> reject-null decision at family alpha."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out: dict[str, bool] = {}
    still = True
    for i, (name, p) in enumerate(items):
        thresh = alpha / (m - i)
        still = still and (p <= thresh)
        out[name] = bool(still)
    return out


def screen(x: np.ndarray, y: np.ndarray, cfg: dict[str, float] | None = None) -> dict[str, object]:
    """Screen tier: paired permutation p + Hedges g + CI. One seed. No correction (R6)."""
    cfg = cfg or {}
    return {
        "tier": "screen",
        "p_perm": permutation_p(
            x, y, int(cfg.get("permutation_resamples", 10_000)), int(cfg.get("seed", 42))
        ),
        "hedges_g": hedges_g(x, y),
        "g_ci95": boot_ci_g(x, y, seed=int(cfg.get("seed", 42))),
        "n": (len(x), len(y)),
    }
