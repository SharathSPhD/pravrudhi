"""The H1 baseline arms: ranking and budget filling."""
import numpy as np
import pytest

from pravrudhi.application.policies import BASELINES, fill_budget, rank_scores, selection_weights


class B:
    def __init__(self, mu, sigma2):
        self.mu, self.sigma2 = mu, sigma2


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
