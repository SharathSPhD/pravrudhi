"""Vendored stats vs committed fixtures generated from the source implementations (never installed in CI)."""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pravrudhi_kernel.stats import boot_ci_g, hedges_g, holm, label_shuffle_null, permutation_p, screen

FX = Path(__file__).parent / "fixtures"
TOL = 1e-9


def _dec(v: Any) -> Any:
    if isinstance(v, dict) and "__float__" in v:
        return float(v["__float__"])
    if isinstance(v, list):
        return [_dec(i) for i in v]
    if isinstance(v, dict):
        return {k: _dec(i) for k, i in v.items()}
    return v


def _load(name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = _dec(json.loads((FX / f"{name}.json").read_text()))
    assert len(rows) >= 50, f"{name}: {len(rows)} fixtures"
    return rows


def _close(a: float, b: float) -> bool:
    if math.isnan(a) and math.isnan(b):
        return True
    return math.isclose(a, b, rel_tol=0.0, abs_tol=TOL) or math.isclose(a, b, rel_tol=TOL)


@pytest.mark.parametrize("row", _load("hedges_g"), ids=lambda r: r["cls"])
def test_hedges_g_parity(row: dict[str, Any]) -> None:
    assert _close(hedges_g(np.asarray(row["x"]), np.asarray(row["y"])), row["out"])


@pytest.mark.parametrize("row", _load("permutation_p"), ids=lambda r: f"{r['cls']}-{'p' if r['paired'] else 'u'}")
def test_permutation_p_parity(row: dict[str, Any]) -> None:
    got = permutation_p(np.asarray(row["x"]), np.asarray(row["y"]), row["n_resamples"], row["seed"], row["paired"])
    # same seed, same numpy generator, same algorithm: exact agreement; tolerance 1e-9, not Monte-Carlo
    assert _close(got, row["out"])


@pytest.mark.parametrize("row", _load("boot_ci_g"), ids=lambda r: r["cls"])
def test_boot_ci_g_parity(row: dict[str, Any]) -> None:
    lo, hi = boot_ci_g(np.asarray(row["x"]), np.asarray(row["y"]), row["n_boot"], 0.05, row["seed"])
    assert _close(lo, row["out"][0]) and _close(hi, row["out"][1])


@pytest.mark.parametrize("row", _load("holm"), ids=lambda r: r["cls"])
def test_holm_parity(row: dict[str, Any]) -> None:
    assert holm(row["pvals"], row["alpha"]) == row["out"]


@pytest.mark.parametrize("row", _load("screen"), ids=lambda r: r["cls"])
def test_screen_parity(row: dict[str, Any]) -> None:
    got = screen(np.asarray(row["x"]), np.asarray(row["y"]), row["cfg"])
    want = row["out"]
    assert got["tier"] == want["tier"] and list(got["n"]) == list(want["n"])  # type: ignore[call-overload]
    assert _close(got["p_perm"], want["p_perm"]) and _close(got["hedges_g"], want["hedges_g"])  # type: ignore[arg-type]
    ci = got["g_ci95"]
    assert _close(ci[0], want["g_ci95"][0]) and _close(ci[1], want["g_ci95"][1])  # type: ignore[index]


@pytest.mark.parametrize("row", _load("label_shuffle_null"), ids=lambda r: f"rs{r['random_state']}")
def test_label_shuffle_parity(row: dict[str, Any]) -> None:
    X, y, w = np.asarray(row["X"]), np.asarray(row["y"]), np.asarray(row["w"])
    got = label_shuffle_null(
        lambda A, b: float(np.mean((A @ w > 0).astype(int) == b)),
        X,
        y,
        n_shuffle=row["n_shuffle"],
        random_state=row["random_state"],
    )
    for k in ("true_score", "null_mean", "null_std", "p_value"):
        assert _close(got[k], row["out"][k]), k


def test_parity_table_prints() -> None:
    """Emits the function x fixture-class x max-abs-diff table the gate cites."""
    table: list[tuple[str, str, float]] = []

    def add(name: str, diffs: list[tuple[str, float]]) -> None:
        by_cls: dict[str, float] = {}
        for cls, d in diffs:
            by_cls[cls] = max(by_cls.get(cls, 0.0), 0.0 if math.isnan(d) else d)
        table.extend((name, c, d) for c, d in sorted(by_cls.items()))

    add(
        "hedges_g",
        [(r["cls"], abs(hedges_g(np.asarray(r["x"]), np.asarray(r["y"])) - r["out"])) for r in _load("hedges_g")],
    )
    add(
        "permutation_p",
        [
            (
                r["cls"],
                abs(permutation_p(np.asarray(r["x"]), np.asarray(r["y"]), r["n_resamples"], r["seed"], r["paired"]) - r["out"]),
            )
            for r in _load("permutation_p")
        ],
    )
    add(
        "boot_ci_g",
        [
            (
                r["cls"],
                max(
                    abs(a - b)
                    for a, b in zip(
                        boot_ci_g(np.asarray(r["x"]), np.asarray(r["y"]), r["n_boot"], 0.05, r["seed"]),
                        r["out"],
                        strict=True,
                    )
                ),
            )
            for r in _load("boot_ci_g")
        ],
    )
    add("holm", [(r["cls"], 0.0 if holm(r["pvals"], r["alpha"]) == r["out"] else 1.0) for r in _load("holm")])
    print("\nPARITY function cls max_abs_diff")
    for row in table:
        print("PARITY", *row)
    assert all(d <= TOL for _, _, d in table)
