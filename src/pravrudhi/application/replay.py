"""`pravrudhi replay`: rebuild research/state.json from the ledger.

`check` verifies the chain and byte-equality with the committed state.
"""

from __future__ import annotations

from pathlib import Path

from pravrudhi_kernel.ledger import replay, verify, write_state
from pravrudhi_kernel.ledger.replay import state_bytes


def replay_command(ledger: Path, state: Path, *, check: bool = False) -> tuple[int, list[str]]:
    if not ledger.exists():
        return 2, [f"no ledger at {ledger}"]
    if check:
        r = verify(ledger)
        if not r.ok:
            return 1, [f"chain BROKEN at seq {r.first_bad_seq}: {r.reason}"]
    st = replay(ledger)
    if check and state.exists():
        if state.read_text() != state_bytes(st):
            return 1, [f"state.json DIFFERS from replay (ledger head {st.ledger_head}, state_hash {st.state_hash})"]
        return 0, [f"chain ok ({st.seq + 1} events); state.json matches replay; state_hash {st.state_hash}"]
    write_state(st, state)
    return 0, [f"wrote {state} ({st.seq + 1} events, head {st.ledger_head}, state_hash {st.state_hash})"]
