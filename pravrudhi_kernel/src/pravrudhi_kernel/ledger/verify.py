"""Chain verification: seq contiguity, hash continuity, timestamp monotonicity.

Names the first broken line.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

from pravrudhi_kernel.ledger.jcs import canonicalize
from pravrudhi_kernel.schema import KernelModel, LedgerEvent


class VerifyResult(KernelModel):
    ok: bool
    n: int
    first_bad_seq: int | None
    reason: str | None
    head_hash: str | None
    t_last: str | None


def iter_events(path: Path) -> Iterator[LedgerEvent]:
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield LedgerEvent.model_validate_json(line)


def verify(path: Path) -> VerifyResult:
    prev_hash: str | None = None
    prev_t = ""
    n = 0
    with Path(path).open("r", encoding="utf-8") as fh:
        for raw in fh:
            if not raw.strip():
                continue
            try:
                ev = LedgerEvent.model_validate_json(raw)
            except ValueError as e:
                return VerifyResult(ok=False, n=n, first_bad_seq=n, reason=f"schema: {e}", head_hash=None, t_last=None)
            if ev.seq != n:
                return VerifyResult(ok=False, n=n, first_bad_seq=n, reason="seq not contiguous", head_hash=None, t_last=None)
            if n == 0:
                expected_prev = hashlib.sha256(("pravrudhi-genesis|" + ev.kernel_release).encode()).hexdigest()
                if ev.prev_hash != expected_prev:
                    return VerifyResult(
                        ok=False,
                        n=0,
                        first_bad_seq=0,
                        reason="bad genesis prev_hash",
                        head_hash=None,
                        t_last=None,
                    )
            elif ev.prev_hash != prev_hash:
                return VerifyResult(ok=False, n=n, first_bad_seq=n, reason="prev_hash mismatch", head_hash=None, t_last=None)
            body = json.loads(ev.model_dump_json(exclude={"this_hash"}))
            expect = hashlib.sha256((ev.prev_hash + "\n" + canonicalize(body)).encode()).hexdigest()
            if ev.this_hash != expect:
                return VerifyResult(ok=False, n=n, first_bad_seq=n, reason="this_hash mismatch", head_hash=None, t_last=None)
            if ev.t < prev_t:
                return VerifyResult(
                    ok=False,
                    n=n,
                    first_bad_seq=n,
                    reason="timestamp not monotone",
                    head_hash=None,
                    t_last=None,
                )
            prev_hash, prev_t, n = ev.this_hash, ev.t, n + 1
    if n == 0:
        return VerifyResult(ok=False, n=0, first_bad_seq=None, reason="empty ledger", head_hash=None, t_last=None)
    return VerifyResult(ok=True, n=n, first_bad_seq=None, reason=None, head_hash=prev_hash, t_last=prev_t)
