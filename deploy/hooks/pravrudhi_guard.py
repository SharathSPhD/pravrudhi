#!/usr/bin/env python3
"""Claude Code PreToolUse hook enforcing Pravrudhi's house rules.

Reads a single JSON object from stdin shaped like
``{"tool_name": str, "tool_input": {...}, ...}`` and refuses three things:

1. ``git add`` (via Bash) touching ``pravrudhi_kernel/``, ``research/``,
   ``gates/`` or ``.pravrudhi/`` — paths CLAUDE.md forbids committing.
2. ``git commit`` (via Bash) whose message carries a ``Co-Authored-By:`` or
   ``Claude-Session`` trailer — the repo's commit-msg hook already enforces
   this; we just fail fast before the shell call runs.
3. Any Write/Edit whose ``file_path`` resolves inside ``pravrudhi_kernel/``
   — T0 is not the agent's to edit.

Exits 2 with a reason on stderr to block a call, exits 0 silently to allow
it. Any input we cannot make sense of (malformed JSON, unexpected shape) is
allowed through rather than crashing the hook chain.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

FORBIDDEN_ADD_PATHS = ("pravrudhi_kernel", "research", "gates", ".pravrudhi")
FORBIDDEN_EDIT_ROOT = "pravrudhi_kernel"
TRAILER_PATTERN = re.compile(r"^\s*Co-Authored-By:", re.MULTILINE | re.IGNORECASE)


class Blocked(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _split_git_invocations(command: str) -> list[list[str]]:
    """Best-effort split of a shell command string into argv-like chunks."""
    invocations: list[list[str]] = []
    for segment in re.split(r"&&|\|\||;|\|", command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        if tokens:
            invocations.append(tokens)
    return invocations


def _touches_forbidden_path(path_arg: str) -> str | None:
    normalized = path_arg.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.rstrip("/")
    for forbidden in FORBIDDEN_ADD_PATHS:
        if normalized == forbidden or normalized.startswith(forbidden + "/"):
            return forbidden
    return None


def check_bash(tool_input: dict) -> None:
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return

    for tokens in _split_git_invocations(command):
        if tokens[0] != "git" or len(tokens) < 2:
            continue
        subcommand = tokens[1]

        if subcommand == "add":
            for arg in tokens[2:]:
                if arg.startswith("-"):
                    continue
                forbidden = _touches_forbidden_path(arg)
                if forbidden is not None:
                    raise Blocked(
                        f"pravrudhi_guard: refusing 'git add {arg}' - "
                        f"{forbidden}/ is forbidden from commits (CLAUDE.md)."
                    )

        if subcommand == "commit" and TRAILER_PATTERN.search(command):
            raise Blocked(
                "pravrudhi_guard: refusing 'git commit' - message carries a "
                "Co-Authored-By: trailer, which the repo's commit-msg hook rejects."
            )

        if subcommand == "commit" and "Claude-Session" in command:
            raise Blocked(
                "pravrudhi_guard: refusing 'git commit' - message carries a "
                "Claude-Session trailer, which the repo's commit-msg hook rejects."
            )


def check_write_edit(tool_input: dict) -> None:
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        return

    cwd = Path.cwd()
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = cwd / candidate

    try:
        relative = candidate.resolve().relative_to(cwd.resolve())
    except ValueError:
        return

    if relative.parts and relative.parts[0] == FORBIDDEN_EDIT_ROOT:
        raise Blocked(
            f"pravrudhi_guard: refusing to write/edit '{file_path}' - "
            f"{FORBIDDEN_EDIT_ROOT}/ is T0 and not the agent's to edit."
        )


def evaluate(payload: dict) -> None:
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return

    if tool_name == "Bash":
        check_bash(tool_input)
    elif tool_name in ("Write", "Edit"):
        check_write_edit(tool_input)


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return 0
        evaluate(payload)
    except Blocked as blocked:
        print(blocked.reason, file=sys.stderr)
        return 2
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
