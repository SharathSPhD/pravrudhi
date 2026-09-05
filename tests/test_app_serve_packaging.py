"""Resolve the web interface in checkouts and installed wheels."""

from __future__ import annotations

from pathlib import Path

import pytest

from pravrudhi.application import app_serve


def test_checkout_preferred(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    checkout = tmp_path / "app" / "frontend" / "out"
    checkout.mkdir(parents=True)
    (checkout / "index.html").write_text("checkout")
    packaged = tmp_path / "packaged"
    packaged.mkdir()
    (packaged / "index.html").write_text("packaged")
    monkeypatch.setattr(app_serve, "PACKAGED_FRONTEND", packaged)

    assert app_serve.frontend_dir(tmp_path) == checkout


def test_packaged_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packaged = tmp_path / "packaged"
    packaged.mkdir()
    (packaged / "index.html").write_text("packaged")
    monkeypatch.setattr(app_serve, "PACKAGED_FRONTEND", packaged)

    assert app_serve.frontend_dir(tmp_path) == packaged


def test_neither_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_serve, "PACKAGED_FRONTEND", tmp_path / "packaged")

    assert app_serve.frontend_dir(tmp_path) is None
