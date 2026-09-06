"""Loom milestone 4's first interpretation job: request preparation and ledger admission for a linear probe."""
import json
from pathlib import Path

from pravrudhi.application.interp import admit_probe, probe_request
from pravrudhi.application.loom import MonitorSpec
from pravrudhi_kernel.ledger import LedgerWriter


def test_probe_request_names_only_what_the_spec_carries():
    spec = MonitorSpec(name="m1", feature="refusal", threshold=None)
    req = probe_request(spec, Path("/in/items.jsonl"))
    assert req == {"items_path": "/in/items.jsonl", "monitor": {"feature": "refusal"}}


def test_probe_request_includes_threshold_when_declared():
    spec = MonitorSpec(name="m1", feature="refusal", threshold=0.8)
    req = probe_request(spec, Path("/in/items.jsonl"))
    assert req["monitor"] == {"feature": "refusal", "threshold": 0.8}


def _job_output(out_dir: Path) -> None:
    out_dir.mkdir(parents=True)
    probe = {
        "feature": "refusal",
        "layer": 12,
        "n_train": 80,
        "n_test": 20,
        "metric": "accuracy",
        "accuracy": 0.85,
        "weights_sha256": "a" * 64,
    }
    meta = {
        "job": "probe_feature",
        "model_sha256": "b" * 64,
        "adapter_sha256": None,
        "items_sha256": "c" * 64,
        "monitor_sha256": "d" * 64,
        "wall_s": 12.3,
        **probe,
    }
    (out_dir / "probe.json").write_text(json.dumps(probe))
    (out_dir / "job_meta.json").write_text(json.dumps(meta))


def test_admit_probe_records_audit_row_by_hash(tmp_path):
    (tmp_path / "research").mkdir()
    LedgerWriter.open(tmp_path / "research" / "ledger.jsonl", "0.1.0")
    out_dir = tmp_path / "out"
    _job_output(out_dir)

    row = admit_probe(tmp_path, out_dir, track="H", night=3)

    assert row["kind"] == "interp_probe"
    assert row["tier"] == "probe"
    assert row["track"] == "H"
    assert row["feature"] == "refusal"
    assert row["layer"] == 12
    assert row["accuracy"] == 0.85
    assert row["model_sha256"] == "b" * 64
    assert len(row["sha256"]) == 64
    assert row["file"] == str((out_dir / "probe.json").relative_to(tmp_path))


def test_admit_probe_seq_advances_the_chain(tmp_path):
    (tmp_path / "research").mkdir()
    LedgerWriter.open(tmp_path / "research" / "ledger.jsonl", "0.1.0")
    out1, out2 = tmp_path / "out1", tmp_path / "out2"
    _job_output(out1)
    _job_output(out2)

    r1 = admit_probe(tmp_path, out1, track="H", night=1)
    r2 = admit_probe(tmp_path, out2, track="H", night=1)

    assert r2["seq"] == r1["seq"] + 1
