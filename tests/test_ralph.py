"""An agent must not be able to end a task by saying it is finished.

Half the defects that reached this project's operator were reported as complete by whoever built them: a page that
answered 200 while rendering an error, a scheduler wired to a flag the installed engine did not have, a table whose
every cell was a dash. The loop exists so that nothing an agent writes can close a task.
"""

from __future__ import annotations

import json
from pathlib import Path

from pravrudhi.application.ralph import (
    RALPH_PREAMBLE,
    attempts,
    command_verifier,
    log_path,
    run_until_done,
)


def _dispatcher(record: list[str], *, accepted: bool = True) -> object:
    def dispatch_once(brief: str) -> tuple[bool, str, float]:
        record.append(brief)
        return accepted, "agent finished", 1.0
    return dispatch_once


class TestTheAgentCannotDeclareVictory:
    def test_a_confident_summary_does_not_close_the_task(self, tmp_path: Path) -> None:
        def dispatch_once(brief: str) -> tuple[bool, str, float]:
            return True, "COMPLETION PROMISE SATISFIED. All features implemented and working.", 1.0

        result = run_until_done(
            dispatch_once, root=tmp_path, task_id="t", brief="do the thing",
            promise="the tests pass", verify=lambda _: (False, "2 failed"),
            max_iterations=2, log=lambda _: None,
        )
        assert not result.passed
        assert result.iterations == 2, "the loop must not stop because the agent claimed success"

    def test_the_external_check_alone_decides(self, tmp_path: Path) -> None:
        def dispatch_once(brief: str) -> tuple[bool, str, float]:
            return False, "agent exited non-zero", 1.0

        result = run_until_done(
            dispatch_once, root=tmp_path, task_id="t", brief="do the thing",
            promise="the file exists", verify=lambda _: (True, "found it"),
            max_iterations=3, log=lambda _: None,
        )
        assert result.passed and result.iterations == 1, "a rejected agent that produced passing work is done"


class TestTheSameBriefComesBack:
    def test_a_failing_check_re_dispatches_the_identical_brief(self, tmp_path: Path) -> None:
        seen: list[str] = []
        run_until_done(
            _dispatcher(seen), root=tmp_path, task_id="t", brief="build the desktop app",
            promise="node --test passes", verify=lambda _: (False, "1 failing"),
            max_iterations=3, log=lambda _: None,
        )
        assert len(seen) == 3
        assert len(set(seen)) == 1, "the brief must not drift between iterations"
        assert "build the desktop app" in seen[0]

    def test_the_promise_is_stated_in_the_brief_the_agent_receives(self, tmp_path: Path) -> None:
        seen: list[str] = []
        run_until_done(
            _dispatcher(seen), root=tmp_path, task_id="t", brief="the work",
            promise="every end-to-end test passes against the running app",
            verify=lambda _: (True, ""), max_iterations=1, log=lambda _: None,
        )
        assert "every end-to-end test passes against the running app" in seen[0]
        assert "You do not decide when it is finished" in seen[0]

    def test_the_loop_stops_as_soon_as_the_check_passes(self, tmp_path: Path) -> None:
        seen: list[str] = []
        calls = {"n": 0}

        def verify(_: Path) -> tuple[bool, str]:
            calls["n"] += 1
            return calls["n"] >= 2, f"check {calls['n']}"

        result = run_until_done(
            _dispatcher(seen), root=tmp_path, task_id="t", brief="x", promise="p",
            verify=verify, max_iterations=5, log=lambda _: None,
        )
        assert result.passed and result.iterations == 2 and len(seen) == 2


class TestEveryAttemptIsRecorded:
    def test_five_failures_leave_five_pieces_of_evidence(self, tmp_path: Path) -> None:
        seen: list[str] = []
        run_until_done(
            _dispatcher(seen), root=tmp_path, task_id="desktop", brief="x",
            promise="the app launches", verify=lambda _: (False, "it did not launch"),
            max_iterations=5, log=lambda _: None,
        )
        rows = attempts(tmp_path)
        assert len(rows) == 5
        assert {r["task_id"] for r in rows} == {"desktop"}
        assert all(r["passed"] is False for r in rows)
        assert "it did not launch" in rows[-1]["detail"]

    def test_a_corrupt_log_line_is_skipped_not_fatal(self, tmp_path: Path) -> None:
        path = log_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text('{"task_id": "a", "passed": true}\n{not json\n')
        assert len(attempts(tmp_path)) == 1


class TestCommandVerifier:
    def test_a_zero_exit_keeps_the_promise(self, tmp_path: Path) -> None:
        ok, detail = command_verifier("true")(tmp_path)
        assert ok and detail == ""

    def test_a_non_zero_exit_breaks_it_and_keeps_the_output(self, tmp_path: Path) -> None:
        ok, detail = command_verifier("echo 'two tests failed' >&2; exit 1")(tmp_path)
        assert not ok and "two tests failed" in detail

    def test_the_check_runs_where_the_agent_wrote(self, tmp_path: Path) -> None:
        (tmp_path / "marker.txt").write_text("here")
        ok, _ = command_verifier("test -f marker.txt")(tmp_path)
        assert ok
        other = tmp_path / "elsewhere"
        other.mkdir()
        ok, _ = command_verifier("test -f marker.txt")(other)
        assert not ok, "checking the wrong tree would pass work that was never written"

    def test_a_hanging_check_fails_rather_than_blocking_forever(self, tmp_path: Path) -> None:
        ok, detail = command_verifier("sleep 5", timeout_s=1)(tmp_path)
        assert not ok and "did not finish" in detail


def test_the_preamble_never_invites_the_agent_to_self_certify() -> None:
    text = RALPH_PREAMBLE.format(promise="p")
    assert "checked by running a command" in text
    assert "Saying the work is complete has no effect" in text


def test_the_recorded_rows_are_json_one_per_line(tmp_path: Path) -> None:
    run_until_done(
        _dispatcher([]), root=tmp_path, task_id="t", brief="x", promise="p",
        verify=lambda _: (True, "ok"), max_iterations=1, log=lambda _: None,
    )
    lines = log_path(tmp_path).read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["passed"] is True
