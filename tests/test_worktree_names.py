"""A task id is also a git branch name, and the first real dispatch of a plan proved nobody had said so."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pravrudhi.agents.base import GitWorktreeMixin


class _Agent(GitWorktreeMixin):
    def __init__(self, root: Path) -> None:
        self.root = root


def _repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "a").write_text("a\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i"], check=True)
    return path


def test_ref_safe_replaces_what_git_refuses() -> None:
    assert GitWorktreeMixin.ref_safe("prabhasa-nyaya:baseline-evaluation") == "prabhasa-nyaya-baseline-evaluation"
    assert GitWorktreeMixin.ref_safe("a b/c~d^e?f") == "a-b-c-d-e-f"
    assert GitWorktreeMixin.ref_safe("plain-id_1.2") == "plain-id_1.2"
    assert GitWorktreeMixin.ref_safe(":::") == "task"


def test_a_task_id_with_a_colon_gets_a_worktree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    ws = _Agent(root).create_workspace("obj:step")
    assert ws.exists() and ws.name == "agent-obj-step"
    branches = subprocess.run(["git", "-C", str(root), "branch", "--list", "agent/*"], capture_output=True, text=True).stdout
    assert "agent/obj-step" in branches
