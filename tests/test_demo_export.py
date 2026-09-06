import json
import re
from pathlib import Path

from pravrudhi.application.demo_export import PAGES, build_demo
from pravrudhi.application.init import init_project
from pravrudhi.application.policies import POLICIES

SECRET_PATTERN = re.compile(
    r"sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?:(?i:api[_-]?key|secret|token|password))[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{8,}"
)


def _leaf_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _leaf_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _leaf_strings(v)
    elif isinstance(obj, str):
        yield obj


def _demo(tmp_path: Path) -> dict:
    init_project(tmp_path)
    return build_demo(tmp_path)


def test_version_block_has_the_four_fields(tmp_path: Path) -> None:
    demo = _demo(tmp_path)
    version = demo["version"]
    assert set(version) == {"engine", "kernel", "commit", "exported_at"}
    assert version["engine"] and version["kernel"]
    assert version["commit"] is None or re.fullmatch(r"[0-9a-f]{4,40}", version["commit"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", version["exported_at"])


def test_capabilities_block_has_the_five_fields(tmp_path: Path) -> None:
    demo = _demo(tmp_path)
    caps = demo["capabilities"]
    assert set(caps) == {"tools", "agents", "policies", "recipes", "pages"}

    assert caps["tools"] and all(set(t) == {"id", "kind", "available"} for t in caps["tools"])
    assert all(isinstance(t["available"], bool) for t in caps["tools"])

    assert caps["agents"] and all(set(a) == {"name", "available"} for a in caps["agents"])
    assert all(isinstance(a["available"], bool) for a in caps["agents"])

    assert caps["policies"] == list(POLICIES)
    assert isinstance(caps["recipes"], int) and caps["recipes"] >= 0
    assert caps["pages"] == list(PAGES) and all(p.startswith("/") for p in caps["pages"])


def test_existing_keys_are_unchanged(tmp_path: Path) -> None:
    demo = _demo(tmp_path)
    assert demo["recorded"] is True
    assert set(demo["engine"]) == {"version", "candidates"}
    assert demo["engine"]["version"] == demo["version"]["engine"]
    for key in ("status", "models", "external", "nights", "runs", "objectives", "recipes", "plans", "featured_run"):
        assert key in demo


def test_no_field_carries_a_token_secret_or_key_pattern(tmp_path: Path) -> None:
    demo = _demo(tmp_path)
    for value in _leaf_strings(demo):
        assert not SECRET_PATTERN.search(value), value
    assert not SECRET_PATTERN.search(json.dumps(demo))
