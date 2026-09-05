"""Runs: a night started from the app is a supervised subprocess whose log becomes live events."""
import time

from fastapi.testclient import TestClient

from pravrudhi.api.runs import RunManager, RunRequest, parse_line
from pravrudhi.application.app_serve import build_app
from pravrudhi.application.init import init_project


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
    client = TestClient(build_app(tmp_path))
    assert client.get("/health").status_code == 200
    assert client.get("/runs").json() == []
    assert client.get("/models").json() == []
    assert client.get("/runs/nope").status_code == 404
    bad = client.post("/runs", json={"target": "rocket"})
    assert bad.status_code == 422
