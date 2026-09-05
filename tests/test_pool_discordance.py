"""Pooling per-item pass vectors from EvalPlus `*_eval_results.json` files across datasets (scripts/pool_discordance.py).

No docker: these are tiny synthetic result files mimicking the shape `application/external.py.parse_evalplus` reads.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

_SPEC = importlib.util.spec_from_file_location(
    "pool_discordance", Path(__file__).resolve().parent.parent / "scripts" / "pool_discordance.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_pool_discordance: ModuleType = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_pool_discordance)

pool = _pool_discordance.pool
per_dataset = _pool_discordance.per_dataset


def _write_results(path: Path, statuses: dict[str, tuple[str, str]]) -> Path:
    """statuses maps task_id -> (base_status, plus_status), the fields `_pass_vector` reads."""
    payload = {"eval": {tid: [{"base_status": b, "plus_status": p}] for tid, (b, p) in statuses.items()}}
    path.write_text(json.dumps(payload))
    return path


def test_pooling_two_datasets_sums_wins_and_losses(tmp_path: Path) -> None:
    # dataset "a": item 1 is a win, item 2 is a loss
    a_base = _write_results(tmp_path / "a_base.json", {"1": ("fail", "fail"), "2": ("pass", "pass")})
    a_cand = _write_results(tmp_path / "a_cand.json", {"1": ("pass", "pass"), "2": ("fail", "fail")})
    # dataset "b": item 1 is a win, item 2 is concordant (pass/pass, no discordance)
    b_base = _write_results(tmp_path / "b_base.json", {"1": ("fail", "fail"), "2": ("pass", "pass")})
    b_cand = _write_results(tmp_path / "b_cand.json", {"1": ("pass", "pass"), "2": ("pass", "pass")})

    pairs = [("a", a_base, a_cand), ("b", b_base, b_cand)]
    pooled = pool(pairs)
    per = per_dataset(pairs)

    assert per["a"].wins == 1 and per["a"].losses == 1
    assert per["b"].wins == 1 and per["b"].losses == 0
    assert pooled.n == 4
    assert pooled.wins == per["a"].wins + per["b"].wins == 2
    assert pooled.losses == per["a"].losses + per["b"].losses == 1


def test_ids_from_different_datasets_never_collide(tmp_path: Path) -> None:
    # both datasets reuse task_id "1" with opposite outcomes; unprefixed keys would let one clobber the other
    a_base = _write_results(tmp_path / "a_base.json", {"1": ("fail", "fail")})
    a_cand = _write_results(tmp_path / "a_cand.json", {"1": ("pass", "pass")})  # win
    b_base = _write_results(tmp_path / "b_base.json", {"1": ("pass", "pass")})
    b_cand = _write_results(tmp_path / "b_cand.json", {"1": ("fail", "fail")})  # loss

    pooled = pool([("a", a_base, a_cand), ("b", b_base, b_cand)])

    assert pooled.n == 2
    assert pooled.wins == 1
    assert pooled.losses == 1


def test_dataset_with_no_discordant_pairs_contributes_nothing(tmp_path: Path) -> None:
    a_base = _write_results(tmp_path / "a_base.json", {"1": ("fail", "fail"), "2": ("pass", "pass")})
    a_cand = _write_results(tmp_path / "a_cand.json", {"1": ("pass", "pass"), "2": ("fail", "fail")})
    # dataset "c" is fully concordant: contributes zero wins and zero losses
    c_base = _write_results(tmp_path / "c_base.json", {"1": ("pass", "pass"), "2": ("fail", "fail")})
    c_cand = _write_results(tmp_path / "c_cand.json", {"1": ("pass", "pass"), "2": ("fail", "fail")})

    without_c = pool([("a", a_base, a_cand)])
    with_c = pool([("a", a_base, a_cand), ("c", c_base, c_cand)])

    assert with_c.wins == without_c.wins
    assert with_c.losses == without_c.losses
    # c's two concordant items still enter the pooled item and concordant counts
    assert with_c.n == without_c.n + 2
    assert with_c.concordant == without_c.concordant + 2
