"""The H1 baseline arms: ranking and budget filling."""
import numpy as np
import pytest

from pravrudhi.application.policies import (
    BASELINES,
    GEAR_NOVELTY_BONUS,
    POLICIES,
    fill_budget,
    rank_scores,
    selection_weights,
)


class B:
    def __init__(self, mu, sigma2, n_obs=0):
        self.mu, self.sigma2, self.n_obs = mu, sigma2, n_obs


class Citta:
    def __init__(self, d):
        self.candidates = d


def _citta():
    return Citta({"a": B(0.05, 0.001), "b": B(0.01, 0.02), "c": B(0.03, 0.001)})


def test_greedy_ranks_by_posterior_mean():
    s = rank_scores("greedy", _citta(), ["a", "b", "c"], np.random.default_rng(0))
    assert sorted(s, key=lambda c: -s[c]) == ["a", "c", "b"]


def test_thompson_can_prefer_a_wide_posterior_and_is_seeded():
    pool = ["a", "b", "c"]
    picks = [sorted(rank_scores("thompson", _citta(), pool, np.random.default_rng(i)), key=lambda c: -rank_scores("thompson",
        _citta(), pool, np.random.default_rng(i))[c])[0] for i in range(40)]
    assert "b" in picks, "a wide posterior should sometimes win under Thompson sampling"
    r1 = rank_scores("thompson", _citta(), pool, np.random.default_rng(7))
    r2 = rank_scores("thompson", _citta(), pool, np.random.default_rng(7))
    assert r1 == r2, "same seed, same draw: a night must replay"


def test_random_ignores_the_evidence():
    c = Citta({"a": B(10.0, 0.001), "b": B(-10.0, 0.001)})
    wins = sum(1 for i in range(60) if max(rank_scores("random", c, ["a", "b"], np.random.default_rng(i)).items(),
        key=lambda kv: kv[1])[0] == "b")
    assert 10 < wins < 50


def test_fill_budget_respects_cost_and_is_deterministic():
    scores = {"a": 0.9, "b": 0.5, "c": 0.7}
    costs = {"a": 0.4, "b": 0.4, "c": 0.4}
    assert fill_budget(scores, costs, 1.0) == ["a", "c"]
    assert fill_budget(scores, costs, 0.0) == []
    # an unaffordable candidate is skipped, not a stop
    assert fill_budget({"a": 9.0, "b": 1.0}, {"a": 99.0, "b": 0.1}, 1.0) == ["b"]
    # ties break on id so the night replays
    assert fill_budget({"z": 1.0, "y": 1.0}, {"z": 0.5, "y": 0.5}, 1.0) == ["y", "z"]


def test_selection_weights_are_a_distribution_over_the_taken():
    w = selection_weights({"a": 1.0, "b": 0.0, "c": 2.0}, ["a", "c"])
    assert w == {"a": 0.5, "b": 0.0, "c": 0.5} and abs(sum(w.values()) - 1.0) < 1e-12
    assert sum(selection_weights({"a": 1.0}, []).values()) == 0.0


def test_efe_is_not_a_baseline():
    with pytest.raises(ValueError):
        rank_scores("efe", _citta(), ["a"], np.random.default_rng(0))
    assert "efe" not in BASELINES


# The two lineage arms of H1 (c) and (d). Before they existed the ledger had no GEAR-like or HGM-like arm, so the
# pre-registered "lower regret than GEAR-like frontier search / HGM-like lineage selection" was not executable.

POOL = ["x", "y", "z"]
LINEAGE = {"x": "p-best", "y": "p-worst", "z": None}


def _lineage_citta():
    """Three archived ancestors carrying evidence; three live candidates whose own means contradict their lineage."""
    return Citta({
        "p-best": B(0.9, 0.001, 3),
        "p-mid": B(0.1, 0.001, 2),
        "p-worst": B(-0.5, 0.001, 3),
        "x": B(-1.0, 0.02, 0),
        "y": B(1.0, 0.02, 0),
        "z": B(0.0, 0.02, 0),
    })


def test_gear_ranks_by_the_standing_of_the_nearest_archived_ancestor():
    s = rank_scores("gear", _lineage_citta(), POOL, np.random.default_rng(0), LINEAGE)
    # three in the archive: best standing 3/3, then 2/3, then 1/3.
    assert s["x"] == pytest.approx(1.0) and s["y"] == pytest.approx(1.0 / 3.0)
    assert s["x"] > s["y"], "a candidate whose parent leads the archive outranks one whose parent trails it"
    # and this is not greedy in disguise: on their own means the order is the other way round.
    g = rank_scores("greedy", _lineage_citta(), POOL, np.random.default_rng(0))
    assert g["y"] > g["x"]


