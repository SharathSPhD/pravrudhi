"""`pravrudhi replay`: rebuild research/state.json from the ledger.

`check` verifies the chain, then distinguishes two failures that must never be confused: a state view that is merely
STALE (a valid snapshot of an earlier prefix of this same ledger, the ordinary result of a night appending rows) is
regenerated and reported; a state view that DIVERGES (a different state at the same sequence number, which means the
ledger was edited or replay semantics changed under it) is an integrity failure and exits non-zero.
"""

from __future__ import annotations

import json
from pathlib import Path

from pravrudhi_kernel.ledger import replay, verify, write_state
from pravrudhi_kernel.ledger.replay import state_bytes
from pravrudhi_kernel.ledger.verify import iter_events


def _hash_at(ledger: Path, seq: int) -> str | None:
    for ev in iter_events(ledger):
        if ev.seq == seq:
            return ev.this_hash
    return None


def replay_command(ledger: Path, state: Path, *, check: bool = False) -> tuple[int, list[str]]:
    if not ledger.exists():
        return 2, [f"no ledger at {ledger}"]
    if check:
        r = verify(ledger)
        if not r.ok:
            return 1, [f"chain BROKEN at seq {r.first_bad_seq}: {r.reason}"]
    st = replay(ledger)
    if check and state.exists():
        current = state_bytes(st)
        if state.read_text() == current:
            return 0, [f"chain ok ({st.seq + 1} events); state.json matches replay; state_hash {st.state_hash}"]
        try:
            saved = json.loads(state.read_text())
        except ValueError:
            return 1, ["state.json is not valid JSON; regenerate it with `pravrudhi replay`"]
        saved_seq, saved_head = saved.get("seq"), saved.get("ledger_head")
        if isinstance(saved_seq, int) and saved_seq < st.seq and _hash_at(ledger, saved_seq) == saved_head:
            write_state(st, state)
            return 0, [
                f"chain ok ({st.seq + 1} events); state.json was STALE at seq {saved_seq} "
                f"(a valid snapshot of this ledger) and has been regenerated; state_hash {st.state_hash}"
            ]
        return 1, [
            f"state.json DIVERGES from replay at seq {saved_seq} (saved head {saved_head}); the ledger chain verifies, "
            f"so either state.json was edited or replay semantics changed. Current head {st.ledger_head}, "
            f"state_hash {st.state_hash}"
        ]
    write_state(st, state)
    return 0, [f"wrote {state} ({st.seq + 1} events, head {st.ledger_head}, state_hash {st.state_hash})"]
