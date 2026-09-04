import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from pravrudhi_kernel.efe import (
    BeliefKeys,
    PrecisionView,
    Shares,
    beta_binomial_update,
    beta_eig,
    decorative_check,
    efe,
    eig,
    expected_log_pref,
    habit_prior,
    infer_precision,
    knapsack_batch,
    posterior_update,
    posterior_update_prediction,
    pseudo_observation_variance,
    rank_hypothesis_candidates,
    selection_probabilities,
)
from pravrudhi_kernel.efe.decorative import bernoulli_kl
from pravrudhi_kernel.efe.types import Precision
from pravrudhi_kernel.efe.update import prior_for
from pravrudhi_kernel.schema import Candidate, Citta, EvidencePlan, Prediction, Preferences
from pravrudhi_kernel.schema.citta import CandidateBelief, NormalBelief

H = "0" * 64
BUCKET = {"task_family": "t", "target_model": "m", "corpus": "c"}
KEYS = BeliefKeys(surface="W3.adapter", strategy="sft", bucket="t|m|c|optimiser", candidate_id="c-0001")
EMPTY = Citta(version=0, surfaces={}, strategies={}, buckets={}, candidates={}, rho_pred={})
PLAN = EvidencePlan(
    seeds=[1], heldout_rotation_id=None, sensors_to_read=[], stage="smoke", sequential_stage=0
)
PREFS = Preferences(beta=1.0, lambda_=2.0, eta=1.0)
pos = st.floats(1e-4, 10.0, allow_nan=False, allow_infinity=False)
val = st.floats(-1.0, 1.0, allow_nan=False, allow_infinity=False)


def _cand(
    cid: str = "c-0001", cost: float = 0.2, surface: str = "W3.adapter", need: str = "executor"
) -> Candidate:
    return Candidate(
        id=cid,
        surface=surface,
        bucket=BUCKET,
        edit_family="optimiser",
        strategy="sft",
        lineage=[],
        diff_ref=H,
        cost_est_gpu_h=cost,
        residency_need=need,
        predicted=Prediction(delta_in=0.0, delta_out=None, conf=0.0, hash=H),
        abstraction_level="madhyama",
        provenance="agama",
    )


@given(st.lists(st.tuples(val, pos), min_size=1, max_size=8), pos)
def test_prop_posterior_update_variance_non_increasing_and_hierarchy_moves_less(
    obs: list[tuple[float, float]], tau0_2: float
) -> None:
    c = EMPTY
    prev_var = math.inf
    for v, s2 in obs:
        c = posterior_update(c, KEYS, v, s2, tau0_2)
        var = c.candidates["c-0001"].sigma2
        assert var <= prev_var + 1e-12 and var > 0
        prev_var = var
    assert c.candidates["c-0001"].n_obs == len(obs)
    assert c.buckets[KEYS.bucket_key].tau2 >= c.candidates["c-0001"].sigma2 - 1e-12
    assert c.version == len(obs)


@given(pos, st.floats(0.0, 1.0), st.floats(0.0, 1.0))
def test_prop_pseudo_observation_variance_grows_with_low_confidence_and_low_rho(
    s2: float, conf: float, rho: float
) -> None:
    v = pseudo_observation_variance(s2, conf, rho)
    assert v > 0 and math.isfinite(v)
    assert pseudo_observation_variance(s2, min(conf + 0.1, 1.0), rho) <= v + 1e-9
    assert pseudo_observation_variance(s2, conf, min(rho + 0.1, 1.0)) <= v + 1e-9


@given(val, st.floats(0.01, 0.99), pos)
def test_prop_posterior_update_prediction_never_outweighs_a_kernel_observation(
    delta_hat: float, conf: float, s2: float
) -> None:
    c = EMPTY.model_copy(update={"rho_pred": {"W3.adapter": 0.5}})
    a = posterior_update_prediction(c, KEYS, delta_hat, conf, s2, 0.01)
    b = posterior_update(c, KEYS, delta_hat, s2, 0.01)
    assert a.candidates["c-0001"].sigma2 >= b.candidates["c-0001"].sigma2 - 1e-12


@given(pos, pos, st.integers(1, 6), pos)
def test_prop_eig_nonnegative_and_vanishes_as_posterior_tightens(
    s2_post: float, s2_eval: float, n: int, tau0_2: float
) -> None:
    wide = EMPTY.model_copy(
        update={"candidates": {"c-0001": CandidateBelief(mu=0.0, sigma2=s2_post, n_obs=1)}}
    )
    nb = NormalBelief(mu=0.0, tau2=1e-12, n=9)
    tight_all = EMPTY.model_copy(
        update={
            "candidates": {"c-0001": CandidateBelief(mu=0.0, sigma2=1e-12, n_obs=9)},
            "surfaces": {"W3.adapter": nb},
            "strategies": {"W3.adapter|sft": nb},
            "buckets": {KEYS.bucket_key: nb},
        }
    )
    e_wide, e_tight = eig(wide, KEYS, s2_eval, n, tau0_2), eig(tight_all, KEYS, s2_eval, n, tau0_2)
    assert e_wide >= 0 and e_tight >= 0 and e_tight < 1e-6
    assert eig(wide, KEYS, s2_eval, n + 1, tau0_2) >= eig(wide, KEYS, s2_eval, n, tau0_2) - 1e-9


