"""Running several agents at once, continuously, without them colliding or overspending.

Delegation handles one task safely. A swarm is the same guarantees applied to many tasks in parallel, plus the
question delegation does not answer: which agent and which model should take this piece of work?

Routing is by tier, and the tiers are about difficulty rather than importance. Mechanical work goes to an
open-weight model on hardware already paid for; ordinary build work goes to a fast hosted agent; design work goes
to a stronger one; and the most capable model is reserved for the few tasks where being wrong is expensive, because
using it everywhere would be waste rather than diligence. A tier is a claim about the work, so it is recorded with
the result and can be argued with afterwards.

Parallelism is bounded by disjoint ownership rather than by a worker count: tasks run together only when their
declared paths cannot collide, which is checked before anything is dispatched rather than discovered in a merge.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pravrudhi.application.delegate import TaskSpec, Verdict, dispatch, overlapping

# tier -> (agent name, model or None for the agent's default). Cost rises with tier; so should difficulty.
ROUTES: dict[str, tuple[str, str | None]] = {
    "mechanical": ("orca:local", "glm-4.7-flash"),
    "standard": ("codex", None),
    "design": ("claude-code", "sonnet"),
    "critical": ("codex", "gpt-6-astra"),
}
TIERS = tuple(ROUTES)


@dataclass(frozen=True)
class SwarmTask:
    spec: TaskSpec
    tier: str = "standard"
    why: str = ""

    def route(self) -> tuple[str, str | None]:
        if self.tier not in ROUTES:
            raise ValueError(f"unknown tier {self.tier!r}; expected one of {', '.join(TIERS)}")
        return ROUTES[self.tier]


def plan(tasks: list[SwarmTask]) -> tuple[list[list[SwarmTask]], list[tuple[str, str]]]:
    """Group tasks into waves that can run together.

    A wave holds tasks whose declared paths are provably disjoint. Anything that conflicts is deferred to a later
    wave rather than dropped, so a conflict costs sequencing rather than work.
    """
    remaining = list(tasks)
    waves: list[list[SwarmTask]] = []
    conflicts: list[tuple[str, str]] = []
    while remaining:
        wave: list[SwarmTask] = []
        deferred: list[SwarmTask] = []
        for t in remaining:
            clash = overlapping([w.spec for w in wave] + [t.spec])
            if clash and any(t.spec.task_id in pair for pair in clash):
                deferred.append(t)
                conflicts.extend(pair for pair in clash if t.spec.task_id in pair)
            else:
                wave.append(t)
        waves.append(wave)
        if len(deferred) == len(remaining):  # nothing could be scheduled; stop rather than spin
            waves.append(deferred)
            break
        remaining = deferred
    return [w for w in waves if w], sorted(set(conflicts))


def run_wave(build_agent: Any, wave: list[SwarmTask], *, log: Any = print) -> list[Verdict]:
    """Dispatch one wave in parallel. Each task gets its own agent instance and its own worktree."""
    results: list[Verdict] = []
    with ThreadPoolExecutor(max_workers=max(1, len(wave))) as pool:
        futures = {}
        for t in wave:
            agent_name, model = t.route()
            agent = build_agent(agent_name, model)
            if agent is None:
                results.append(
                    Verdict(task_id=t.spec.task_id, agent=agent_name, accepted=False,
                            reasons=[f"no agent available for tier {t.tier} ({agent_name})"])
                )
                continue
            log(f"dispatch {t.spec.task_id} -> {agent.name} [{t.tier}]{' ' + t.why if t.why else ''}")
            futures[pool.submit(dispatch, agent, t.spec, log=log)] = t
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:  # an agent crashing must not take the wave with it
                results.append(
                    Verdict(task_id=t.spec.task_id, agent=t.route()[0], accepted=False, reasons=[f"dispatch raised: {e}"])
                )
    return results


def run_swarm(build_agent: Any, tasks: list[SwarmTask], *, log: Any = print) -> dict[str, Any]:
    waves, conflicts = plan(tasks)
    log(f"swarm: {len(tasks)} tasks in {len(waves)} wave(s); {len(conflicts)} conflict pair(s) deferred")
    verdicts: list[Verdict] = []
    for i, wave in enumerate(waves, 1):
        log(f"--- wave {i}: {', '.join(t.spec.task_id for t in wave)}")
        verdicts.extend(run_wave(build_agent, wave, log=log))
    accepted = [v for v in verdicts if v.accepted]
    log(f"swarm: {len(accepted)}/{len(verdicts)} accepted")
    return {
        "waves": len(waves),
        "conflicts": conflicts,
        "accepted": [v.to_dict() for v in accepted],
        "rejected": [v.to_dict() for v in verdicts if not v.accepted],
    }


def render_swarm(result: dict[str, Any]) -> str:
    lines = [f"swarm: {len(result['accepted'])} accepted, {len(result['rejected'])} rejected, {result['waves']} wave(s)"]
    for v in result["accepted"]:
        lines.append(f"  ok    {v['task_id']:16} {v['agent']:22} {len(v['files'])} file(s)  {v['wall_s']}s")
    for v in result["rejected"]:
        lines.append(f"  FAIL  {v['task_id']:16} {v['agent']:22} {'; '.join(v['reasons'])[:90]}")
    return "\n".join(lines)


__all__ = ["ROUTES", "TIERS", "SwarmTask", "plan", "run_wave", "run_swarm", "render_swarm", "TaskSpec", "json", "replace"]
