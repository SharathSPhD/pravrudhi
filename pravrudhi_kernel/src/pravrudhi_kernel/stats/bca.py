"""Efron's bias-corrected and accelerated bootstrap interval (06-evaluation-and-statistics.md §3.1)."""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from pravrudhi_kernel.stats.core import hedges_g


def _ndtr(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _ndtri(p: float) -> float:
    # Acklam's rational approximation, |rel err| < 1.15e-9; adequate for interval endpoints
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


def bca_ci(
    data: np.ndarray,
    stat: Callable[[np.ndarray], float],
    *,
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """BCa interval for a statistic of one sample (item-level resampling). Degenerate data → (θ̂, θ̂)."""
    x = np.asarray(data, float)
    n = x.size
    theta = float(stat(x))
    if n < 2 or np.all(x == x[0]):
        return theta, theta
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boots = np.array([stat(x[i]) for i in idx])
    boots = boots[np.isfinite(boots)]
    if boots.size == 0:
        return theta, theta
    prop = float(np.mean(boots < theta))
    prop = min(max(prop, 1.0 / (boots.size + 1)), 1.0 - 1.0 / (boots.size + 1))
    z0 = _ndtri(prop)
    jack = np.array([stat(np.delete(x, i)) for i in range(n)])
    jm = jack.mean()
    num = np.sum((jm - jack) ** 3)
    den = 6.0 * (np.sum((jm - jack) ** 2) ** 1.5)
    a = float(num / den) if den > 0 else 0.0
    out = []
    for zq in (_ndtri(alpha / 2), _ndtri(1 - alpha / 2)):
        adj = z0 + (z0 + zq) / (1 - a * (z0 + zq))
        q_adj = _ndtr(adj) if np.isfinite(adj) else _ndtr(zq)  # degenerate stream (ADR-0014): percentile fallback
        out.append(float(np.quantile(boots, min(max(q_adj, 0.0), 1.0))))
    lo, hi = sorted(out)
    return lo, hi


def boot_ci_bca_mean(d: np.ndarray, *, n_boot: int = 10_000, alpha: float = 0.05, seed: int = 42) -> tuple[float, float]:
    return bca_ci(np.asarray(d, float), lambda v: float(np.mean(v)), n_boot=n_boot, alpha=alpha, seed=seed)


def boot_ci_bca_g(
    x: np.ndarray, y: np.ndarray, *, n_boot: int = 10_000, alpha: float = 0.05, seed: int = 42
) -> tuple[float, float]:
    """BCa on Hedges' g for the paired design: resample item indices jointly."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.size != y.size:
        raise ValueError("paired design requires equal sizes")
    pairs = np.stack([x, y], axis=1)

    def g_of(rows: np.ndarray) -> float:
        return hedges_g(rows[:, 0], rows[:, 1])

    n = pairs.shape[0]
    theta = g_of(pairs)
    if n < 3:
        return theta, theta
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boots = np.array([g_of(pairs[i]) for i in idx])
    boots = boots[np.isfinite(boots)]
    if boots.size == 0 or np.all(boots == boots[0]):
        return theta, theta
    prop = float(np.mean(boots < theta))
    prop = min(max(prop, 1.0 / (boots.size + 1)), 1.0 - 1.0 / (boots.size + 1))
    z0 = _ndtri(prop)
    jack = np.array([g_of(np.delete(pairs, i, axis=0)) for i in range(n)])
    jm = jack.mean()
    den = 6.0 * (np.sum((jm - jack) ** 2) ** 1.5)
    a = float(np.sum((jm - jack) ** 3) / den) if den > 0 else 0.0
    out = []
    for zq in (_ndtri(alpha / 2), _ndtri(1 - alpha / 2)):
        adj = z0 + (z0 + zq) / (1 - a * (z0 + zq))
        q_adj = _ndtr(adj) if np.isfinite(adj) else _ndtr(zq)  # degenerate stream (ADR-0014): percentile fallback
        out.append(float(np.quantile(boots, min(max(q_adj, 0.0), 1.0))))
    lo, hi = sorted(out)
    return lo, hi
