"""Telling a vendor's usage limit apart from an ordinary failure, and remembering it for a while.

Today a limit reads exactly like a bug: the agent's CLI exits non-zero (or exits zero having done nothing) and the
router records a loss, the same as it would for a prompt the model genuinely botched. That is wrong twice over. It
punishes a route for something that says nothing about its quality, and it does not stop the engine from dispatching
the very next task to the same account, which is still limited and will fail the same way for hours.

This module gives the difference a name (`classify`) and a place to remember it (a cooldown file beside the routing
log), so a limited account can be skipped for a while and tried again automatically -- rather than either quietly
eating the loss or stopping the loop for a human to notice.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import yaml

PACKAGED_LIMITS_CONFIG = Path(__file__).resolve().parents[1] / "assets" / "configs" / "limits.yaml"

DEFAULT_COOLDOWN_MINUTES = 60.0


class RouteLike(Protocol):
    """The one thing `usable_routes` needs from a route: which agent it dispatches through.

    Declared read-only. A bare `agent: str` member requires a settable attribute, which a frozen dataclass such
    as `routing.Route` does not provide, so the real route type failed to satisfy the protocol at all.
    """

    @property
    def agent(self) -> str: ...



def _load_config(path: Path | None = None) -> dict[str, Any]:
    raw = yaml.safe_load((path or PACKAGED_LIMITS_CONFIG).read_text())
    return raw if isinstance(raw, dict) else {}


def _limit_patterns() -> dict[str, list[str]]:
    patterns = _load_config().get("patterns") or {}
    return {str(agent_id): [str(p) for p in (phrases or [])] for agent_id, phrases in patterns.items()}


# Loaded once at import: a small, packaged config, not operator state that changes at runtime.
LIMIT_PATTERNS: dict[str, list[str]] = _limit_patterns()


def _default_cooldown_minutes(agent_id: str) -> float:
    minutes = _load_config().get("cooldown_minutes") or {}
    if agent_id in minutes:
        return float(minutes[agent_id])
    return float(minutes.get("default", DEFAULT_COOLDOWN_MINUTES))


def classify(agent_id: str, text: str, returncode: int) -> str:
    """"ok", "limited" or "failed" for one finished agent run.

    A wrong call in either direction only costs a cooldown or a loss recorded slightly late; it never crashes a
    wave, so the match against `LIMIT_PATTERNS` is deliberately a loose, case-insensitive substring test rather than
    a precise parse of a vendor's error format that would need updating every time that format changes.
    """
    haystack = (text or "").lower()
    if any(phrase.lower() in haystack for phrase in LIMIT_PATTERNS.get(agent_id, ())):
        return "limited"
    return "ok" if returncode == 0 else "failed"


def _cooldown_path(root: Path) -> Path:
    return Path(root) / ".pravrudhi" / "agent_cooldown.json"


def _read(root: Path) -> dict[str, str]:
    p = _cooldown_path(root)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}  # a corrupt cooldown file must not stop the router; it just forgets the cooldowns
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _write(root: Path, data: dict[str, str]) -> None:
    p = _cooldown_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, sort_keys=True))


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def mark_limited(root: Path, agent_id: str, *, minutes: float | None = None, now: datetime | None = None) -> None:
    """Remember that `agent_id` just reported a usage limit, so the router leaves it alone for a while."""
    when = _aware(now or datetime.now(UTC))
    mins = minutes if minutes is not None else _default_cooldown_minutes(agent_id)
    until = when + timedelta(minutes=mins)
    data = _read(root)
    data[agent_id] = until.strftime("%Y-%m-%dT%H:%M:%SZ")
    _write(root, data)


def cooling(root: Path, now: datetime | None = None) -> dict[str, str]:
    """Every agent id still inside its cooldown window, mapped to when that window ends."""
    when = _aware(now or datetime.now(UTC))
    out: dict[str, str] = {}
    for agent_id, until_iso in _read(root).items():
        try:
            until = datetime.strptime(until_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except ValueError:
            continue  # a hand-edited or corrupt entry must not wedge the agent as permanently cooling
        if until > when:
            out[agent_id] = until_iso
    return out


def is_cool(root: Path, agent_id: str, now: datetime | None = None) -> bool:
    return agent_id in cooling(root, now)


def clear(root: Path, agent_id: str) -> None:
    """Forget a cooldown early, e.g. once the operator confirms the account works again."""
    data = _read(root)
    if agent_id in data:
        del data[agent_id]
        _write(root, data)


def usable_routes[R: RouteLike](root: Path, routes: list[R], now: datetime | None = None) -> list[R]:
    """`routes` with every route whose agent is currently cooling down removed.

    Generic in the route type rather than typed to the protocol: a `list` is invariant, so a caller holding
    concrete routes could neither pass its list in nor read concrete attributes off what came back.
    """
    cool = cooling(root, now)
    return [r for r in routes if r.agent not in cool]


__all__ = [
    "LIMIT_PATTERNS",
    "classify",
    "mark_limited",
    "cooling",
    "is_cool",
    "clear",
    "usable_routes",
]
