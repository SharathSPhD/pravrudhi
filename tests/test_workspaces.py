"""Tests for src/pravrudhi/application/workspaces.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from pravrudhi.application import workspaces


def test_workspaces_root_defaults_under_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRAVRUDHI_WORKSPACES", raising=False)
    assert workspaces.workspaces_root() == Path.home() / ".pravrudhi" / "workspaces"


def test_workspaces_root_honours_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRAVRUDHI_WORKSPACES", str(tmp_path))
    assert workspaces.workspaces_root() == tmp_path


def test_workspace_dir_rejects_path_traversal_in_user_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRAVRUDHI_WORKSPACES", str(tmp_path))
    with pytest.raises(workspaces.WorkspaceError):
        workspaces.workspace_dir("../../etc", "my-workspace")


def test_workspace_dir_rejects_separators_in_user_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRAVRUDHI_WORKSPACES", str(tmp_path))
    with pytest.raises(workspaces.WorkspaceError):
        workspaces.workspace_dir("user/evil", "my-workspace")


def test_workspace_dir_rejects_bad_slug(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRAVRUDHI_WORKSPACES", str(tmp_path))
    with pytest.raises(workspaces.WorkspaceError):
        workspaces.workspace_dir("user-1", "../escape")
    with pytest.raises(workspaces.WorkspaceError):
        workspaces.workspace_dir("user-1", "Not_A_Valid_Slug!")


def test_workspace_dir_resolves_under_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRAVRUDHI_WORKSPACES", str(tmp_path))
    path = workspaces.workspace_dir("user-1", "my-workspace")
    assert path == (tmp_path / "user-1" / "my-workspace").resolve()


def test_ensure_workspace_creates_config_and_ledger(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRAVRUDHI_WORKSPACES", str(tmp_path))
    path = workspaces.ensure_workspace("user-1", "my-workspace")
    assert path.exists()
    assert (path / ".pravrudhi" / "config.yaml").exists()
    assert (path / "research" / "ledger.jsonl").exists()


def test_ensure_workspace_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRAVRUDHI_WORKSPACES", str(tmp_path))
    first = workspaces.ensure_workspace("user-1", "my-workspace")
    ledger = first / "research" / "ledger.jsonl"
    before = ledger.read_bytes()
    second = workspaces.ensure_workspace("user-1", "my-workspace")
    assert second == first
    assert ledger.read_bytes() == before


def test_list_workspaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRAVRUDHI_WORKSPACES", str(tmp_path))
    assert workspaces.list_workspaces("user-1") == []
    workspaces.ensure_workspace("user-1", "alpha")
    workspaces.ensure_workspace("user-1", "beta")
    assert workspaces.list_workspaces("user-1") == ["alpha", "beta"]


def test_list_workspaces_rejects_unsafe_user_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PRAVRUDHI_WORKSPACES", str(tmp_path))
    with pytest.raises(workspaces.WorkspaceError):
        workspaces.list_workspaces("../etc")
