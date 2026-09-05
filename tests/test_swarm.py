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
    """The two rules here were both learned by measurement, and the earlier version of this test encoded the
    opposite of each.

    It asserted that mechanical work runs on a local model. It does not: a local open-weight model produced no
    change at all, twice, on tasks a hosted agent finished in minutes.

    It asserted that ordinary work should take the agent's default model. On this account that default is the most
    expensive model available, so naming nothing meant paying the top rate for everything: twenty sessions in one
    day cost seven million input tokens. Every tier now names its model, and only `critical` names the top one.
    """
    assert set(TIERS) == set(ROUTES)
    assert ROUTES["critical"] == ("codex", "gpt-6-astra")
    assert all(model for _, model in ROUTES.values()), "every tier names its model; a default is a silent bill"
    top = ROUTES["critical"][1]
    cheaper = [tier for tier, (_, model) in ROUTES.items() if tier != "critical" and model == top]
    assert not cheaper, f"the most expensive model is reserved for critical work, not {cheaper}"
    with pytest.raises(ValueError):
        SwarmTask(TaskSpec("x", "p", ("a",)), "urgent").route()


def test_dispatch_tells_the_agent_not_to_survey_the_repository():
    """Measured cost was about 355,000 input tokens per session, most of it an agent orienting itself rather than
    reading the files its task named."""
    from pravrudhi.application.swarm import SCOPE_PREAMBLE

    assert "Do not survey" in SCOPE_PREAMBLE
    assert SCOPE_PREAMBLE.endswith("\n\n"), "it is prepended to a prompt, so it must not run into it"


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
