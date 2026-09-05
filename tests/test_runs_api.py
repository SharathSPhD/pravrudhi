"""Runs: a night started from the app is a supervised subprocess whose log becomes live events."""
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pravrudhi.api.runs import RunManager, RunRequest, parse_line
from pravrudhi.application.app_serve import build_app
from pravrudhi.application.init import init_project


@pytest.mark.parametrize("target, subcommand", [("model", "night"), ("harness", "harness-night")])
@pytest.mark.parametrize("override", [None, ""])
def test_command_uses_current_interpreter(tmp_path, monkeypatch, target, subcommand, override):
    monkeypatch.delenv("PRAVRUDHI_CLI", raising=False)
    if override is not None:
        monkeypatch.setenv("PRAVRUDHI_CLI", override)
    cmd = RunManager(tmp_path)._command(RunRequest(target=target), 1)
    assert cmd[:4] == [sys.executable, "-m", "pravrudhi", subcommand]


@pytest.mark.parametrize("target, subcommand", [("model", "night"), ("harness", "harness-night")])
def test_command_honours_cli_override(tmp_path, monkeypatch, target, subcommand):
    monkeypatch.setenv("PRAVRUDHI_CLI", '"/opt/pinned engine/bin/python" -m pravrudhi')
    cmd = RunManager(tmp_path)._command(RunRequest(target=target), 1)
    assert cmd[:4] == ["/opt/pinned engine/bin/python", "-m", "pravrudhi", subcommand]


@pytest.mark.parametrize("relative_root", [False, True])
def test_command_passes_absolute_train_parquet_when_present(tmp_path, monkeypatch, relative_root):
    train = tmp_path / ".pravrudhi" / "data" / "gsm8k-train.parquet"
    train.parent.mkdir(parents=True)
    train.touch()
    monkeypatch.chdir(tmp_path)
    root = Path(".") if relative_root else tmp_path
    cmd = RunManager(root)._command(RunRequest(target="model"), 1)
    value = cmd[cmd.index("--train-parquet") + 1]
    assert Path(value).is_absolute()
    assert Path(value) == train
    assert "--train-parquet" not in RunManager(root)._command(RunRequest(target="harness"), 1)


def test_command_omits_missing_train_parquet(tmp_path):
    cmd = RunManager(tmp_path)._command(RunRequest(target="model"), 1)
    assert "--train-parquet" not in cmd


def test_module_entrypoint_prints_version(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "pravrudhi", "--version"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("pravrudhi ")


def test_parse_recognises_the_engine_lines_and_keeps_the_rest():
    p = parse_line("c-0120: seed 0 incumbent=0.735 candidate=0.780 delta=+0.045 boundary=continue (n=1, E=1.65)")
    assert p["type"] == "paired" and p["delta"] == 0.045 and p["decision"] == "continue" and p["n"] == 1
    assert parse_line("proposer: 8 raw, 7 accepted, strategies ['x']")["accepted"] == 7
    assert parse_line("round 2: 3 selected, 2.49 GPU-h remaining")["remaining_gpu_h"] == 2.49
    assert parse_line("harness night 3 closed: spent 0.32/2.0")["status"] == "closed"
    assert parse_line("c-0060: PROMOTED harness (T2); now the incumbent")["candidate"] == "c-0060"
    assert parse_line("something the parser has never seen") == {"type": "log", "text": "something the parser has never seen"}


def test_a_run_streams_its_events_and_can_be_stopped(tmp_path, monkeypatch):
    init_project(tmp_path)
    mgr = RunManager(tmp_path)
    # stand in for the night CLI with a script that emits the engine's own line formats
    monkeypatch.setattr(
        RunManager, "_command",
        lambda self, req, night: ["bash", "-c",
            "echo 'proposer: 4 raw, 4 accepted, strategies []'; sleep 0.2; "
            "echo 'c-0001: seed 0 incumbent=0.50 candidate=0.60 delta=+0.100 boundary=continue (n=1, E=2.0)'; sleep 0.2; "
            "echo 'night 1 closed: spent 0.01/1.0 GPU-h'"],
    )
    run = mgr.start(RunRequest(target="model", bench="gsm8k", policy="greedy"))
    assert run.night == 1 and run.status == "running"
    for _ in range(60):
        if run.status != "running":
            break
        time.sleep(0.1)
    types = [e["type"] for e in run.events]
    assert "proposed" in types and "paired" in types and "closed" in types and types[-1] == "end"
    assert run.status == "finished" and run.best_delta == 0.1


def test_second_concurrent_run_is_refused_and_stop_works(tmp_path, monkeypatch):
    init_project(tmp_path)
    mgr = RunManager(tmp_path)
    monkeypatch.setattr(RunManager, "_command", lambda self, req, night: ["bash", "-c", "sleep 30"])
    run = mgr.start(RunRequest(target="harness"))
    try:
        mgr.start(RunRequest(target="harness"))
        raise AssertionError("expected 409")
    except Exception as e:
        assert "already in progress" in str(e)
    mgr.stop(run.id)
    for _ in range(50):
        if run.status == "stopped":
            break
        time.sleep(0.1)
    assert run.status == "stopped"


def test_app_serves_api_and_runs_router_on_one_app(tmp_path):
    init_project(tmp_path)
    client = TestClient(build_app(tmp_path), base_url="http://127.0.0.1:8008")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/runs").json() == []
    assert client.get("/api/models").json() == []
    assert client.get("/api/runs/nope").status_code == 404
    from pravrudhi.api.localguard import TOKEN_HEADER, app_token

    bad = client.post("/api/runs", json={"target": "rocket"}, headers={TOKEN_HEADER: app_token(tmp_path)})
    assert bad.status_code == 422, "the token gets you in; the schema still judges the request"
