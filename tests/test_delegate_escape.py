"""An agent that writes into the main checkout instead of its worktree is rejected, not recorded as idle.

Two agents once did exactly this because their task quoted absolute paths under the main tree. Their worktrees
were empty, so they were recorded as having produced nothing, and the files they wrote were swept into the next
commit unreviewed. The worktree diff cannot see an escape; only the main tree can.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pravrudhi.agents.base import AgentRun, Diff
from pravrudhi.application.delegate import TaskSpec, dispatch


def _repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "a.txt").write_text("a\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i"], check=True)
    return path


class EscapingAgent:
    """Writes its deliverable into the main checkout, leaving its worktree untouched."""

    name = "escaper"

    def __init__(self, root: Path, ws: Path) -> None:
        self.root, self.ws = root, ws

    def create_workspace(self, task_id: str) -> Path:
        return self.ws

    def run(self, prompt: str, workspace: Path, timeout_s: int = 0) -> AgentRun:
        (self.root / "escaped.py").write_text("x = 1\n")
        return AgentRun(agent=self.name, ok=True, exit_code=0, wall_s=0.1, text="", workspace=workspace)

    def collect_changes(self, workspace: Path) -> Diff:
        return Diff()


def test_a_write_into_the_main_checkout_is_named_as_an_escape(tmp_path: Path) -> None:
    root = _repo(tmp_path / "main")
    ws = tmp_path / "ws"
    ws.mkdir()
    v = dispatch(EscapingAgent(root, ws), TaskSpec("t", "do it", ("escaped.py",), validate="true"), log=lambda *a: None)
    assert not v.accepted
    assert any("outside its worktree" in r and "escaped.py" in r for r in v.reasons), v.reasons


def test_pre_existing_uncommitted_work_in_main_is_not_blamed_on_the_agent(tmp_path: Path) -> None:
    root = _repo(tmp_path / "main")
    (root / "mine.txt").write_text("the operator's own uncommitted work\n")
    ws = tmp_path / "ws"
    ws.mkdir()

    class Idle(EscapingAgent):
        def run(self, prompt: str, workspace: Path, timeout_s: int = 0) -> AgentRun:
            return AgentRun(agent=self.name, ok=True, exit_code=0, wall_s=0.1, text="", workspace=workspace)

    v = dispatch(Idle(root, ws), TaskSpec("t", "do it", ("x",), validate="true"), log=lambda *a: None)
    assert not any("outside its worktree" in r for r in v.reasons), v.reasons


def test_the_brief_tells_the_agent_to_write_relative_paths(tmp_path: Path) -> None:
    root = _repo(tmp_path / "main")
    ws = tmp_path / "ws"
    ws.mkdir()
    seen: dict[str, str] = {}

    class Recorder(EscapingAgent):
        def run(self, prompt: str, workspace: Path, timeout_s: int = 0) -> AgentRun:
            seen["prompt"] = prompt
            return AgentRun(agent=self.name, ok=True, exit_code=0, wall_s=0.1, text="", workspace=workspace)

    dispatch(Recorder(root, ws), TaskSpec("t", "do it", ("x",), validate="true"), log=lambda *a: None)
    assert "never write to an absolute path in the main checkout" in seen["prompt"]


def test_the_operators_own_concurrent_edits_in_main_are_not_blamed_on_the_agent(tmp_path: Path) -> None:
    """While a wave runs the operator keeps editing main. Two agents were once rejected for files the operator had
    changed in unrelated modules; only a change inside the task's own allowed paths is an escape."""
    root = _repo(tmp_path / "main")
    ws = tmp_path / "ws"
    ws.mkdir()

    class OperatorEditsMeanwhile(EscapingAgent):
        def run(self, prompt: str, workspace: Path, timeout_s: int = 0) -> AgentRun:
            (self.root / "unrelated_module.py").write_text("# the operator's edit, not the agent's\n")
            return AgentRun(agent=self.name, ok=True, exit_code=0, wall_s=0.1, text="", workspace=workspace)

    v = dispatch(OperatorEditsMeanwhile(root, ws), TaskSpec("t", "do it", ("deliverable.py",), validate="true"),
                 log=lambda *a: None)
    assert not any("outside its worktree" in r for r in v.reasons), v.reasons
