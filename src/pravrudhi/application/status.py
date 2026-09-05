"""`pravrudhi status`: what the ledger says, nothing else."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pravrudhi_kernel.ledger import replay, verify
from pravrudhi_kernel.ledger.verify import iter_events


def status(root: Path) -> dict[str, Any]:
    ledger = root / "research" / "ledger.jsonl"
    if not ledger.exists():
        return {"initialised": False}
    v = verify(ledger)
    st = replay(ledger)
    nights: dict[int, dict[str, Any]] = {}
    for ev in iter_events(ledger):
        p = ev.payload
        if ev.kind == "audit" and p.get("kind") == "night_end":
            nights[ev.night] = {
                "spent_gpu_h": p.get("spent_gpu_h"),
                "outcomes": p.get("outcomes"),
                "incumbent": p.get("incumbent"),
            }
    counts = {b: sum(1 for x in st.badges.values() if x == b) for b in ("grey", "amber", "green", "red")}
    return {
        "initialised": True,
        "chain_ok": v.ok,
        "events": v.n,
        "ledger_head": st.ledger_head,
        "state_hash": st.state_hash,
        "candidates": len(st.candidates),
        "badges": counts,
        "promoted": st.promoted,
        "pruned": len(st.pruned),
        "nights": nights,
        "inbox_pending": st.inbox_pending,
        "locks": st.locks.model_dump(),
    }
