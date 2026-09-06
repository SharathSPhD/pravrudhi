"""Publishing must refuse rather than half-complete.

Each of these cases actually happened. A page shipped before the snapshot carried its data and rendered "this
recording predates the requests log" on the public site while working against a live engine. A build succeeded
and the commit went out unpushed, so the deployment that rebuilds on push never ran. The order of the steps and
the refusals are the lesson, so they are what is tested.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from pravrudhi.application.publish import (
    CHECK_PAGES,
    build_interface,
    export_snapshot,
    publish,
    verify_pages,
)


def _ok(cmd: list[str], out: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")


def _fail(cmd: list[str], err: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=err)


def _is(cmd: list[str], sub: str) -> bool:
    """A git subcommand, ignoring the -c identity flags the house rules require before it."""
    return cmd[:1] == ["git"] and sub in cmd


def _workspace(tmp_path: Path, *, snapshot: dict[str, Any] | None = None, pages: dict[str, str] | None = None) -> Path:
    fe = tmp_path / "app" / "frontend"
    (fe / "public").mkdir(parents=True)
    (fe / "package.json").write_text('{"name": "x"}')
    (fe / "public" / "demo.json").write_text(json.dumps(snapshot if snapshot is not None else {"requests": {}}))
    out = fe / "out"
    out.mkdir()
    for page in CHECK_PAGES:
        name = "index.html" if page == "/" else f"{page.strip('/')}.html"
        (out / name).write_text((pages or {}).get(page, "<html>real content</html>"))
    return tmp_path


class TestTheStepsRunInOrder:
    def test_nothing_is_committed_when_the_export_fails(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path)
        seen: list[list[str]] = []

        def runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            seen.append(cmd)
            return _fail(cmd, "ledger unreadable") if "demo-export" in cmd else _ok(cmd)

        result = publish(root, runner=runner)
        assert not result.published
        assert "export failed" in result.reason
        assert not any(_is(c, "commit") for c in seen), "a stale snapshot must never be committed"

    def test_nothing_is_pushed_when_the_build_fails(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path)
        seen: list[list[str]] = []

        def runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            seen.append(cmd)
            return _fail(cmd, "Type error in page.tsx") if cmd[-1] == "build" else _ok(cmd)

        result = publish(root, runner=runner)
        assert not result.published and "build failed" in result.reason
        assert not any(_is(c, "push") for c in seen)

    def test_the_snapshot_is_exported_before_the_interface_is_built(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path)
        order: list[str] = []

        def runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            if "demo-export" in cmd:
                order.append("export")
            if cmd[-1] == "build":
                order.append("build")
            if _is(cmd, "commit"):
                order.append("commit")
            if _is(cmd, "push"):
                order.append("push")
            if cmd[:3] == ["git", "diff", "--cached"]:
                return _ok(cmd, "app/frontend/public/demo.json\n")
            return _ok(cmd, "abc1234")

        publish(root, runner=runner)
        assert order == ["export", "build", "commit", "push"], order


class TestARenderedErrorStopsThePublish:
    def test_a_page_showing_a_stale_recording_notice_is_a_failure(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path, pages={"/requests": "<html>This recording predates the requests log.</html>"})
        seen: list[list[str]] = []

        def runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            seen.append(cmd)
            return _ok(cmd)

        result = publish(root, runner=runner)
        assert not result.published
        assert "predates" in result.reason and "/requests" in result.reason
        assert not any(_is(c, "push") for c in seen)

    def test_a_page_that_cannot_reach_the_engine_is_a_failure(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path, pages={"/swarm": "<html>Could not reach the engine's swarm API.</html>"})
        step = verify_pages(root)
        assert not step.ok and "/swarm" in step.detail

    def test_a_page_that_was_never_built_is_a_failure(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path)
        (root / "app" / "frontend" / "out" / "candidates.html").unlink()
        step = verify_pages(root)
        assert not step.ok and "candidates" in step.detail

    def test_pages_carrying_content_pass(self, tmp_path: Path) -> None:
        step = verify_pages(_workspace(tmp_path))
        assert step.ok and str(len(CHECK_PAGES)) in step.detail


class TestSteps:
    def test_the_export_reports_what_the_snapshot_contains(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path, snapshot={"requests": {}, "candidates": [], "inbox": []})
        step = export_snapshot(root, lambda cmd, cwd: _ok(cmd))
        assert step.ok and "candidates" in step.detail

    def test_an_unreadable_snapshot_fails_the_export(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path)
        (root / "app" / "frontend" / "public" / "demo.json").write_text("{not json")
        step = export_snapshot(root, lambda cmd, cwd: _ok(cmd))
        assert not step.ok and "unreadable" in step.detail

    def test_the_local_bundle_is_built_without_a_base_path(self, tmp_path: Path) -> None:
        """A sub-path baked into the bundle the engine serves at its own root breaks every asset."""
        root = _workspace(tmp_path)
        seen: list[list[str]] = []

        def runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            seen.append(cmd)
            return _ok(cmd)

        assert build_interface(root, runner).ok
        assert seen[0][0] == "npm", seen[0]

        seen.clear()
        assert build_interface(root, runner, base_path="/pravrudhi/app").ok
        assert "NEXT_PUBLIC_BASE_PATH=/pravrudhi/app" in seen[0]

    def test_publishing_can_stop_before_the_push(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path)
        seen: list[list[str]] = []

        def runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            seen.append(cmd)
            if cmd[:3] == ["git", "diff", "--cached"]:
                return _ok(cmd, "app/frontend/public/demo.json\n")
            return _ok(cmd, "abc1234")

        result = publish(root, runner=runner, do_push=False)
        assert result.published and "not pushed" in result.reason
        assert not any(_is(c, "push") for c in seen)

    def test_an_unchanged_snapshot_is_not_an_error(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path)

        def runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
            return _ok(cmd, "")  # `git diff --cached` reports nothing staged

        result = publish(root, runner=runner)
        assert result.published, result.reason
