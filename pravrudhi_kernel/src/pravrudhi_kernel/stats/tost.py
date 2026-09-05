"""Canary non-inferiority: lower one-sided test at α with the full TOST record kept for the record (§13.3)."""

from __future__ import annotations

import numpy as np

from pravrudhi_kernel.schema.common import KernelModel
from pravrudhi_kernel.stats.bca import boot_ci_bca_mean


class NonInferiority(KernelModel):
    delta_mean: float
    margin: float
    alpha: float
    ci_lower: float
    ci_upper: float
    non_inferior: bool
    tost_p_lower: float
    tost_p_upper: float
    equivalent: bool
    n: int


def non_inferiority(d: np.ndarray, margin: float, *, alpha: float = 0.05, n_boot: int = 10_000, seed: int = 42) -> NonInferiority:
    """d = candidate − incumbent per item.

    H0: Δ ≤ −margin is rejected iff the (1−2α) BCa lower bound exceeds −margin.
    """
    if margin <= 0:
        raise ValueError("margin must be positive")
    x = np.asarray(d, float)
    n = int(x.size)
    mean = float(x.mean()) if n else 0.0
    lo, hi = boot_ci_bca_mean(x, n_boot=n_boot, alpha=2 * alpha, seed=seed) if n else (0.0, 0.0)
    rng = np.random.default_rng(seed)
    if n >= 2 and not np.all(x == x[0]):
        boots = x[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
        p_lower = float((1 + np.sum(boots <= -margin)) / (n_boot + 1))
        p_upper = float((1 + np.sum(boots >= margin)) / (n_boot + 1))
    else:
        p_lower = 0.0 if mean > -margin else 1.0
        p_upper = 0.0 if mean < margin else 1.0
    return NonInferiority(
        delta_mean=mean,
        margin=margin,
        alpha=alpha,
        ci_lower=lo,
        ci_upper=hi,
        non_inferior=bool(n >= 1 and lo > -margin),
        tost_p_lower=p_lower,
        tost_p_upper=p_upper,
        equivalent=bool(p_lower < alpha and p_upper < alpha),
        n=n,
    )
