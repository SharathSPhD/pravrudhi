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
import shlex
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


def _envelope(text: str) -> dict | None:
    """Orca replies with {id, ok, result, _meta}; return `result` when the call succeeded."""
    try:
        v = json.loads(text)
    except ValueError:
        return None
    if not isinstance(v, dict):
        return None
    if v.get("ok") is False:
        return {"_error": (v.get("error") or {}).get("message", "orca call failed")}
    r = v.get("result")
    return r if isinstance(r, dict) else v


def _dig(d: dict | None, *path: str):
    cur: object = d or {}
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


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
        _orca(["repo", "add", "--path", str(self.root), "--json"])

    def create_workspace(self, task_id: str, base_ref: str = "HEAD") -> Path:
        """Ask Orca for a worktree; fall back to a plain git worktree only if Orca declines to report a path."""
        if not self.available():
            raise OrcaUnavailable("orca-ide runtime is not reachable (it needs a display server; see `orca-ide serve`)")
        self.register_repo()
        code, out, err = _orca(
            ["worktree", "create", "--name", f"pravrudhi-{task_id}", "--repo", f"path:{self.root}",
             "--base-branch", base_ref, "--json"]
        )
        info = _envelope(out)
        path = _dig(info, "worktree", "path") or (info or {}).get("path")
        if not path:
            raise OrcaUnavailable(f"orca worktree create returned no path (exit {code}): {(err or out)[:300]}")
        return Path(path)

    def agent_command(self, prompt: str) -> list[str]:
        """The headless invocation Orca runs in the worktree's terminal."""
        if self.agent_id == "claude":
            return ["claude", "-p", prompt, "--output-format", "json", "--allowed-tools", "Read,Edit,Write,Grep,Glob,Bash"]
        if self.agent_id == "codex":
            return ["codex", "exec", "--sandbox", "workspace-write", "--skip-git-repo-check", prompt]
        raise OrcaUnavailable(f"no headless invocation known for agent {self.agent_id!r}")

    def run(self, prompt: str, workspace: Path, timeout_s: int | None = None) -> AgentRun:
        """Run the agent in an Orca-managed terminal and wait for the process to exit.

        Orca owns the worktree and the terminal, so the session is visible and reviewable in Orca alongside any
        other agent. Waiting on exit rather than on a TUI going idle keeps the result deterministic, which an
        unattended loop needs; the agent's own headless mode supplies the structured output.
        """
        timeout_s = timeout_s or self.timeout_s
        t0 = time.monotonic()
        cmd = " ".join(shlex.quote(c) for c in self.agent_command(prompt))
        code, out, err = _orca(
            ["terminal", "create", "--worktree", f"path:{workspace}", "--title", f"pravrudhi-{self.agent_id}",
             "--command", cmd, "--json"],
            timeout_s=180,
        )
        info = _envelope(out) or {}
        handle = _dig(info, "terminal", "handle") or info.get("handle")
        if not handle:
            reason = info.get("_error") or (err or out)[:300]
            return AgentRun(agent=self.name, ok=False, exit_code=code or 1, wall_s=time.monotonic() - t0,
                            text="", workspace=workspace, stderr_tail=str(reason))
        self._terminals[str(workspace)] = str(handle)
        _orca(["terminal", "wait", "--terminal", str(handle), "--for", "exit",
               "--timeout-ms", str(int(timeout_s * 1000)), "--json"], timeout_s=timeout_s + 120)
        rcode, rout, rerr = _orca(["terminal", "read", "--terminal", str(handle), "--limit", "4000", "--json"], timeout_s=180)
        payload = _envelope(rout) or {}
        rows = payload.get("lines") or payload.get("rows") or payload.get("output")
        text = "\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows) if isinstance(rows, list) else rout
        return AgentRun(agent=self.name, ok=rcode == 0, exit_code=rcode, wall_s=time.monotonic() - t0,
                        text=text, workspace=workspace, session_id=str(handle), stderr_tail=rerr[-2000:])

    def stop(self, workspace: Path) -> None:
        handle = self._terminals.pop(str(workspace), None)
        if handle:
            _orca(["terminal", "close", "--terminal", handle])
        _orca(["worktree", "rm", "--worktree", f"path:{workspace}"])


__all__ = ["OrcaAgent", "OrcaUnavailable", "AgentRun", "Diff"]
