"""Selection policies: the arms of H1.

CHARTER §2 H1 asks whether an expected-free-energy controller over an explicit hierarchical posterior reaches the
target with lower regret per GPU-hour than (a) a greedy ratchet, (b) a greedy ratchet behind the same sequential
gate, (c) GEAR-like frontier search and (d) HGM-like lineage Thompson sampling, at matched experiment count. Until
this module existed the engine had only the EFE arm, so the headline claim could not be examined at all. Until the
`gear` and `hgm` arms below existed only `efe`, `greedy`, `thompson` and `random` were implemented, so H1's clauses
(c) and (d) had no arm to run against: "beats GEAR" and "beats HGM" were pre-registered but not executable, which is
what the whole-project adversarial review found and what these two arms repair.

A policy decides two things and nothing else: the order in which live candidates are considered, and how the night's
budget is filled. Everything downstream — paired evaluation on the same rotation and seed, the sequential boundary,
the canaries, every ledger row — is identical across arms. That is what makes the comparison controlled: the arms
differ in selection, not in gating or measurement.

`efe` keeps the full machinery (habit prior, Thompson draw over the softmax of −G, the epistemic reservation f_epi
and the planted/sensor shares). The baselines deliberately do NOT get that machinery: a greedy ratchet that reserved
budget for the highest-information candidate would not be a greedy ratchet. They fill the budget deterministically in
rank order, which is the honest reading of each baseline. `gear` and `hgm` reserve nothing either, exactly as
`greedy` does not.

What citta exposes, and what it does not: `CandidateBelief` is `mu`, `sigma2`, `n_obs` and nothing else, and the
Citta carries no edge between a candidate and its parent — `deliberate` synthesises `lineage=[incumbent_id]` when it
builds the Candidate and does not pass it here. So the lineage arms take an OPTIONAL `lineage` map (child id →
parent id) which a caller may supply, and, when it is absent, fall back to the only ancestry citta itself can
attest. Each fallback is stated in the arm's docstring rather than hidden. Note also that `n_obs` counts āgama
pseudo-observations: `posterior_update_prediction` routes a sealed prediction through `posterior_update`, which
increments the count. It is therefore an *evidence* count, not a count of kernel observations, and it is used here as
the closest available reading of "observed count" — stated, not assumed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

POLICIES = ("efe", "greedy", "thompson", "random", "gear", "hgm")
BASELINES = ("greedy", "thompson", "random", "gear", "hgm")

# These two belong in research/prereg/controller.yaml once an arm is actually pre-registered for a night; rank_scores
# is handed no config path by `deliberate`, so they are named here rather than being buried as literals in the rules.
GEAR_NOVELTY_BONUS = 0.5
"""Standing awarded to a candidate whose lineage has no observed ancestor. Archive standing runs in (0, 1], so 0.5
places the unexplored lineage mid-archive: above a candidate descended from the archive's weaker half, below one
descended from its stronger half. That is the exploration/exploitation trade a frontier search makes explicit."""

HGM_PRIOR_PSEUDO_COUNT = 1.0
"""Evidence weight of a candidate's own posterior against its lineage's, in units of observations. With n_lin
observations behind the lineage the shrinkage weight is n_lin / (n_lin + 1): one observation's worth of lineage
evidence moves the score half way to the lineage mean."""


def _posterior(citta: Any, cid: str) -> tuple[float, float, int]:
    """Read (mu, sigma2, n_obs) for one candidate, tolerating a candidate citta has never heard of.

    A candidate can be live before any predict row has been folded in, in which case the belief is simply absent from
    the Citta; the loop must still rank it rather than raising. The defaults are the kernel's own uninformative ones.
    """
    b = citta.candidates.get(cid)
    if b is None:
        return 0.0, 1.0, 0
    return float(getattr(b, "mu", 0.0)), float(getattr(b, "sigma2", 1.0)), int(getattr(b, "n_obs", 0))


def _archive(citta: Any) -> list[str]:
    """Every candidate citta holds evidence for, best first by posterior mean; ties on id so the archive replays.

    This is the population an evolutionary rule has actually seen: candidates from earlier nights, promoted or pruned
    or still live, all of them scored by the same posterior. The live pool is the current generation drawn from it.
    """
    observed = [cid for cid in getattr(citta, "candidates", {}) if _posterior(citta, cid)[2] > 0]
    return sorted(observed, key=lambda c: (-_posterior(citta, c)[0], c))


def _ancestors(cid: str, lineage: Mapping[str, str | None] | None, known: set[str]) -> list[str]:
    """The candidate's parent chain, nearest parent first, restricted to ancestors the archive knows.

    citta records no parent edge (see the module docstring), so with no `lineage` map the chain is empty and each
    caller states what it does with that. The walk carries a seen-set: a ledger repair that made a candidate its own
    ancestor would otherwise hang the night rather than fail it.
    """
    if lineage is None:
        return []
    out: list[str] = []
    seen = {cid}
    node = lineage.get(cid)
    while node is not None and node not in seen:
        seen.add(node)
        if node in known:
            out.append(node)
        node = lineage.get(node)
    return out


def gear_scores(citta: Any, pool: list[str], lineage: Mapping[str, str | None] | None = None) -> dict[str, float]:
    """H1 (c), GEAR-like frontier search reduced to a selection rule over the same candidate stream.

    The reduction: an archive-based evolutionary search is kept only as its selection step. The archive is every
    candidate citta holds evidence for, ranked by posterior mean; a live candidate inherits the *ordinal standing* of
    its nearest archived ancestor, normalised to (0, 1], and a candidate whose lineage reaches no archived ancestor
    takes GEAR_NOVELTY_BONUS instead. Everything else a frontier search does — mutation operators, the archive's own
    admission rule, multi-objective fronts — is out of scope here, because the arm may differ from `efe` in selection
    only. Ranking is ordinal, which is what separates this arm from `greedy`: `greedy` reads the cardinal mean, so a
    candidate whose parent barely leads the archive outranks the field by however much it leads; here it inherits one
    rank's worth of standing and no more, and every unexplored lineage sits at the same novelty score.

    Missing field, stated: citta exposes no parent id. With no `lineage` map the nearest ancestor a candidate can
    attest is its own archive entry — a candidate carrying evidence of its own stands in the archive on its own
    account — and a candidate with no evidence yet is the novel one. Pass `lineage` to get the parent-standing rule
    the reduction is written for.

    Citation: CHARTER.md §2 H1 (c) "GEAR-like frontier search" and §3 "GEAR-Evolve's frontier search"
    (Karpathy-lineage autoresearch, AlphaEvolve-class archive evolution). This is a reduction to that family's
    selection step, not a reimplementation of any published system.
    """
    archive = _archive(citta)
    n = len(archive)
    standing = {cid: (n - i) / n for i, cid in enumerate(archive)}
    out: dict[str, float] = {}
    for cid in pool:
        chain = _ancestors(cid, lineage, set(standing))
        if chain:
            out[cid] = standing[chain[0]]
        elif lineage is None and cid in standing:
            out[cid] = standing[cid]
        else:
            out[cid] = GEAR_NOVELTY_BONUS
    return out


def hgm_scores(citta: Any, pool: list[str], lineage: Mapping[str, str | None] | None = None) -> dict[str, float]:
    """H1 (d), HGM-like hierarchical-posterior selection reduced to a selection rule over the same candidate stream.

    The reduction: score by the candidate's posterior mean shrunk toward its lineage's mean, with the weight on the
    lineage set by how much evidence the lineage carries — w = n_lin / (n_lin + HGM_PRIOR_PSEUDO_COUNT), the
    conjugate form. A candidate descended from a well-measured lineage is therefore judged by the lineage; a lone
    candidate, whose lineage carries no evidence at all, keeps its own prior untouched (w = 0). The lineage mean is
    evidence-weighted across the chain, so a heavily measured grandparent counts for more than a barely measured
    parent. The self-improvement machinery an HGM puts around that posterior is out of scope: the arm may differ from
    `efe` in selection only.

    Missing field, stated: citta exposes no parent id, and `n_obs` counts sealed predictions as pseudo-observations
    (module docstring). With no `lineage` map the arm falls back to the coarsest ancestry the engine does record —
    `deliberate` gives every live candidate the same parent, the incumbent, whose standing citta summarises only
    through the candidates it has actually measured. The lineage of a candidate is then the archive *excluding
    itself*, leave-one-out, so no candidate is ever shrunk toward its own mean; a candidate carrying much of the
    archive's evidence keeps most of its own estimate, and one carrying none is pulled to the archive mean. Pass
    `lineage` to get the parent-chain rule the reduction is written for.

    Citation: CHARTER.md §2 H1 (d) "HGM-like lineage Thompson sampling" and §1's Huxley-Gödel Machine; the shrinkage
    is standard hierarchical partial pooling (James–Stein / empirical Bayes), which is what the kernel's own
    `posterior_update` already does up the surface/strategy/bucket hierarchy.
    """
    archive = set(_archive(citta))
    out: dict[str, float] = {}
    for cid in pool:
        mu, _, _ = _posterior(citta, cid)
        chain = _ancestors(cid, lineage, archive) if lineage is not None else sorted(archive - {cid})
        n_lin = 0.0
        acc = 0.0
        for a in chain:
            a_mu, _, a_n = _posterior(citta, a)
            n_lin += a_n
            acc += a_n * a_mu
        if n_lin <= 0.0:
            out[cid] = mu
            continue
        w = n_lin / (n_lin + HGM_PRIOR_PSEUDO_COUNT)
        out[cid] = (1.0 - w) * mu + w * (acc / n_lin)
    return out


def rank_scores(
    policy: str,
    citta: Any,
    pool: list[str],
    rng: np.random.Generator,
    lineage: Mapping[str, str | None] | None = None,
) -> dict[str, float]:
    """Score each live candidate under a baseline arm; higher is selected first.

    `greedy` ranks by the posterior mean, which is the best estimate of the candidate's effect that the loop holds at
    this moment (for an unobserved candidate that is the prior updated by the proposer's sealed prediction). It is the
    ratchet: always take what currently looks best. `thompson` draws one sample from each candidate's posterior and
    ranks by the draw, so a wide posterior can win. `random` ignores the evidence entirely and is the null arm.
    `gear` and `hgm` are the two lineage arms; see their own docstrings for the reduction each one makes.

    `lineage` is optional because `deliberate` has no parent map to pass — it is accepted so a caller that does hold
    one loses nothing, and so the lineage arms are testable against the rule they are written for. `gear` and `hgm`
    are deterministic and never touch `rng`.
    """
    if policy not in BASELINES:
        raise ValueError(f"not a baseline policy: {policy}")
    if policy == "gear":
        return gear_scores(citta, pool, lineage)
    if policy == "hgm":
        return hgm_scores(citta, pool, lineage)
    out: dict[str, float] = {}
    for cid in pool:
        mu, var, _ = _posterior(citta, cid)
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
