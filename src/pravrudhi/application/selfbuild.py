"""Pravrudhi's own swarm has been driven from ad-hoc scripts in a scratch directory: a developer holding a
Python shell would write a one-off list of tasks, wire up an agent factory by hand, and throw the result away
once the change landed. Nothing about that path was part of the product, so the engine could not turn its own
swarm on itself except through someone else's private tooling.

This module is that missing capability, built on the same primitives `application/subagents.py` uses to turn an
objective's plan into dispatched work: a self-build task is declared in YAML rather than assembled from an
`IntentPlanProposal`, but it is planned, routed, dispatched and recorded exactly the way a proposal step is.

The one rule that matters is the refusal `load_plan` enforces: a self-build task may improve the engine's own
source, tests and assets, but it may never claim a path under `pravrudhi_kernel/`, `research/`, `gates/` or
`.pravrudhi/`. Those are respectively the kernel a self-build task is not qualified to grade itself against, and
the evidence and operational state that record what the engine has already done. An engine that could edit the
ground it is judged against could rewrite its own report card, so that path is refused before anything is
dispatched, not caught afterward in a diff.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from pravrudhi.application import routing, swarm
from pravrudhi.application.delegate import TaskSpec

PACKAGED_EXAMPLE = Path(__file__).resolve().parents[1] / "assets" / "selfbuild" / "example.yaml"

# A self-build task may touch the engine's own source, tests, docs and assets. It may never claim a path under
# these: the kernel it would then be grading itself against, and the evidence and operational state that record
# what the engine has already done.
PROTECTED_PREFIXES: tuple[str, ...] = ("pravrudhi_kernel/", "research/", "gates/", ".pravrudhi/")


class SelfBuildError(ValueError):
    """A self-build plan that would let a task edit the kernel or the evidence it produces."""


@dataclass(frozen=True)
class BuildTask:
    """One task in a self-build plan, as declared in YAML."""

    id: str
    prompt: str
    allowed_paths: tuple[str, ...]
    validate: str = "uv run pytest -q"
    tier: str = "standard"
    why: str = ""

    def to_swarm_task(self) -> swarm.SwarmTask:
        spec = TaskSpec(task_id=self.id, prompt=self.prompt, allowed_paths=self.allowed_paths, validate=self.validate)
        return swarm.SwarmTask(spec, self.tier, why=self.why)


def _refuse_protected_paths(task_id: str, allowed_paths: tuple[str, ...]) -> None:
    for path in allowed_paths:
        hit = next((prefix for prefix in PROTECTED_PREFIXES if path.startswith(prefix)), None)
        if hit is not None:
            raise SelfBuildError(
                f"self-build task {task_id!r} claims {path!r}: a self-build task may not edit the kernel or the "
                f"evidence, so paths under {', '.join(PROTECTED_PREFIXES)} are refused"
            )


def load_plan(path: Path) -> list[swarm.SwarmTask]:
    """Load a self-build plan from YAML, refusing any task whose `allowed_paths` touch `pravrudhi_kernel/`,
    `research/`, `gates/` or `.pravrudhi/`. That refusal is the point of this module."""
    raw = yaml.safe_load(Path(path).read_text())
    tasks: list[swarm.SwarmTask] = []
    for row in raw.get("tasks", []):
        task_id = str(row["id"])
        allowed = tuple(str(p) for p in row["allowed_paths"])
        _refuse_protected_paths(task_id, allowed)
        build_task = BuildTask(
            id=task_id,
            prompt=str(row["prompt"]),
            allowed_paths=allowed,
            validate=str(row.get("validate", "uv run pytest -q")),
            tier=str(row.get("tier", "standard")),
            why=str(row.get("why", "")),
        )
        tasks.append(build_task.to_swarm_task())
    return tasks


@dataclass(frozen=True)
class BuildRun:
    """One dispatched self-build task and what the swarm's own verdict said about it."""

    task_id: str
    route: str
    accepted: bool
    wall_s: float
    files: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    at: str = ""


def runs_path(root: Path) -> Path:
    return Path(root) / ".pravrudhi" / "selfbuild" / "runs.jsonl"


def record_run(root: Path, run: BuildRun) -> None:
    """Append one run. Operational state, like `subagents.py`'s runs.jsonl: no evidence document may cite it."""
    p = runs_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = asdict(run)
    row["files"] = list(run.files)
    row["reasons"] = list(run.reasons)
    row["at"] = run.at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with p.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def runs(root: Path) -> list[BuildRun]:
    """Every recorded self-build run. A corrupt line is skipped, not fatal."""
    p = runs_path(root)
    if not p.exists():
        return []
    out: list[BuildRun] = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            out.append(
                BuildRun(
                    task_id=str(d["task_id"]),
                    route=str(d["route"]),
                    accepted=bool(d["accepted"]),
                    wall_s=float(d.get("wall_s", 0.0)),
                    files=tuple(d.get("files", ())),
                    reasons=tuple(d.get("reasons", ())),
                    at=str(d.get("at", "")),
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue  # a corrupt line must not blind the caller to the rest
    return out


def run_plan(root: Path, tasks: list[swarm.SwarmTask], *, build_agent: Any, log: Any = print) -> list[BuildRun]:
    """Dispatch every task through the swarm and record what came back.

    Waves are planned with `swarm.plan` so tasks whose declared paths could collide never run together, and each
    wave runs through `swarm.run_wave(root=root)` so the router learns from the outcome, exactly as
    `subagents.dispatch_plan` does for an objective's plan.
    """
    waves, conflicts = swarm.plan(tasks)
    if conflicts:
        log(f"selfbuild: {len(conflicts)} conflicting task pair(s) deferred to a later wave: {conflicts}")
    out: list[BuildRun] = []
    for wave in waves:
        for verdict in swarm.run_wave(build_agent, wave, log=log, root=root):
            run = BuildRun(
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


def preview(tasks: list[swarm.SwarmTask], root: Path) -> list[dict[str, Any]]:
    """What `run_plan` would dispatch, without dispatching it."""
    out: list[dict[str, Any]] = []
    table = None
    rows: list[routing.Outcome] = []
    try:  # the router's choice, from measured outcomes, so the preview matches what run_plan would do
        table, rows = routing.load_table(), routing.outcomes(root)
    except (OSError, routing.RoutingError):
        table = None
    for task in tasks:
        agent: str
        model: str | None
        if table is not None:
            agent, model = routing.choose(table, rows, task.tier).route.pair()
        else:
            agent, model = task.route()
        out.append(
            {
                "task_id": task.spec.task_id,
                "tier": task.tier,
                "agent": agent,
                "model": model,
                "allowed_paths": list(task.spec.allowed_paths),
                "validate": task.spec.validate,
                "why": task.why,
            }
        )
    return out


__all__ = [
    "SelfBuildError",
    "BuildTask",
    "BuildRun",
    "PROTECTED_PREFIXES",
    "PACKAGED_EXAMPLE",
    "load_plan",
    "run_plan",
    "preview",
    "record_run",
    "runs",
    "runs_path",
]
