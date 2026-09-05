"""Decorative-agent check (D9): if scores do not condition on the action, the night fails loudly.

Generalises game-llm's efe_rank.py refusal ("every candidate scored identically") to two statistics:
the coefficient of variation of G across the pool and the information the selection carries about identity.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from pravrudhi_kernel.efe.types import DecorativeVerdict

EPS = 1e-12


def _cv(values: np.ndarray) -> float:
    if values.size < 2:
        return 0.0
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return 0.0
    scale = max(float(np.mean(np.abs(finite))), EPS)
    return float(np.std(finite, ddof=1) / scale)


def _mi_bits(q: np.ndarray) -> float:
    """log2(N) − H(Q): bits the selection distribution carries about candidate identity relative to
    uniform."""
    q = q[q > 0]
    if q.size == 0:
        return 0.0
    q = q / q.sum()
    h = float(-(q * np.log2(q)).sum())
    return max(0.0, math.log2(len(q)) - h) if len(q) > 1 else 0.0


def decorative_check(
    scores: Mapping[str, float], selection: Mapping[str, float], cv_min: float, mi_min_bits: float
) -> DecorativeVerdict:
    ids = list(scores)
    g = np.array([scores[i] for i in ids], dtype=float)
    q = np.array([selection.get(i, 0.0) for i in ids], dtype=float)
    cv = _cv(g)
    mi = _mi_bits(q)
    if len(ids) < 2:
        return DecorativeVerdict(verdict="fail", cv_G=cv, mi_bits=mi, reason="fewer than two candidates")
    if len({round(float(x), 9) for x in g if math.isfinite(x)}) == 1:
        return DecorativeVerdict(verdict="fail", cv_G=cv, mi_bits=mi, reason="every candidate scored identically")
    if cv < cv_min:
        return DecorativeVerdict(verdict="fail", cv_G=cv, mi_bits=mi, reason=f"cv_G {cv:.4g} < {cv_min}")
    if mi < mi_min_bits:
        return DecorativeVerdict(verdict="fail", cv_G=cv, mi_bits=mi, reason=f"mi_bits {mi:.4g} < {mi_min_bits}")
    return DecorativeVerdict(verdict="pass", cv_G=cv, mi_bits=mi, reason=None)


# ---- game-llm efe_rank lineage: hypothesis-diagnosticity scoring, kept so its cycle fixtures remain tests
# ----


def _clip(p: float) -> float:
    return min(max(p, EPS), 1.0 - EPS)


def bernoulli_kl(posterior: float, prior: float) -> float:
    p, q = _clip(posterior), _clip(prior)
    return p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))


def rank_hypothesis_candidates(spec: Mapping[str, Any], cost_weight: float | None = None) -> dict[str, Any]:
    """Port of game-llm efe_rank.score + degenerate verdict. Returns {'degenerate', 'ranking',
    'entropy_nats'}."""
    beliefs = {k: float(v) for k, v in spec["beliefs"].items()}
    for hyp, p in beliefs.items():
        if not 0.0 < p < 1.0:
            raise ValueError(f"belief for {hyp!r} is {p}; certainty admits no update")
    cw = float(spec.get("cost_weight", 0.0)) if cost_weight is None else cost_weight
    ranked = []
    for c in spec["candidates"]:
        epistemic = pragmatic = 0.0
        for hyp, sp in c.get("diagnosticity", {}).items():
            if hyp not in beliefs:
                raise ValueError(f"candidate {c['name']!r} refers to unknown hypothesis {hyp!r}")
            p_true, p_false = float(sp[0]), float(sp[1])
            prior = beliefs[hyp]
            p_pos = _clip(prior * p_true + (1 - prior) * p_false)
            post_pos = prior * p_true / p_pos
            post_neg = prior * (1 - p_true) / (1 - p_pos)
            epistemic += p_pos * bernoulli_kl(post_pos, prior) + (1 - p_pos) * bernoulli_kl(post_neg, prior)
            pragmatic += float(c.get("payoff", {}).get(hyp, 0.0)) * p_pos
        cost = cw * float(c.get("cost", 0.0))
        ranked.append(
            {
                "name": c["name"],
                "epistemic": epistemic,
                "pragmatic": pragmatic,
                "cost": cost,
                "total": -(epistemic + pragmatic) + cost,
            }
        )
    ranked.sort(key=lambda s: s["total"])
    degenerate = len({round(s["total"], 9) for s in ranked}) == 1 and len(ranked) > 1
    ent = 0.0
    for p in beliefs.values():
        q = _clip(p)
        ent += -(q * math.log(q) + (1 - q) * math.log(1 - q))
    return {"degenerate": degenerate, "ranking": ranked, "entropy_nats": ent}
