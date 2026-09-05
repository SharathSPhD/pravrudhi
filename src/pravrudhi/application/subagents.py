"""Subagent building was a capability of the people building Pravrudhi, not of Pravrudhi itself.

`application/swarm.py` and `delegate.py` already dispatch delegated work safely and route it by measured
outcome, but only a developer holding a Python shell could turn a plan into tasks: a user who stated an
objective through `intent.compile_intent` had no way to ask the engine to fan that plan's steps out to the
agent fleet. This module is that missing bridge, from an `IntentPlanProposal` to dispatched `SwarmTask`s and
back to a record of what happened.

Everything a subagent produces here is a PROPOSAL. Nothing in this module writes to the ledger, to `research/`,
to `gates/` or to `pravrudhi_kernel/`; a subagent's allowed paths are confined to its own scratch directory, and
a dispatch's outcome is recorded beside the workspace's other operational state, never as evidence.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pravrudhi.application import swarm
from pravrudhi.application.delegate import TaskSpec
from pravrudhi.application.intent import Capability, IntentPlanProposal, IntentStepProposal
from pravrudhi.application.objectives import Objective

# Difficulty, not importance, decides the tier -- same principle as swarm.ROUTES. Evaluation and corpus work
# is mechanical checking and filtering; finetune and rl steps choose and shape a candidate, which is harder to
# get wrong safely, so they go to the stronger design tier. Every other capability (pretrain, performance,
# retrieval, safety, agents) touches what a gate will later judge, so it defaults to the critical tier.
_TIER_BY_CAPABILITY: dict[str, str] = {
    "evaluate": "standard",
    "corpus": "standard",
    "finetune": "design",
    "rl": "design",
}
_DEFAULT_TIER = "critical"


def _tier_for(capability: Capability) -> str:
    return _TIER_BY_CAPABILITY.get(capability, _DEFAULT_TIER)


def _scratch_dir(objective: Objective, step: IntentStepProposal) -> str:
    return f".pravrudhi/subagents/{objective.id}/{step.id}"


def _prompt_for(objective: Objective, step: IntentStepProposal, scratch: str, validate: str) -> str:
    recipes = ", ".join(step.recipe_ids) if step.recipe_ids else "none catalogued"
    return (
        f"Objective (verbatim intent): {objective.intent}\n\n"
        f"Step {step.id!r}, capability {step.capability!r}.\n"
        f"Candidate recipe ids: {recipes}.\n"
        f"Success criterion: {step.check.criterion}\n\n"
        "Everything you write is a PROPOSAL toward this step, not evidence: nothing you produce may write to "
        "the ledger, research/, gates/ or pravrudhi_kernel/.\n"
        f"Write only under {scratch}/.\n"
        f"Validate your work with `{validate}`."
    )


def tasks_from_plan(objective: Objective, plan: IntentPlanProposal, *, root: Path) -> list[swarm.SwarmTask]:
    """One `SwarmTask` per step of `plan`, in order, each confined to its own scratch directory.

    A step never gets write access to `research/`, `gates/` or `pravrudhi_kernel/`: its `allowed_paths` name
    only `.pravrudhi/subagents/<objective>/<step>/`, which this call also creates so the directory exists
    before any agent is asked to write into it.
    """
    tasks: list[swarm.SwarmTask] = []
    for step in plan.steps:
        scratch = _scratch_dir(objective, step)
        (Path(root) / scratch).mkdir(parents=True, exist_ok=True)
        validate = "uv run pytest -q"
        spec = TaskSpec(
            task_id=f"{objective.id}:{step.id}",
            prompt=_prompt_for(objective, step, scratch, validate),
            allowed_paths=(f"{scratch}/*",),
            validate=validate,
        )
        tier = _tier_for(step.capability)
        tasks.append(swarm.SwarmTask(spec, tier, why=f"{step.capability} step of objective {objective.id}"))
    return tasks


@dataclass(frozen=True)
class SubagentRun:
    """One dispatched step and what the swarm's own verdict said about it. Not evidence: see module docstring."""

    objective: str
    step: str
    task_id: str
    route: str
    accepted: bool
    wall_s: float
    files: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    at: str = ""


def runs_path(root: Path) -> Path:
    return Path(root) / ".pravrudhi" / "subagents" / "runs.jsonl"


def record_run(root: Path, run: SubagentRun) -> None:
    """Append one run. Operational state, like `routing.jsonl`: no evidence document may cite it."""
    p = runs_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = asdict(run)
    row["files"] = list(run.files)
    row["reasons"] = list(run.reasons)
    row["at"] = run.at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with p.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def runs(root: Path, objective: str | None = None) -> list[SubagentRun]:
    """Every recorded run, optionally filtered to one objective. A corrupt line is skipped, not fatal."""
    p = runs_path(root)
    if not p.exists():
        return []
    out: list[SubagentRun] = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            run = SubagentRun(
                objective=str(d["objective"]),
                step=str(d["step"]),
                task_id=str(d["task_id"]),
                route=str(d["route"]),
                accepted=bool(d["accepted"]),
                wall_s=float(d.get("wall_s", 0.0)),
                files=tuple(d.get("files", ())),
                reasons=tuple(d.get("reasons", ())),
                at=str(d.get("at", "")),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        if objective is None or run.objective == objective:
            out.append(run)
    return out


def dispatch_plan(
    objective: Objective, plan: IntentPlanProposal, *, root: Path, build_agent: Any, log: Any = print,
) -> list[SubagentRun]:
    """Dispatch every step of `plan` through the swarm and record what came back.

    Waves are planned with `swarm.plan` so tasks whose scratch directories could collide never run together,
    and each wave runs through `swarm.run_wave(root=root)` so the router learns from the outcome. Every result
    is a `SubagentRun`, appended to `.pravrudhi/subagents/runs.jsonl` -- a record of what the swarm did, not a
    claim that any step produced evidence. Nothing here writes to the ledger, research/, gates/ or
    pravrudhi_kernel/; a subagent's output is a proposal until a human reviews and executes it.
    """
    tasks = tasks_from_plan(objective, plan, root=root)
    waves, conflicts = swarm.plan(tasks)
    if conflicts:
        log(f"subagents: {len(conflicts)} conflicting task pair(s) deferred to a later wave: {conflicts}")
    out: list[SubagentRun] = []
    for wave in waves:
        for verdict in swarm.run_wave(build_agent, wave, log=log, root=root):
            _, step_id = verdict.task_id.split(":", 1)
            run = SubagentRun(
                objective=objective.id,
                step=step_id,
                task_id=verdict.task_id,
                route=verdict.agent,
                accepted=verdict.accepted,
                wall_s=verdict.wall_s,
                files=tuple(verdict.files),
                reasons=tuple(verdict.reasons),
            )
            record_run(root, run)
            out.append(run)
    return out


def preview(objective: Objective, plan: IntentPlanProposal, root: Path) -> list[dict[str, Any]]:
    """What `dispatch_plan` would dispatch, without dispatching it -- what the UI shows before a user commits."""
    out: list[dict[str, Any]] = []
    for task in tasks_from_plan(objective, plan, root=root):
        agent, model = task.route()
        _, step_id = task.spec.task_id.split(":", 1)
        out.append({
            "objective": objective.id,
            "step": step_id,
            "task_id": task.spec.task_id,
            "tier": task.tier,
            "agent": agent,
            "model": model,
            "allowed_paths": list(task.spec.allowed_paths),
            "validate": task.spec.validate,
            "why": task.why,
        })
    return out


__all__ = ["SubagentRun", "tasks_from_plan", "dispatch_plan", "preview", "record_run", "runs", "runs_path"]
