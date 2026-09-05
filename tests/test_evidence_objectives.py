"""The evidence record omitted the user's intent and could not distinguish missing evidence from no effect."""

from pathlib import Path

import pytest

from pravrudhi.application.evidence import render_objectives
from pravrudhi.application.objectives import Benchmark, Objective, progress, write
from pravrudhi_kernel.ledger import LedgerWriter


@pytest.mark.parametrize("conditions", [("base", "candidate"), ("base",), ("candidate",), ()])
def test_objectives_preserve_intent_and_measurement_states(tmp_path: Path, conditions: tuple[str, ...]) -> None:
    measured = Objective(
        id="legal-intent",
        intent="Answer questions of law with the statute relied on.\nKeep the user's wording intact.",
        track="nyaya",
        benchmarks=(Benchmark(id="law", tool="lm-eval", metric="law acc,none"),),
    )
    unmeasured = Objective(
        id="unmeasured-intent",
        intent="Explain the reasoning behind each answer.",
        track="reasoning",
        benchmarks=measured.benchmarks,
    )
    write(tmp_path, measured)
    write(tmp_path, unmeasured)
    ledger = tmp_path / "research" / "ledger.jsonl"
    writer = LedgerWriter.open(ledger, "0.1.0")
    for condition in conditions:
        writer.append(
            "audit",
            "auditor",
            {
                "kind": "external_eval",
                "severity": "info",
                "tier": "external",
                "track": measured.track,
                "condition": condition,
                "tool": "lm-eval",
                "metrics": {"law": {"acc,none": 0.4 if condition == "base" else 0.5, "acc_stderr,none": 0.01}},
                "n_samples": {"law": 1000},
            },
            epoch=0,
            night=1,
        )

    document = render_objectives(tmp_path)
    assert measured.intent in document
    assert unmeasured.intent in document
    assert measured.track in document and unmeasured.track in document
    section = document.split(f"## {unmeasured.id}")[1]
    assert "unmeasured" in section.lower()
    assert "no external result" in section
    assert "| law acc,none |" not in section
    assert "0.0000" not in section
    (standing,) = progress(measured, ledger)
    if standing.state == "measured":
        assert standing.baseline is not None and standing.latest is not None
        assert standing.delta is not None and standing.delta_lo is not None and standing.delta_hi is not None
        assert (
            f"| law acc,none | {standing.baseline.value:.4f} | {standing.latest.value:.4f} | "
            f"{standing.delta:+.4f} | [{standing.delta_lo:+.4f}, {standing.delta_hi:+.4f}] |"
        ) in document
    elif standing.state == "baseline_only":
        assert standing.baseline is not None
        assert f"{standing.baseline.value:.4f}" in document
        assert standing.reason in document
        assert "0.0000" not in document
    else:
        assert standing.reason in document
        assert "| law acc,none |" not in document


def test_workspace_without_ledger_is_unmeasured(tmp_path: Path) -> None:
    write(tmp_path, Objective("new-intent", "Explain statutes.", "nyaya", (Benchmark("law", "lm-eval", "law"),)))
    document = render_objectives(tmp_path)
    assert "unmeasured" in document.lower()
    assert "| law |" not in document
    assert "0.0000" not in document


def test_workspace_without_objectives_says_so(tmp_path: Path) -> None:
    assert "No objectives" in render_objectives(tmp_path)
