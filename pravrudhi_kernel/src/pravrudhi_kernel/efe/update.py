"""Posterior update, EIG, preferences, precision, EFE (02-efe-controller-spec.md §1–§2). Pure functions."""

from __future__ import annotations

import math

from pravrudhi_kernel.efe.types import BeliefKeys, EFETerms, Precision, PrecisionView
from pravrudhi_kernel.schema import Candidate, Citta, EvidencePlan, Preferences
from pravrudhi_kernel.schema.citta import CandidateBelief, NormalBelief
from pravrudhi_kernel.schema.common import Surface

EPS = 1e-9


def _phi(z: float) -> float:
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


def _Phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def pseudo_observation_variance(
    sigma2_eval: float, conf: float, rho_pred: float, rho_floor: float = 0.05
) -> float:
    """σ²_LLM = max(σ²_eval, σ²_eval · (1−c)/c · 1/ρ_pred).

    c and ρ are clipped so a zero-confidence prediction is inert, not NaN. The floor at one kernel observation is a
    conservative reading of "āgama until executed": testimony never carries more precision than one measurement
    (deviation recorded in gate_L2; the blueprint formula has no floor).
    """
    c = min(max(conf, EPS), 1.0 - EPS)
    rho = max(rho_pred, rho_floor)
    return max(sigma2_eval, sigma2_eval * (1.0 - c) / c / rho)


def _normal_update(prior: NormalBelief, value: float, sigma2_obs: float) -> NormalBelief:
    prec = 1.0 / prior.tau2 + 1.0 / sigma2_obs
    tau2 = 1.0 / prec
    mu = tau2 * (prior.mu / prior.tau2 + value / sigma2_obs)
    return NormalBelief(mu=mu, tau2=tau2, n=prior.n + 1)


def prior_for(citta: Citta, keys: BeliefKeys, tau0_2: float) -> CandidateBelief:
    """A new candidate's prior comes from the most specific level that has data: bucket > strategy > surface > τ₀²."""
    for level in (
        citta.buckets.get(keys.bucket_key),
        citta.strategies.get(keys.strategy_key or ""),
        citta.surfaces.get(keys.surface),
    ):
        if level is not None and level.n > 0:
            return CandidateBelief(mu=level.mu, sigma2=level.tau2, n_obs=0)
    return CandidateBelief(mu=0.0, sigma2=tau0_2, n_obs=0)


def posterior_update(citta: Citta, keys: BeliefKeys, value: float, sigma2_obs: float, tau0_2: float) -> Citta:
    """Conjugate Normal update at the candidate level, then empirical-Bayes updates up the hierarchy.

    Each level above the candidate treats the observation as a draw with variance σ²_obs plus the within-level
    spread it already carries, so an observation moves a surface mean less than it moves the candidate.
    """
    if sigma2_obs <= 0:
        raise ValueError("sigma2_obs must be positive")
    cand = citta.candidates.get(keys.candidate_id) or prior_for(citta, keys, tau0_2)
    prec = 1.0 / cand.sigma2 + 1.0 / sigma2_obs
    new_sigma2 = 1.0 / prec
    new_mu = new_sigma2 * (cand.mu / cand.sigma2 + value / sigma2_obs)
    candidates = dict(citta.candidates)
    candidates[keys.candidate_id] = CandidateBelief(mu=new_mu, sigma2=new_sigma2, n_obs=cand.n_obs + 1)

    def lvl(store: dict[str, NormalBelief], key: str, spread: float) -> dict[str, NormalBelief]:
        out = dict(store)
        prior = out.get(key) or NormalBelief(mu=0.0, tau2=tau0_2, n=0)
        out[key] = _normal_update(prior, value, sigma2_obs + spread)
        return out

    buckets = lvl(citta.buckets, keys.bucket_key, cand.sigma2)
    strategies = citta.strategies
    if keys.strategy_key is not None:
        strategies = lvl(citta.strategies, keys.strategy_key, cand.sigma2 + buckets[keys.bucket_key].tau2)
    surfaces = lvl(citta.surfaces, keys.surface, cand.sigma2 + buckets[keys.bucket_key].tau2)
    return citta.model_copy(
        update={
            "version": citta.version + 1,
            "candidates": candidates,
            "buckets": buckets,
            "strategies": strategies,
            "surfaces": surfaces,
        }
    )


def posterior_update_prediction(
    citta: Citta, keys: BeliefKeys, delta_hat: float, conf: float, sigma2_eval: float, tau0_2: float
) -> Citta:
    """An LLM prediction is āgama: a pseudo-observation whose variance grows with low confidence and low ρ_pred."""
    rho = citta.rho_pred.get(keys.surface, 0.0)
    return posterior_update(
        citta, keys, delta_hat, pseudo_observation_variance(sigma2_eval, conf, rho), tau0_2
    )


def beta_binomial_update(alpha: float, beta: float, successes: int, failures: int) -> tuple[float, float]:
    if alpha <= 0 or beta <= 0 or successes < 0 or failures < 0:
        raise ValueError("alpha, beta positive; counts non-negative")
    return alpha + successes, beta + failures


