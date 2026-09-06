"""The catalogue page renders every tool, recipe and sandbox policy the engine knows about. None of that is a
secret, and nothing along the way should be able to smuggle one in: not the API data the page fetches, not the
sandbox policy config it mirrors, and not the frontend source that renders it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from pravrudhi.application.app_serve import build_app
from pravrudhi.application.credentials import redact
from pravrudhi.application.init import init_project
from pravrudhi.application.sandbox_policy import PACKAGED_CONFIG, load_policies

H = {"host": "127.0.0.1:8008"}

FRONTEND_ROOT = Path(__file__).resolve().parents[1] / "app" / "frontend" / "src"
CATALOGUE_SOURCES = (
    FRONTEND_ROOT / "app" / "catalogue" / "page.tsx",
    FRONTEND_ROOT / "components" / "catalogue" / "ToolsTable.tsx",
    FRONTEND_ROOT / "components" / "catalogue" / "RecipesTable.tsx",
    FRONTEND_ROOT / "components" / "catalogue" / "PoliciesTable.tsx",
    FRONTEND_ROOT / "lib" / "catalogue.ts",
)

SMELL_WORDS = ("token", "secret", "password", "api_key", "apikey", "bearer", "authorization")


def _strings(node: Any) -> list[str]:
    """Every string value reachable from a parsed JSON document."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def _assert_no_secret_shaped_string(strings: list[str]) -> None:
    for s in strings:
        assert redact(s) == s, f"secret-shaped string found: {s!r}"
        lowered = s.lower()
        for smell in SMELL_WORDS:
            assert smell not in lowered, f"{smell!r} found in {s!r}"


def _client(tmp_path: Path) -> TestClient:
    init_project(tmp_path)
    return TestClient(build_app(tmp_path), headers=H)


def test_tools_endpoint_carries_no_secret_shaped_field(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/api/tools").json()
    assert body["tools"], "the catalogue page has nothing to show without this"
    _assert_no_secret_shaped_string(_strings(body))


def test_recipes_endpoint_carries_no_secret_shaped_field(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/api/recipes").json()
    assert body["recipes"], "the catalogue page has nothing to show without this"
    _assert_no_secret_shaped_string(_strings(body))


def test_sandbox_policy_config_carries_no_secret_shaped_field() -> None:
    policies = load_policies()
    assert policies, "the policies section has nothing to show without this"
    for policy in policies.values():
        _assert_no_secret_shaped_string(
            [
                policy.id,
                *policy.allowed_paths,
                *policy.denied_paths,
                policy.network,
                *policy.tools,
                policy.validate,
            ]
        )
    _assert_no_secret_shaped_string([PACKAGED_CONFIG.read_text()])


def test_catalogue_page_source_carries_no_secret_shaped_string() -> None:
    for path in CATALOGUE_SOURCES:
        assert path.is_file(), f"expected catalogue source at {path}"
        _assert_no_secret_shaped_string([path.read_text()])


def test_catalogue_page_mirrors_the_declared_sandbox_policies() -> None:
    """The Policies section hardcodes a copy of sandbox_policies.yaml (no live route exposes it); this pins that
    copy to the declared config so a change to one without the other fails loudly instead of silently drifting."""
    source = (FRONTEND_ROOT / "lib" / "catalogue.ts").read_text()
    for policy in load_policies().values():
        assert f'id: "{policy.id}"' in source, f"policy {policy.id!r} missing from the frontend mirror"
        for path in policy.allowed_paths:
            assert f'"{path}"' in source, f"allowed path {path!r} of policy {policy.id!r} missing from the mirror"
        for path in policy.denied_paths:
            assert f'"{path}"' in source, f"denied path {path!r} of policy {policy.id!r} missing from the mirror"
        assert f'"{policy.network}"' in source, f"network {policy.network!r} of policy {policy.id!r} missing"
        assert str(policy.max_wall_s) in source, f"max_wall_s of policy {policy.id!r} missing from the mirror"
