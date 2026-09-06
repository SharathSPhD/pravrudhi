"""The heartbeat: one wake-up finds the most-neglected undone step across every objective and dispatches it."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

from pravrudhi.agents.base import AgentRun, Diff
from pravrudhi.application.heartbeat import beat, history, load_config, log_path
from pravrudhi.application.objectives import Benchmark, Objective
from pravrudhi.application.objectives import write as write_objective
from pravrudhi.application.subagents import SubagentRun, record_run, runs
from pravrudhi_kernel.schema import LedgerEvent


def make_objective(oid: str, *, domain: str = "") -> Objective:
    return Objective(
        id=oid,
        intent=f"Improve {oid}.",
        track="model",
        benchmarks=(Benchmark(id="b1", tool="lm-eval", metric=f"{oid}_acc"),),
        domain=domain,
    )


def make_event(seq: int, night: int, payload: dict[str, object], kind: str = "audit") -> str:
    ev = LedgerEvent(
        seq=seq, t="2026-01-01T00:00:00.000Z", epoch=0, night=night, cycle=None, kind=kind,  # type: ignore[arg-type]
        actor="kernel", candidate_id=None, surface=None, bucket=None, provenance=None, kernel_release="0.1.0",
        payload=payload, prev_hash="0" * 64, this_hash="0" * 64,
    )
    return ev.model_dump_json()


def write_ledger(root: Path, lines: list[str]) -> None:
    ledger = root / "research" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_config(root: Path, **overrides: object) -> None:
    path = root / ".pravrudhi" / "heartbeat.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    base = {"interval_min": 60, "max_dispatch_per_beat": 1, "quiet_hours": [], "allow_gpu": False}
    base.update(overrides)
    path.write_text(yaml.safe_dump(base), encoding="utf-8")


class OkAgent:
    """A fake agent that always produces an accepted-shaped diff. See tests/test_subagents.py's OkAgent."""

    name = "fake"

    def __init__(self, files: list[str]):
        self.files = files

    def create_workspace(self, task_id: str, base_ref: str = "HEAD") -> Path:
        return Path(tempfile.mkdtemp())

    def run(self, prompt: str, workspace: Path, timeout_s: int = 60) -> AgentRun:
        return AgentRun(agent=self.name, ok=True, exit_code=0, wall_s=0.1, text="", workspace=workspace)

    def collect_changes(self, workspace: Path) -> Diff:
        return Diff(files=list(self.files))


def ok_dispatch(name: str, model: str | None) -> OkAgent:
    # A path under the real scratch directory a step's task declares (application/subagents.py's `_scratch_dir`),
    # so `TaskSpec.owns` accepts it and this fake agent's "work" is judged in scope rather than rejected as stray.
    return OkAgent(["proposals/obj-a/baseline-evaluation/README.md"])


def test_load_config_falls_back_to_packaged_defaults(tmp_path):
    config = load_config(tmp_path)
    assert config == load_config(tmp_path)
    assert config.interval_min == 60
    assert config.max_dispatch_per_beat == 1
    assert config.quiet_hours == ()
    assert config.allow_gpu is False


def test_no_objectives_is_a_recorded_no_op(tmp_path):
    record = beat(tmp_path, dispatch=ok_dispatch)
    assert record.chose is None
    assert record.result is None
    assert "no objectives" in record.reason
    assert record.looked_at == ()

    logged = history(tmp_path, 10)
    assert len(logged) == 1
    assert logged[0].reason == record.reason
    assert log_path(tmp_path).exists()


def test_quiet_hours_yield_a_no_op_with_the_reason(tmp_path):
    write_objective(tmp_path, make_objective("obj-a"))
    set_config(tmp_path, quiet_hours=[3])

    record = beat(tmp_path, dispatch=ok_dispatch, now=datetime(2026, 1, 1, 3, 30, tzinfo=UTC))

    assert record.chose is None
    assert record.result is None
    assert "quiet hours" in record.reason
    assert record.looked_at == ()
    assert runs(tmp_path) == []


def test_dispatches_the_next_undone_step_and_records_an_accepted_run(tmp_path):
    write_objective(tmp_path, make_objective("obj-a"))

    record = beat(tmp_path, dispatch=ok_dispatch, now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

    assert record.chose == {"objective": "obj-a", "step": "baseline-evaluation"}
    assert record.result is not None
    assert record.result["accepted"] is True
    assert "dispatched obj-a:baseline-evaluation" in record.reason

    on_disk = runs(tmp_path, objective="obj-a")
    assert len(on_disk) == 1
    assert on_disk[0].step == "baseline-evaluation"
    assert on_disk[0].accepted is True


def test_picks_the_stalest_objective(tmp_path):
    write_objective(tmp_path, make_objective("obj-old"))
    write_objective(tmp_path, make_objective("obj-new"))

    # Both objectives already have their baseline step accepted, so each one's next undone step is
    # candidate-evaluation; obj-old was dispatched long ago and obj-new only just now, so the stale one wins.
    record_run(tmp_path, SubagentRun(
        objective="obj-old", step="baseline-evaluation", task_id="obj-old:baseline-evaluation", route="fake",
        accepted=True, wall_s=1.0, at="2020-01-01T00:00:00Z",
    ))
    record_run(tmp_path, SubagentRun(
        objective="obj-new", step="baseline-evaluation", task_id="obj-new:baseline-evaluation", route="fake",
        accepted=True, wall_s=1.0, at="2030-01-01T00:00:00Z",
    ))

    record = beat(tmp_path, dispatch=ok_dispatch, now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

    assert record.chose == {"objective": "obj-old", "step": "candidate-evaluation"}


def test_honours_max_dispatch_per_beat(tmp_path):
    write_objective(tmp_path, make_objective("obj-a"))
    set_config(tmp_path, max_dispatch_per_beat=0)

    record = beat(tmp_path, dispatch=ok_dispatch, now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

    assert record.chose == {"objective": "obj-a", "step": "baseline-evaluation"}
    assert record.result is None
    assert "max_dispatch_per_beat" in record.reason
    assert runs(tmp_path) == []


def test_skips_gpu_steps_while_a_run_is_in_progress(tmp_path):
    objective = make_objective("legal-domain", domain="legal-domain")
    write_objective(tmp_path, objective)
    set_config(tmp_path, allow_gpu=True)

    # Fast-forward past the evaluate/corpus steps so the next undone step is the finetune step, which needs the GPU.
    for step_id in ("baseline-evaluation", "corpus"):
        record_run(tmp_path, SubagentRun(
            objective=objective.id, step=step_id, task_id=f"{objective.id}:{step_id}", route="fake",
            accepted=True, wall_s=1.0,
        ))
    write_ledger(tmp_path, [make_event(1, 1, {"kind": "night_start", "track": "model"})])

    record = beat(tmp_path, dispatch=ok_dispatch, now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

    assert record.chose == {"objective": objective.id, "step": "finetune"}
    assert record.result is None
    assert "GPU" in record.reason and "in progress" in record.reason
    assert len(runs(tmp_path, objective=objective.id)) == 2
