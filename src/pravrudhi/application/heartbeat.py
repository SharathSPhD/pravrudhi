"""OpenClaw's heartbeat: an assistant that wakes on a schedule, looks at what it is responsible for, and does the
next small thing.

Every other way this engine moves is a command a user typed: `pravrudhi intent`, `pravrudhi subagents dispatch`,
`pravrudhi update apply`. Objectives (`application/objectives.py`) can sit fully planned and fully unstarted
forever, because a plan (`application/intent.py`) is not itself an action, and nothing here previously turned one
into the other without an operator's keystroke. A heartbeat closes that gap with the smallest possible mechanism:
one wake-up looks at every declared objective, finds the single most-neglected undone step across all of them, and
dispatches exactly that one through the same swarm machinery a human would use (`application/subagents.py`,
`application/swarm.py`), under the same proposal sandbox policy (`application/sandbox_policy.py`).

A beat that finds nothing to do, or is not allowed to do it, is still a beat: it is recorded with the reason,
because a heartbeat that only logs when it acts cannot be told apart from one that stopped ticking. Nothing here
writes to the ledger, `research/`, `gates/` or `pravrudhi_kernel/` — a dispatched step produces a proposal exactly
as it would under manual dispatch, for a human to review and execute.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from pravrudhi.agents.registry import build_agent as _registry_build_agent
from pravrudhi.application import recipes, subagents, swarm
from pravrudhi.application.intent import compile_intent
from pravrudhi.application.objectives import load_all
from pravrudhi.application.sandbox_policy import apply_policy, policy_for
from pravrudhi.application.update_apply import run_in_progress

PACKAGED_CONFIG = Path(__file__).resolve().parents[1] / "assets" / "configs" / "heartbeat.yaml"

# Capabilities whose step trains or intensively exercises a model on the GPU that a live night has already
# claimed. Evaluation, corpus curation, retrieval, safety review and harness (agents) steps only ever produce a
# proposal document for a human to review and run (see application/subagents.py's module docstring), so those may
# proceed unattended; the ones here would actually compete for the hardware.
GPU_CAPABILITIES: frozenset[str] = frozenset({"pretrain", "finetune", "rl", "performance"})

BuildAgentFn = Callable[[str, str | None], Any]

DispatchFn = BuildAgentFn


def _config_path(root: Path) -> Path:
    return Path(root) / ".pravrudhi" / "heartbeat.yaml"


@dataclass(frozen=True)
class HeartbeatConfig:
    interval_min: int = 60
    max_dispatch_per_beat: int = 1
    quiet_hours: tuple[int, ...] = ()
    allow_gpu: bool = False


def load_config(root: Path) -> HeartbeatConfig:
    """The operator's heartbeat policy at `.pravrudhi/heartbeat.yaml`, or the packaged defaults if unset."""
    path = _config_path(root)
    raw: dict[str, Any] = yaml.safe_load(
        path.read_text(encoding="utf-8") if path.is_file() else PACKAGED_CONFIG.read_text(encoding="utf-8")
    ) or {}
    return HeartbeatConfig(
        interval_min=int(raw.get("interval_min", 60)),
        max_dispatch_per_beat=int(raw.get("max_dispatch_per_beat", 1)),
        quiet_hours=tuple(int(h) for h in (raw.get("quiet_hours") or ())),
        allow_gpu=bool(raw.get("allow_gpu", False)),
    )


@dataclass(frozen=True)
class BeatRecord:
    """What one call to `beat` did, or why it did nothing. Appended to `.pravrudhi/heartbeat.jsonl` unconditionally,
    a no-op beat included, so the log can be read as "is the heartbeat still ticking", not only "what did it do"."""

    at: str
    looked_at: tuple[str, ...]
    chose: dict[str, str] | None
    reason: str
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.at,
            "looked_at": list(self.looked_at),
            "chose": self.chose,
            "reason": self.reason,
            "result": self.result,
        }


def log_path(root: Path) -> Path:
    return Path(root) / ".pravrudhi" / "heartbeat.jsonl"


def _at(moment: datetime) -> str:
    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append(root: Path, record: BeatRecord) -> None:
    path = log_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def _finish(
    root: Path, moment: datetime, looked_at: tuple[str, ...], chose: dict[str, str] | None, reason: str,
    result: dict[str, Any] | None,
) -> BeatRecord:
    record = BeatRecord(at=_at(moment), looked_at=looked_at, chose=chose, reason=reason, result=result)
    _append(root, record)
    return record


