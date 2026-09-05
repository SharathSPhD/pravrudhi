"""Two writers on one ledger interleave with a head_resync audit; the chain never forks (ADR-0013)."""
from pravrudhi_kernel.ledger import LedgerWriter
from pravrudhi_kernel.ledger.verify import iter_events, verify


def test_stale_head_resyncs_instead_of_forking(tmp_path):
    p = tmp_path / "ledger.jsonl"
    a = LedgerWriter.open(p, "0.1.0")
    b = LedgerWriter.open(p, "0.1.0")
    a.append("audit", "kernel", {"kind": "x"}, epoch=0, night=1)
    a.append("audit", "kernel", {"kind": "y"}, epoch=0, night=1)
    ev = b.append("audit", "auditor", {"kind": "z"}, epoch=0, night=2)  # b's head is stale by two rows
    res = verify(p)
    assert res.ok and res.n == 5
    kinds = [e.payload["kind"] for e in iter_events(p)]
    assert kinds == ["genesis", "x", "y", "head_resync", "z"]
    assert ev.seq == 4
    a.append("audit", "kernel", {"kind": "w"}, epoch=0, night=1)  # a is now stale too
    assert verify(p).ok and verify(p).n == 7
