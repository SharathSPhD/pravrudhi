"""Interpretation specs derived from an objective used to exist only as an idea, never checked against a program.

These tests run `specs_from_objective` and `program_with_interpretation` over the three objectives shipped in
`src/pravrudhi/assets/objectives/`, so the derivation is checked against real intents rather than a fixture
invented for the test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pravrudhi.application.intent import compile_intent
from pravrudhi.application.loom import FeatureSpec, MonitorSpec, interpretation_terms, lift
from pravrudhi.application.loom_interp import program_with_interpretation, specs_from_objective
from pravrudhi.application.objectives import PACKAGED_OBJECTIVES, Objective, load

_OBJECTIVE_PATHS = sorted(PACKAGED_OBJECTIVES.glob("*.yaml"))
_OBJECTIVE_IDS = [p.stem for p in _OBJECTIVE_PATHS]


@pytest.fixture(params=_OBJECTIVE_PATHS, ids=_OBJECTIVE_IDS)
def objective(request: pytest.FixtureRequest) -> Objective:
    path: Path = request.param
    return load(path)


def test_shipped_objectives_exist() -> None:
    assert _OBJECTIVE_IDS == ["code-harness", "math-reasoning", "prabhasa-nyaya"]


def test_one_monitor_per_benchmark(objective: Objective) -> None:
    specs = specs_from_objective(objective)
    monitors = [s for s in specs if isinstance(s, MonitorSpec)]
    assert len(monitors) == len(objective.benchmarks)
    assert [m.name for m in monitors] == [_ident_safe(b.metric) for b in objective.benchmarks]


def test_monitor_threshold_is_target_delta_or_unspecified(objective: Objective) -> None:
    monitors = [s for s in specs_from_objective(objective) if isinstance(s, MonitorSpec)]
    for m in monitors:
        assert m.threshold == objective.target_delta


def test_feature_specs_only_for_configured_domain(objective: Objective) -> None:
    features = [s for s in specs_from_objective(objective) if isinstance(s, FeatureSpec)]
    if objective.domain == "legal":
        assert [f.name for f in features] == ["cites_statute", "abstains_when_unsure"]
    else:
        assert features == []


def test_program_with_interpretation_lifts_cleanly(objective: Objective) -> None:
    plan = compile_intent(objective, recipes=())
    program = program_with_interpretation(objective, plan)
    parsed = lift(program)  # must not raise
    terms = interpretation_terms(parsed)
    recovered_monitors = {(m.name, m.feature, m.threshold) for m in terms if isinstance(m, MonitorSpec)}
    expected_monitors = {
        (m.name, m.feature, m.threshold)
        for m in specs_from_objective(objective)
        if isinstance(m, MonitorSpec)
    }
    assert recovered_monitors == expected_monitors


def test_unspecified_threshold_is_a_comment_not_a_number() -> None:
    objective = load(PACKAGED_OBJECTIVES / "code-harness.yaml")
    assert objective.target_delta is None
    plan = compile_intent(objective, recipes=())
    program = program_with_interpretation(objective, plan)
    assert "threshold unspecified" in program
    assert "probe_r2 >" not in program


def test_specified_threshold_renders_a_real_assert() -> None:
    objective = load(PACKAGED_OBJECTIVES / "prabhasa-nyaya.yaml")
    assert objective.target_delta == 0.03
    plan = compile_intent(objective, recipes=())
    program = program_with_interpretation(objective, plan)
    assert "probe_r2 > 0.03;" in program


def _ident_safe(text: str) -> str:
    import re

    safe = re.sub(r"[^A-Za-z0-9_]", "_", text)
    return safe if safe and not safe[0].isdigit() else f"_{safe}"
