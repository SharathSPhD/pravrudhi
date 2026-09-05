import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from pravrudhi_kernel.stats import (
    Variance,
    bca_ci,
    boot_ci_bca_g,
    boot_ci_bca_mean,
    boot_ci_g,
    hedges_g,
    holm,
    label_shuffle_null,
    non_inferiority,
    permutation_p,
    screen,
    sequential_boundary,
    wilson_ci,
)
from pravrudhi_kernel.stats.sequential import conf_seq_halfwidth, e_process, effective_sigma

finite = st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False)


def vec(n_min: int = 2, n_max: int = 12):  # type: ignore[no-untyped-def]
    return st.integers(n_min, n_max).flatmap(lambda n: arrays(np.float64, n, elements=finite))


def pair(n_min: int = 2, n_max: int = 12):  # type: ignore[no-untyped-def]
    return st.integers(n_min, n_max).flatmap(
        lambda n: st.tuples(arrays(np.float64, n, elements=finite), arrays(np.float64, n, elements=finite))
    )


@given(pair())
@settings(max_examples=60, deadline=None)
def test_prop_hedges_g_antisymmetric_under_arm_swap(xy: tuple[np.ndarray, np.ndarray]) -> None:
    x, y = xy
    assert math.isclose(hedges_g(x, y), -hedges_g(y, x), abs_tol=1e-9, rel_tol=1e-9)


@given(pair())
@settings(max_examples=40, deadline=None)
def test_prop_permutation_p_in_unit_interval(xy: tuple[np.ndarray, np.ndarray]) -> None:
    x, y = xy
    p = permutation_p(x, y, 200, 1)
    assert 0.0 < p <= 1.0


@given(pair(4, 10))
@settings(max_examples=25, deadline=None)
def test_prop_boot_ci_g_is_ordered(xy: tuple[np.ndarray, np.ndarray]) -> None:
    x, y = xy
    lo, hi = boot_ci_g(x, y, 100, 0.05, 1)
    assert lo <= hi


@given(st.dictionaries(st.text(min_size=1, max_size=4), st.floats(0, 1), min_size=1, max_size=8))
def test_prop_holm_monotone_and_rejects_only_below_alpha(pvals: dict[str, float]) -> None:
    out = holm(pvals, 0.05)
    rej = [p for n, p in pvals.items() if out[n]]
    acc = [p for n, p in pvals.items() if not out[n]]
    assert all(p <= 0.05 for p in rej)
    assert not rej or not acc or max(rej) <= min(acc)


@given(pair(3, 8))
@settings(max_examples=15, deadline=None)
def test_prop_screen_reports_all_fields(xy: tuple[np.ndarray, np.ndarray]) -> None:
    x, y = xy
    s = screen(x, y, {"permutation_resamples": 100, "seed": 2})
    assert s["tier"] == "screen" and set(s) == {"tier", "p_perm", "hedges_g", "g_ci95", "n"}


@given(vec(3, 15))
@settings(max_examples=30, deadline=None)
def test_prop_bca_ci_contains_point_estimate(d: np.ndarray) -> None:
    lo, hi = bca_ci(d, lambda v: float(np.mean(v)), n_boot=300, seed=3)
    m = float(np.mean(d))
    assert lo - 1e-9 <= m <= hi + 1e-9


@given(vec(3, 15))
@settings(max_examples=20, deadline=None)
def test_prop_boot_ci_bca_mean_contains_point_estimate(d: np.ndarray) -> None:
    lo, hi = boot_ci_bca_mean(d, n_boot=300, seed=5)
    assert lo - 1e-9 <= float(np.mean(d)) <= hi + 1e-9


@given(pair(4, 10))
@settings(max_examples=15, deadline=None)
def test_prop_boot_ci_bca_g_ordered_and_finite(xy: tuple[np.ndarray, np.ndarray]) -> None:
    x, y = xy
    lo, hi = boot_ci_bca_g(x, y, n_boot=200, seed=4)
    assert lo <= hi and math.isfinite(lo) and math.isfinite(hi)