def history(root: Path, n: int = 20) -> list[BeatRecord]:
    """The last `n` beats, oldest first. A corrupt line is skipped, not fatal, like `subagents.runs`."""
    path = log_path(root)
    if not path.exists():
        return []
    out: list[BeatRecord] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            out.append(
                BeatRecord(
                    at=str(d["at"]),
                    looked_at=tuple(d.get("looked_at") or ()),
                    chose=d.get("chose"),
                    reason=str(d.get("reason") or ""),
                    result=d.get("result"),
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return out[-n:] if n > 0 else out


def _default_build_agent(root: Path) -> BuildAgentFn:
    def build(name: str, model: str | None) -> Any:
        return _registry_build_agent(root, name, model)

    return build


def beat(root: Path, *, dispatch: DispatchFn | None = None, now: datetime | None = None) -> BeatRecord:
    """One heartbeat: find the single most-neglected undone step across every declared objective and dispatch it.

    `dispatch` takes the shape `swarm.run_wave` already expects of a `build_agent`: `(name, model) -> agent`.
    Injecting it is what lets a test exercise every branch here without ever running a real agent; production
    callers may pass one, or leave it unset to use the fleet's own `agents.registry.build_agent`.
    """
    root = Path(root)
    moment = now.astimezone(UTC) if now and now.tzinfo else (now.replace(tzinfo=UTC) if now else datetime.now(UTC))
    config = load_config(root)

    if moment.hour in config.quiet_hours:
        return _finish(root, moment, (), None, f"quiet hours: {moment.hour:02d}:00 UTC is in {config.quiet_hours}", None)

    objectives = load_all(root)
    looked_at = tuple(o.id for o in objectives)
    if not objectives:
        return _finish(root, moment, looked_at, None, "no objectives declared in this workspace", None)

    catalogue = tuple(recipes.library())
    installed = frozenset(recipes.installed())

    candidates: list[tuple[str, str, str, Any]] = []  # (last_dispatch_at, objective_id, step_id, task)
    steps_by_key: dict[tuple[str, str], Any] = {}
    for objective in objectives:
        plan = compile_intent(objective, catalogue, installed_skills=installed)
        tasks = subagents.tasks_from_plan(objective, plan, root=root)
        steps_by_id = {step.id: step for step in plan.steps}
        obj_runs = subagents.runs(root, objective.id)
        accepted_steps = {r.step for r in obj_runs if r.accepted}
        next_task = next(
            (t for t in tasks if t.spec.task_id.split(":", 1)[1] not in accepted_steps), None
        )
        if next_task is None:
            continue
        step_id = next_task.spec.task_id.split(":", 1)[1]
        steps_by_key[(objective.id, step_id)] = steps_by_id[step_id]
        last_at = max((r.at for r in obj_runs), default="")
        candidates.append((last_at, objective.id, step_id, next_task))

    if not candidates:
        return _finish(root, moment, looked_at, None, "every objective's plan is fully dispatched and accepted", None)

    candidates.sort(key=lambda c: (c[0], c[1]))
    _, objective_id, step_id, task = candidates[0]
    step = steps_by_key[(objective_id, step_id)]
    chose = {"objective": objective_id, "step": step_id}

    needs_gpu = step.capability in GPU_CAPABILITIES
    if needs_gpu and not config.allow_gpu:
        return _finish(root, moment, looked_at, chose, f"step {step_id!r} needs the GPU and allow_gpu is false", None)
    if needs_gpu and run_in_progress(root):
        return _finish(
            root, moment, looked_at, chose, f"step {step_id!r} needs the GPU and a run is already in progress", None
        )
    if config.max_dispatch_per_beat < 1:
        return _finish(
            root, moment, looked_at, chose, "max_dispatch_per_beat is 0; nothing may be dispatched this beat", None
        )

    build_agent = dispatch or _default_build_agent(root)
    scoped = replace(task, spec=apply_policy(task.spec, policy_for("proposal")))
    verdict = swarm.run_wave(build_agent, [scoped], log=lambda _msg: None, root=root)[0]
    run = subagents.SubagentRun(
        objective=objective_id, step=step_id, task_id=verdict.task_id, route=verdict.agent,
        accepted=verdict.accepted, wall_s=verdict.wall_s, files=tuple(verdict.files), reasons=tuple(verdict.reasons),
    )
    subagents.record_run(root, run)
    result = {"accepted": run.accepted, "route": run.route, "files": list(run.files), "reasons": list(run.reasons)}
    verb = "accepted" if run.accepted else "rejected"
    return _finish(root, moment, looked_at, chose, f"dispatched {objective_id}:{step_id} ({verb})", result)


__all__ = ["BeatRecord", "GPU_CAPABILITIES", "HeartbeatConfig", "beat", "history", "load_config", "log_path"]
