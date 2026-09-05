"""ADR-0017: an extreme draw must not overflow the e-process; the boundary still decides."""
import math

from pravrudhi_kernel.stats.sequential import Variance, e_process, sequential_boundary


def test_extreme_delta_is_finite_and_prunes():
    b = Variance(bench="mbppplus", sigma_seed=0.0105, tau=0.021, delta_min=0.021, alpha_eff=0.05, alpha_fut=0.20,
                 k_max=4, sigma_mode="adaptive", n0=3)
    e = e_process([-0.31], 0.0105, 0.021)
    assert math.isfinite(e)
    r = sequential_boundary([-0.31], b)
    assert r.decision == "prune" and math.isfinite(r.e_value)
    assert sequential_boundary([0.31], b).decision == "confirm"


def test_min_n_confirm_delays_a_single_seed_crossing():
    kw = dict(bench="mbppplus", sigma_seed=0.0105, tau=0.021, delta_min=0.021, alpha_eff=0.05, alpha_fut=0.20,
              k_max=4, sigma_mode="adaptive", n0=3)
    assert sequential_boundary([0.09], Variance(**kw)).decision == "confirm"
    strict = Variance(**kw, min_n_confirm=2)
    assert sequential_boundary([0.09], strict).decision == "continue"
    assert sequential_boundary([0.09, 0.08], strict).decision == "confirm"
    assert sequential_boundary([-0.31], strict).decision == "prune"
