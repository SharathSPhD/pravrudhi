"""Exercise readiness against real temporary installations, including incomplete and damaged state."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pravrudhi import KERNEL_VERSION
from pravrudhi.application.doctor import run_doctor
from pravrudhi.application.init import PACKAGED_PREREG
from pravrudhi_kernel.ledger import LedgerWriter
from pravrudhi_kernel.metrics import seal_pool


@pytest.fixture
def ready_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "project"
    (root / ".pravrudhi").mkdir(parents=True)
    (root / ".pravrudhi" / "config.yaml").write_text("version: 1\n")
    LedgerWriter.open(root / "research" / "ledger.jsonl", KERNEL_VERSION)
    shutil.copytree(PACKAGED_PREREG, root / "research" / "prereg")
    seal_pool(root / ".pravrudhi" / "kernel" / "pools" / "test", "test", [{"question": "1+1", "answer": "2"}], {})
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text("#!/bin/sh\nexit 0\n")
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    return root


def test_uninitialised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("PATH", "")
    report = run_doctor(tmp_path)
    assert report["ok"] is False
    assert {check["name"] for check in report["checks"]} == {"initialised", "ledger", "docker", "pools", "prereg"}
    for check in report["checks"]:
        assert set(check) == {"name", "ok", "detail"}
        assert check["ok"] is False
        assert isinstance(check["detail"], str) and check["detail"]
    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr() == ("", "")


def test_initialised(ready_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    before = {p.relative_to(ready_root): p.read_bytes() for p in ready_root.rglob("*") if p.is_file()}
    report = run_doctor(ready_root)
    assert report["ok"] is True
    assert len(report["checks"]) == 5
    assert all(check["ok"] is True and check["detail"] for check in report["checks"])
    assert before == {p.relative_to(ready_root): p.read_bytes() for p in ready_root.rglob("*") if p.is_file()}
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(("path", "failed"), [
    (".pravrudhi/config.yaml", {"initialised"}),
    ("research/ledger.jsonl", {"initialised", "ledger"}),
    (".pravrudhi/kernel/pools/test/manifest.json", {"pools"}),
    ("research/prereg/controller.yaml", {"prereg"}),
])
def test_missing_file(ready_root: Path, path: str, failed: set[str]) -> None:
    (ready_root / path).unlink()
    report = run_doctor(ready_root)
    assert report["ok"] is False
    assert {check["name"] for check in report["checks"] if not check["ok"]} == failed


def test_missing_docker(ready_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")
    report = run_doctor(ready_root)
    assert report["ok"] is False
    assert [check["name"] for check in report["checks"] if not check["ok"]] == ["docker"]


@pytest.mark.parametrize("damage", ["tamper", "empty", "malformed", "encoding"])
def test_invalid_ledger(ready_root: Path, damage: str) -> None:
    ledger = ready_root / "research" / "ledger.jsonl"
    if damage == "tamper":
        event = json.loads(ledger.read_text())
        event["payload"]["kind"] = "changed"
        ledger.write_text(json.dumps(event) + "\n")
    else:
        ledger.write_bytes({"empty": b"", "malformed": b"not json\n", "encoding": b"\xff"}[damage])
    report = run_doctor(ready_root)
    assert report["ok"] is False
    failures = [check for check in report["checks"] if not check["ok"]]
    assert len(failures) == 1 and failures[0]["name"] == "ledger"
    if damage == "tamper":
        assert "this_hash mismatch" in failures[0]["detail"]
