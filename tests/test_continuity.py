from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest

from pravrudhi import __version__ as ENGINE_VERSION
from pravrudhi.application import continuity
from pravrudhi.application.objectives import Benchmark, Objective, write as write_objective


def _objective(oid: str = "demo") -> Objective:
    return Objective(
        id=oid,
        intent="Improve the demo track without breaking anything else.",
        track=oid,
        benchmarks=(Benchmark(id="acc", tool="lm-eval", metric="acc"),),
    )


def test_note_rejects_unknown_kind(tmp_path: Path) -> None:
    with pytest.raises(continuity.ContinuityError):
        continuity.note(tmp_path, kind="not-a-real-kind", summary="whatever")


def test_entries_round_trip(tmp_path: Path) -> None:
    written = [
        continuity.note(tmp_path, kind="dispatch", summary="dispatched step one", agent="claude"),
        continuity.note(tmp_path, kind="limited", summary="hit the daily limit", agent="claude"),
        continuity.note(tmp_path, kind="fallback", summary="handed off to codex", agent="codex"),
    ]
    read = continuity.entries(tmp_path)
    assert [e.summary for e in read] == [w.summary for w in written]
    assert [e.kind for e in read] == [w.kind for w in written]
    assert [e.agent for e in read] == [w.agent for w in written]


def test_entries_are_capped(tmp_path: Path) -> None:
    for i in range(5):
        continuity.note(tmp_path, kind="milestone", summary=f"step {i}")
    read = continuity.entries(tmp_path, n=2)
    assert [e.summary for e in read] == ["step 3", "step 4"]


def test_entries_skip_corrupt_line(tmp_path: Path) -> None:
    continuity.note(tmp_path, kind="dispatch", summary="good entry one")
    path = continuity.log_path(tmp_path)
    with path.open("a") as fh:
        fh.write("{not json\n")
    continuity.note(tmp_path, kind="handback", summary="good entry two")
    read = continuity.entries(tmp_path)
    assert [e.summary for e in read] == ["good entry one", "good entry two"]


def test_handover_names_open_step_and_cooling_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_objective(tmp_path, _objective())

    fake_availability = types.ModuleType("pravrudhi.application.availability")
    fake_availability.cooling = lambda root: {"aider": "2026-09-10T00:00:00Z"}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pravrudhi.application.availability", fake_availability)

    brief = continuity.handover(tmp_path)

    assert "demo: baseline-evaluation" in brief
    assert "aider until 2026-09-10T00:00:00Z" in brief


def test_handover_has_no_number_not_passed_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_objective(tmp_path, _objective())
    at1 = continuity.note(
        tmp_path, kind="dispatch", summary="dispatched baseline", agent="claude", objective="demo",
    ).at
    at2 = continuity.note(
        tmp_path, kind="limited", summary="hit the daily limit", agent="claude", objective="demo",
    ).at

    fake_availability = types.ModuleType("pravrudhi.application.availability")
    until = "2026-09-11T06:00:00Z"
    fake_availability.cooling = lambda root: {"claude": until}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pravrudhi.application.availability", fake_availability)

    brief = continuity.handover(tmp_path)

    allowed = "".join([ENGINE_VERSION, at1, at2, until])
    for token in re.findall(r"\d+", brief):
        assert token in allowed, f"unexplained number {token!r} in handover brief"


def test_write_handover_writes_relative_dest(tmp_path: Path) -> None:
    continuity.note(tmp_path, kind="milestone", summary="something happened")
    out = continuity.write_handover(tmp_path)
    assert out == tmp_path / "HANDOVER.md"
    assert out.is_file()
    assert "# Handover" in out.read_text()
