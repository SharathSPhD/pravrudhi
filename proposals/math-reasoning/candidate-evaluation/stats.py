"""Statistics helpers for candidate-vs-baseline comparison.

Stdlib-only (no numpy/scipy dependency) so this proposal can be compiled
and exercised without pulling in the project's real training/eval stack.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float


def wilson_interval(k: int, n: int, confidence: float = 0.95) -> Interval:
    """Wilson score interval for a single proportion k/n.

    Preferred over the naive normal approximation because it stays inside
    [0, 1] and is well-behaved for small n or proportions near 0 or 1 --
    both of which show up on a held-out set of a few hundred word problems.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    z = _z_for_confidence(confidence)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    low = (centre - half) / denom
    high = (centre + half) / denom
    return Interval(point=p, low=max(0.0, low), high=min(1.0, high))


def newcombe_diff_interval(
    k1: int, n1: int, k2: int, n2: int, confidence: float = 0.95
) -> Interval:
    """Newcombe (1998) interval for the difference of two independent
    proportions p2 - p1, built from the two single-proportion Wilson
    intervals. Used to ask "is the candidate's accuracy distinguishable
    from the baseline's, at this confidence level" without assuming
    normality.
    """
    i1 = wilson_interval(k1, n1, confidence)
    i2 = wilson_interval(k2, n2, confidence)
    point = i2.point - i1.point
    low = point - math.sqrt((i1.point - i1.low) ** 2 + (i2.high - i2.point) ** 2)
    high = point + math.sqrt((i1.high - i1.point) ** 2 + (i2.point - i2.low) ** 2)
    return Interval(point=point, low=low, high=high)


def required_n_for_margin(margin: float, confidence: float = 0.95, p: float = 0.5) -> int:
    """Sample size needed so a single-proportion Wilson/normal interval has
    the given half-width at worst-case variance (p=0.5), used to justify
    the proposed evaluation_sample_count.
    """
    z = _z_for_confidence(confidence)
    n = (z * z * p * (1 - p)) / (margin * margin)
    return math.ceil(n)


def _z_for_confidence(confidence: float) -> float:
    # Small fixed table covers the confidence levels an objective is
    # realistically going to declare; avoids depending on scipy.stats.norm.
    table = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}
    if confidence in table:
        return table[confidence]
    closest = min(table, key=lambda c: abs(c - confidence))
    return table[closest]
