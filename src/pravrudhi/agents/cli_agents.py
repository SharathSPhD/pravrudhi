"""Adapters for first-party coding-agent CLIs: Claude Code and Codex.

Each agent gets its own git worktree, is invoked non-interactively, and returns a diff. Nothing about Pravrudhi's
controller is specific to either vendor: both satisfy the same `CodingAgent` protocol, so an experiment can compare
them the way it compares two recipes, and neither is load-bearing.

Authentication is the operator's, not ours. These adapters never read, write or log a credential; they invoke a CLI
that is already signed in and report `available()` as false when it is not.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from pravrudhi.agents.base import AgentRun, Diff, GitWorktreeMixin


def _run(cmd: list[str], cwd: Path, timeout_s: int, env: dict[str, str] | None = None) -> tuple[int, str, str, float]:
    t0 = time.monotonic()
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_s, env={**os.environ, **(env or {})}
        )
        return p.returncode, p.stdout, p.stderr, time.monotonic() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return 124, out, err + f"\ntimeout after {timeout_s}s", time.monotonic() - t0


class ClaudeCodeAgent(GitWorktreeMixin):
    """Claude Code driven through its documented headless mode.

    `claude -p <prompt> --output-format json` runs one non-interactive turn and prints a JSON envelope carrying the
    result text, the session id and the cost. Tools are restricted to what a code change needs; the worktree is the
    only directory the agent is given.
    """

    name = "claude-code"

    def __init__(self, root: Path, model: str | None = None, allowed_tools: str = "Read,Edit,Write,Grep,Glob,Bash") -> None:
        self.root, self.model, self.allowed_tools = Path(root), model, allowed_tools

    def available(self) -> bool:
        return shutil.which("claude") is not None

    def run(self, prompt: str, workspace: Path, timeout_s: int = 1800) -> AgentRun:
        cmd = ["claude", "-p", prompt, "--output-format", "json", "--allowed-tools", self.allowed_tools]
        if self.model:
            cmd += ["--model", self.model]
        code, out, err, wall = _run(cmd, workspace, timeout_s)
        text, session, cost = out, None, None
        try:
            env = json.loads(out)
            if isinstance(env, dict):
                text = str(env.get("result", out))
                session = env.get("session_id")
                cost = env.get("total_cost_usd")
                if env.get("is_error"):
                    code = code or 1
        except ValueError:
            pass
        return AgentRun(
            agent=self.name, ok=code == 0, exit_code=code, wall_s=wall, text=text,
            workspace=workspace, session_id=session, cost_usd=cost, stderr_tail=err[-2000:],
        )


class CodexAgent(GitWorktreeMixin):
    """Codex driven through `codex exec`, its documented non-interactive subcommand.

    The sandbox mode is passed through rather than defaulted to anything permissive: an agent editing this repository
    should not be able to reach the network or write outside its worktree unless the operator says so.
    """

    name = "codex"

    def __init__(self, root: Path, model: str | None = None, sandbox: str = "workspace-write") -> None:
        self.root, self.model, self.sandbox = Path(root), model, sandbox

    def available(self) -> bool:
        return shutil.which("codex") is not None

    def logged_in(self) -> bool:
        """True when Codex has stored credentials. Distinguishes 'not installed' from 'installed, not signed in'."""
        if not self.available():
            return False
        code, out, err, _ = _run(["codex", "login", "status"], self.root, 60)
        return code == 0 and "not logged in" not in (out + err).lower()

    def run(self, prompt: str, workspace: Path, timeout_s: int = 1800) -> AgentRun:
        cmd = ["codex", "exec", "--cd", str(workspace), "--sandbox", self.sandbox, "--skip-git-repo-check"]
        if self.model:
            cmd += ["--model", self.model]
        cmd.append(prompt)
        code, out, err, wall = _run(cmd, workspace, timeout_s)
        return AgentRun(
            agent=self.name, ok=code == 0, exit_code=code, wall_s=wall, text=out,
            workspace=workspace, stderr_tail=err[-2000:],
        )


def unified_agents(root: Path) -> dict[str, GitWorktreeMixin]:
    return {a.name: a for a in (ClaudeCodeAgent(root), CodexAgent(root))}


__all__ = ["ClaudeCodeAgent", "CodexAgent", "AgentRun", "Diff", "unified_agents"]