def beta_eig(alpha: float, beta: float) -> float:
    """Mutual information (nats) between one Bernoulli outcome and the Beta-distributed rate, by enumeration."""
    if alpha <= 0 or beta <= 0:
        raise ValueError("alpha, beta positive")
    p1 = alpha / (alpha + beta)

    def h(a: float, b: float) -> float:  # differential entropy of Beta(a,b) via lgamma
        lb = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        return lb - (a - 1) * (_digamma(a) - _digamma(a + b)) - (b - 1) * (_digamma(b) - _digamma(a + b))

    return max(0.0, h(alpha, beta) - (p1 * h(alpha + 1, beta) + (1 - p1) * h(alpha, beta + 1)))


def _digamma(x: float) -> float:
    r = 0.0
    while x < 6.0:
        r -= 1.0 / x
        x += 1.0
    f = 1.0 / (x * x)
    return (
        r
        + math.log(x)
        - 0.5 / x
        - f * (1.0 / 12 - f * (1.0 / 120 - f * (1.0 / 252 - f * (1.0 / 240 - f / 132))))
    )


def eig(citta: Citta, keys: BeliefKeys, sigma2_eval: float, n_seeds: int, tau0_2: float) -> float:
    """EIG (nats) of one more evaluation with n_seeds seeds: candidate term plus hierarchy terms (§2.1).

    Each term is ½ ln(1 + prior variance at that level / effective noise); the hierarchy terms are what make an
    under-sampled bucket, strategy or surface worth more than a well-known one.
    """
    if sigma2_eval <= 0 or n_seeds < 1:
        raise ValueError("sigma2_eval positive, n_seeds >= 1")
    noise = sigma2_eval / n_seeds
    cand = citta.candidates.get(keys.candidate_id) or prior_for(citta, keys, tau0_2)
    total = 0.5 * math.log1p(cand.sigma2 / noise)
    for store, key in (
        (citta.buckets, keys.bucket_key),
        (citta.strategies, keys.strategy_key or ""),
        (citta.surfaces, keys.surface),
    ):
        lvl = store.get(key)
        var = lvl.tau2 if lvl is not None else tau0_2
        total += 0.5 * math.log1p(var / (noise + cand.sigma2))
    return max(0.0, total)


def expected_log_pref(
    citta: Citta,
    cand: Candidate,
    prefs: Preferences,
    keys: BeliefKeys,
    tau0_2: float,
    *,
    p_canary_fail: float = 0.0,
    audit_severity: float = 0.0,
    zeta: float = 1.0,
) -> float:
    """E[ln P(o | C)] under the candidate's posterior on Δ_out (§1.3). −∞ for anything touching T0."""
    if not prefs.admits(cand) or cand.surface == Surface.T0_kernel:
        return -math.inf
    b = citta.candidates.get(cand.id) or prior_for(citta, keys, tau0_2)
    m, s = b.mu, math.sqrt(b.sigma2)
    # E[max(0, −X)] for X ~ N(m, s²)
    e_neg = s * _phi(m / s) - m * _Phi(-m / s) if s > 0 else max(0.0, -m)
    return prefs.beta * m - prefs.lambda_ * e_neg - prefs.eta * p_canary_fail - zeta * audit_severity


def infer_precision(view: PrecisionView) -> Precision:
    """γ_epi rises with pool posterior-predictive variance, floored at f_epi; γ_prag follows ρ_pred, floored."""
    if view.pool_post_var:
        v = sum(view.pool_post_var) / len(view.pool_post_var)
        epi = v / (v + view.sigma2_eval)
    else:
        epi = 1.0
    epi = min(1.0, max(view.f_epi, epi))
    prag = min(1.0, max(view.rho_floor, view.rho_pred))
    return Precision(epi=epi, prag=prag)


def efe(
    citta: Citta,
    cand: Candidate,
    plan: EvidencePlan,
    prefs: Preferences,
    gamma: Precision,
    kappa: float,
    budget: float,
    sigma2_eval: float,
    tau0_2: float,
    *,
    keys: BeliefKeys | None = None,
    p_canary_fail: float = 0.0,
    audit_severity: float = 0.0,
) -> EFETerms:
    """G_γ(a) = −γ_epi·EIG − γ_prag·E[ln P(o|C)] + κ·cost/B (§2). Lower is better."""
    if budget <= 0 or kappa < 0:
        raise ValueError("budget positive, kappa non-negative")
    k = keys or BeliefKeys(
        surface=str(cand.surface),
        strategy=cand.strategy,
        bucket=f"{cand.bucket.task_family}|{cand.bucket.target_model}|{cand.bucket.corpus}|{cand.edit_family}",
        candidate_id=cand.id,
    )
    e = eig(citta, k, sigma2_eval, len(plan.seeds), tau0_2)
    pr = expected_log_pref(
        citta, cand, prefs, k, tau0_2, p_canary_fail=p_canary_fail, audit_severity=audit_severity
    )
    cost_term = kappa * cand.cost_est_gpu_h / budget
    g = math.inf if pr == -math.inf else -gamma.epi * e - gamma.prag * pr + cost_term
    return EFETerms(
        candidate_id=cand.id, G=g, EIG=e, pragmatic=pr, cost_term=cost_term, gamma=gamma, kappa=kappa
    )
