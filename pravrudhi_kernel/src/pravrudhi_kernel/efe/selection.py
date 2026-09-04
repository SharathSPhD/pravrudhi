"""Softmax with habit prior, Thompson-like sampling and the residency-aware knapsack (§2.3). Pure; RNG injected."""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from pravrudhi_kernel.efe.types import BeliefKeys, SelectionBatch, Shares
from pravrudhi_kernel.schema import Candidate, Citta


def habit_prior(citta: Citta, keys: BeliefKeys, tau0_2: float) -> float:
    """E(a) ∝ posterior probability that the bucket's mean effect is positive; never zero, never one."""
    lvl = (
        citta.buckets.get(keys.bucket_key)
        or citta.strategies.get(keys.strategy_key or "")
        or citta.surfaces.get(keys.surface)
    )
    mu, tau2 = (lvl.mu, lvl.tau2) if lvl is not None else (0.0, tau0_2)
    p = 0.5 * (1.0 + math.erf(mu / math.sqrt(2.0 * tau2)))
    return min(max(p, 1e-6), 1.0 - 1e-6)


def selection_probabilities(G: Mapping[str, float], habit: Mapping[str, float]) -> dict[str, float]:
    """Q(a) = softmax(−G(a) + ln E(a)). A candidate with G = +∞ (T0-touching) gets exactly zero."""
    ids = list(G)
    if not ids:
        return {}
    logits = np.array([-G[i] + math.log(habit.get(i, 1.0)) for i in ids], dtype=float)
    finite = np.isfinite(logits)
    if not finite.any():
        return dict.fromkeys(ids, 0.0)
    z = np.full(len(ids), -np.inf)
    m = logits[finite].max()
    z[finite] = np.exp(logits[finite] - m)
    z[~finite] = 0.0
    q = z / z.sum()
    return {i: float(v) for i, v in zip(ids, q, strict=True)}


def knapsack_batch(
    Q: Mapping[str, float],
    cands: Mapping[str, Candidate],
    eig_nats: Mapping[str, float],
    budget_gpu_h: float,
    shares: Shares,
    rng: np.random.Generator,
) -> SelectionBatch:
    """Fill the night by sampling without replacement ∝ Q until the effective budget is spent.

    B' = B·(1 − planted − sensors). The epistemic floor is enforced by reserving f_epi·B' for the highest-EIG
    candidates before the Thompson draw. Residency: `reasoner` candidates go to the deliberation window,
    `executor` candidates to execution windows; an execution-window-exclusive job is at most one per night.
    """
    if budget_gpu_h <= 0:
        raise ValueError("budget must be positive")
    b_eff = budget_gpu_h * (1.0 - shares.planted - shares.sensors)
    ids = [i for i, q in Q.items() if q > 0 and i in cands]
    chosen: list[str] = []
    spent = 0.0
    epistemic: list[str] = []
    reserve = shares.f_epi * b_eff
    for i in sorted(ids, key=lambda k: -eig_nats.get(k, 0.0)):
        c = cands[i].cost_est_gpu_h
        if spent + c <= reserve:
            chosen.append(i)
            epistemic.append(i)
            spent += c
    remaining = [i for i in ids if i not in chosen]
    while remaining:
        w = np.array([Q[i] for i in remaining], dtype=float)
        if w.sum() <= 0:
            break
        pick = remaining[int(rng.choice(len(remaining), p=w / w.sum()))]
        remaining.remove(pick)
        c = cands[pick].cost_est_gpu_h
        if spent + c <= b_eff:
            chosen.append(pick)
            spent += c
    deliberation = [i for i in chosen if cands[i].residency_need == "reasoner"]
    execution = [i for i in chosen if cands[i].residency_need != "reasoner"]
    exclusive = [i for i in execution if cands[i].cost_est_gpu_h >= 0.5 * b_eff]
    if len(exclusive) > 1:
        keep = max(exclusive, key=lambda k: Q[k])
        for drop in exclusive:
            if drop != keep:
                execution.remove(drop)
                chosen.remove(drop)
                spent -= cands[drop].cost_est_gpu_h
        exclusive = [keep]
    return SelectionBatch(
        deliberation=deliberation,
        execution=execution,
        exclusive=exclusive,
        spent_gpu_h=spent,
        budget_effective=b_eff,
        epistemic_ids=epistemic,
    )
