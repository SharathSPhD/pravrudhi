"""The recipe library: published training and evaluation recipes an objective may draw on.

NVIDIA's NeMo, Megatron-Bridge, NeMo-RL and NemoClaw skills are already a corpus of working recipes for the
operations this engine needs — corpus curation, supervised fine-tuning, LoRA, reinforcement learning, large-scale
pretraining, evaluation and sandboxed agent operation. Reimplementing any of that would be waste, so the engine
carries a catalogue rather than an implementation.

Two things follow, and both are deliberate. The catalogue ships with the wheel, so a user who installs Pravrudhi on
a machine with none of those skills still sees what exists and where to get it. And `availability` reports which
recipes are actually present here by looking for the skill directory, so the engine never implies a capability the
machine does not have.

Nothing in this module is evidence. A recipe becomes evidence when a night runs it and the ledger records the
result at the tier it passed.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PACKAGED_LIBRARY = Path(__file__).resolve().parents[1] / "assets" / "recipes" / "library.json"

# Where agent skills are installed. Overridable so a test never depends on the operator's home directory and so a
# packaged install can point at a different location.
SKILL_DIRS_ENV = "PRAVRUDHI_SKILL_DIRS"
DEFAULT_SKILL_DIRS = (Path.home() / ".claude" / "skills",)


@dataclass(frozen=True)
class Recipe:
    id: str
    capability: str
    title: str
    skill: str
    summary: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def skill_dirs() -> tuple[Path, ...]:
    raw = os.environ.get(SKILL_DIRS_ENV)
    if raw:
        return tuple(Path(p).expanduser() for p in raw.split(os.pathsep) if p.strip())
    return DEFAULT_SKILL_DIRS


def library(path: Path | None = None) -> list[Recipe]:
    doc = json.loads((path or PACKAGED_LIBRARY).read_text())
    return [
        Recipe(
            id=str(r["id"]),
            capability=str(r["capability"]),
            title=str(r["title"]),
            skill=str(r["skill"]),
            summary=str(r.get("summary") or ""),
            source=str(r.get("source") or ""),
        )
        for r in doc["recipes"]
    ]


def installed(dirs: tuple[Path, ...] | None = None) -> set[str]:
    """Skill names present on this machine."""
    out: set[str] = set()
    for d in dirs if dirs is not None else skill_dirs():
        if d.is_dir():
            out.update(p.name for p in d.iterdir() if p.is_dir())
    return out


def availability(path: Path | None = None, dirs: tuple[Path, ...] | None = None) -> list[dict[str, Any]]:
    """Every catalogued recipe, each marked available or not on this machine."""
    have = installed(dirs)
    return [{**r.to_dict(), "available": r.skill in have} for r in library(path)]


def by_capability(path: Path | None = None, dirs: tuple[Path, ...] | None = None) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in availability(path, dirs):
        out.setdefault(r["capability"], []).append(r)
    return out


def resolve(ids: tuple[str, ...], path: Path | None = None, dirs: tuple[Path, ...] | None = None) -> dict[str, Any]:
    """What an objective's named recipes resolve to here: known and available, known but absent, or unknown.

    An objective naming a recipe this build has never heard of is a real condition — a user may have written the
    file by hand — and it is reported rather than silently dropped."""
    cat = {r["id"]: r for r in availability(path, dirs)}
    known = [cat[i] for i in ids if i in cat]
    return {
        "available": [r for r in known if r["available"]],
        "absent": [r for r in known if not r["available"]],
        "unknown": [i for i in ids if i not in cat],
    }
