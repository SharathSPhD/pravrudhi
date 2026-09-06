"""Self-build plans: the kernel/evidence refusal, tier mapping, preview side-effects, and run recording."""

from __future__ import annotations

import pytest
import yaml

from pravrudhi.application.selfbuild import (
    PACKAGED_EXAMPLE,
    BuildRun,
    SelfBuildError,
    load_plan,
    preview,
    record_run,
    run_plan,
    runs,
    runs_path,
)


def _write_plan(tmp_path, tasks):
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump({"tasks": tasks}))
    return path


def test_the_packaged_example_loads_and_is_harmless():
    tasks = load_plan(PACKAGED_EXAMPLE)
    assert len(tasks) == 2
    for t in tasks:
        for pattern in t.spec.allowed_paths:
            assert not pattern.startswith(("pravrudhi_kernel/", "research/", "gates/", ".pravrudhi/"))


def test_a_plan_naming_the_kernel_is_refused_with_that_path_in_the_message(tmp_path):
    path = _write_plan(
        tmp_path,
        [{"id": "sneaky", "prompt": "p", "allowed_paths": ["pravrudhi_kernel/stats.py"]}],
    )
    with pytest.raises(SelfBuildError) as e:
        load_plan(path)
    assert "pravrudhi_kernel/stats.py" in str(e.value)


def test_a_plan_naming_research_gates_or_dotpravrudhi_is_also_refused(tmp_path):
    for protected in ("research/ledger.jsonl", "gates/L1.json", ".pravrudhi/routing.jsonl"):
        path = _write_plan(tmp_path, [{"id": "sneaky", "prompt": "p", "allowed_paths": [protected]}])
        with pytest.raises(SelfBuildError) as e:
            load_plan(path)
        assert protected in str(e.value), protected


def test_tiers_map_from_the_declared_field_with_standard_as_default(tmp_path):
    path = _write_plan(
        tmp_path,
        [
            {"id": "a", "prompt": "p", "allowed_paths": ["src/a.py"], "tier": "mechanical"},
            {"id": "b", "prompt": "p", "allowed_paths": ["src/b.py"], "tier": "critical"},
            {"id": "c", "prompt": "p", "allowed_paths": ["src/c.py"]},
        ],
    )
    tiers = {t.spec.task_id: t.tier for t in load_plan(path)}
    assert tiers == {"a": "mechanical", "b": "critical", "c": "standard"}


def test_preview_shows_what_would_dispatch_without_writing_anything(tmp_path):
    tasks = load_plan(PACKAGED_EXAMPLE)
    items = preview(tasks, tmp_path)
    assert len(items) == len(tasks)
    for item in items:
        assert item["tier"] in {"mechanical", "standard", "design", "critical"}
        assert item["allowed_paths"]
        assert item["agent"]

    assert not runs_path(tmp_path).exists()
    assert list(tmp_path.iterdir()) == []


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


def test_run_plan_records_one_run_per_task(tmp_path):
    tasks = load_plan(PACKAGED_EXAMPLE)
    results = run_plan(tmp_path, tasks, build_agent=lambda name, model: OkAgent(["x.py"]), log=lambda s: None)

    assert len(results) == len(tasks)
    assert all(isinstance(r, BuildRun) for r in results)
    assert {r.task_id for r in results} == {t.spec.task_id for t in tasks}

    on_disk = runs(tmp_path)
    assert len(on_disk) == len(tasks)
    assert {r.task_id for r in on_disk} == {r.task_id for r in results}


def test_runs_round_trip(tmp_path):
    run = BuildRun(task_id="x", route="fake", accepted=True, wall_s=1.5, files=("a.py",), reasons=())
    record_run(tmp_path, run)

    got = runs(tmp_path)
    assert len(got) == 1
    assert got[0].task_id == "x"
    assert got[0].route == "fake"
    assert got[0].accepted is True
    assert got[0].files == ("a.py",)
    assert got[0].at  # filled in by record_run