@given(st.integers(1, 500), st.data())
def test_prop_wilson_ci_shrinks_with_n_and_brackets_rate(n: int, data: st.DataObject) -> None:
    k = data.draw(st.integers(0, n))
    lo, hi = wilson_ci(k, n)
    assert 0.0 <= lo <= k / n <= hi <= 1.0
    lo2, hi2 = wilson_ci(4 * k, 4 * n)
    assert (hi2 - lo2) <= (hi - lo) + 1e-12


@given(vec(2, 12), st.floats(0.001, 1.0))
@settings(max_examples=30, deadline=None)
def test_prop_non_inferiority_consistent_with_its_own_ci(d: np.ndarray, margin: float) -> None:
    r = non_inferiority(d, margin, n_boot=300, seed=6)
    assert r.non_inferior == (r.ci_lower > -margin)
    assert r.ci_lower - 1e-9 <= r.delta_mean <= r.ci_upper + 1e-9
    assert 0.0 <= r.tost_p_lower <= 1.0 and 0.0 <= r.tost_p_upper <= 1.0


@given(st.integers(5, 30), st.integers(0, 50))
@settings(max_examples=20, deadline=None)
def test_prop_label_shuffle_null_p_in_unit_interval(n: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 2))
    y = (X[:, 0] > 0).astype(int)
    r = label_shuffle_null(lambda A, b: float(np.mean((A[:, 0] > 0).astype(int) == b)), X, y, n_shuffle=30, random_state=seed)
    assert 0.0 < r["p_value"] <= 1.0 and r["true_score"] == 1.0


BENCH = Variance(bench="test", sigma_seed=0.02, tau=0.02, delta_min=0.02, k_max=6)
FIXED = Variance(bench="t", sigma_seed=0.02, tau=0.02, delta_min=0.02, k_max=6, sigma_mode="fixed")


def test_prop_sequential_boundary_never_confirms_on_empty_or_negative() -> None:
    assert sequential_boundary([], BENCH).decision == "continue"
    for xs in ([-0.5], [-0.1, -0.2, -0.3], [0.0] * 6):
        assert sequential_boundary(xs, BENCH).decision != "confirm"


@given(st.lists(st.floats(-0.1, 0.1, allow_nan=False), min_size=1, max_size=6))
def test_prop_sequential_boundary_confirm_has_positive_mean_and_crossed_e(xs: list[float]) -> None:
    r = sequential_boundary(xs, BENCH)
    if r.decision == "confirm":
        assert r.xbar > 0 and r.e_value >= 1 / BENCH.alpha_eff
    if r.decision == "prune" and r.n < BENCH.k_max:
        assert r.hetvabhasa == "asiddha"


@given(st.integers(1, 12))
def test_prop_conf_seq_halfwidth_monotone_in_n(n: int) -> None:
    assert conf_seq_halfwidth(n + 1, 0.02, 0.02, 0.2) <= conf_seq_halfwidth(n, 0.02, 0.02, 0.2) + 1e-12


@given(st.lists(st.floats(-0.1, 0.1, allow_nan=False), min_size=0, max_size=6))
def test_prop_e_process_positive_and_one_on_empty(xs: list[float]) -> None:
    e = e_process(xs, 0.02, 0.02)
    assert e > 0 and (xs or e == 1.0)


@given(st.lists(st.floats(-0.1, 0.1, allow_nan=False), min_size=0, max_size=6))
def test_prop_effective_sigma_positive_and_fixed_is_prior(xs: list[float]) -> None:
    assert effective_sigma(xs, FIXED) == FIXED.sigma_seed
    assert effective_sigma(xs, BENCH) > 0


def test_prop_sequential_boundary_false_confirm_rate_under_null_bounded() -> None:
    """Under theta=0 with the true sigma, confirm across all stages must not exceed alpha_eff."""
    rng = np.random.default_rng(20260904)
    n_streams, confirms = 4000, 0
    for _ in range(n_streams):
        xs: list[float] = []
        for _k in range(BENCH.k_max):
            xs.append(float(rng.normal(0.0, BENCH.sigma_seed)))
            r = sequential_boundary(xs, BENCH)
            if r.decision == "confirm":
                confirms += 1
                break
            if r.decision == "prune":
                break
    lo, hi = wilson_ci(confirms, n_streams)
    print(f"\nSEQ null confirm rate={confirms / n_streams:.4f} wilson=[{lo:.4f},{hi:.4f}] n={n_streams}")
    assert lo <= BENCH.alpha_eff
