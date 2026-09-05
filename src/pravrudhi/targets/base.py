"""The Target protocol (spec §3).

A Target declares what may change and how a change is evaluated; it never scores.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from pravrudhi_kernel.sandbox import JobSpec
from pravrudhi_kernel.schema import Candidate


class Surface(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str  # e.g. W3.adapter
    strategies: list[str]
    execution_families: list[str]


class Artefact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: str  # baseline | adapter | harness
    path: str | None  # host path of the adapter/harness dir; None for the unmodified baseline
    content_hash: str


class CanarySpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    margin: float = Field(gt=0.0)
    direction: str  # "non_inferior" (score must not drop by margin) | "ratio_floor" | "abs_increase_cap"


class Target(Protocol):
    name: str

    def surfaces(self) -> list[Surface]: ...
    def baseline(self) -> Artefact: ...
    def materialise(self, cand: Candidate, recipe: dict[str, object], work: Path) -> Path: ...
    def train_job(self, work: Path, recipe: dict[str, object], resources: dict[str, str]) -> JobSpec | None: ...
    def canaries(self) -> list[CanarySpec]: ...
