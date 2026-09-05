"""A local engine that can start GPU work must not answer arbitrary web pages."""

from fastapi.testclient import TestClient

from pravrudhi.api.localguard import TOKEN_HEADER, app_token, token_path
from pravrudhi.application.app_serve import build_app
from pravrudhi.application.init import init_project


def _client(tmp_path):
    """A client whose Host header is a real loopback address, as a browser on the local engine would send."""
    init_project(tmp_path)
    return TestClient(build_app(tmp_path), base_url="http://127.0.0.1:8008"), tmp_path


def test_reading_is_open_but_starting_a_run_needs_the_local_token(tmp_path):
    client, root = _client(tmp_path)
    assert client.get("/health").status_code == 200, "a dashboard should read without ceremony"
    refused = client.post("/runs", json={"target": "model"})
    assert refused.status_code == 401 and TOKEN_HEADER in refused.json()["detail"]
    ok = client.post("/runs", json={"target": "model", "budget_gpu_h": 0.01},
                     headers={TOKEN_HEADER: app_token(root)})
    assert ok.status_code != 401


def test_a_malicious_page_cannot_start_a_run_even_with_a_stolen_shape(tmp_path):
    client, root = _client(tmp_path)
    r = client.post("/runs", json={"target": "model"},
                    headers={"origin": "https://evil.example", TOKEN_HEADER: app_token(root)})
    assert r.status_code == 403 and "cross-origin" in r.json()["detail"]


def test_dns_rebinding_is_refused_by_the_host_header(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/health", headers={"host": "attacker.example"}).status_code == 421
    assert client.get("/health", headers={"host": "127.0.0.1:8008"}).status_code == 200
    assert client.get("/health", headers={"host": "localhost:8008"}).status_code == 200


def test_no_permissive_cors_by_default_and_the_token_is_not_readable_cross_origin(tmp_path, monkeypatch):
    monkeypatch.delenv("PRAVRUDHI_ALLOWED_ORIGINS", raising=False)
    client, _ = _client(tmp_path)
    r = client.get("/health", headers={"origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") is None, "no wildcard for a local unauthenticated engine"
    assert client.get("/app-token", headers={"origin": "https://evil.example"}).status_code == 403
    assert client.get("/app-token").status_code == 200


def test_the_token_file_is_owner_only(tmp_path):
    _, root = _client(tmp_path)
    tok = app_token(root)
    assert len(tok) > 20
    assert oct(token_path(root).stat().st_mode)[-3:] == "600"
    assert app_token(root) == tok, "the token is stable once created"


def test_an_operator_can_name_origins_when_they_mean_to(tmp_path, monkeypatch):
    monkeypatch.setenv("PRAVRUDHI_ALLOWED_ORIGINS", "https://pravrudhi.vercel.app")
    client, root = _client(tmp_path)
    r = client.get("/health", headers={"origin": "https://pravrudhi.vercel.app"})
    assert r.headers.get("access-control-allow-origin") == "https://pravrudhi.vercel.app"
    assert client.post("/runs", json={"target": "model"},
                       headers={"origin": "https://pravrudhi.vercel.app", TOKEN_HEADER: app_token(root)}).status_code != 403
