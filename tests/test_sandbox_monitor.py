"""observe() is the load-bearing piece of the sandbox monitor: it turns a worktree's uncommitted diff into a
verdict against a declared policy, and persists the verdict when the policy was broken. These tests build a real
git worktree by hand rather than mocking git, since the whole point of the module is what a real diff says."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pravrudhi.application.sandbox_monitor import (
    Observation,
    SandboxPolicy,
    observe,
    violations,
    violations_path,
)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _make_worktree(base: Path) -> Path:
    wt = base / "wt"
    wt.mkdir()
    _git(["init", "-q"], wt)
    _git(["config", "user.email", "test@example.com"], wt)
    _git(["config", "user.name", "test"], wt)
    (wt / "allowed").mkdir()
    (wt / "allowed" / "old.txt").write_text("old\n")
    (wt / "keep.txt").write_text("keep\n")
    _git(["add", "-A"], wt)
    _git(["commit", "-q", "-m", "base"], wt)
    return wt


def test_observe_separates_allowed_writes_from_a_policy_violation(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    wt = _make_worktree(tmp_path)

    (wt / "allowed" / "new.txt").write_text("new content\n")
    (wt / "outside.txt").write_text("escaped the policy\n")
    (wt / "allowed" / "old.txt").unlink()

    policy = SandboxPolicy(allowed_paths=("allowed/*",))
    obs = observe(root, "demo:step", wt, policy)

    assert obs.created == ("allowed/new.txt", "outside.txt")
    assert obs.deleted == ("allowed/old.txt",)
    assert obs.modified == ()
    assert obs.bytes_written > 0

    # allowed/new.txt and allowed/old.txt are within the policy; outside.txt is not.
    assert obs.allowed_count == 2
    assert len(obs.violations) == 1
    violation = obs.violations[0]
    assert violation.task_id == "demo:step"
    assert violation.path == "outside.txt"
    assert violation.allowed_paths == ("allowed/*",)


def test_violation_is_persisted_to_the_workspace_ledger(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    wt = _make_worktree(tmp_path)
    (wt / "outside.txt").write_text("escaped\n")

    observe(root, "demo:step", wt, SandboxPolicy(allowed_paths=("allowed/*",)))

    assert violations_path(root).exists()
    recorded = violations(root, 10)
    assert any(v["task_id"] == "demo:step" and v["path"] == "outside.txt" for v in recorded)


def test_repeated_observation_does_not_duplicate_a_still_open_violation(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    wt = _make_worktree(tmp_path)
    (wt / "outside.txt").write_text("escaped\n")

    policy = SandboxPolicy(allowed_paths=("allowed/*",))
    observe(root, "demo:step", wt, policy)
    observe(root, "demo:step", wt, policy)

    recorded = [v for v in violations(root, 100) if v["task_id"] == "demo:step" and v["path"] == "outside.txt"]
    assert len(recorded) == 1


def test_a_file_only_inside_the_policy_is_never_flagged(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    wt = _make_worktree(tmp_path)
    (wt / "allowed" / "new.txt").write_text("fine\n")

    obs = observe(root, "demo:step", wt, SandboxPolicy(allowed_paths=("allowed/*",)))

    assert obs.violations == ()
    assert obs.allowed_count == 1
    assert not violations_path(root).exists()


def test_observing_a_missing_worktree_returns_empty_observation_rather_than_raising(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    missing = tmp_path / "does-not-exist"

    obs = observe(root, "demo:step", missing, SandboxPolicy(allowed_paths=("allowed/*",)))

    assert obs == Observation()
