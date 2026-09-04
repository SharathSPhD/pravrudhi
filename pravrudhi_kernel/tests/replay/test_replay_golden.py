import importlib.util
import json
from pathlib import Path

from pravrudhi_kernel.ledger import replay, verify
from pravrudhi_kernel.ledger.replay import badge, state_bytes
from pravrudhi_kernel.schema.common import EventKind

GOLDEN = Path(__file__).parent / "golden"


def gen_main(out: Path) -> None:
    spec = importlib.util.spec_from_file_location("gen_golden", Path(__file__).parent / "gen_golden.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main(out)


def test_golden_ledgers_regenerate_byte_identically(tmp_path: Path) -> None:
    gen_main(tmp_path)
    for k in range(5):
        assert (tmp_path / f"ledger_{k}.jsonl").read_bytes() == (GOLDEN / f"ledger_{k}.jsonl").read_bytes()


def test_golden_ledgers_verify_and_cover_every_kind() -> None:
    kinds_all: set[str] = set()
    for k in range(5):
        p = GOLDEN / f"ledger_{k}.jsonl"
        r = verify(p)
        assert r.ok and r.n >= 200, (k, r)
        kinds_all |= {json.loads(line)["kind"] for line in p.read_text().splitlines()}
    assert kinds_all == {e.value for e in EventKind}


def test_replay_matches_committed_state_bytes() -> None:
    for k in range(5):
        st = replay(GOLDEN / f"ledger_{k}.jsonl")
        assert state_bytes(st) == (GOLDEN / f"state_{k}.json").read_text()
        assert st.state_hash == json.loads((GOLDEN / f"state_{k}.json").read_text())["state_hash"]


def test_badges_follow_the_rule() -> None:
    st = replay(GOLDEN / "ledger_0.jsonl")
    assert set(st.badges.values()) >= {"grey", "amber", "green", "red"}
    for cid, c in st.candidates.items():
        assert st.badges[cid] == badge(c)
        if c.pruned or c.audit_high:
            assert st.badges[cid] == "red"
        elif c.promoted:
            assert st.badges[cid] == "green"


def test_replay_is_pure_and_prefix_consistent(tmp_path: Path) -> None:
    src = GOLDEN / "ledger_1.jsonl"
    lines = src.read_text().splitlines()
    half = tmp_path / "half.jsonl"
    half.write_text("\n".join(lines[:120]) + "\n")
    a = replay(half)
    b = replay(half)
    assert state_bytes(a) == state_bytes(b)
    assert a.seq == 119
