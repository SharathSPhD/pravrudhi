"""Harness-track deltas are paired on identical items; the unpaired sqrt(s1^2+s2^2) form overstates the interval.

`objectives.progress()` combined baseline and candidate standard errors as if the two evaluations were independent
samples. They are not: an evalplus run scores the same 164 held-out items both times, so a McNemar-paired test on
the shared items (see `application/discordance.py`) is the correct statistic, and can call a result significant
that the unpaired form calls noise. `parse_evalplus` now carries a per-item pass/fail vector in the ledger row so
`progress()` can compute that paired statistic when both rows carry one; older rows without it fall back exactly as
before.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pravrudhi.application.discordance import discordance
from pravrudhi.application.objectives import parse, progress
from pravrudhi_kernel.ledger import LedgerWriter

OBJ = {
    "id": "harness-mvp",
    "intent": "improve the code harness on HumanEval+",
    "track": "harness",
    "benchmarks": [{"id": "he", "tool": "evalplus", "metric": "humaneval+ pass@1"}],
}

TASK_IDS = [f"HumanEval/{i}" for i in range(164)]
WINS_IDS = TASK_IDS[0:15]
LOSS_IDS = TASK_IDS[15:22]
CONCORDANT_PASS_IDS = TASK_IDS[22:122]
CONCORDANT_FAIL_IDS = TASK_IDS[122:164]


def _items(*, candidate: bool) -> dict[str, int]:
    """The base's (candidate=False) or candidate's (candidate=True) pass/fail vector over the 164 shared items."""
    out: dict[str, int] = {}
    for t in WINS_IDS:
        out[t] = 1 if candidate else 0
    for t in LOSS_IDS:
        out[t] = 0 if candidate else 1
    for t in CONCORDANT_PASS_IDS:
        out[t] = 1
    for t in CONCORDANT_FAIL_IDS:
        out[t] = 0
    return out


def _evalplus_payload(
    condition: str, *, items: dict[str, int] | None, dataset: str = "humaneval", track: str = "harness"
) -> dict[str, Any]:
    n = len(TASK_IDS)
    plus_pass = sum((items or {}).values()) if items is not None else n // 2
    payload: dict[str, Any] = {
        "kind": "external_eval",
        "severity": "info",
        "tier": "external",
        "track": track,
        "condition": condition,
        "model": "Qwen/Qwen3-0.6B",
        "sha256": "0" * 64,
        "tool": "evalplus",
        "tool_version": "0.3.1",
        "dataset": dataset,
        "n_samples": {dataset: n},
        "metrics": {
            dataset: {"pass@1_base": plus_pass / n, "pass@1_plus": plus_pass / n},
            f"{dataset}_counts": {"n": n, "base_pass": plus_pass, "plus_pass": plus_pass},
        },
    }
    if items is not None:
        payload["items"] = items
    return payload


def _ledger(path: Path, payloads: list[dict[str, Any]]) -> Path:
    w = LedgerWriter.open(path, "0.1.0")
    for payload in payloads:
        w.append("audit", "auditor", payload, epoch=0, night=1)
    return path


def test_paired_rows_yield_the_mcnemar_statistic_not_the_unpaired_interval(tmp_path: Path) -> None:
    base_items = _items(candidate=False)
    latest_items = _items(candidate=True)
    led = _ledger(
        tmp_path / "l.jsonl",
        [
            _evalplus_payload("base", items=base_items),
            _evalplus_payload("adapter:c-0001", items=latest_items),
        ],
    )
    (p,) = progress(parse(OBJ), led)
    assert p.state == "measured"
    assert p.paired is True
    assert p.wins == 15
    assert p.losses == 7
    d = discordance(base_items, latest_items)
    assert p.p_mcnemar == pytest.approx(d.p_mcnemar)
    assert p.delta == pytest.approx(d.delta)
    assert p.delta_lo is not None and p.delta_hi is not None
    assert p.delta_lo < p.delta < p.delta_hi


def test_rows_without_items_fall_back_to_the_unpaired_form(tmp_path: Path) -> None:
    led = _ledger(
        tmp_path / "l.jsonl",
        [
            _evalplus_payload("base", items=None),
            _evalplus_payload("adapter:c-0001", items=None),
        ],
    )
    (p,) = progress(parse(OBJ), led)
    assert p.state == "measured"
    assert p.paired is False
    assert p.wins is None and p.losses is None and p.p_mcnemar is None
    assert p.delta == pytest.approx(0.0, abs=1e-9)


def test_one_row_with_items_and_one_without_falls_back_to_the_unpaired_form(tmp_path: Path) -> None:
    """A shared-ids check, not just a key-presence check: pairing needs both sides to carry items."""
    led = _ledger(
        tmp_path / "l.jsonl",
        [
            _evalplus_payload("base", items=_items(candidate=False)),
            _evalplus_payload("adapter:c-0001", items=None),
        ],
    )
    (p,) = progress(parse(OBJ), led)
    assert p.state == "measured"
    assert p.paired is False
    assert p.wins is None and p.losses is None and p.p_mcnemar is None
