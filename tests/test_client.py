"""A typed client must work with a real engine, not a mock."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pravrudhi.api.localguard import app_token
from pravrudhi.api.schemas import HealthResponse, ObjectiveResponse, ObjectivesResponse
from pravrudhi.application.app_serve import build_app
from pravrudhi.application.init import init_project
from pravrudhi.client import Client, ClientError


def test_client_health(tmp_path: Path) -> None:
    """The client reads the service identity without ceremony."""
    init_project(tmp_path)
    app = build_app(tmp_path)

    # Use FastAPI's TestClient which wraps the app synchronously
    test_client = TestClient(app, headers={"host": "127.0.0.1:8008"})

    # Wrap it as an httpx.Client-like object for our Client class
    class SyncAdapter:
        def __init__(self, tc: TestClient) -> None:
            self.tc = tc

        def request(
            self, method: str, url: str, *, headers: dict | None = None, **kwargs
        ):
            path = url.replace("http://127.0.0.1:8008", "")
            return self.tc.request(method, path, headers=headers, **kwargs)

    adapter = SyncAdapter(test_client)
    client = Client(base_url="http://127.0.0.1:8008", _http_client=adapter)  # type: ignore[arg-type]
    response = client._request("GET", "/health", HealthResponse)

    assert isinstance(response, HealthResponse)
    assert response.ok is True
    assert response.version


def test_client_list_objectives(tmp_path: Path) -> None:
    """The client lists objectives with proper typing."""
    init_project(tmp_path)
    app = build_app(tmp_path)
    test_client = TestClient(app, headers={"host": "127.0.0.1:8008"})

    class SyncAdapter:
        def __init__(self, tc: TestClient) -> None:
            self.tc = tc

        def request(self, method: str, url: str, *, headers: dict | None = None, **kwargs):
            path = url.replace("http://127.0.0.1:8008", "")
            return self.tc.request(method, path, headers=headers, **kwargs)

    adapter = SyncAdapter(test_client)
    client = Client(base_url="http://127.0.0.1:8008", _http_client=adapter)  # type: ignore[arg-type]
    response = client._request("GET", "/objectives", ObjectivesResponse)

    assert isinstance(response, ObjectivesResponse)
    assert isinstance(response.objectives, list)
    assert isinstance(response.problems, list)


def test_client_create_objective(tmp_path: Path) -> None:
    """The client can create an objective."""
    init_project(tmp_path)
    app = build_app(tmp_path)

    token = app_token(tmp_path)
    test_client = TestClient(app, headers={"host": "127.0.0.1:8008"})

    class SyncAdapter:
        def __init__(self, tc: TestClient) -> None:
            self.tc = tc

        def request(self, method: str, url: str, *, headers: dict | None = None, **kwargs):
            path = url.replace("http://127.0.0.1:8008", "")
            return self.tc.request(method, path, headers=headers, **kwargs)

    adapter = SyncAdapter(test_client)
    client = Client(
        base_url="http://127.0.0.1:8008",
        token=token,
        _http_client=adapter,  # type: ignore[arg-type]
    )
    response = client._request(
        "POST",
        "/objectives",
        ObjectiveResponse,
        json={
            "id": "test-obj",
            "intent": "improve something",
            "track": "lora",
            "benchmarks": [
                {
                    "id": "b1",
                    "tool": "lm-eval",
                    "metric": "accuracy",
                    "direction": "up",
                }
            ],
            "domain": "test",
            "recipes": [],
            "target_delta": 0.1,
            "notes": "test",
        },
    )

    assert isinstance(response, ObjectiveResponse)
    assert response.id == "test-obj"
    assert response.intent == "improve something"


def test_client_missing_token_raises_error() -> None:
    """A state-changing call without a token raises ClientError."""
    client = Client(base_url="http://127.0.0.1:8008", token=None)
    client.token = None

    with pytest.raises(ClientError) as exc_info:
        client._request("POST", "/objectives", None, json={})

    assert exc_info.value.status_code == 401
    assert "token" in str(exc_info.value).lower()
    assert ".pravrudhi/app_token" in str(exc_info.value)


def test_client_404_raises_error(tmp_path: Path) -> None:
    """A 404 response raises ClientError."""
    init_project(tmp_path)
    app = build_app(tmp_path)
    test_client = TestClient(app, headers={"host": "127.0.0.1:8008"})

    class SyncAdapter:
        def __init__(self, tc: TestClient) -> None:
            self.tc = tc

        def request(self, method: str, url: str, *, headers: dict | None = None, **kwargs):
            path = url.replace("http://127.0.0.1:8008", "")
            return self.tc.request(method, path, headers=headers, **kwargs)

    adapter = SyncAdapter(test_client)
    client = Client(base_url="http://127.0.0.1:8008", _http_client=adapter)  # type: ignore[arg-type]

    with pytest.raises(ClientError) as exc_info:
        client._request("GET", "/candidates/no-such-id", None)

    assert exc_info.value.status_code == 404
    assert "/candidates/no-such-id" in exc_info.value.path


def test_client_sends_host_header() -> None:
    """The client includes the Host header in all requests."""
    client = Client(base_url="http://127.0.0.1:8008")
    headers = client._headers(require_token=False)
    assert "Host" in headers
    assert headers["Host"] == "127.0.0.1:8008"


def test_client_token_in_state_changing_headers() -> None:
    """The client includes the token in state-changing requests."""
    client = Client(base_url="http://127.0.0.1:8008", token="test-token")
    headers = client._headers(require_token=True)
    assert "x-pravrudhi-token" in headers
    assert headers["x-pravrudhi-token"] == "test-token"
