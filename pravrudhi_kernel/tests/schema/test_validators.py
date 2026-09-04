import pytest
from pydantic import ValidationError

from pravrudhi_kernel.schema import (
    Candidate,
    ClosureReport,
    GateReport,
    GateSide,
    Layer,
    Prediction,
    Preferences,
)

H = "0" * 64


def _cand(surface: str) -> Candidate:
    return Candidate(
        id="c-0002",
        surface=surface,
        bucket={"task_family": "x", "target_model": "y", "corpus": "z"},
        edit_family="f",
        lineage=[],
        diff_ref=H,
        cost_est_gpu_h=0.1,
        residency_need="either",
        predicted=Prediction(delta_in=0.0, delta_out=None, conf=0.0, hash=H),
        abstraction_level="para",
        provenance="agama",
    )


def test_preferences_forbid_t0_by_construction() -> None:
    p = Preferences(beta=1.0, lambda_=0.5, eta=0.1)
    assert p.t0_forbidden is True
    with pytest.raises(ValidationError):
        Preferences(beta=1.0, lambda_=0.5, eta=0.1, t0_forbidden=False)  # type: ignore[arg-type]


def test_preferences_reject_t0_touching_candidate() -> None:
    p = Preferences(beta=1.0, lambda_=0.5, eta=0.1)
    assert p.admits(_cand("W3.adapter")) is True
    assert p.admits(_cand("T0.kernel")) is False


def test_candidate_is_agama_at_birth() -> None:
    with pytest.raises(ValidationError):
        Candidate.model_validate(_cand("W3.adapter").model_dump() | {"provenance": "pratyaksha"})


def _gate(status: str, hetv: str | None, verdict: str = "pass") -> GateReport:
    layer = Layer(verdict="pass", evidence=["x"])
    return GateReport(
        id="L9",
        kind="loop",
        status=status,
        tier="smoke",
        measure_class="n/a",
        code_gate=GateSide(verdict=verdict, evidence=["x"]),
        domain_gate=GateSide(verdict=verdict, evidence=["x"]),
        closure=ClosureReport(
            technical=layer,
            empirical=layer,
            integrity=layer,
            artifacts=layer,
            memory=layer,
            signoff=Layer(verdict="pending", evidence=[]),
        ),
        hetvabhasa=hetv,
        deviations=[],
        signoff={"by": None, "at": None, "note": None},
        ledger_head=None,
        kernel_release="0.1.0",
    )


def test_pruned_requires_hetvabhasa() -> None:
    with pytest.raises(ValidationError):
        _gate("pruned", None, verdict="pruned")
    assert _gate("pruned", "asiddha", verdict="pruned").hetvabhasa == "asiddha"


def test_pass_requires_both_gates_pass() -> None:
    with pytest.raises(ValidationError):
        _gate("pass", None, verdict="fail")
