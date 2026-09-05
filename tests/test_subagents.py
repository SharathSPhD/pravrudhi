"""Turning an intent plan into dispatched subagent work, safely and as proposals only."""

from __future__ import annotations

from pravrudhi.application.intent import IntentPlanProposal, IntentStepProposal, SuccessCheckProposal
from pravrudhi.application.objectives import Benchmark, Objective
from pravrudhi.application.subagents import SubagentRun, dispatch_plan, preview, record_run, runs, tasks_from_plan

OBJECTIVE = Objective(
    id="legal-domain",
    intent="Improve legal-domain QA accuracy without losing general ability.",
    track="model",
    benchmarks=(Benchmark(id="b1", tool="lm-eval", metric="legal_qa_acc"),),
)


def _step(ident: str, capability: str, recipe_ids: tuple[str, ...] = ("r1",)) -> IntentStepProposal:
    return IntentStepProposal(
        id=ident,
        capability=capability,  # type: ignore[arg-type]
        recipe_ids=recipe_ids,
        available_recipe_ids=recipe_ids,
        availability="available",
        consumes=("objective",),
        produces=("x",),
        check=SuccessCheckProposal("Check the candidate against a held-out set."),
        quantities=(),
        reason="required by the plan",
    )


def _plan(*steps: IntentStepProposal) -> IntentPlanProposal:
    return IntentPlanProposal(
        objective=OBJECTIVE,
        steps=steps,
        external_inputs=(),
        unknown_recipe_ids=(),
        assumptions=(),
        review_required=(),
    )


PLAN = _plan(_step("corpus", "corpus"), _step("finetune", "finetune"), _step("candidate-evaluation", "evaluate"))


def test_one_task_per_step_in_plan_order(tmp_path):
    tasks = tasks_from_plan(OBJECTIVE, PLAN, root=tmp_path)
    assert [t.spec.task_id.split(":", 1)[1] for t in tasks] == ["corpus", "finetune", "candidate-evaluation"]


def test_allowed_paths_are_scoped_to_a_scratch_directory_and_never_touch_protected_paths(tmp_path):
    tasks = tasks_from_plan(OBJECTIVE, PLAN, root=tmp_path)
    for task in tasks:
        for pattern in task.spec.allowed_paths:
            assert pattern.startswith(f".pravrudhi/subagents/{OBJECTIVE.id}/")
            assert not pattern.startswith(("research/", "gates/", "pravrudhi_kernel/"))


def test_tiers_map_from_capability_as_specified(tmp_path):
    plan = _plan(
        _step("corpus", "corpus"),
        _step("finetune", "finetune"),
        _step("rl", "rl"),
        _step("candidate-evaluation", "evaluate"),
        _step("pretrain", "pretrain"),
        _step("performance", "performance"),
        _step("retrieval", "retrieval"),
        _step("safety", "safety"),
        _step("agents", "agents"),
    )
    tiers = {t.spec.task_id.split(":", 1)[1]: t.tier for t in tasks_from_plan(OBJECTIVE, plan, root=tmp_path)}
    assert tiers["corpus"] == "standard"
    assert tiers["candidate-evaluation"] == "standard"
    assert tiers["finetune"] == "design"
    assert tiers["rl"] == "design"
    for touching_gates in ("pretrain", "performance", "retrieval", "safety", "agents"):
        assert tiers[touching_gates] == "critical"


class OkAgent:
    """A fake agent that always produces an accepted-shaped diff. See tests/test_swarm.py's OkAgent."""

    name = "fake"

    def __init__(self, files):
        self.files = files

    def create_workspace(self, task_id, base_ref="HEAD"):
        import tempfile
        from pathlib import Path

        return Path(tempfile.mkdtemp())

    def run(self, prompt, workspace, timeout_s=60):
        from pravrudhi.agents.base import AgentRun

        return AgentRun(agent=self.name, ok=True, exit_code=0, wall_s=0.1, text="", workspace=workspace)

    def collect_changes(self, workspace):
        from pravrudhi.agents.base import Diff

        return Diff(files=list(self.files))


def test_dispatch_plan_records_one_run_per_task_and_returns_them(tmp_path):
    results = dispatch_plan(
        OBJECTIVE, PLAN, root=tmp_path, build_agent=lambda name, model: OkAgent(["x.py"]), log=lambda s: None,
    )
    assert len(results) == len(PLAN.steps)
    assert all(isinstance(r, SubagentRun) for r in results)
    assert {r.step for r in results} == {"corpus", "finetune", "candidate-evaluation"}
    assert all(r.objective == OBJECTIVE.id for r in results)

    on_disk = runs(tmp_path, objective=OBJECTIVE.id)
    assert len(on_disk) == len(PLAN.steps)
    assert {r.task_id for r in on_disk} == {r.task_id for r in results}


def test_runs_round_trip_and_filter_by_objective(tmp_path):
    run = SubagentRun(
        objective="obj-a", step="corpus", task_id="obj-a:corpus", route="fake",
        accepted=True, wall_s=1.5, files=("a.py",), reasons=(),
    )
    record_run(tmp_path, run)

    got = runs(tmp_path)
    assert len(got) == 1
    assert got[0].objective == "obj-a"
    assert got[0].step == "corpus"
    assert got[0].task_id == "obj-a:corpus"
    assert got[0].route == "fake"
    assert got[0].accepted is True
    assert got[0].files == ("a.py",)
    assert got[0].at  # filled in by record_run

    assert runs(tmp_path, objective="obj-a") == got
    assert runs(tmp_path, objective="obj-b") == []


def test_preview_shows_what_would_dispatch_without_creating_the_runs_file(tmp_path):
    items = preview(OBJECTIVE, PLAN, tmp_path)
    assert len(items) == len(PLAN.steps)
    assert {i["step"] for i in items} == {"corpus", "finetune", "candidate-evaluation"}
    for item in items:
        assert item["objective"] == OBJECTIVE.id
        assert item["tier"] in {"standard", "design", "critical"}
        assert item["allowed_paths"]

    assert not (tmp_path / ".pravrudhi" / "subagents" / "runs.jsonl").exists()
