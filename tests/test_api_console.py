from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pravrudhi import KERNEL_VERSION
from pravrudhi.api.server import create_app
from pravrudhi.application.evidence import render_h1
from pravrudhi.application.init import init_project
from pravrudhi_kernel.ledger import LedgerWriter


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    init_project(tmp_path)
    return tmp_path


@pytest.fixture
def client(tmp_root: Path) -> Iterator[TestClient]:
    with TestClient(create_app(tmp_root), base_url="http://127.0.0.1:8008") as client:
        yield client


@pytest.mark.parametrize("endpoint", ["/api/doctor", "/api/hosts", "/api/agents", "/api/external", "/api/nights", "/api/h1/lora/1-2-3"])
def test_console_endpoints(client: TestClient, endpoint: str) -> None:
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert isinstance(response.json(), (dict, list))


@pytest.mark.parametrize("nights", ["bad", "1-two", "1--2", "-1", "1-", "1.5", "1%202"])
def test_h1_malformed_nights(client: TestClient, nights: str) -> None:
    assert client.get(f"/api/h1/lora/{nights}").status_code == 400


def test_fresh_nights(client: TestClient) -> None:
    assert client.get("/api/nights").json() == []


def test_local_host(client: TestClient) -> None:
    assert any(row["host"]["name"] == "local" for row in client.get("/api/hosts").json()["hosts"])


def test_h1_markdown(client: TestClient, tmp_root: Path) -> None:
    assert client.get("/api/h1/harness/2-4").json() == {
        "markdown": render_h1(tmp_root / "research" / "ledger.jsonl", (2, 4), "harness")
    }


def test_nights_pair_latest_start_by_night_and_track(client: TestClient, tmp_root: Path) -> None:
    writer = LedgerWriter.open(tmp_root / "research" / "ledger.jsonl", KERNEL_VERSION)
    for night, payload in [
        (1, {"kind": "night_start", "track": "lora", "selection_policy": "old"}),
        (1, {"kind": "night_start", "track": "lora", "selection_policy": "efe"}),
        (2, {"kind": "night_start", "track": "lora", "selection_policy": "other-night"}),
        (1, {"kind": "night_start", "track": "harness", "selection_policy": "greedy"}),
        (1, {"kind": "night_end", "spent_gpu_h": 1.5, "outcomes": {"kept": 1}, "incumbent": "c-1"}),
        (1, {"kind": "night_end", "track": "harness", "spent_gpu_h": 2, "outcomes": {}, "incumbent": "h-1"}),
        (1, {"kind": "night_start", "track": "lora", "selection_policy": "future"}),
    ]:
        writer.append("audit", "kernel", {"severity": "info", **payload}, epoch=0, night=night)
    assert client.get("/api/nights").json() == [
        {"night": 1, "track": "lora", "selection_policy": "efe", "spent_gpu_h": 1.5,
         "outcomes": {"kept": 1}, "incumbent": "c-1"},
        {"night": 1, "track": "harness", "selection_policy": "greedy", "spent_gpu_h": 2,
         "outcomes": {}, "incumbent": "h-1"},
    ]


# A local engine that can start GPU work must not echo a wildcard: unset means no cross-origin access at all,
# not "any page may read this". See api/localguard.py and tests/test_localguard.py.
@pytest.mark.parametrize("origins, expected", [(None, None), ("", None),
    (" https://console.example, https://other.example ", "https://console.example"),
    ("https://other.example", None)])
def test_cors(tmp_root: Path, monkeypatch: pytest.MonkeyPatch, origins: str | None, expected: str | None) -> None:
    if origins is None:
        monkeypatch.delenv("PRAVRUDHI_ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("PRAVRUDHI_ALLOWED_ORIGINS", origins)
    with TestClient(create_app(tmp_root), base_url="http://127.0.0.1:8008") as client:
        response = client.get("/api/nights", headers={"Origin": "https://console.example"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == expected
