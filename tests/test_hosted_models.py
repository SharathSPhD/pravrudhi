"""Hosted free-tier models are the operator's own quota, and both gates must hold.

A stranger's installation must never reach them: it has no key, and even with one the surface refuses. The tests
that matter here are the refusals, because the failure they prevent is spending someone else's money.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pravrudhi.models import hosted


@dataclass(frozen=True)
class _User:
    id: str = "u1"
    email: str | None = "someone@example.com"
    role: str = "authenticated"


def test_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv(hosted.OPT_IN, raising=False)
    ok, why = hosted.available()
    assert not ok and hosted.OPT_IN in why


def test_refused_without_the_opt_in_even_for_an_admin(monkeypatch) -> None:
    monkeypatch.delenv(hosted.OPT_IN, raising=False)
    with pytest.raises(hosted.HostedRefused):
        hosted.assert_admin(_User(role="admin"))


def test_local_engine_with_identity_disabled_needs_only_the_opt_in(monkeypatch) -> None:
    monkeypatch.setenv(hosted.OPT_IN, "1")
    monkeypatch.setenv("PRAVRUDHI_AUTH", "disabled")
    hosted.assert_admin(None)


def test_a_logged_in_stranger_cannot_spend_the_operators_quota(monkeypatch) -> None:
    monkeypatch.setenv(hosted.OPT_IN, "1")
    monkeypatch.setenv("PRAVRUDHI_AUTH", "optional")
    monkeypatch.setenv(hosted.ADMIN_EMAIL, "owner@example.com")
    with pytest.raises(hosted.HostedRefused):
        hosted.assert_admin(_User(email="stranger@example.com"))


def test_the_admin_is_allowed_by_email_or_by_role(monkeypatch) -> None:
    monkeypatch.setenv(hosted.OPT_IN, "1")
    monkeypatch.setenv("PRAVRUDHI_AUTH", "optional")
    monkeypatch.setenv(hosted.ADMIN_EMAIL, "owner@example.com")
    hosted.assert_admin(_User(email="Owner@Example.com"))
    hosted.assert_admin(_User(email="other@example.com", role="admin"))


def test_identity_on_but_no_admin_configured_refuses_rather_than_guessing(monkeypatch) -> None:
    monkeypatch.setenv(hosted.OPT_IN, "1")
    monkeypatch.setenv("PRAVRUDHI_AUTH", "required")
    monkeypatch.delenv(hosted.ADMIN_EMAIL, raising=False)
    with pytest.raises(hosted.HostedRefused):
        hosted.assert_admin(_User(role="admin"))


def test_usage_is_empty_when_the_capability_is_not_available(monkeypatch) -> None:
    monkeypatch.delenv(hosted.OPT_IN, raising=False)
    assert hosted.usage() == []


def test_the_client_path_is_outside_the_package(monkeypatch) -> None:
    """The key and the shared ledger live in the operator's home, never in the repository or the wheel."""
    monkeypatch.delenv("PRAVRUDHI_FREELLM_PATH", raising=False)
    import pravrudhi

    assert str(hosted.client_path()).startswith(str(hosted.Path.home()))
    assert str(pravrudhi.__file__) not in str(hosted.client_path())
