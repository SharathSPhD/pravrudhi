"""`replay --verify` must distinguish a stale state view from a diverging one."""
import json

from pravrudhi.application.replay import replay_command
from pravrudhi_kernel.ledger import LedgerWriter


def _ledger(tmp_path):
    p = tmp_path / "ledger.jsonl"
    w = LedgerWriter.open(p, "0.1.0")
    w.append("audit", "kernel", {"kind": "a"}, epoch=0, night=1)
    return p, w


def test_stale_state_is_regenerated_not_flagged(tmp_path):
    p, w = _ledger(tmp_path)
    st = tmp_path / "state.json"
    assert replay_command(p, st)[0] == 0
    w.append("audit", "kernel", {"kind": "b"}, epoch=0, night=1)  # a night appends; the snapshot is now stale
    code, msgs = replay_command(p, st, check=True)
    assert code == 0 and "STALE" in msgs[0]
    assert replay_command(p, st, check=True)[0] == 0  # regenerated, so now it matches


def test_edited_state_diverges_and_fails(tmp_path):
    p, _ = _ledger(tmp_path)
    st = tmp_path / "state.json"
    replay_command(p, st)
    d = json.loads(st.read_text())
    d["ledger_head"] = "0" * 64  # same seq, different content: not a valid snapshot of this ledger
    st.write_text(json.dumps(d))
    code, msgs = replay_command(p, st, check=True)
    assert code == 1 and "DIVERGES" in msgs[0]


def test_broken_chain_still_fails_first(tmp_path):
    p, _ = _ledger(tmp_path)
    st = tmp_path / "state.json"
    replay_command(p, st)
    p.write_text(p.read_text().replace('"kind":"a"', '"kind":"tampered"'))
    code, msgs = replay_command(p, st, check=True)
    assert code == 1 and "BROKEN" in msgs[0]
