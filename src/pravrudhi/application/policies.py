"""Selection policies: the arms of H1.

CHARTER §2 H1 asks whether an expected-free-energy controller over an explicit hierarchical posterior reaches the
target with lower regret per GPU-hour than (a) a greedy ratchet, (b) a greedy ratchet behind the same sequential
gate, (c) frontier search and (d) lineage Thompson sampling, at matched experiment count. Until this module existed
the engine had only the EFE arm, so the headline claim could not be examined at all.

A policy decides two things and nothing else: the order in which live candidates are considered, and how the night's
budget is filled. Everything downstream — paired evaluation on the same rotation and seed, the sequential boundary,
the canaries, every ledger row — is identical across arms. That is what makes the comparison controlled: the arms
differ in selection, not in gating or measurement.

`efe` keeps the full machinery (habit prior, Thompson draw over the softmax of −G, the epistemic reservation f_epi
and the planted/sensor shares). The baselines deliberately do NOT get that machinery: a greedy ratchet that reserved
budget for the highest-information candidate would not be a greedy ratchet. They fill the budget deterministically in
rank order, which is the honest reading of each baseline.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

POLICIES = ("efe", "greedy", "thompson", "random")
BASELINES = ("greedy", "thompson", "random")


def rank_scores(policy: str, citta: Any, pool: list[str], rng: np.random.Generator) -> dict[str, float]:
    """Score each live candidate under a baseline arm; higher is selected first.

    `greedy` ranks by the posterior mean, which is the best estimate of the candidate's effect that the loop holds at
    this moment (for an unobserved candidate that is the prior updated by the proposer's sealed prediction). It is the
    ratchet: always take what currently looks best. `thompson` draws one sample from each candidate's posterior and
    ranks by the draw, so a wide posterior can win. `random` ignores the evidence entirely and is the null arm.
    """
    if policy not in BASELINES:
        raise ValueError(f"not a baseline policy: {policy}")
    out: dict[str, float] = {}
    for cid in pool:
        b = citta.candidates.get(cid)
        mu = float(getattr(b, "mu", 0.0)) if b is not None else 0.0
        var = float(getattr(b, "sigma2", 1.0)) if b is not None else 1.0
        if policy == "greedy":
            out[cid] = mu
        elif policy == "thompson":
            out[cid] = float(rng.normal(mu, math.sqrt(max(var, 1e-12))))
        else:
            out[cid] = float(rng.random())
    return out


def fill_budget(scores: dict[str, float], costs: dict[str, float], budget_gpu_h: float) -> list[str]:
    """Take candidates in descending score while the budget allows, skipping any that no longer fit.

    Ties break on candidate id so a night is reproducible from the ledger. A candidate whose cost exceeds the whole
    budget is never selected; the loop continues rather than stopping, so one expensive candidate cannot starve a night.
    """
    order = sorted(scores, key=lambda c: (-scores[c], c))
    chosen: list[str] = []
    spent = 0.0
    for cid in order:
        c = max(float(costs.get(cid, 0.0)), 0.0)
        if spent + c <= budget_gpu_h:
            chosen.append(cid)
            spent += c
    return chosen


def selection_weights(scores: dict[str, float], chosen: list[str]) -> dict[str, float]:
    """A well-formed distribution for the `select` row of a baseline arm.

    The baselines are deterministic given their scores, so there is no sampling distribution to record. Recording the
    realised choice (uniform over what was taken) keeps every select row the same shape across arms without implying
    a probability the arm never computed.
    """
    if not chosen:
        return {c: 0.0 for c in scores}
    p = 1.0 / len(chosen)
    return {c: (p if c in chosen else 0.0) for c in scores}
