import math

import numpy as np

from pravrudhi_kernel.stats import bca_ci, boot_ci_bca_g, non_inferiority
from pravrudhi_kernel.stats.bca import _ndtr, _ndtri


def test_prop_bca_ci_degenerate_inputs_return_point() -> None:
    assert bca_ci(np.array([1.0]), lambda v: float(np.mean(v))) == (1.0, 1.0)
    assert bca_ci(np.array([2.0, 2.0, 2.0]), lambda v: float(np.mean(v))) == (2.0, 2.0)


def test_prop_bca_ci_handles_non_finite_bootstrap_stat() -> None:
    lo, hi = bca_ci(np.array([1.0, 2.0, 3.0, 4.0]), lambda v: float("nan"), n_boot=50)
    assert math.isnan(lo) and math.isnan(hi)


def test_prop_boot_ci_bca_g_small_and_degenerate() -> None:
    assert (
        boot_ci_bca_g(np.array([1.0, 2.0]), np.array([0.0, 1.0]))
        == (boot_ci_bca_g(np.array([1.0, 2.0]), np.array([0.0, 1.0]))[0],) * 2
    )
    lo, hi = boot_ci_bca_g(np.array([1.0, 1.0, 1.0, 1.0]), np.array([0.0, 0.0, 0.0, 0.0]), n_boot=50)
    assert lo == hi


def test_prop_boot_ci_bca_g_rejects_unpaired_lengths() -> None:
    try:
        boot_ci_bca_g(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0]))
    except ValueError as e:
        assert "paired" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_prop_ndtri_inverts_ndtr_across_tails() -> None:
    for p in (1e-6, 0.01, 0.024, 0.3, 0.5, 0.7, 0.976, 0.99, 1 - 1e-6):
        assert abs(_ndtr(_ndtri(p)) - p) < 1e-7
    assert _ndtri(0.0) == -math.inf and _ndtri(1.0) == math.inf


def test_prop_non_inferiority_degenerate_paths() -> None:
    r = non_inferiority(np.array([0.5]), 0.1)
    assert r.n == 1 and r.non_inferior and r.tost_p_lower == 0.0
    r0 = non_inferiority(np.array([]), 0.1)
    assert r0.n == 0 and not r0.non_inferior
