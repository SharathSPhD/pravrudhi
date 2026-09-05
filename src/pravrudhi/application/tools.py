"""The tools, connectors and plugins an engine like this can draw on, made discoverable inside Pravrudhi itself.

The recipe library made the training recipes on this machine visible to the engine and its users; the same argument
applies to everything else the engine can reach -- the coding agents, the model servers, the container runtime, the
MCP connectors that deploy and store and browse. Without a catalogue, a user (or the engine's own chat) has no way
to know what is available here without reading the host's configuration, and a stranger who installs Pravrudhi has
no way to know what it could use if they set it up.

This is a catalogue, not an execution layer. Listing a tool is not a claim that it has been invoked, and nothing in
this module calls any tool: it names each one, says what it provides, and reports whether it is present on this
machine by a stated detector -- an executable on PATH, or a named environment variable. A tool with no honest
detector is not listed, and no secret is ever stored here.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PACKAGED_CATALOGUE = Path(__file__).resolve().parents[1] / "assets" / "tools" / "catalogue.json"

Detector = Callable[[str, str], bool]


def _default_detector(kind: str, value: str) -> bool:
    """Whether a tool is present, by the only two detectors that need no secret: an executable on PATH, or a named
    environment variable being set."""
    if kind == "path":
        return shutil.which(value) is not None
    if kind == "env":
        return bool(os.environ.get(value))
    return False


@dataclass(frozen=True)
class Tool:
    id: str
    category: str
    title: str
    provides: str
    detect_kind: str
    detect_value: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["detect"] = {"kind": self.detect_kind, "value": self.detect_value}
        del d["detect_kind"], d["detect_value"]
        return d


def catalogue(path: Path | None = None) -> list[Tool]:
    doc = json.loads((path or PACKAGED_CATALOGUE).read_text())
    return [
        Tool(
            id=str(t["id"]),
            category=str(t["category"]),
            title=str(t["title"]),
            provides=str(t.get("provides") or ""),
            detect_kind=str(t["detect"]["kind"]),
            detect_value=str(t["detect"]["value"]),
        )
        for t in doc["tools"]
    ]


def availability(path: Path | None = None, detector: Detector | None = None) -> list[dict[str, Any]]:
    """Every catalogued tool, each marked available or not on this machine."""
    det = detector or _default_detector
    return [{**t.to_dict(), "available": det(t.detect_kind, t.detect_value)} for t in catalogue(path)]


def by_category(path: Path | None = None, detector: Detector | None = None) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for t in availability(path, detector):
        out.setdefault(t["category"], []).append(t)
    return out


def resolve(ids: tuple[str, ...], path: Path | None = None, detector: Detector | None = None) -> dict[str, Any]:
    """What a set of named tool ids resolves to here: available, present-in-catalogue-but-absent, or unknown."""
    cat = {t["id"]: t for t in availability(path, detector)}
    known = [cat[i] for i in ids if i in cat]
    return {
        "available": [t for t in known if t["available"]],
        "absent": [t for t in known if not t["available"]],
        "unknown": [i for i in ids if i not in cat],
    }
