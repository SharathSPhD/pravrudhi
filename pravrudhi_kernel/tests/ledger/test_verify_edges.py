import json
from pathlib import Path

from pravrudhi_kernel.ledger import LedgerWriter, verify


def _ledger(tmp_path: Path) -> tuple[LedgerWriter, Path]:
    p = tmp_path / "l.jsonl"
    w = LedgerWriter.open(p, "0.1.0")
    w.append("spend", "executor", {"gpu_h": 1.0}, epoch=0, night=1)
    w.append("spend", "executor", {"gpu_h": 2.0}, epoch=0, night=1)
    return w, p


def test_empty_ledger(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    p.write_text("\n")
    r = verify(p)
    assert not r.ok and r.reason == "empty ledger"


def test_schema_error_names_line(tmp_path: Path) -> None:
    _, p = _ledger(tmp_path)
    lines = p.read_text().splitlines()
    lines[2] = '{"not": "an event"}'
    p.write_text("\n".join(lines) + "\n")
    r = verify(p)
    assert not r.ok and r.first_bad_seq == 2 and r.reason is not None and r.reason.startswith("schema")


def test_bad_genesis_prev_hash(tmp_path: Path) -> None:
    _, p = _ledger(tmp_path)
    lines = p.read_text().splitlines()
    row = json.loads(lines[0])
    row["prev_hash"] = "f" * 64
    lines[0] = json.dumps(row)
    p.write_text("\n".join(lines) + "\n")
    r = verify(p)
    assert not r.ok and r.first_bad_seq == 0 and r.reason == "bad genesis prev_hash"


def test_prev_hash_mismatch(tmp_path: Path) -> None:
    _, p = _ledger(tmp_path)
    lines = p.read_text().splitlines()
    row = json.loads(lines[2])
    row["prev_hash"] = "e" * 64
    lines[2] = json.dumps(row)
    p.write_text("\n".join(lines) + "\n")
    r = verify(p)
    assert not r.ok and r.first_bad_seq == 2 and r.reason == "prev_hash mismatch"


def test_timestamp_not_monotone_is_detected_even_with_valid_hashes(tmp_path: Path) -> None:
    p = tmp_path / "t.jsonl"
    ticks = iter(["2026-09-04T00:00:02.000Z", "2026-09-04T00:00:01.000Z"])
    w = LedgerWriter.open(p, "0.1.0", clock=lambda: next(ticks))
    # writer clamps a backwards clock to t_last, so the file stays monotone; force the violation on disk
    w.append("spend", "executor", {"gpu_h": 1.0}, epoch=0, night=1)
    lines = p.read_text().splitlines()
    row = json.loads(lines[1])
    assert row["t"] == "2026-09-04T00:00:02.000Z"
    # rebuild line 1 with an earlier t and a correct hash chain to isolate the monotonicity check
    from pravrudhi_kernel.ledger.writer import chain_hash

    row["t"] = "2026-09-04T00:00:00.000Z"
    body = {k: v for k, v in row.items() if k != "this_hash"}
    row["this_hash"] = chain_hash(row["prev_hash"], body)
    lines[1] = json.dumps(row)
    p.write_text("\n".join(lines) + "\n")
    r = verify(p)
    assert not r.ok and r.reason == "timestamp not monotone"
