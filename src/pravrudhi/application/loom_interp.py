"""An objective's monitors and gates lived only in the reviewer's head, so a Loom program never carried them.

This module is milestone 3 of Loom in Pravrudhi: it derives `InterpretationSpec` proposals from an `Objective`
so that a compiled plan's rendered program names the checks its own objective implies, rather than leaving a
human to hand-write a `monitor` decl after reading the objective's YAML. `specs_from_objective` never invents a
number or a feature name that the objective or a checked-in config did not already carry: a benchmark without a
`target_delta` produces a monitor with an unspecified threshold, and a domain absent from the interpretation
defaults produces no feature at all. `program_with_interpretation` glues the resulting specs onto a plan's
lowered source so the two halves -- capability steps and interpretation terms -- travel as one program that
still round-trips through `lift`.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from pravrudhi.application.intent import IntentPlanProposal
from pravrudhi.application.loom import (
    FeatureSpec,
    InterpretationSpec,
    MonitorSpec,
    lower,
    lower_interpretation,
)
from pravrudhi.application.objectives import Objective

INTERPRETATION_DEFAULTS_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "configs" / "interpretation_defaults.yaml"
)

_UNSAFE_IDENT_CHARS = re.compile(r"[^A-Za-z0-9_]")


def _ident_safe(text: str) -> str:
    """A benchmark id or metric name may carry punctuation a Loom identifier cannot."""
    safe = _UNSAFE_IDENT_CHARS.sub("_", text)
    return safe if safe and not safe[0].isdigit() else f"_{safe}"


@lru_cache(maxsize=1)
def _domain_features(path: Path) -> dict[str, tuple[str, ...]]:
    if not path.exists():
        return {}
    raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    return {str(domain): tuple(str(name) for name in (names or [])) for domain, names in raw.items()}


def specs_from_objective(objective: Objective) -> tuple[InterpretationSpec, ...]:
    """The interpretation terms one objective implies: never a guess, always traceable to the objective or config.

    A `FeatureSpec` is proposed for each feature name the checked-in `interpretation_defaults.yaml` lists under
    `objective.domain`; a domain missing from that mapping proposes no feature. A `MonitorSpec` is proposed for
    each declared benchmark, named after its metric and reading a feature named after the benchmark id, gated at
    `objective.target_delta` when the objective has one and left unspecified (a comment, once rendered) when it
    does not.
    """
    specs: list[InterpretationSpec] = []
    for name in _domain_features(INTERPRETATION_DEFAULTS_PATH).get(objective.domain, ()):
        specs.append(FeatureSpec(_ident_safe(name)))
    for benchmark in objective.benchmarks:
        specs.append(
            MonitorSpec(
                name=_ident_safe(benchmark.metric),
                feature=_ident_safe(benchmark.id),
                threshold=objective.target_delta,
            )
        )
    return tuple(specs)


def program_with_interpretation(objective: Objective, plan: IntentPlanProposal) -> str:
    """A plan's Loom source plus the interpretation terms its objective implies, as one program.

    Nothing here executes: `lower(plan)` renders the capability steps exactly as `lower` always has, and
    `lower_interpretation` appends the monitors (and any domain features) `specs_from_objective` proposed. The
    result still parses with `lift`, and `interpretation_terms` recovers every monitor this function added.
    """
    return lower(plan) + lower_interpretation(specs_from_objective(objective))
