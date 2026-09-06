"""Tests for the `build` and `update` CLI commands: preview side-effects, kernel refusal, version reporting."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from pravrudhi import __version__
from pravrudhi.application.selfbuild import PACKAGED_EXAMPLE
from pravrudhi.cli.app import app

runner = CliRunner()


def _invoke(*args: str) -> object:
    return runner.invoke(app, args)


def test_build_preview_lists_packaged_example_tasks_and_writes_nothing(tmp_path: Path) -> None:
    result = _invoke("build", str(PACKAGED_EXAMPLE), "--root", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert "selfbuild-example-readme-note" in result.stdout
    assert "selfbuild-example-test-docstring" in result.stdout
    assert "preview" in result.stdout
    assert not (tmp_path / ".pravrudhi").exists()


def test_build_plan_naming_the_kernel_exits_nonzero_naming_the_path(tmp_path: Path) -> None:
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        yaml.safe_dump(
            {
                "tasks": [
                    {"id": "sneaky", "prompt": "p", "allowed_paths": ["pravrudhi_kernel/stats.py"]},
                ]
            }
        )
    )

    result = _invoke("build", str(plan), "--root", str(tmp_path))
    assert result.exit_code != 0
    output = (result.stdout or "") + (result.stderr or "")
    assert "pravrudhi_kernel/stats.py" in output


def test_update_prints_the_current_version() -> None:
    result = _invoke("update")
    assert result.exit_code == 0, result.output
    assert __version__ in result.stdout
