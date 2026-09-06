"""Bring-your-own-key HTTP surface: the provider registry, and validate/store/remove for one caller's key."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import pravrudhi.application.credentials as credentials
from pravrudhi.api.localguard import TOKEN_HEADER, app_token
from pravrudhi.application.app_serve import build_app
from pravrudhi.application.init import init_project

H = {"host": "127.0.0.1:8008"}


def _client(tmp_path: Path) -> TestClient:
    init_project(tmp_path)
    return TestClient(build_app(tmp_path), headers=H)


def _token_header(tmp_path: Path) -> dict[str, str]:
    return {TOKEN_HEADER: app_token(tmp_path)}


def test_provider_registry_lists_every_provider_unconfigured_and_never_a_key(tmp_path: Path) -> None:
    c = _client(tmp_path)
    body = c.get("/api/providers").json()
    assert {p["id"] for p in body} == set(credentials.PROVIDERS)
    for entry in body:
        provider = credentials.PROVIDERS[entry["id"]]
        assert entry["title"] == provider.title
        assert entry["key_prefix"] == provider.key_prefix
        assert entry["configured"] is False
        assert set(entry) == {"id", "title", "configured", "key_prefix"}, "no field here may carry a key"


def test_unknown_provider_is_rejected_on_set_and_delete(tmp_path: Path) -> None:
    c = _client(tmp_path)
    headers = _token_header(tmp_path)
    assert c.post("/api/providers/not-a-provider/key", json={"key": "x"}, headers=headers).status_code == 404
    assert c.delete("/api/providers/not-a-provider/key", headers=headers).status_code == 404


def test_storing_a_key_validates_it_and_the_key_never_leaves_the_process(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(credentials, "validate", lambda *a, **kw: (True, "ok"))
    c = _client(tmp_path)
    headers = _token_header(tmp_path)
    secret_key = "sk-thisisaverysecretlookingapikey1234567890"

    r = c.post("/api/providers/openai/key", json={"key": secret_key}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"provider": "openai", "configured": True, "validated": True, "reason": "ok"}
    assert secret_key not in r.text

    listing = c.get("/api/providers")
    assert secret_key not in listing.text
    entry = next(p for p in listing.json() if p["id"] == "openai")
    assert entry["configured"] is True

    stored = (tmp_path / ".pravrudhi" / "credentials" / "openai.key").read_text().strip()
    assert stored == secret_key, "the file store is expected to hold the real key; only the wire contract must not"

    d = c.delete("/api/providers/openai/key", headers=headers)
    assert d.status_code == 200
    assert d.json() == {"provider": "openai", "configured": False}
    assert secret_key not in d.text
    assert not (tmp_path / ".pravrudhi" / "credentials" / "openai.key").exists()


def test_a_failed_validation_still_stores_the_key_and_the_reason_is_redacted(tmp_path: Path, monkeypatch) -> None:
    leaking_reason = "probe failed: key sk-leakedvaluelookalike1234567890 was rejected"
    monkeypatch.setattr(credentials, "validate", lambda *a, **kw: (False, leaking_reason))
    c = _client(tmp_path)
    headers = _token_header(tmp_path)

    r = c.post(
        "/api/providers/anthropic/key",
        json={"key": "sk-ant-anothersecretvalue1234567890"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {
        "provider": "anthropic",
        "configured": True,
        "validated": False,
        "reason": credentials.redact(leaking_reason),
    }
    assert "sk-leakedvaluelookalike1234567890" not in r.text
    assert (tmp_path / ".pravrudhi" / "credentials" / "anthropic.key").exists()


def test_state_changing_provider_routes_require_the_local_token(tmp_path: Path) -> None:
    c = _client(tmp_path)
    assert c.post("/api/providers/openai/key", json={"key": "sk-whatever1234567890"}).status_code == 401
    assert c.delete("/api/providers/openai/key").status_code == 401
