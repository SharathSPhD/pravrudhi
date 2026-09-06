"""An agent dispatched into its own worktree was invisible while it ran: the routing log and the run logs
(`application/subagents.py`, `application/selfbuild.py`) record what was dispatched and what came back, but
nothing in between showed what a live agent was actually touching, how much of its wall-clock budget it had
spent, or whether it had written outside the paths its task declared. NemoClaw names this gap directly for a
container sandbox -- a declared network policy, a way to list and check running sandboxes, and a TUI that shows
blocked requests -- and OpenClaw's own swarm kept a persisted record of what each dispatched agent had done
(`agentMemory.js`) rather than trusting a live view alone. This module is the same idea applied to a git worktree
instead of a container.

`observe` reports what one worktree has touched against its base commit and its declared `SandboxPolicy`.
`watch` joins that to every agent process actually running right now, reusing the exact process-table scan
`api/server.py`'s `GET /api/swarm/live` already read with (`scan_live_agents`, moved here rather than
re-implemented) so the two views can never drift apart. `violations` is the persisted history of every write a
policy actually forbade, at `.pravrudhi/violations.jsonl` -- the record that makes a policy real rather than
decorative, the role OpenClaw's audit log played for its own swarm.
"""

from __future__ import annotations

import contextlib
import fnmatch
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# The three ways this engine launches a coding agent as a subprocess, matched against a process's argv. Kept
# here, not in api/server.py, so `watch` and `GET /api/swarm/live` read the process table exactly one way.
LIVE_AGENT_PATTERNS: dict[str, str] = {"claude -p": "claude", "codex exec": "codex", "agent_code": "agent_code"}

# `delegate.TaskSpec`'s own default: the one wall-clock budget actually declared anywhere in this codebase. Used
# only as the budget for a live worktree whose own policy could not be reconstructed -- never presented as a
# measured number.
DEFAULT_TIMEOUT_S = 1800


def parse_live_agents(ps_output: str) -> list[dict[str, Any]]:
    """The classification behind `scan_live_agents`, taking `ps -eo pid,etimes,args` output as plain text so a
    caller that must own its own subprocess call (`api/server.py`'s `GET /api/swarm/live`, so a test can
    monkeypatch `subprocess.run` where it already looks) still shares the one place that decides which
    processes are agents, and never has to echo the full command line, which could carry a secret."""
    rows: list[dict[str, Any]] = []
    for line in ps_output.splitlines()[1:]:
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        pid_s, etimes_s, args = parts
        kind = next((k for pattern, k in LIVE_AGENT_PATTERNS.items() if pattern in args), None)
        if kind is None:
            continue
        try:
            pid, elapsed_s = int(pid_s), int(etimes_s)
        except ValueError:
            continue
        worktree: str | None = None
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
            if "/.worktrees/" in cwd:
                worktree = cwd
        except OSError:
            pass
        rows.append({"pid": pid, "elapsed_s": elapsed_s, "kind": kind, "worktree": worktree})
    return rows


def scan_live_agents() -> list[dict[str, Any]]:
    """Every agent process on this machine right now: pid, elapsed seconds, which launch pattern matched, and
    (if its cwd is a `.worktrees/` checkout) that path. Reads the process table itself and classifies it with
    `parse_live_agents`; `watch` below calls this directly."""
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True, timeout=5, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return parse_live_agents(out)


@dataclass(frozen=True)
class SandboxPolicy:
    """The paths a dispatched agent may touch and how long it has to do it -- the same scope
    `application.delegate.TaskSpec` briefs an agent with, reused here as the yardstick a live worktree is judged
    against rather than a second definition of "allowed" drifting from the first.

    Empty `allowed_paths` means no policy could be reconstructed for this worktree, not that it may touch
    nothing: `owns` treats that case as unrestricted so an unknown policy never manufactures a false violation.
    """

    allowed_paths: tuple[str, ...] = ()
    timeout_s: int = DEFAULT_TIMEOUT_S

    def owns(self, path: str) -> bool:
        if not self.allowed_paths:
            return True
        for pat in self.allowed_paths:
            if pat.endswith("/") and path.startswith(pat):
                return True
            if fnmatch.fnmatch(path, pat):
                return True
        return False


@dataclass(frozen=True)
class Violation:
    """One write a policy forbade: the task that made it, the path it touched, and the policy that forbade it."""

    task_id: str
    path: str
    allowed_paths: tuple[str, ...]
    at: str = ""


@dataclass(frozen=True)
class Observation:
    """What one worktree has touched against its base commit, and how that stacks up against its policy."""

    created: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()
    bytes_written: int = 0
    allowed_count: int = 0
    violations: tuple[Violation, ...] = ()


def _git(args: list[str], cwd: Path, timeout_s: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout_s, check=False)


def violations_path(root: Path) -> Path:
    return Path(root) / ".pravrudhi" / "violations.jsonl"


