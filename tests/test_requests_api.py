from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pravrudhi.api.localguard import TOKEN_HEADER, app_token
from pravrudhi.api.server import create_app
from pravrudhi.application.requests import Criterion, capture


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path), base_url="http://127.0.0.1:8008")


def _auth(root: Path) -> dict[str, str]:
    return {TOKEN_HEADER: app_token(root)}


def test_backlog_shape(tmp_path: Path, client: TestClient) -> None:
    capture(
        tmp_path, "make the dashboard show request status",
        criteria=[Criterion("ship it", source="operator")],
    )

    resp = client.get("/api/requests")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["open"] == 1
    assert "by_state" in data
    assert "oldest_open_days" in data
    row = data["requests"][0]
    assert row["text"] == "make the dashboard show request status"
    assert row["progress"] == [0, 1]
    assert row["criteria"][0]["source"] == "operator"
    assert row["criteria"][0]["met"] is False


def test_advance_to_delivered_with_unmet_criterion_is_409(tmp_path: Path, client: TestClient) -> None:
    req = capture(
        tmp_path, "wire the API to the ledger",
        criteria=[Criterion("endpoint responds", source="operator")],
    )
    in_progress = client.post(
        f"/api/requests/{req.id}/advance", json={"state": "in_progress"}, headers=_auth(tmp_path)
    )
    assert in_progress.status_code == 200

    resp = client.post(f"/api/requests/{req.id}/advance", json={"state": "delivered"}, headers=_auth(tmp_path))

    assert resp.status_code == 409
    assert "endpoint responds" in resp.json()["detail"]


def test_posting_evidence_marks_criterion_met(tmp_path: Path, client: TestClient) -> None:
    req = capture(
        tmp_path, "wire the API to the ledger",
        criteria=[Criterion("endpoint responds", source="operator")],
    )
    client.post(f"/api/requests/{req.id}/advance", json={"state": "in_progress"}, headers=_auth(tmp_path))

    resp = client.post(
        f"/api/requests/{req.id}/criteria/0/evidence",
        json={"kind": "commit", "ref": "abc1234", "note": "verified locally"},
        headers=_auth(tmp_path),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["criteria"][0]["met"] is True
    assert body["criteria"][0]["evidence"][0] == {"kind": "commit", "ref": "abc1234", "note": "verified locally"}

    delivered = client.post(f"/api/requests/{req.id}/advance", json={"state": "delivered"}, headers=_auth(tmp_path))
    assert delivered.status_code == 200
    assert delivered.json()["state"] == "delivered"


def test_no_response_field_carries_a_secret_shaped_string(tmp_path: Path, client: TestClient) -> None:
    req = capture(
        tmp_path, "add a status page for the request backlog",
        criteria=[Criterion("checked", source="operator")],
    )
    token = app_token(tmp_path)

    for resp in (client.get("/api/requests"), client.get(f"/api/requests/{req.id}")):
        assert resp.status_code == 200
        assert token not in resp.text
        lowered = resp.text.lower()
        assert not any(marker in lowered for marker in ("api_key", "secret", "password", "bearer "))
