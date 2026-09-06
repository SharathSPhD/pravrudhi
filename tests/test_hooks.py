"""Drive deploy/hooks/pravrudhi_guard.py as a subprocess, the way Claude Code does.

The hook reads a PreToolUse JSON payload on stdin and either blocks the call
(exit 2, reason on stderr) or allows it (exit 0, silent).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parent.parent / "deploy" / "hooks" / "pravrudhi_guard.py"
REPO_ROOT = HOOK_PATH.parent.parent.parent


def run_hook(payload: object, raw_stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    stdin = raw_stdin if raw_stdin is not None else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_blocks_git_add_on_pravrudhi_kernel() -> None:
    result = run_hook(
        {"tool_name": "Bash", "tool_input": {"command": "git add pravrudhi_kernel/foo.py"}}
    )
    assert result.returncode == 2
    assert "pravrudhi_kernel" in result.stderr
    assert result.stdout == ""


def test_blocks_git_add_on_research() -> None:
    result = run_hook({"tool_name": "Bash", "tool_input": {"command": "git add research/notes.md"}})
    assert result.returncode == 2
    assert "research" in result.stderr


def test_blocks_git_add_on_gates() -> None:
    result = run_hook({"tool_name": "Bash", "tool_input": {"command": "git add gates/ledger.json"}})
    assert result.returncode == 2
    assert "gates" in result.stderr


def test_blocks_git_add_on_dot_pravrudhi() -> None:
    result = run_hook(
        {"tool_name": "Bash", "tool_input": {"command": "git add .pravrudhi/state.json"}}
    )
    assert result.returncode == 2
    assert ".pravrudhi" in result.stderr


def test_blocks_git_add_with_chained_commands() -> None:
    result = run_hook(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git add src/pravrudhi/cli.py && git add gates/foo.json"},
        }
    )
    assert result.returncode == 2
    assert "gates" in result.stderr


def test_blocks_commit_with_co_authored_by_trailer() -> None:
    message = "Fix the thing\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
    result = run_hook(
        {"tool_name": "Bash", "tool_input": {"command": f'git commit -m "{message}"'}}
    )
    assert result.returncode == 2
    assert "Co-Authored-By" in result.stderr


def test_blocks_commit_with_claude_session_trailer() -> None:
    message = "Fix the thing\n\nClaude-Session: abc123"
    result = run_hook(
        {"tool_name": "Bash", "tool_input": {"command": f'git commit -m "{message}"'}}
    )
    assert result.returncode == 2
    assert "Claude-Session" in result.stderr


def test_blocks_write_inside_pravrudhi_kernel() -> None:
    result = run_hook(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "pravrudhi_kernel/src/thing.py", "content": "x = 1\n"},
        }
    )
    assert result.returncode == 2
    assert "pravrudhi_kernel" in result.stderr


def test_blocks_edit_inside_pravrudhi_kernel_absolute_path() -> None:
    result = run_hook(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(REPO_ROOT / "pravrudhi_kernel" / "src" / "thing.py"),
                "old_string": "a",
                "new_string": "b",
            },
        }
    )
    assert result.returncode == 2
    assert "pravrudhi_kernel" in result.stderr


def test_allows_ordinary_edit_silently() -> None:
    result = run_hook(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "src/pravrudhi/cli.py",
                "old_string": "a",
                "new_string": "b",
            },
        }
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_allows_ordinary_git_add() -> None:
    result = run_hook({"tool_name": "Bash", "tool_input": {"command": "git add src/pravrudhi/cli.py"}})
    assert result.returncode == 0
    assert result.stderr == ""


def test_allows_ordinary_commit_message() -> None:
    result = run_hook({"tool_name": "Bash", "tool_input": {"command": 'git commit -m "Fix the thing"'}})
    assert result.returncode == 0
    assert result.stderr == ""


def test_allows_unrelated_tool() -> None:
    result = run_hook({"tool_name": "Read", "tool_input": {"file_path": "pravrudhi_kernel/src/thing.py"}})
    assert result.returncode == 0
    assert result.stderr == ""


def test_malformed_json_exits_zero() -> None:
    result = run_hook(None, raw_stdin="{not valid json")
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_empty_stdin_exits_zero() -> None:
    result = run_hook(None, raw_stdin="")
    assert result.returncode == 0


def test_unexpected_json_shape_exits_zero() -> None:
    result = run_hook(["not", "a", "dict"])
    assert result.returncode == 0


def test_missing_tool_input_exits_zero() -> None:
    result = run_hook({"tool_name": "Bash"})
    assert result.returncode == 0
