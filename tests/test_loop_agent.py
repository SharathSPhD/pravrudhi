"""LoopAgent drives a real tool-calling loop, never a real model in these tests: `chat` is always scripted."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pravrudhi.agents.loop_agent import (
    LoopAgent,
    ToolsConfig,
    _allowed_command,
    _allowed_patterns,
    _list_dir,
    _parse_tool_call,
    _read_file,
    _run_command,
    _search,
    _write_file,
)

ALLOWED_LINE = "You may create or modify ONLY these paths: a.txt, sub/*.py."


def _native_response(name: str, args: dict[str, Any], content: str | None = None) -> dict[str, Any]:
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": content,
                "tool_calls": [{"id": "call_1", "type": "function",
                                 "function": {"name": name, "arguments": json.dumps(args)}}],
            }
        }]
    }


def _json_fallback_response(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant",
                                      "content": json.dumps({"tool": name, "args": args})}}]}


def _scripted(responses: list[dict[str, Any]]):
    calls: list[list[dict[str, Any]]] = []

    def chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        calls.append(messages)
        return responses[len(calls) - 1]

    chat.calls = calls  # type: ignore[attr-defined]
    return chat


def _worktree(tmp_path: Path) -> Path:
    wt = tmp_path / "wt"
    wt.mkdir()
    return wt


# ---- the loop itself -------------------------------------------------------


def test_two_step_session_reads_then_writes_and_finishes(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    (wt / "a.txt").write_text("hello")
    chat = _scripted([
        _native_response("read_file", {"path": "a.txt"}),
        _native_response("write_file", {"path": "a.txt", "content": "hello world"}),
        _native_response("finish", {"summary": "updated a.txt"}),
    ])
    agent = LoopAgent(tmp_path, chat=chat)
    run = agent.run(f"do the thing.\n{ALLOWED_LINE}", wt)
    assert run.ok is True
    assert run.text == "updated a.txt"
    assert (wt / "a.txt").read_text() == "hello world"


def test_path_outside_the_worktree_is_refused_and_named(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    chat = _scripted([
        _native_response("read_file", {"path": "/etc/passwd"}),
        _native_response("finish", {"summary": "done"}),
    ])
    agent = LoopAgent(tmp_path, chat=chat)
    run = agent.run(f"do it.\n{ALLOWED_LINE}", wt)
    assert run.ok is True  # the model recovered and finished; the refusal is what we check
    transcript = (wt / ".pravrudhi" / "loop.jsonl").read_text().splitlines()
    first = json.loads(transcript[0])
    assert first["tool"] == "read_file"
    assert "refused" in first["result"]["error"]
    assert "/etc/passwd" in first["result"]["error"]


def test_dot_dot_traversal_is_refused(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    chat = _scripted([
        _native_response("write_file", {"path": "../escape.txt", "content": "x"}),
        _native_response("finish", {"summary": "done"}),
    ])
    agent = LoopAgent(tmp_path, chat=chat)
    run = agent.run(f"do it.\n{ALLOWED_LINE}", wt)
    assert run.ok is True
    transcript = (wt / ".pravrudhi" / "loop.jsonl").read_text().splitlines()
    first = json.loads(transcript[0])
    assert "refused" in first["result"]["error"]
    assert "../escape.txt" in first["result"]["error"]
    assert not (tmp_path / "escape.txt").exists()


def test_a_command_off_the_allow_list_is_refused(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    chat = _scripted([
        _native_response("run_command", {"command": "rm -rf /"}),
        _native_response("finish", {"summary": "done"}),
    ])
    agent = LoopAgent(tmp_path, chat=chat)
    run = agent.run(f"do it.\n{ALLOWED_LINE}", wt)
    assert run.ok is True
    transcript = (wt / ".pravrudhi" / "loop.jsonl").read_text().splitlines()
    first = json.loads(transcript[0])
    assert "refused" in first["result"]["error"]
    assert "rm -rf /" in first["result"]["error"]


def test_max_steps_ends_the_run_with_ok_false_and_a_reason(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    chat = _scripted([_native_response("list_dir", {"path": "."}) for _ in range(10)])
    agent = LoopAgent(tmp_path, chat=chat, max_steps=3)
    run = agent.run(f"do it.\n{ALLOWED_LINE}", wt)
    assert run.ok is False
    assert "max_steps" in run.text
    assert "3" in run.text


def test_the_json_fallback_path_is_exercised(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    (wt / "a.txt").write_text("v1")
    chat = _scripted([
        _json_fallback_response("write_file", {"path": "a.txt", "content": "v2"}),
        _json_fallback_response("finish", {"summary": "wrote v2"}),
    ])
    agent = LoopAgent(tmp_path, chat=chat)
    run = agent.run(f"do it.\n{ALLOWED_LINE}", wt)
    assert run.ok is True
    assert (wt / "a.txt").read_text() == "v2"
    transcript = [json.loads(line) for line in (wt / ".pravrudhi" / "loop.jsonl").read_text().splitlines()]
    assert transcript[0]["native"] is False


def test_an_unparseable_reply_ends_the_run(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    chat = _scripted([{"choices": [{"message": {"role": "assistant", "content": "not json and no tool call"}}]}])
    agent = LoopAgent(tmp_path, chat=chat)
    run = agent.run(f"do it.\n{ALLOWED_LINE}", wt)
    assert run.ok is False
    assert "could not parse" in run.text


def test_the_transcript_is_written(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    chat = _scripted([
        _native_response("list_dir", {"path": "."}),
        _native_response("finish", {"summary": "looked around"}),
    ])
    agent = LoopAgent(tmp_path, chat=chat)
    agent.run(f"do it.\n{ALLOWED_LINE}", wt)
    transcript_path = wt / ".pravrudhi" / "loop.jsonl"
    assert transcript_path.exists()
    lines = [json.loads(line) for line in transcript_path.read_text().splitlines()]
    assert len(lines) == 2
    assert lines[0]["event"] == "tool" and lines[0]["tool"] == "list_dir"
    assert lines[1]["event"] == "finish"


# ---- tools, each tested on its own -----------------------------------------


def test_allowed_patterns_parses_the_dispatch_brief_line() -> None:
    assert _allowed_patterns(ALLOWED_LINE) == ("a.txt", "sub/*.py")
    assert _allowed_patterns("no such line here") == ()


def test_read_file_tool(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    (wt / "f.txt").write_text("hi")
    assert _read_file("f.txt", wt) == {"content": "hi"}
    assert "no such file" in _read_file("missing.txt", wt)["error"]
    assert "refused" in _read_file("../outside.txt", wt)["error"]
    assert "refused" in _read_file("/etc/passwd", wt)["error"]


def test_write_file_tool(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    ok = _write_file("a.txt", "content", wt, ("a.txt",))
    assert ok == {"ok": True, "path": "a.txt"}
    assert (wt / "a.txt").read_text() == "content"
    refused = _write_file("b.txt", "x", wt, ("a.txt",))
    assert "refused" in refused["error"] and "b.txt" in refused["error"]
    assert not (wt / "b.txt").exists()
    escaped = _write_file("../escape.txt", "x", wt, ("../escape.txt",))
    assert "refused" in escaped["error"]
    assert not (tmp_path / "escape.txt").exists()


def test_list_dir_tool(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    (wt / "sub").mkdir()
    (wt / "a.txt").write_text("x")
    entries = _list_dir(".", wt)["entries"]
    assert "a.txt" in entries and "sub/" in entries
    assert "refused" in _list_dir("../..", wt)["error"]
    assert "no such directory" in _list_dir("nope", wt)["error"]


def test_search_tool_finds_a_match(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    (wt / "a.py").write_text("def needle():\n    pass\n")
    result = _search("needle", ".", wt)
    assert any("needle" in m for m in result["matches"])
    assert "refused" in _search("needle", "../..", wt)["error"]


def test_allowed_command() -> None:
    prefixes = ("git status", "ls")
    assert _allowed_command("git status", prefixes)
    assert _allowed_command("git status --short", prefixes)
    assert not _allowed_command("git stash", prefixes)
    assert not _allowed_command("rm -rf /", prefixes)


def test_run_command_tool_allow_list(tmp_path: Path) -> None:
    wt = _worktree(tmp_path)
    ok = _run_command("echo hi", wt, ("echo",), 10)
    assert ok["exit_code"] == 0
    assert "hi" in ok["stdout"]
    refused = _run_command("rm -rf /", wt, ("echo",), 10)
    assert "refused" in refused["error"] and "rm -rf /" in refused["error"]


def test_parse_tool_call_native_and_fallback_and_none() -> None:
    native = _parse_tool_call(_native_response("finish", {"summary": "s"})["choices"][0]["message"])
    assert native == ("finish", {"summary": "s"}, True)
    fallback = _parse_tool_call(_json_fallback_response("finish", {"summary": "s"})["choices"][0]["message"])
    assert fallback == ("finish", {"summary": "s"}, False)
    assert _parse_tool_call({"role": "assistant", "content": "just prose"}) is None
    assert _parse_tool_call({"role": "assistant", "content": None}) is None


def test_available_reflects_hosted_gate_when_no_base_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pravrudhi.models import hosted

    monkeypatch.delenv(hosted.OPT_IN, raising=False)
    agent = LoopAgent(tmp_path, chat=lambda m, t: {})
    assert agent.available() is False
    agent_with_url = LoopAgent(tmp_path, chat=lambda m, t: {}, base_url="http://localhost:8080/v1")
    assert agent_with_url.available() is True


def test_tools_config_loads_from_a_custom_path(tmp_path: Path) -> None:
    from pravrudhi.agents.loop_agent import load_tools_config

    p = tmp_path / "tools.yaml"
    p.write_text("allow_prefixes: [\"echo\"]\ncommand_timeout_s: 5\n")
    cfg = load_tools_config(p)
    assert cfg == ToolsConfig(allow_prefixes=("echo",), command_timeout_s=5)
