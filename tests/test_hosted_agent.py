"""A hosted free-tier model answers once with JSON; nothing it names outside the brief's allow-list gets written."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pravrudhi.agents.hosted_agent import HostedAgent
from pravrudhi.application.routing import load_table
from pravrudhi.models import hosted

PROMPT = "Do the task.\nYou may create or modify ONLY these paths: allowed/a.py, allowed/sub/b.py."


def _agent() -> HostedAgent:
    return HostedAgent(Path("/nonexistent-root"), model="qwen3-coder-plus")


def _patch_reply(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    monkeypatch.setattr(hosted, "chat", lambda model, messages, **kw: reply)


def test_files_inside_allowed_paths_are_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    reply = json.dumps({"files": [{"path": "allowed/sub/b.py", "content": "x = 1\n"}], "note": "wrote b.py"})
    _patch_reply(monkeypatch, reply)
    run = _agent().run(PROMPT, tmp_path)
    assert run.ok
    assert (tmp_path / "allowed/sub/b.py").read_text() == "x = 1\n"
    assert "wrote b.py" in run.text


def test_a_path_outside_the_allowed_list_is_refused_and_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reply = json.dumps({"files": [{"path": "forbidden/x.py", "content": "evil = True\n"}], "note": "note"})
    _patch_reply(monkeypatch, reply)
    run = _agent().run(PROMPT, tmp_path)
    assert not run.ok
    assert not (tmp_path / "forbidden/x.py").exists()
    assert "forbidden/x.py" in run.text


def test_a_path_that_tries_to_leave_the_worktree_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    reply = json.dumps({"files": [{"path": "../escape.py", "content": "evil = True\n"}], "note": "note"})
    _patch_reply(monkeypatch, reply)
    run = _agent().run(PROMPT, tmp_path)
    assert not run.ok
    assert not (tmp_path.parent / "escape.py").exists()
    assert "../escape.py" in run.text


def test_an_empty_answer_yields_ok_false(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_reply(monkeypatch, "")
    run = _agent().run(PROMPT, tmp_path)
    assert not run.ok


def test_the_qwen_coder_route_exists_in_the_packaged_table() -> None:
    t = load_table()
    assert "qwen-coder" in t.routes
    route = t.routes["qwen-coder"]
    assert route.agent == "hosted"
    assert "qwen-coder" in [r.id for r in t.permitted("mechanical")]
