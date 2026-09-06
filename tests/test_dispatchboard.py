"""The dispatch board: an ad hoc brief queued, run through the swarm, and recorded -- or refused outright."""

from __future__ import annotations

import time

import pytest

from pravrudhi.application.dispatchboard import DispatchError, cancel, get, jobs, run_next, submit


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


def _build_agent(files):
    return lambda name, model: OkAgent(files)


def _wait_for_terminal(root, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = get(root, job_id)
        if job is not None and job.state in ("accepted", "rejected"):
            return job
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach a terminal state within {timeout}s")


def test_a_job_runs_and_records_its_verdict(tmp_path):
    job = submit(
        tmp_path,
        title="write a note",
        brief="write proposals/x/README.md",
        allowed_paths=("proposals/x/*",),
        validate="true",
        tier="mechanical",
        agent="fake",
    )
    assert job.state == "queued"

    started = run_next(tmp_path, _build_agent(["proposals/x/README.md"]), log=lambda s: None)
    assert started is not None
    assert started.id == job.id
    assert started.state == "running"

    finished = _wait_for_terminal(tmp_path, job.id)
    assert finished.accepted is True
    assert finished.route == "fake"
    assert finished.files == ("proposals/x/README.md",)
    assert finished.reasons == ()
    assert finished.ended

    # The job is exactly what jobs() lists, not a second untracked copy.
    assert [j.id for j in jobs(tmp_path, 10)] == [job.id]


def test_a_path_escaping_the_workspace_is_refused_and_named(tmp_path):
    with pytest.raises(DispatchError) as excinfo:
        submit(
            tmp_path,
            title="bad",
            brief="do something",
            allowed_paths=("proposals/../../etc/passwd",),
            validate="true",
            tier="mechanical",
        )
    assert "proposals/../../etc/passwd" in str(excinfo.value)
    assert jobs(tmp_path, 10) == []


def test_a_brief_with_no_allowed_paths_is_refused(tmp_path):
    with pytest.raises(DispatchError):
        submit(tmp_path, title="bad", brief="do something", allowed_paths=(), validate="true", tier="mechanical")


def test_the_queue_cap_refuses_the_twenty_first_job(tmp_path):
    for i in range(20):
        submit(
            tmp_path,
            title=f"job {i}",
            brief="do something",
            allowed_paths=(f"proposals/q{i}/*",),
            validate="true",
            tier="mechanical",
        )
    assert len(jobs(tmp_path, 100)) == 20

    with pytest.raises(DispatchError):
        submit(
            tmp_path,
            title="one too many",
            brief="do something",
            allowed_paths=("proposals/q20/*",),
            validate="true",
            tier="mechanical",
        )
    assert len(jobs(tmp_path, 100)) == 20


def test_cancel_stops_a_queued_job(tmp_path):
    job = submit(
        tmp_path,
        title="cancel me",
        brief="do something",
        allowed_paths=("proposals/c/*",),
        validate="true",
        tier="mechanical",
    )

    cancelled = cancel(tmp_path, job.id)
    assert cancelled.state == "cancelled"
    assert cancelled.ended

    on_disk = get(tmp_path, job.id)
    assert on_disk is not None
    assert on_disk.state == "cancelled"

    # A cancelled job is never picked up by run_next.
    assert run_next(tmp_path, _build_agent([]), log=lambda s: None) is None


def test_cancel_of_a_finished_job_is_a_no_op(tmp_path):
    job = submit(
        tmp_path,
        title="finish me",
        brief="write proposals/y/README.md",
        allowed_paths=("proposals/y/*",),
        validate="true",
        tier="mechanical",
        agent="fake",
    )
    run_next(tmp_path, _build_agent(["proposals/y/README.md"]), log=lambda s: None)
    finished = _wait_for_terminal(tmp_path, job.id)
    assert finished.state == "accepted"

    unchanged = cancel(tmp_path, job.id)
    assert unchanged.state == "accepted"
