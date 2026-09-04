"""Label-shuffle null for any fitted probe. Ported from prayoga.shared.metrics.label_shuffle_null; numpy only.

A probe that does not beat the 99th percentile of its shuffle null is not a sensor.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


def label_shuffle_null(
    fit_score: Callable[[np.ndarray, np.ndarray], float],
    X: np.ndarray,
    y: np.ndarray,
    *,
    n_shuffle: int = 1_000,
    random_state: int = 42,
) -> dict[str, float]:
    rng = np.random.RandomState(random_state)
    true_score = float(fit_score(X, y))
    null = np.empty(n_shuffle)
    y = np.asarray(y)
    for i in range(n_shuffle):
        null[i] = fit_score(X, y[rng.permutation(len(y))])
    p = float((np.sum(null >= true_score) + 1) / (n_shuffle + 1))
    return {
        "true_score": true_score,
        "null_mean": float(null.mean()),
        "null_std": float(null.std()),
        "null_p99": float(np.percentile(null, 99)),
        "p_value": p,
    }
