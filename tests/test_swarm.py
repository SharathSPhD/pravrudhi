"""Swarm scheduling: conflict-free waves, tier routing, and failures that stay contained."""
import pytest

from pravrudhi.application.delegate import TaskSpec, Verdict
from pravrudhi.application.swarm import ROUTES, TIERS, SwarmTask, plan, render_swarm, run_swarm

A = SwarmTask(TaskSpec("a", "p", ("src/a.py",)), "standard")
B = SwarmTask(TaskSpec("b", "p", ("src/b.py",)), "mechanical")
WIDE = SwarmTask(TaskSpec("wide", "p", ("src/*.py",)), "critical")


def test_disjoint_tasks_share_a_wave_and_conflicts_are_deferred_not_dropped():
    waves, conflicts = plan([A, B, WIDE])
    assert [t.spec.task_id for t in waves[0]] == ["a", "b"]
    assert [t.spec.task_id for t in waves[1]] == ["wide"]
    assert ("a", "wide") in conflicts
    assert sum(len(w) for w in waves) == 3, "no task may be dropped"


def test_every_tier_routes_and_the_expensive_model_is_reserved():
    assert set(TIERS) == set(ROUTES)
    assert ROUTES["critical"] == ("codex", "gpt-6-astra")
    assert ROUTES["mechanical"][0].startswith("orca:"), "mechanical work runs on hardware already paid for"
    assert ROUTES["standard"][1] is None, "ordinary work uses the agent's default model"
    with pytest.raises(ValueError):
        SwarmTask(TaskSpec("x", "p", ("a",)), "urgent").route()


class OkAgent:
    name = "fake"

    def __init__(self, files):
        self.files = files

    def create_workspace(self, task_id, base_ref="HEAD"):
        import tempfile
        from pathlib import Path

        return Path(tempfile.mkdtemp())

    def run(self, prompt, workspace, timeout_s=60):
        from pravrudhi.agents.base import AgentRun

        return AgentRun(agent=self.name, ok=True, exit_code=0, wall_s=0.1, text="", workspace=workspace)

    def collect_changes(self, workspace):
        from pravrudhi.agents.base import Diff

        return Diff(files=list(self.files))


def test_a_missing_agent_is_recorded_not_fatal():
    out = run_swarm(lambda name, model: None, [A, B], log=lambda s: None)
    assert out["accepted"] == [] and len(out["rejected"]) == 2
    assert all("no agent available" in r["reasons"][0] for r in out["rejected"])


def test_a_crashing_agent_does_not_take_the_wave_with_it():
    def factory(name, model):
        raise RuntimeError("boom") if name == "codex" else None

    class Boom:
        name = "boom"

        def create_workspace(self, *a, **k):
            raise RuntimeError("worktree failed")

    out = run_swarm(lambda name, model: Boom(), [A], log=lambda s: None)
    assert len(out["rejected"]) == 1 and "dispatch raised" in out["rejected"][0]["reasons"][0]


def test_render_is_readable():
    text = render_swarm({"waves": 1, "conflicts": [], "accepted": [
        Verdict("a", "codex", True, [], ["src/a.py"], "", 1.0).to_dict()], "rejected": [
        Verdict("b", "claude", False, ["validation failed"], [], "", 2.0).to_dict()]})
    assert "ok    a" in text and "FAIL  b" in text and "validation failed" in text


def test_uncommitted_work_is_warned_about_because_worktrees_branch_from_head(tmp_path):
    """The base a worktree branches from is HEAD, not the working tree; a task needing uncommitted work fails."""
    import subprocess

    from pravrudhi.application.swarm import run_swarm, uncommitted

    for c in (["init", "-q", "-b", "main"], ["config", "user.email", "t@e"], ["config", "user.name", "t"]):
        subprocess.run(["git", *c], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True, capture_output=True)
    assert uncommitted(tmp_path) == []
    (tmp_path / "a.py").write_text("x = 2\n")
    assert uncommitted(tmp_path) == ["a.py"]

    said = []
    run_swarm(lambda n, m: None, [A], root=tmp_path, log=said.append)
    assert any("uncommitted" in s for s in said)
