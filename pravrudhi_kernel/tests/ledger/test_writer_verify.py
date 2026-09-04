import json
from collections.abc import Callable
from pathlib import Path

import pytest

from pravrudhi_kernel.ledger import ChainBroken, LedgerWriter, verify


def clock() -> Callable[[], str]:
    n = [0]

    def tick() -> str:
        n[0] += 1
        return f"2026-09-04T00:{(n[0] // 60) % 60:02d}:{n[0] % 60:02d}.000Z"

    return tick


@pytest.fixture
def ledger(tmp_path: Path) -> tuple[LedgerWriter, Path]:
    p = tmp_path / "research" / "ledger.jsonl"
    w = LedgerWriter.open(p, "0.1.0", clock=clock())
    return w, p


def test_open_writes_genesis_and_head(ledger: tuple[LedgerWriter, Path]) -> None:
    w, p = ledger
    lines = p.read_text().splitlines()
    assert len(lines) == 1
    g = json.loads(lines[0])
    assert g["seq"] == 0 and g["kind"] == "audit" and g["payload"]["kind"] == "genesis"
    head = json.loads(w.head_path.read_text())
    assert head == {"seq": 0, "this_hash": g["this_hash"]}
    assert verify(p).ok


def test_append_chains_and_verifies(ledger: tuple[LedgerWriter, Path]) -> None:
    w, p = ledger
    ev = w.append(
        "propose",
        "proposer",
        {"op": "patch"},
        epoch=0,
        night=1,
        cycle=1,
        candidate_id="c-0001",
        surface="W3.adapter",
        bucket={"task_family": "a", "target_model": "b", "corpus": "c"},
        provenance="agama",
    )
    ev2 = w.append(
        "spend", "executor", {"gpu_h": 0.1, "run_id": "r1"}, epoch=0, night=1, cycle=1, candidate_id="c-0001"
    )
    assert ev.seq == 1 and ev2.seq == 2 and ev2.prev_hash == ev.this_hash
    r = verify(p)
    assert r.ok and r.n == 3 and r.head_hash == ev2.this_hash


def test_refused_event_leaves_file_untouched(ledger: tuple[LedgerWriter, Path]) -> None:
    w, p = ledger
    before = p.read_bytes()
    with pytest.raises(ValueError):
        w.append("observe", "kernel", {}, epoch=0, night=1)  # observe requires provenance
    with pytest.raises(ValueError):
        w.append(
            "observe", "executor", {}, epoch=0, night=1, provenance="pratyaksha"
        )  # only the kernel writes observe
    assert p.read_bytes() == before


def test_tamper_is_detected_and_reopen_refused(ledger: tuple[LedgerWriter, Path]) -> None:
    w, p = ledger
    for i in range(5):
        w.append("spend", "executor", {"gpu_h": 0.1 * i}, epoch=0, night=1)
    lines = p.read_text().splitlines()
    row = json.loads(lines[3])
    row["payload"]["gpu_h"] = 99.0
    lines[3] = json.dumps(row)
    p.write_text("\n".join(lines) + "\n")
    r = verify(p)
    assert not r.ok and r.first_bad_seq == 3 and r.reason == "this_hash mismatch"
    with pytest.raises(ChainBroken):
        LedgerWriter.open(p, "0.1.0")


def test_reopen_continues_chain(tmp_path: Path) -> None:
    p = tmp_path / "ledger.jsonl"
    w = LedgerWriter.open(p, "0.1.0", clock=clock())
    w.append("spend", "executor", {"gpu_h": 1.0}, epoch=0, night=1)
    w2 = LedgerWriter.open(p, "0.1.0", clock=clock())
    ev = w2.append("spend", "executor", {"gpu_h": 2.0}, epoch=0, night=1)
    assert ev.seq == 2 and verify(p).ok


def test_seq_gap_detected(ledger: tuple[LedgerWriter, Path]) -> None:
    w, p = ledger
    w.append("spend", "executor", {"gpu_h": 1.0}, epoch=0, night=1)
    w.append("spend", "executor", {"gpu_h": 1.0}, epoch=0, night=1)
    lines = p.read_text().splitlines()
    p.write_text("\n".join([lines[0], lines[2]]) + "\n")
    r = verify(p)
    assert not r.ok and r.first_bad_seq == 1
