"""When a paid account is spent, the free-tier sentinel must carry the work.

The operator's requirement of 2026-09-06: "let pravrudhi system be robust enough to completely work irrespective
of paid models hitting session limits (run 24x7)". Before this, a usage limit was recorded as an ordinary failure:
the route lost a point it did not deserve, the task died, and the loop stopped until a person noticed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pravrudhi.application import availability, continuity, routing
from pravrudhi.application.delegate import TaskSpec, Verdict
from pravrudhi.application.swarm import SwarmTask, run_wave


class _Agent:
    """An agent that reports a vendor usage-limit message, or succeeds, depending on how it was built."""

    def __init__(self, name: str, *, limited: bool) -> None:
        self.name = name
        self._limited = limited

    def run(self, prompt: str, workspace: Path, timeout_s: int = 1800) -> Any:  # pragma: no cover - unused
        raise AssertionError("run_wave must go through dispatch, which is patched in these tests")


def _factory(calls: list[str]) -> Any:
    def build(name: str, model: str | None) -> Any:
        calls.append(name)
        return _Agent(name, limited=(name == "claude-code"))

    return build


def test_a_usage_limit_moves_the_task_to_the_sentinel(tmp_path: Path, monkeypatch: Any) -> None:
    dispatched: list[str] = []

    def fake_dispatch(agent: Any, spec: TaskSpec, *, log: Any = print) -> Verdict:
        dispatched.append(agent.name)
        if agent._limited:
            return Verdict(spec.task_id, agent.name, False, ["Claude usage limit reached. Your limit will reset"])
        return Verdict(spec.task_id, agent.name, True, [], wall_s=1.0)

    monkeypatch.setattr("pravrudhi.application.swarm.dispatch", fake_dispatch)
    calls: list[str] = []
    task = SwarmTask(TaskSpec("t1", "do a thing", ("x.py",), "true", 60), "standard", "why")

    out = run_wave(_factory(calls), [task], log=lambda *_: None, root=tmp_path)

    assert len(out) == 1
    assert out[0].accepted, out[0].reasons
    assert out[0].agent == "hosted", f"the sentinel should have taken over, got {out[0].agent}"
    assert dispatched == ["claude-code", "hosted"], dispatched


def test_the_limited_route_is_cooled_and_not_blamed(tmp_path: Path, monkeypatch: Any) -> None:
    def fake_dispatch(agent: Any, spec: TaskSpec, *, log: Any = print) -> Verdict:
        if agent._limited:
            return Verdict(spec.task_id, agent.name, False, ["Claude usage limit reached"])
        return Verdict(spec.task_id, agent.name, True, [], wall_s=1.0)

    monkeypatch.setattr("pravrudhi.application.swarm.dispatch", fake_dispatch)
    task = SwarmTask(TaskSpec("t2", "do a thing", ("x.py",), "true", 60), "standard", "why")
    run_wave(_factory([]), [task], log=lambda *_: None, root=tmp_path)

    assert "claude-code" in availability.cooling(tmp_path), "the spent account must cool down"

    # a limit is not evidence about quality, so no losing outcome may be recorded against the route
    outcomes = routing.outcomes(tmp_path)
    assert not [o for o in outcomes if o.route_id == "sonnet" and not o.accepted], outcomes

    kinds = [e.kind for e in continuity.entries(tmp_path, 10)]
    assert "limited" in kinds and "fallback" in kinds, kinds