@given(st.floats(0.0, 2.0), st.floats(0.0, 2.0))
def test_prop_efe_monotone_in_cost_and_infinite_for_t0(c1: float, c2: float) -> None:
    lo, hi = sorted((c1, c2))
    g = Precision(epi=0.5, prag=1.0)
    t_lo = efe(EMPTY, _cand(cost=lo), PLAN, PREFS, g, 1.0, 8.0, 0.0004, 0.01)
    t_hi = efe(EMPTY, _cand(cost=hi), PLAN, PREFS, g, 1.0, 8.0, 0.0004, 0.01)
    assert t_lo.G <= t_hi.G + 1e-12
    assert math.isinf(efe(EMPTY, _cand(surface="T0.kernel"), PLAN, PREFS, g, 1.0, 8.0, 0.0004, 0.01).G)


@given(val, pos)
def test_prop_expected_log_pref_penalises_downside_more_than_it_rewards_upside(mu: float, s2: float) -> None:
    up = EMPTY.model_copy(update={"candidates": {"c-0001": CandidateBelief(mu=abs(mu), sigma2=s2, n_obs=1)}})
    down = EMPTY.model_copy(
        update={"candidates": {"c-0001": CandidateBelief(mu=-abs(mu), sigma2=s2, n_obs=1)}}
    )
    a, b = (
        expected_log_pref(up, _cand(), PREFS, KEYS, 0.01),
        expected_log_pref(down, _cand(), PREFS, KEYS, 0.01),
    )
    assert a >= b
    assert expected_log_pref(up, _cand(surface="T0.kernel"), PREFS, KEYS, 0.01) == -math.inf


@given(st.lists(pos, max_size=6), pos, st.floats(0.0, 1.0))
def test_prop_infer_precision_respects_floors_and_bounds(pool: list[float], s2: float, rho: float) -> None:
    p = infer_precision(
        PrecisionView(pool_post_var=pool, sigma2_eval=s2, rho_pred=rho, f_epi=0.15, rho_floor=0.05)
    )
    assert 0.15 <= p.epi <= 1.0 and 0.05 <= p.prag <= 1.0


@given(st.integers(0, 20), st.integers(0, 20), pos, pos)
def test_prop_beta_binomial_update_counts_add(s: int, f: int, a: float, b: float) -> None:
    a2, b2 = beta_binomial_update(a, b, s, f)
    assert a2 == a + s and b2 == b + f


@given(st.dictionaries(st.text("abc", min_size=1, max_size=3), st.floats(-5, 5), min_size=1, max_size=6))
def test_prop_selection_probabilities_is_a_distribution_and_monotone_in_G(G: dict[str, float]) -> None:
    Q = selection_probabilities(G, {k: 1.0 for k in G})
    assert abs(sum(Q.values()) - 1.0) < 1e-9
    ks = sorted(G, key=lambda k: G[k])
    for a, b in zip(ks, ks[1:], strict=False):
        assert Q[a] >= Q[b] - 1e-12


@given(val, pos)
def test_prop_habit_prior_in_open_unit_interval_and_monotone_in_mean(mu: float, tau2: float) -> None:
    c = EMPTY.model_copy(update={"buckets": {KEYS.bucket_key: NormalBelief(mu=mu, tau2=tau2, n=1)}})
    h = habit_prior(c, KEYS, 0.01)
    c2 = EMPTY.model_copy(update={"buckets": {KEYS.bucket_key: NormalBelief(mu=mu + 0.1, tau2=tau2, n=1)}})
    assert 0 < h < 1 and habit_prior(c2, KEYS, 0.01) >= h


@settings(max_examples=40, deadline=None)
@given(st.integers(2, 10), st.floats(0.5, 10.0), st.integers(0, 1000))
def test_prop_knapsack_batch_respects_budget_and_residency(n: int, budget: float, seed: int) -> None:
    rng = np.random.default_rng(seed)
    cands = {}
    for i in range(n):
        need = "reasoner" if i % 3 == 0 else "executor"
        cands[f"c-{i:04d}"] = _cand(f"c-{i:04d}", cost=float(rng.uniform(0.05, 0.6 * budget)), need=need)
    Q = {k: 1.0 / n for k in cands}
    eigs = {k: float(rng.uniform(0, 1)) for k in cands}
    b = knapsack_batch(Q, cands, eigs, budget, Shares(planted=0.1, sensors=0.1, f_epi=0.15), rng)
    assert b.spent_gpu_h <= b.budget_effective + 1e-9
    assert b.budget_effective == budget * 0.8
    assert all(cands[i].residency_need == "reasoner" for i in b.deliberation)
    assert all(cands[i].residency_need != "reasoner" for i in b.execution)
    assert len(b.exclusive) <= 1
    assert set(b.epistemic_ids) <= set(b.deliberation) | set(b.execution)


