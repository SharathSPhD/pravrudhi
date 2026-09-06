"""Feed the same brief back until the work is genuinely finished, and never take the agent's word for it.

An agent that has run out of ideas writes a summary saying the task is complete, and the harness believes it. Half
the defects in this project reached the operator that way: a page that answered 200 while rendering an error, a
scheduler wired to a flag the installed engine did not have, a table whose every cell was a dash. Each was reported
as done by whoever built it.

The Ralph discipline answers that. A task carries a completion promise, and the promise is checked by running
something, not by reading what the agent wrote. If the check fails the identical brief goes back — the agent sees
its own previous attempt in the worktree and in git history — and it tries again, until the check passes or the
iteration budget runs out. The agent never gets to declare victory.

Two properties are load-bearing.

The check is external. `verify` is a command whose exit status decides, or a callable the caller supplies. Nothing
in the agent's output can satisfy it, so an agent cannot escape by claiming success, and the phrase "completion
promise" appearing in its summary means nothing here.

The check's own output goes back with the brief. The first loop run here failed on an environment fact the agent
could not have known and could not see — Electron's sandbox helper needs root — and it would have retried blind
four times. Handing back what the check said is not a softening of the discipline: the agent still cannot decide
it is finished, it is simply told what is wrong.

Every attempt is recorded. `.pravrudhi/ralph.jsonl` keeps each iteration with what the check said, so a loop that
ran five times and failed five times leaves five pieces of evidence rather than one cheerful summary.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VerifyFn = Callable[[Path], tuple[bool, str]]

MAX_ITERATIONS = 5

RALPH_PREAMBLE = """This task runs under a completion loop. You do not decide when it is finished.

COMPLETION PROMISE: {promise}

The promise is checked by running a command, not by reading anything you write. If the check fails you will be
given this identical brief again, with your previous attempt still present in the worktree and in git history,
and you will be expected to find what is still wrong and fix it. Saying the work is complete has no effect
whatsoever on the check, so do not spend words on it.

If you cannot finish, leave the work in the best state you can reach and say plainly in your final message what
is still broken and what you tried. That is useful. A confident summary of work that does not pass the check is
not, and it is the single most common way defects have reached this project's operator.
"""

LAST_CHECK = """

--- WHAT THE CHECK SAID ON YOUR PREVIOUS ATTEMPT (iteration {iteration}) ---
{detail}
--- end of check output ---

Read that before changing anything. It is the actual reason the work is not finished yet.
"""


@dataclass
class Attempt:
    iteration: int
    accepted: bool
    passed: bool
    detail: str
    wall_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration, "accepted": self.accepted, "passed": self.passed,
            "detail": self.detail, "wall_s": round(self.wall_s, 1),
        }


@dataclass
class LoopResult:
    task_id: str
    passed: bool
    iterations: int
    reason: str
    attempts: list[Attempt] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "passed": self.passed, "iterations": self.iterations,
            "reason": self.reason, "attempts": [a.to_dict() for a in self.attempts],
        }


def log_path(root: Path) -> Path:
    return Path(root) / ".pravrudhi" / "ralph.jsonl"


def _record(root: Path, task_id: str, promise: str, attempt: Attempt) -> None:
    path = log_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "task_id": task_id,
           "promise": promise, **attempt.to_dict()}
    with path.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def command_verifier(command: str, *, timeout_s: int = 1800) -> VerifyFn:
    """A promise kept by a command's exit status. The output is recorded either way, truncated."""

    def verify(cwd: Path) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout_s
            )
        except subprocess.TimeoutExpired:
            return False, f"the check did not finish within {timeout_s}s"
        out = (result.stdout + result.stderr).strip()
        tail = "\n".join(out.splitlines()[-12:])[:1200]
        return result.returncode == 0, tail

    return verify


def attempts(root: Path, n: int = 50) -> list[dict[str, Any]]:
    path = log_path(root)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-n:]


def run_until_done(
    dispatch_once: Callable[[str], tuple[bool, str, float]],
    *,
    root: Path,
    task_id: str,
    brief: str,
    promise: str,
    verify: VerifyFn,
    workspace: Path | None = None,
    max_iterations: int = MAX_ITERATIONS,
    log: Callable[[str], None] = print,
) -> LoopResult:
    """Dispatch the same brief until the promise verifiably holds.

    `dispatch_once` takes the full brief and returns (accepted, detail, wall_s). It is a callable rather than an
    agent so a test can drive this without a model. `verify` runs against `workspace` — the worktree the agent
    actually wrote in — because checking the main tree would pass on work that was never merged.
    """
    root = Path(root)
    base = RALPH_PREAMBLE.format(promise=promise) + "\n" + brief
    log_attempts: list[Attempt] = []
    last: str = ""

    for i in range(1, max(1, max_iterations) + 1):
        full = base + (LAST_CHECK.format(iteration=i - 1, detail=last[:2000]) if last else "")
        accepted, detail, wall = dispatch_once(full)
        where = workspace or root
        passed, check_detail = verify(where)
        attempt = Attempt(i, accepted, passed, check_detail or detail, wall)
        log_attempts.append(attempt)
        _record(root, task_id, promise, attempt)
        said = (check_detail or detail).strip()
        why = "" if passed else f" -- {said.splitlines()[-1][:160] if said else 'no output'}"
        log(f"ralph {task_id} iteration {i}: agent {'accepted' if accepted else 'rejected'}, "
            f"check {'PASSED' if passed else 'failed'}{why}")
        last = check_detail or detail
        if passed:
            return LoopResult(task_id, True, i, f"the promise holds after {i} iteration(s)", log_attempts)

    last = log_attempts[-1].detail if log_attempts else ""
    return LoopResult(
        task_id, False, len(log_attempts),
        f"the promise did not hold after {len(log_attempts)} iteration(s); last check said: {last[:300]}",
        log_attempts,
    )


__all__ = [
    "LAST_CHECK", "MAX_ITERATIONS", "RALPH_PREAMBLE", "Attempt", "LoopResult", "VerifyFn",
    "attempts", "command_verifier", "log_path", "run_until_done",
]