def _read_violations(root: Path) -> list[dict[str, Any]]:
    p = violations_path(root)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _record_violations(root: Path, found: tuple[Violation, ...]) -> None:
    """Append every violation not already on record. `watch` calls `observe` on every poll of a still-running
    agent, so without this dedupe a single ongoing violation would be re-appended every few seconds."""
    if not found:
        return
    seen = {(row.get("task_id"), row.get("path")) for row in _read_violations(root)}
    fresh = [v for v in found if (v.task_id, v.path) not in seen]
    if not fresh:
        return
    p = violations_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        for v in fresh:
            fh.write(
                json.dumps(
                    {
                        "task_id": v.task_id,
                        "path": v.path,
                        "allowed_paths": list(v.allowed_paths),
                        "at": v.at,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def violations(root: Path, n: int = 100) -> list[dict[str, Any]]:
    """The persisted violation history, newest first -- the record that makes a policy real rather than
    decorative."""
    return list(reversed(_read_violations(root)[-n:]))


def observe(root: Path, task_id: str, worktree: Path, policy: SandboxPolicy) -> Observation:
    """What `worktree` has touched against its base commit: created, modified and deleted paths, the total bytes
    written, how many of those paths `policy` allows, and every write that fell outside it -- each of those
    persisted to `violations_path(root)` so the policy's history outlives this one call.

    A worktree's branch is created from its base commit and an agent dispatched through
    `application.delegate.dispatch` never commits inside it (see `agents.base.GitWorktreeMixin`), so a plain
    `git diff` against `HEAD` already is the diff against that base commit. A worktree that does not exist --
    never created, or already torn down -- answers with an empty observation rather than raising.
    """
    wt = Path(worktree)
    if not wt.is_dir():
        return Observation()
    diff = _git(["diff", "--numstat", "HEAD"], wt)
    if diff.returncode != 0:
        return Observation()
    changed: set[str] = set()
    for line in diff.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            changed.add(parts[2])
    created = sorted(_git(["ls-files", "--others", "--exclude-standard"], wt).stdout.split())
    created_set = set(created)
    modified = sorted(f for f in changed - created_set if (wt / f).exists())
    deleted = sorted(f for f in changed - created_set if not (wt / f).exists())

    bytes_written = 0
    for f in (*created, *modified):
        with contextlib.suppress(OSError):  # a file the agent deleted between listing and measuring
            bytes_written += (wt / f).stat().st_size

    touched = sorted({*created, *modified, *deleted})
    allowed_count = sum(1 for p in touched if policy.owns(p))
    forbidden = [p for p in touched if not policy.owns(p)]
    at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    flagged = tuple(Violation(task_id=task_id, path=p, allowed_paths=policy.allowed_paths, at=at) for p in forbidden)
    _record_violations(root, flagged)

    return Observation(
        created=tuple(created),
        modified=tuple(modified),
        deleted=tuple(deleted),
        bytes_written=bytes_written,
        allowed_count=allowed_count,
        violations=flagged,
    )


def _policy_from_task_id(task_id: str) -> SandboxPolicy:
    """Best-effort reconstruction of a subagent's declared scope from its task id.

    `application.subagents.tasks_from_plan` builds `{objective.id}:{step.id}` as the task id and
    `proposals/{objective.id}/{step.id}/*` as its one allowed path; naming the worktree then collapses that
    colon to a hyphen (`agents.base.GitWorktreeMixin.ref_safe`). Splitting on the first separator recovers both
    halves whenever neither id itself contains one. When the shape does not match this returns an unrestricted
    policy rather than asserting a scope nobody declared.
    """
    sep = ":" if ":" in task_id else "-" if "-" in task_id else None
    if sep is None:
        return SandboxPolicy()
    objective_id, step_id = task_id.split(sep, 1)
    return SandboxPolicy(allowed_paths=(f"proposals/{objective_id}/{step_id}/*",))


def watch(root: Path) -> list[dict[str, Any]]:
    """Every live agent process, joined to its worktree and its policy, with elapsed time and the fraction of
    its wall-clock budget spent."""
    root = Path(root)
    rows: list[dict[str, Any]] = []
    for row in scan_live_agents():
        worktree = row["worktree"]
        if worktree is None:
            continue
        task_id = Path(worktree).name.removeprefix("agent-")
        policy = _policy_from_task_id(task_id)
        obs = observe(root, task_id, Path(worktree), policy)
        elapsed_s = int(row["elapsed_s"])
        rows.append(
            {
                "pid": row["pid"],
                "kind": row["kind"],
                "task_id": task_id,
                "worktree": worktree,
                "elapsed_s": elapsed_s,
                "budget_s": policy.timeout_s,
                "budget_fraction": elapsed_s / policy.timeout_s if policy.timeout_s else None,
                "allowed_paths": list(policy.allowed_paths),
                "observation": obs,
            }
        )
    return rows


__all__ = [
    "DEFAULT_TIMEOUT_S",
    "LIVE_AGENT_PATTERNS",
    "Observation",
    "SandboxPolicy",
    "Violation",
    "observe",
    "parse_live_agents",
    "scan_live_agents",
    "violations",
    "violations_path",
    "watch",
]
