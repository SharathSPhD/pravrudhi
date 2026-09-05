"""Re-chain ledger rows written by a writer whose head was stale (concurrent writers).

usage: uv run python scripts/ledger_rechain.py research/ledger.jsonl
Keeps the longest valid prefix, re-appends every later row with its payload and timestamp intact (new seq, new
hashes), then appends an audit{kind: chain_repair} row naming the rows that were re-chained and their original
hashes. The broken file is kept beside the ledger as ledger.jsonl.broken-<utc>.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from pravrudhi_kernel.ledger import LedgerWriter
from pravrudhi_kernel.ledger.verify import verify
from pravrudhi_kernel.ledger.writer import chain_hash


def main(path: Path) -> None:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    good: list[dict] = []
    for r in rows:
        if r["seq"] != len(good) or (good and r["prev_hash"] != good[-1]["this_hash"]):
            break
        good.append(r)
    bad = rows[len(good):]
    if not bad:
        print("chain is intact; nothing to do")
        return
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(path.name + f".broken-{stamp}")
    shutil.copy2(path, backup)
    path.write_text("".join(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n" for r in good))
    # the writer serialises via pydantic; rewrite the prefix through verify to be sure the bytes still chain
    res = verify(path)
    assert res.ok, res
    it = iter(bad)
    cur = {"t": None}
    w = LedgerWriter.open(path, good[-1]["kernel_release"], clock=lambda: cur["t"])
    moved = []
    for r in bad:
        cur["t"] = r["t"]
        ev = w.append(
            r["kind"], r["actor"], r["payload"], epoch=r["epoch"], night=r["night"], cycle=r["cycle"],
            candidate_id=r["candidate_id"], surface=r["surface"], bucket=r["bucket"], provenance=r["provenance"],
        )
        moved.append({"old_seq": r["seq"], "old_this_hash": r["this_hash"], "old_prev_hash": r["prev_hash"], "new_seq": ev.seq})
    cur["t"] = None
    w._clock = None  # type: ignore[assignment]
    from pravrudhi_kernel.ledger.writer import now_rfc3339_ms

    w._clock = now_rfc3339_ms
    w.append(
        "audit", "kernel",
        {"kind": "chain_repair", "severity": "high", "reason": "concurrent writer appended from a stale head",
         "first_bad_seq": bad[0]["seq"], "rows_rechained": moved, "backup": backup.name},
        epoch=0, night=0,
    )
    res = verify(path)
    print(json.dumps({"ok": res.ok, "n": res.n, "rechained": len(moved), "backup": backup.name}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
