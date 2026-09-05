import json

import pytest
from pydantic import ValidationError

from pravrudhi_kernel.schema import (
    Candidate,
    Citta,
    ClosureReport,
    EvidencePlan,
    GateReport,
    GateSide,
    Layer,
    LedgerEvent,
    Observation,
    Prediction,
    Preferences,
)

H = "0" * 64


def _candidate() -> Candidate:
    return Candidate(
        id="c-0001",
        surface="W3.adapter",
        bucket={"task_family": "gsm8k", "target_model": "Qwen/Qwen3-4B", "corpus": "gsm8k-train"},
        edit_family="optimiser",
        lineage=[],
        diff_ref=H,
        cost_est_gpu_h=0.25,
        residency_need="executor",
        predicted=Prediction(delta_in=0.02, delta_out=None, conf=0.4, hash=H),
        abstraction_level="madhyama",
        provenance="agama",
    )


ROUNDTRIP_CASES = [
    _candidate(),
    Observation(
        candidate_id="c-0001",
        per_item_scores_ref="research/runs/r-0001/items.jsonl",
        delta_in=0.013,
        delta_out=None,
        n_items=200,
        seeds=[11],
        cost_gpu_h=0.21,
        sensor_reads={},
        provenance="pratyaksha",
        run_hash=H,
        isolation="container",
    ),
    EvidencePlan(seeds=[11, 23, 37], heldout_rotation_id=None, sensors_to_read=[], stage="smoke", sequential_stage=0),
    Preferences(beta=1.0, lambda_=0.5, eta=0.1),
    Citta(version=1, surfaces={}, buckets={}, candidates={}, rho_pred={}),
    LedgerEvent(
        seq=0,
        t="2026-09-04T00:00:00.000Z",
        epoch=0,
        night=0,
        cycle=None,
        kind="audit",
        actor="kernel",
        candidate_id=None,
        surface=None,
        bucket=None,
        provenance=None,
        kernel_release="0.1.0",
        payload={"kind": "genesis", "kernel_release": "0.1.0", "schema_hash": H, "glossary_hash": H},
        prev_hash=H,
        this_hash=H,
    ),
    GateReport(
        id="L0",
        kind="loop",
        status="pass",
        tier="smoke",
        measure_class="n/a",
        code_gate=GateSide(verdict="pass", evidence=["ci=local"]),
        domain_gate=GateSide(verdict="pass", evidence=["no_claim"]),
        closure=ClosureReport(
            technical=Layer(verdict="pass", evidence=["make smoke green"]),
            empirical=Layer(verdict="pass", evidence=["no_claim"]),
            integrity=Layer(verdict="pass", evidence=["no T0 path touched outside epoch 0"]),
            artifacts=Layer(verdict="pass", evidence=["tree diff recorded"]),
            memory=Layer(verdict="pass", evidence=["journal entry appended"]),
            signoff=Layer(verdict="pending", evidence=[]),
        ),
        hetvabhasa=None,
        deviations=[],
        signoff={"by": None, "at": None, "note": None},
        ledger_head=None,
        kernel_release="0.1.0",
    ),
]


@pytest.mark.parametrize("obj", ROUNDTRIP_CASES, ids=lambda o: type(o).__name__)
def test_json_roundtrip_is_identity(obj: object) -> None:
    cls = type(obj)
    text = obj.model_dump_json(by_alias=True)  # type: ignore[attr-defined]
    back = cls.model_validate_json(text)  # type: ignore[attr-defined]
    assert back == obj
    assert json.loads(back.model_dump_json(by_alias=True)) == json.loads(text)  # type: ignore[attr-defined]


def test_unknown_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidencePlan(
            seeds=[1],
            heldout_rotation_id=None,
            sensors_to_read=[],
            stage="smoke",
            sequential_stage=0,
            extra=1,
        )  # type: ignore[call-arg]


def test_wire_key_is_english_export() -> None:
    d = json.loads(_candidate().model_dump_json())
    assert "provenance" in d and "pramana" not in d
