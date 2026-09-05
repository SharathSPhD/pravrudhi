"""An objective must refuse to be unmeasurable, and its progress must distinguish 'no data' from 'no effect'."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pravrudhi_kernel.ledger import LedgerWriter

from pravrudhi.application import recipes
from pravrudhi.application.objectives import (
    Benchmark,
    Objective,
    ObjectiveError,
    copy_example,
    examples,
    load,
    load_all,
    parse,
    problems,
    progress,
    summary,
    write,
)

GOOD = {
    "id": "legal-mvp",
    "intent": "answer a question of law with the statute it relied on",
    "track": "nyaya",
    "benchmarks": [{"id": "law", "tool": "lm-eval", "metric": "mmlu_professional_law acc,none"}],
}


def test_parse_accepts_a_complete_objective() -> None:
    o = parse(GOOD)
    assert o.id == "legal-mvp"
    assert o.benchmarks[0].direction == "up"
    assert o.target_delta is None


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        ({"intent": ""}, "no intent"),
        ({"track": ""}, "no track"),
        ({"benchmarks": []}, "declares no benchmark"),
        ({"id": "Legal MVP"}, "lowercase letters"),
        ({"benchmarks": [{"id": "x", "metric": "m", "direction": "sideways"}]}, "direction must be"),
        ({"benchmarks": [{"id": "x"}]}, "names no metric"),
    ],
)
def test_parse_refuses_an_objective_that_could_not_be_measured(mutate: dict, fragment: str) -> None:
    with pytest.raises(ObjectiveError) as e:
        parse({**GOOD, **mutate})
    assert fragment in str(e.value)


def _ledger(path: Path, rows: list[tuple[str, float, float]]) -> Path:
    """Build a real ledger with the real writer. The hash chain is what makes a ledger a ledger, so a hand-written
    JSONL stand-in would test something the engine never reads."""
    w = LedgerWriter.open(path, "0.1.0")
    for condition, value, stderr in rows:
        w.append("audit", "auditor", _payload(condition, value, stderr), epoch=0, night=1)
    return path


def _payload(condition: str, value: float, stderr: float, track: str = "nyaya") -> dict:
    return {
        "kind": "external_eval",
        "severity": "info",
        "tier": "external",
        "track": track,
        "condition": condition,
        "model": "Qwen/Qwen3-0.6B",
        "sha256": "0" * 64,
        "tool": "lm-eval",
        "n_samples": {"mmlu_professional_law": 1000},
        "metrics": {"mmlu_professional_law": {"acc,none": value, "acc_stderr,none": stderr}},
    }


def test_progress_says_unmeasured_rather_than_zero(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "l.jsonl", [])
    (p,) = progress(parse(GOOD), led)
    assert p.state == "unmeasured"
    assert p.delta is None
    assert "no external result" in p.reason


def test_progress_distinguishes_a_baseline_with_nothing_to_compare(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "l.jsonl", [("base", 0.40, 0.01)])
    (p,) = progress(parse(GOOD), led)
    assert p.state == "baseline_only"
    assert p.baseline is not None and p.baseline.value == pytest.approx(0.40)
    assert p.latest is None and p.delta is None


def test_progress_reports_a_measured_delta_with_its_interval(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "l.jsonl", [("base", 0.40, 0.01), ("adapter:c-0001", 0.50, 0.01)])
    (p,) = progress(parse(GOOD), led)
    assert p.state == "measured"
    assert p.delta == pytest.approx(0.10, abs=1e-9)
    assert p.delta_lo is not None and p.delta_hi is not None and p.delta_lo < p.delta < p.delta_hi
    assert p.significant is True


def test_a_delta_whose_interval_spans_zero_is_not_called_an_improvement(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "l.jsonl", [("base", 0.40, 0.05), ("adapter:c-0001", 0.41, 0.05)])
    (p,) = progress(parse(GOOD), led)
    assert p.delta == pytest.approx(0.01, abs=1e-9)
    assert p.significant is False


def test_a_baseline_replication_is_not_a_candidate(tmp_path: Path) -> None:
    """`base-replicate` re-measures the baseline. Counting it as a candidate would report the noise floor as an
    effect, which is the error the noise-floor study exists to prevent."""
    led = _ledger(tmp_path / "l.jsonl", [("base", 0.40, 0.01), ("base-replicate", 0.39, 0.01)])
    (p,) = progress(parse(GOOD), led)
    assert p.state == "baseline_only"


def test_target_is_met_only_when_the_interval_also_excludes_zero(tmp_path: Path) -> None:
    spec = {**GOOD, "target_delta": 0.05}
    led = _ledger(tmp_path / "l.jsonl", [("base", 0.40, 0.05), ("adapter:c-1", 0.47, 0.05)])
    (p,) = progress(parse(spec), led)
    assert p.delta == pytest.approx(0.07, abs=1e-9)  # exceeds the target
    assert p.significant is False
    assert p.met is False  # but the interval spans zero, so the target is not met


def test_write_then_load_round_trips(tmp_path: Path) -> None:
    o = parse(GOOD)
    p = write(tmp_path, o)
    assert p == tmp_path / ".pravrudhi" / "objectives" / "legal-mvp.yaml"
    back = load(p)
    assert back.intent == o.intent and back.track == o.track and back.benchmarks == o.benchmarks
    assert yaml.safe_load(p.read_text())["created"]  # stamped on write


def test_a_malformed_file_is_skipped_but_reported(tmp_path: Path) -> None:
    write(tmp_path, parse(GOOD))
    bad = tmp_path / ".pravrudhi" / "objectives" / "broken.yaml"
    bad.write_text("intent: no track and no benchmarks\n")
    assert [o.id for o in load_all(tmp_path)] == ["legal-mvp"]
    assert [f for f, _ in problems(tmp_path)] == ["broken.yaml"]


def test_the_shipped_examples_all_load() -> None:
    assert "prabhasa-nyaya" in examples()
    for name in examples():
        o = load(Path(__file__).resolve().parents[1] / "src" / "pravrudhi" / "assets" / "objectives" / f"{name}.yaml")
        assert o.intent and o.benchmarks


def test_copy_example_lands_in_the_workspace(tmp_path: Path) -> None:
    p = copy_example(tmp_path, "prabhasa-nyaya")
    assert p.exists()
    assert load(p).domain == "legal"
    with pytest.raises(ObjectiveError):
        copy_example(tmp_path, "no-such-example")


def test_summary_is_honest_about_a_workspace_with_no_ledger(tmp_path: Path) -> None:
    s = summary(tmp_path, parse(GOOD))
    assert s["intent"] == GOOD["intent"]
    assert s["progress"][0]["state"] == "unmeasured"
    assert "no ledger" in s["progress"][0]["reason"]


def test_recipe_library_marks_what_is_absent(tmp_path: Path) -> None:
    lib = tmp_path / "library.json"
    lib.write_text(
        json.dumps(
            {
                "version": 1,
                "recipes": [
                    {"id": "here", "capability": "finetune", "title": "T", "skill": "present-skill", "summary": "", "source": ""},
                    {"id": "gone", "capability": "finetune", "title": "T", "skill": "missing-skill", "summary": "", "source": ""},
                ],
            }
        )
    )
    skills = tmp_path / "skills"
    (skills / "present-skill").mkdir(parents=True)
    got = {r["id"]: r["available"] for r in recipes.availability(lib, (skills,))}
    assert got == {"here": True, "gone": False}
    res = recipes.resolve(("here", "gone", "invented"), lib, (skills,))
    assert [r["id"] for r in res["available"]] == ["here"]
    assert [r["id"] for r in res["absent"]] == ["gone"]
    assert res["unknown"] == ["invented"]


def test_the_shipped_library_is_wellformed() -> None:
    lib = recipes.library()
    assert len(lib) >= 10
    assert len({r.id for r in lib}) == len(lib)
    assert {r.capability for r in lib} >= {"corpus", "finetune", "evaluate"}


def test_stderr_key_is_derived_from_the_metric_not_from_gsm8k() -> None:
    """Regression. The earlier form substituted the literal string `exact_match`, so for a metric named `acc,none`
    the lookup fell back to the value itself and the rendered plus-or-minus column printed the value twice."""
    from pravrudhi.application.external import stderr_key

    assert stderr_key("exact_match,strict-match") == "exact_match_stderr,strict-match"
    assert stderr_key("acc,none") == "acc_stderr,none"
    assert stderr_key("acc_norm,none") == "acc_norm_stderr,none"
    assert stderr_key("bleu") == "bleu_stderr"
