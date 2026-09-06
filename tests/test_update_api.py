"""GET/PUT /api/update/config and POST /api/update/apply|rollback.

`update_apply.apply` and `.rollback` do real work (fetch, install, switch symlinks), so every test here
monkeypatches them and checks only that the route wires the config store and the ApplyResult through faithfully,
including the concurrency guard that refuses a second apply while one is still running.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pravrudhi.api.localguard import app_token
from pravrudhi.api.server import create_app
from pravrudhi.application import update_apply
from pravrudhi.application.update_apply import ApplyResult


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path), base_url="http://127.0.0.1:8008")


def _auth(root: Path) -> dict[str, str]:
    return {"x-pravrudhi-token": app_token(root)}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path


def test_update_config_round_trips(client: TestClient, root: Path) -> None:
    got = client.get("/api/update/config")
    assert got.status_code == 200
    assert got.json() == {
        "channel": "release",
        "auto_apply": False,
        "check_interval_min": 1440,
        "keep_previous": 2,
    }

    saved = client.put(
        "/api/update/config",
        json={"channel": "dev", "auto_apply": True, "check_interval_min": 30, "keep_previous": 5},
        headers=_auth(root),
    )
    assert saved.status_code == 200
    assert saved.json() == {
        "channel": "dev",
        "auto_apply": True,
        "check_interval_min": 30,
        "keep_previous": 5,
    }

    reread = client.get("/api/update/config")
    assert reread.json() == saved.json()


def test_apply_returns_the_result(client: TestClient, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_apply(
        apply_root: Path, *, channel: str | None = None, fetch: object = None, runner: object = None
    ) -> ApplyResult:
        seen["root"] = apply_root
        seen["channel"] = channel
        return ApplyResult(True, "0.2.2", "switched to 0.2.2", False)

    monkeypatch.setattr(update_apply, "apply", fake_apply)

    res = client.post("/api/update/apply", json={"channel": "release"}, headers=_auth(root))
    assert res.status_code == 200
    assert res.json() == {"applied": True, "version": "0.2.2", "reason": "switched to 0.2.2", "rolled_back": False}
    assert seen["channel"] == "release"


def test_apply_kill_switch_reason_surfaces_verbatim(
    client: TestClient, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reason = "PRAVRUDHI_NO_UPDATE=1: automatic updates are disabled"

    def fake_apply(
        apply_root: Path, *, channel: str | None = None, fetch: object = None, runner: object = None
    ) -> ApplyResult:
        return ApplyResult(False, None, reason, False)

    monkeypatch.setattr(update_apply, "apply", fake_apply)

    res = client.post("/api/update/apply", json={}, headers=_auth(root))
    assert res.status_code == 200
    body = res.json()
    assert body["applied"] is False
    assert body["reason"] == reason


def test_rollback_returns_the_result(client: TestClient, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_rollback(rollback_root: Path) -> ApplyResult:
        return ApplyResult(True, "0.2.0", "rolled back to 0.2.0", True)

    monkeypatch.setattr(update_apply, "rollback", fake_rollback)

    res = client.post("/api/update/rollback", headers=_auth(root))
    assert res.status_code == 200
    assert res.json() == {"applied": True, "version": "0.2.0", "reason": "rolled back to 0.2.0", "rolled_back": True}


def test_apply_refuses_with_409_while_one_is_in_progress(
    client: TestClient, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = threading.Event()
    release = threading.Event()

    def slow_apply(
        apply_root: Path, *, channel: str | None = None, fetch: object = None, runner: object = None
    ) -> ApplyResult:
        entered.set()
        release.wait(timeout=5)
        return ApplyResult(True, "0.2.3", "switched to 0.2.3", False)

    monkeypatch.setattr(update_apply, "apply", slow_apply)

    first_response: list[object] = []

    def call_first() -> None:
        first_response.append(client.post("/api/update/apply", json={}, headers=_auth(root)))

    thread = threading.Thread(target=call_first)
    thread.start()
    assert entered.wait(timeout=5), "the first apply never started"

    second = client.post("/api/update/apply", json={}, headers=_auth(root))
    assert second.status_code == 409

    release.set()
    thread.join(timeout=5)
    assert first_response[0].status_code == 200  # type: ignore[attr-defined]
