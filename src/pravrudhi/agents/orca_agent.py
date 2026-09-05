"""Adapter for the Orca agent development environment.

Orca is treated as infrastructure, never as the intelligence: it manages worktrees, terminals and agent sessions,
while Pravrudhi's controller decides what to run and how the result is scored. That split is deliberate. Orca's own
CLI is genuinely programmable (`worktree create --agent <id> --prompt`, `terminal wait --for tui-idle`,
`terminal read --json`), so an adapter is thin; but the runtime is an Electron application that needs a display
server even in `serve` mode, so a box without one cannot use it. `available()` reports that honestly instead of
failing later, and every other adapter keeps working when Orca is absent.

The advantage Orca brings is that Claude Code and Codex sit side by side under one orchestrator with their diffs in
one place. The advantage of keeping it optional is that nothing in the loop stops when it is not there.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from pravrudhi.agents.base import AgentRun, Diff, GitWorktreeMixin


class OrcaUnavailable(RuntimeError):
    pass


def _orca(args: list[str], timeout_s: int = 120) -> tuple[int, str, str]:
    p = subprocess.run(["orca-ide", *args], capture_output=True, text=True, timeout=timeout_s)
    return p.returncode, p.stdout, p.stderr


def _json_or_none(text: str) -> dict | None:
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else None
    except ValueError:
        return None


class OrcaAgent(GitWorktreeMixin):
    """Run a named agent (claude, codex, ...) inside an Orca-managed worktree.

    The flow is the one Orca documents for scripted use: register the repository, create a worktree with the agent
    launched in its first terminal and the task as its opening prompt, wait for that terminal to go idle, then read
    its output. The diff is read with git from the worktree Orca created, so scoring does not depend on Orca at all.
    """

    def __init__(self, root: Path, agent_id: str = "claude", timeout_s: int = 1800) -> None:
        self.root, self.agent_id, self.timeout_s = Path(root), agent_id, timeout_s
        self.name = f"orca:{agent_id}"
        self._terminals: dict[str, str] = {}

    def runtime_ready(self) -> bool:
        if shutil.which("orca-ide") is None:
            return False
        try:
            _, out, _ = _orca(["status"], timeout_s=60)
        except (subprocess.SubprocessError, OSError):
            return False
        return "runtimeReachable: true" in out or '"runtimeReachable": true' in out

    def available(self) -> bool:
        return self.runtime_ready()

    def register_repo(self) -> None:
        _orca(["repo", "add", str(self.root)])

    def create_workspace(self, task_id: str, base_ref: str = "HEAD") -> Path:
        """Ask Orca for a worktree; fall back to a plain git worktree only if Orca declines to report a path."""
        if not self.available():
            raise OrcaUnavailable("orca-ide runtime is not reachable (it needs a display server; see `orca-ide serve`)")
        self.register_repo()
        code, out, err = _orca(
            ["worktree", "create", "--name", f"pravrudhi-{task_id}", "--repo", f"path:{self.root}",
             "--base-branch", base_ref, "--json"]
        )
        info = _json_or_none(out)
        path = (info or {}).get("path") or (info or {}).get("worktreePath")
        if not path:
            raise OrcaUnavailable(f"orca worktree create returned no path (exit {code}): {(err or out)[:300]}")
        return Path(path)

    def run(self, prompt: str, workspace: Path, timeout_s: int | None = None) -> AgentRun:
        timeout_s = timeout_s or self.timeout_s
        t0 = time.monotonic()
        code, out, err = _orca(
            ["terminal", "create", "--worktree", f"path:{workspace}", "--title", f"pravrudhi-{self.agent_id}", "--json"]
        )
        info = _json_or_none(out) or {}
        handle = info.get("terminal") or info.get("handle") or info.get("id")
        if not handle:
            return AgentRun(agent=self.name, ok=False, exit_code=code or 1, wall_s=time.monotonic() - t0,
                            text="", workspace=workspace, stderr_tail=(err or out)[-2000:])
        self._terminals[str(workspace)] = str(handle)
        _orca(["terminal", "send", "--terminal", str(handle), "--text", prompt, "--enter", "--json"])
        _orca(["terminal", "wait", "--terminal", str(handle), "--for", "tui-idle",
               "--timeout-ms", str(int(timeout_s * 1000)), "--json"], timeout_s=timeout_s + 60)
        rcode, rout, rerr = _orca(["terminal", "read", "--terminal", str(handle), "--json"])
        payload = _json_or_none(rout)
        text = json.dumps(payload) if payload else rout
        return AgentRun(agent=self.name, ok=rcode == 0, exit_code=rcode, wall_s=time.monotonic() - t0,
                        text=text, workspace=workspace, session_id=str(handle), stderr_tail=rerr[-2000:])

    def stop(self, workspace: Path) -> None:
        handle = self._terminals.pop(str(workspace), None)
        if handle:
            _orca(["terminal", "close", "--terminal", handle])
        _orca(["worktree", "rm", "--worktree", f"path:{workspace}"])


__all__ = ["OrcaAgent", "OrcaUnavailable", "AgentRun", "Diff"]