def test_gear_gives_an_unexplored_lineage_the_novelty_bonus():
    s = rank_scores("gear", _lineage_citta(), POOL, np.random.default_rng(0), LINEAGE)
    assert s["z"] == pytest.approx(GEAR_NOVELTY_BONUS)
    assert s["x"] > s["z"] > s["y"], "novelty sits mid-archive: below a strong lineage, above a weak one"


def test_gear_falls_back_to_the_candidates_own_archive_entry_when_no_lineage_is_given():
    # citta records no parent id; with no map the only ancestry a candidate can attest is its own evidence.
    c = Citta({"a": B(0.9, 0.001, 2), "b": B(-0.9, 0.001, 2), "new": B(0.5, 0.02, 0)})
    s = rank_scores("gear", c, ["a", "b", "new"], np.random.default_rng(0))
    assert s["a"] == pytest.approx(1.0) and s["b"] == pytest.approx(0.5)
    assert s["new"] == pytest.approx(GEAR_NOVELTY_BONUS)


def test_hgm_shrinks_toward_the_lineage_in_proportion_to_the_lineages_evidence():
    c = Citta({
        "p-strong": B(-0.5, 0.001, 4),
        "p-weak": B(-0.5, 0.001, 1),
        "strong-kid": B(0.5, 0.02, 0),
        "weak-kid": B(0.5, 0.02, 0),
        "lone": B(0.5, 0.02, 0),
    })
    lin = {"strong-kid": "p-strong", "weak-kid": "p-weak", "lone": None}
    s = rank_scores("hgm", c, ["strong-kid", "weak-kid", "lone"], np.random.default_rng(0), lin)
    assert s["lone"] == pytest.approx(0.5), "a lone candidate is judged by its own prior, untouched"
    moved = {k: abs(v - 0.5) for k, v in s.items()}
    assert moved["lone"] < moved["weak-kid"] < moved["strong-kid"]
    assert s["strong-kid"] == pytest.approx(0.2 * 0.5 + 0.8 * -0.5)  # w = 4 / (4 + 1)


def test_hgm_falls_back_to_a_leave_one_out_archive_and_never_shrinks_a_candidate_toward_itself():
    c = Citta({"a": B(1.0, 0.001, 4), "b": B(-1.0, 0.001, 4), "new": B(0.2, 0.02, 0)})
    s = rank_scores("hgm", c, ["a", "new"], np.random.default_rng(0))
    # `new` carries no evidence, so the archive (mean 0.0) is almost all of its score.
    assert 0.0 < s["new"] < 0.2
    # `a` is shrunk toward the archive WITHOUT itself, i.e. toward b, so it crosses zero; including itself
    # (archive mean 0.0) could only have pulled it down to 0.2.
    assert s["a"] < 0.0


def test_the_lineage_arms_are_deterministic_and_never_touch_the_rng():
    for policy in ("gear", "hgm"):
        a = rank_scores(policy, _lineage_citta(), POOL, np.random.default_rng(1), LINEAGE)
        b = rank_scores(policy, _lineage_citta(), POOL, np.random.default_rng(99), LINEAGE)
        assert a == b, f"{policy} must replay from the ledger alone"


def test_the_lineage_arms_fill_the_budget_exactly_as_greedy_does():
    costs = {c: 0.4 for c in POOL}
    rng = np.random.default_rng(0)
    filled = {
        p: fill_budget(rank_scores(p, _lineage_citta(), POOL, rng, LINEAGE), costs, 1.0)
        for p in ("greedy", "gear", "hgm")
    }
    # no arm reserves budget: each takes the same number of candidates, differing only in which.
    assert all(len(v) == 2 for v in filled.values())
    assert filled["gear"] == ["x", "z"] and filled["greedy"] == ["y", "z"]
    whole = {p: fill_budget(rank_scores(p, _lineage_citta(), POOL, rng, LINEAGE), costs, 10.0)
             for p in ("greedy", "gear", "hgm")}
    assert all(sorted(v) == POOL for v in whole.values()), "with budget to spare every arm takes the whole pool"


def test_the_lineage_arms_are_registered_arms():
    for policy in ("gear", "hgm"):
        assert policy in POLICIES and policy in BASELINES, "a night must be launchable with --policy " + policy
