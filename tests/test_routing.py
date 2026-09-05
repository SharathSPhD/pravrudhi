"""Routing must spend cheaply until the log gives it a reason not to, and must never widen a route's permissions."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pravrudhi.application.routing import (
    Outcome,
    RoutingError,
    choose,
    load_table,
    outcomes,
    record_outcome,
    records,
    report,
)

TABLE = {
    "minimum_trials": 3,
    "confidence": 0.95,
    "routes": [
        {"id": "cheap", "agent": "codex", "model": "m-cheap", "relative_cost": 1.0, "tiers": ["mechanical", "standard"]},
        {"id": "dear", "agent": "codex", "model": "m-dear", "relative_cost": 10.0,
         "tiers": ["mechanical", "standard", "critical"]},
        {"id": "banned", "agent": "orca:local", "model": "m-local", "relative_cost": 0.0, "tiers": []},
    ],
    "declared": {"mechanical": ["cheap", "dear"], "standard": ["cheap", "dear"], "critical": ["dear"]},
}


def _table(tmp_path: Path, doc: dict | None = None):
    p = tmp_path / "routing.yaml"
    p.write_text(yaml.safe_dump(doc or TABLE))
    return load_table(p)


def _rows(tier: str, route: str, wins: int, losses: int) -> list[Outcome]:
    return [Outcome(tier, route, f"t{i}", True, 10.0) for i in range(wins)] + [
        Outcome(tier, route, f"f{i}", False, 10.0) for i in range(losses)
    ]


def test_a_free_route_that_never_works_is_permitted_at_no_tier(tmp_path: Path) -> None:
    """The local model costs nothing and, on the measured evidence, does nothing. Cost alone must not select it."""
    t = _table(tmp_path)
    for tier in ("mechanical", "standard", "critical"):
        assert "banned" not in [r.id for r in t.permitted(tier)]
        assert choose(t, [], tier).route.id != "banned"


def test_with_no_evidence_the_declared_order_decides_and_says_so(tmp_path: Path) -> None:
    c = choose(_table(tmp_path), [], "mechanical")
    assert c.route.id == "cheap"
    assert "declared order" in c.reason


def test_a_cheap_route_is_tried_while_it_is_still_unmeasured(tmp_path: Path) -> None:
    t = _table(tmp_path)
    c = choose(t, _rows("mechanical", "dear", 5, 0), "mechanical")
    assert c.route.id == "cheap", "an unmeasured cheaper route is worth a trial before paying ten times"
    assert "too few to rule out" in c.reason


def test_a_cheap_route_that_is_clearly_worse_loses(tmp_path: Path) -> None:
    t = _table(tmp_path)
    rows = _rows("mechanical", "cheap", 0, 12) + _rows("mechanical", "dear", 12, 0)
    c = choose(t, rows, "mechanical")
    assert c.route.id == "dear"
    assert "best measured success rate" in c.reason


def test_a_cheap_route_that_merely_looks_worse_keeps_the_work(tmp_path: Path) -> None:
    """With few trials almost nothing is distinguishable, and that is the point: the expensive route has to earn
    the spend, not merely lead."""
    t = _table(tmp_path)
    rows = _rows("mechanical", "cheap", 3, 1) + _rows("mechanical", "dear", 4, 0)
    c = choose(t, rows, "mechanical")
    assert c.route.id == "cheap"
    assert "not yet justified" in c.reason


def test_evidence_at_one_tier_does_not_leak_to_another(tmp_path: Path) -> None:
    t = _table(tmp_path)
    rows = _rows("mechanical", "cheap", 0, 12)
    assert choose(t, rows, "standard").route.id == "cheap", "a failure at one tier says nothing about another"


def test_a_tier_with_no_permitted_route_is_an_error_not_a_silent_default(tmp_path: Path) -> None:
    doc = {**TABLE, "declared": {**TABLE["declared"], "design": []}}
    with pytest.raises(RoutingError):
        choose(_table(tmp_path, doc), [], "design")


def test_a_declared_order_naming_an_unknown_route_is_refused_at_load(tmp_path: Path) -> None:
    doc = {**TABLE, "declared": {**TABLE["declared"], "mechanical": ["cheap", "ghost"]}}
    with pytest.raises(RoutingError) as e:
        _table(tmp_path, doc)
    assert "ghost" in str(e.value)


def test_the_log_round_trips_and_survives_a_corrupt_line(tmp_path: Path) -> None:
    record_outcome(tmp_path, Outcome("standard", "cheap", "task-a", True, 12.5))
    (tmp_path / ".pravrudhi" / "routing.jsonl").open("a").write("{not json\n")
    record_outcome(tmp_path, Outcome("standard", "cheap", "task-b", False, 8.0))
    rows = outcomes(tmp_path)
    assert [o.task_id for o in rows] == ["task-a", "task-b"]
    assert rows[0].at, "every outcome is stamped"


def test_the_routing_log_is_not_the_ledger(tmp_path: Path) -> None:
    """It records what the engine spent on its own upkeep, not what an experiment measured, so it must not land in
    research/ where the evidence lives."""
    record_outcome(tmp_path, Outcome("standard", "cheap", "t", True, 1.0))
    assert (tmp_path / ".pravrudhi" / "routing.jsonl").exists()
    assert not (tmp_path / "research").exists()


def test_records_include_a_route_with_no_trials(tmp_path: Path) -> None:
    rs = records(_table(tmp_path), _rows("standard", "cheap", 2, 0), "standard")
    by = {r.route_id: r for r in rs}
    assert by["cheap"].trials == 2 and by["cheap"].measured
    assert by["dear"].trials == 0 and not by["dear"].measured


def test_the_shipped_table_reserves_the_dearest_model_for_critical_work() -> None:
    t = load_table()
    dearest = max(t.routes.values(), key=lambda r: r.relative_cost)
    cheaper_tiers = [tier for tier in ("mechanical", "standard") if choose(t, [], tier).route.id == dearest.id]
    assert not cheaper_tiers, f"cold-start routing sends {cheaper_tiers} to the dearest route"
    assert choose(t, [], "critical").route.id == dearest.id


def test_report_covers_every_tier(tmp_path: Path) -> None:
    rows = report(tmp_path, _table(tmp_path))
    assert {r["tier"] for r in rows} == {"mechanical", "standard", "critical"}
    assert all(r.get("reason") for r in rows)
