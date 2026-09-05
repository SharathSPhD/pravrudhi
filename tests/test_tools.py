"""The tool catalogue reports what is present on this machine, and never claims a tool it cannot detect."""

from __future__ import annotations

from pathlib import Path

from pravrudhi.application import tools


def _detector(present: set[tuple[str, str]]):
    def det(kind: str, value: str) -> bool:
        return (kind, value) in present

    return det


def test_availability_marks_present_and_absent() -> None:
    got = {t["id"]: t["available"] for t in tools.availability(detector=_detector({("path", "git")}))}
    assert got["mcp-git"] is True
    assert got["agent-codex"] is False


def test_by_category_groups_every_tool() -> None:
    cats = tools.by_category(detector=_detector(set()))
    assert {"agent", "mcp", "model-server", "connector"} <= set(cats)
    total = sum(len(v) for v in cats.values())
    assert total == len(tools.catalogue())


def test_resolve_separates_available_absent_and_unknown() -> None:
    res = tools.resolve(("mcp-git", "agent-codex", "invented"), detector=_detector({("path", "git")}))
    assert [t["id"] for t in res["available"]] == ["mcp-git"]
    assert [t["id"] for t in res["absent"]] == ["agent-codex"]
    assert res["unknown"] == ["invented"]


def test_the_shipped_catalogue_is_wellformed() -> None:
    cat = tools.catalogue()
    assert len(cat) >= 8
    assert len({t.id for t in cat}) == len(cat), "no duplicate ids"
    assert all(t.detect_kind in ("path", "env") for t in cat), "only secret-free detectors"
    assert all(t.provides for t in cat)


def test_no_secret_is_stored_in_the_catalogue() -> None:
    raw = (Path(tools.__file__).resolve().parents[1] / "assets" / "tools" / "catalogue.json").read_text().lower()
    for smell in ("token", "secret", "password", "api_key", "apikey", "bearer"):
        assert smell not in raw, f"the catalogue must not carry a {smell}"