@given(st.integers(2, 12), st.floats(1.0, 3.0))
def test_prop_decorative_check_fails_on_constant_scores_passes_on_planted_spread(
    n: int, spread: float
) -> None:
    ids = [f"c-{i:04d}" for i in range(n)]
    const = dict.fromkeys(ids, 1.234)
    Q_uniform = {i: 1.0 / n for i in ids}
    assert decorative_check(const, Q_uniform, 0.05, 0.05).verdict == "fail"
    spread_scores = {i: float(k) * spread for k, i in enumerate(ids)}
    Q = selection_probabilities(spread_scores, {i: 1.0 for i in ids})
    v = decorative_check(spread_scores, Q, 0.05, 0.05)
    assert v.verdict == "pass", v


def test_prop_rank_hypothesis_candidates_degenerate_only_when_alike() -> None:
    spec = {
        "beliefs": {"h": 0.3},
        "cost_weight": 0.0,
        "candidates": [
            {"name": "a", "cost": 0, "diagnosticity": {"h": [0.9, 0.1]}, "payoff": {"h": 1.0}},
            {"name": "b", "cost": 0, "diagnosticity": {"h": [0.5, 0.5]}, "payoff": {"h": 0.0}},
        ],
    }
    assert rank_hypothesis_candidates(spec)["degenerate"] is False
    spec["candidates"][1] = dict(spec["candidates"][0], name="b")
    assert rank_hypothesis_candidates(spec)["degenerate"] is True


@given(pos, pos)
def test_prop_beta_eig_bounded_by_one_bit_and_vanishes_with_evidence(a: float, b: float) -> None:
    e = beta_eig(a, b)
    assert 0.0 <= e <= math.log(2) + 1e-9
    assert beta_eig(a + 5000, b + 5000) < 1e-3


@given(st.floats(0.0, 1.0), st.floats(0.0, 1.0))
def test_prop_bernoulli_kl_nonnegative_and_zero_on_equal(p: float, q: float) -> None:
    assert bernoulli_kl(p, q) >= -1e-12
    assert abs(bernoulli_kl(p, p)) < 1e-12


@given(val, pos, pos)
def test_prop_prior_for_uses_most_specific_level_with_data(mu: float, tau2: float, tau0_2: float) -> None:
    assert prior_for(EMPTY, KEYS, tau0_2) == CandidateBelief(mu=0.0, sigma2=tau0_2, n_obs=0)
    with_surface = EMPTY.model_copy(update={"surfaces": {"W3.adapter": NormalBelief(mu=mu, tau2=tau2, n=2)}})
    assert prior_for(with_surface, KEYS, tau0_2).mu == mu
    with_bucket = with_surface.model_copy(
        update={"buckets": {KEYS.bucket_key: NormalBelief(mu=mu + 1, tau2=tau2, n=1)}}
    )
    assert prior_for(with_bucket, KEYS, tau0_2).mu == mu + 1


def test_prop_selection_probabilities_edge_cases() -> None:
    assert selection_probabilities({}, {}) == {}
    assert selection_probabilities({"a": math.inf, "b": math.inf}, {}) == {"a": 0.0, "b": 0.0}


def test_prop_knapsack_batch_keeps_one_exclusive_job_and_rejects_bad_budget() -> None:
    rng = np.random.default_rng(1)
    big = {f"c-{i:04d}": _cand(f"c-{i:04d}", cost=5.0) for i in range(3)}
    Q = {k: 1 / 3 for k in big}
    b = knapsack_batch(
        Q, big, dict.fromkeys(big, 0.0), 10.0, Shares(planted=0.0, sensors=0.0, f_epi=0.15), rng
    )
    assert len(b.exclusive) == 1 and b.spent_gpu_h == 5.0
    try:
        knapsack_batch(Q, big, {}, 0.0, Shares(planted=0.0, sensors=0.0, f_epi=0.15), rng)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_prop_decorative_check_edge_branches() -> None:
    assert decorative_check({"a": 1.0}, {"a": 1.0}, 0.05, 0.05).reason == "fewer than two candidates"
    v = decorative_check({"a": 1.0, "b": 1.0001}, {"a": 0.5, "b": 0.5}, 0.05, 0.05)
    assert v.verdict == "fail" and v.reason is not None and v.reason.startswith("cv_G")
    v = decorative_check({"a": math.inf, "b": 1.0, "c": 2.0}, {"a": 0.0, "b": 0.5, "c": 0.5}, 0.05, 0.05)
    assert v.verdict == "fail" and v.reason is not None and v.reason.startswith("mi_bits")


def test_prop_rank_hypothesis_candidates_rejects_bad_input() -> None:
    import pytest

    with pytest.raises(ValueError):
        rank_hypothesis_candidates({"beliefs": {"h": 1.0}, "candidates": []})
    with pytest.raises(ValueError):
        rank_hypothesis_candidates(
            {"beliefs": {"h": 0.5}, "candidates": [{"name": "a", "diagnosticity": {"zz": [0.5, 0.5]}}]}
        )
