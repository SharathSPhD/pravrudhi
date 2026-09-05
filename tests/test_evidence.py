from pathlib import Path

from pravrudhi.application.evidence import render_noise_floor
from pravrudhi_kernel.ledger import LedgerWriter

H = "a" * 64


def test_render_noise_floor_is_deterministic_and_reads_only_the_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    w = LedgerWriter.open(ledger, "0.1.0")
    w.append(
        "audit",
        "kernel",
        {"kind": "study_start", "severity": "info", "study": "noise_floor", "design": {"k": 4}},
        epoch=0,
        night=0,
    )
    bucket = {"task_family": "t", "target_model": "m", "corpus": "c"}
    for seed, v in ((0, 0.5), (1, 0.75)):
        w.append(
            "observe",
            "kernel",
            {
                "study": "noise_floor",
                "rotation_id": "rot1",
                "seed_index": seed,
                "isolation": "container",
                "observed": {"value": v, "n_items": 4},
                "hashes": {"model": H},
                "job": {"tok_s": 100.0},
            },
            epoch=0,
            night=0,
            cycle=seed + 1,
            candidate_id="c-0000",
            surface="W3.adapter",
            bucket=bucket,
            provenance="pratyaksha",
        )
    a = render_noise_floor(ledger, None)
    b = render_noise_floor(ledger, None)
    assert a == b and "| 2 | rot1 | 0 | 0.5000 | 4 |" in a and "Runs: 2; items scored: 8; pooled pass rate 0.6250" in a
    assert "Wilson 95%" in a and "k=4" in a
