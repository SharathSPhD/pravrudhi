"""Always-valid sequential boundary on a candidate's per-seed effects (06 §4; C10 variance-adaptive form).

E-process: Gaussian-mixture SPRT with prior θ ~ N(0, τ²). σ is either the frozen benchmark σ_seed (fixed) or
a shrinkage estimate that starts at σ_seed and moves toward the stream's own sample SD (adaptive), so
the boundary does not depend on a single pre-study σ. `xs` is rebuilt from the ledger each time;
nothing is stored.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field

from pravrudhi_kernel.schema.common import KernelModel

Decision = Literal["prune", "continue", "confirm"]


class Variance(KernelModel):
    bench: str
    sigma_seed: float = Field(gt=0.0)
    tau: float = Field(gt=0.0)
    delta_min: float = Field(gt=0.0)
    alpha_eff: float = Field(default=0.05, gt=0.0, lt=1.0)
    alpha_fut: float = Field(default=0.20, gt=0.0, lt=1.0)
    k_max: int = Field(default=6, ge=1)
    sigma_mode: Literal["fixed", "adaptive"] = "adaptive"
    n0: int = Field(default=3, ge=1)


class BoundaryResult(KernelModel):
    decision: Decision
    n: int
    xbar: float
    e_value: float
    halfwidth: float
    sigma_used: float
    hetvabhasa: Literal["asiddha", "savyabhicara"] | None


def effective_sigma(xs: list[float], bench: Variance) -> float:
    n = len(xs)
    if bench.sigma_mode == "fixed" or n < 2:
        return bench.sigma_seed
    m = sum(xs) / n
    s2 = sum((x - m) ** 2 for x in xs) / (n - 1)
    w = bench.n0
    return math.sqrt((w * bench.sigma_seed**2 + (n - 1) * s2) / (w + n - 1))


def e_process(xs: list[float], sigma: float, tau: float) -> float:
    n = len(xs)
    if n == 0:
        return 1.0
    s2, t2, S = sigma * sigma, tau * tau, sum(xs)
    log_e = 0.5 * math.log(s2 / (s2 + n * t2)) + t2 * S * S / (2 * s2 * (s2 + n * t2))
    # ADR-0017: a draw many sigma from zero overflows exp(); every decision threshold is below 1e3, so the e-value is
    # capped at exp(700) (about 1e304) with the comparison unchanged
    return math.exp(min(log_e, 700.0))


def conf_seq_halfwidth(n: int, sigma: float, tau: float, alpha: float) -> float:
    if n == 0:
        return math.inf
    s2, t2 = sigma * sigma, tau * tau
    return math.sqrt(s2 * (s2 + n * t2) / (n * n * t2) * math.log((s2 + n * t2) / (alpha * alpha * s2)))


def sequential_boundary(xs: list[float], bench: Variance) -> BoundaryResult:
    n = len(xs)
    sigma = effective_sigma(xs, bench)
    if n == 0:
        return BoundaryResult(
            decision="continue",
            n=0,
            xbar=0.0,
            e_value=1.0,
            halfwidth=math.inf,
            sigma_used=sigma,
            hetvabhasa=None,
        )
    xbar = sum(xs) / n
    e = e_process(xs, sigma, bench.tau)
    w = conf_seq_halfwidth(n, sigma, bench.tau, bench.alpha_fut)
    if e >= 1.0 / bench.alpha_eff and xbar > 0:
        return BoundaryResult(decision="confirm", n=n, xbar=xbar, e_value=e, halfwidth=w, sigma_used=sigma, hetvabhasa=None)
    if xbar + w < bench.delta_min:
        return BoundaryResult(decision="prune", n=n, xbar=xbar, e_value=e, halfwidth=w, sigma_used=sigma, hetvabhasa="asiddha")
    if n >= bench.k_max:
        return BoundaryResult(
            decision="prune",
            n=n,
            xbar=xbar,
            e_value=e,
            halfwidth=w,
            sigma_used=sigma,
            hetvabhasa="savyabhicara",
        )
    return BoundaryResult(decision="continue", n=n, xbar=xbar, e_value=e, halfwidth=w, sigma_used=sigma, hetvabhasa=None)
