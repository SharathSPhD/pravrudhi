"""Append-only hash-chained JSONL writer. The only path by which evidence enters the ledger."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pravrudhi_kernel.ledger.jcs import canonicalize
from pravrudhi_kernel.ledger.verify import verify
from pravrudhi_kernel.schema import Bucket, LedgerEvent
from pravrudhi_kernel.schema.common import Pramana, Surface


class ChainBroken(RuntimeError):
    pass


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def genesis_prev_hash(kernel_release: str) -> str:
    return _sha("pravrudhi-genesis|" + kernel_release)


def chain_hash(prev_hash: str, event_without_this_hash: dict[str, Any]) -> str:
    return _sha(prev_hash + "\n" + canonicalize(event_without_this_hash))


def schema_hash() -> str:
    return _sha(canonicalize(LedgerEvent.model_json_schema()))


def now_rfc3339_ms() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(UTC).microsecond // 1000:03d}Z"


class LedgerWriter:
    """Holds the chain head; every append verifies continuity and fsyncs.

    `clock` is injectable so golden ledgers are byte-deterministic.
    """

    def __init__(self, path: Path, kernel_release: str, *, clock: Callable[[], str] | None = None) -> None:
        self.path = Path(path)
        self.kernel_release = kernel_release
        self._clock = clock or now_rfc3339_ms
        self.seq = -1
        self.head_hash = genesis_prev_hash(kernel_release)
        self.t_last = ""

    @property
    def head_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".head")

    @classmethod
    def open(
        cls,
        path: Path,
        kernel_release: str,
        *,
        clock: Callable[[], str] | None = None,
        glossary_hash: str | None = None,
    ) -> LedgerWriter:
        w = cls(path, kernel_release, clock=clock)
        if w.path.exists() and w.path.stat().st_size > 0:
            res = verify(w.path)
            if not res.ok:
                raise ChainBroken(f"{w.path}: {res.reason} at seq {res.first_bad_seq}")
            assert res.head_hash is not None and res.t_last is not None
            w.seq, w.head_hash, w.t_last = res.n - 1, res.head_hash, res.t_last
            return w
        w.path.parent.mkdir(parents=True, exist_ok=True)
        w.append(
            "audit",
            "kernel",
            {
                "kind": "genesis",
                "kernel_release": kernel_release,
                "schema_hash": schema_hash(),
                "glossary_hash": glossary_hash or _sha("no-glossary"),
            },
            epoch=0,
            night=0,
        )
        return w

    def append(
        self,
        kind: str,
        actor: str,
        payload: dict[str, Any],
        *,
        epoch: int,
        night: int,
        cycle: int | None = None,
        candidate_id: str | None = None,
        surface: str | Surface | None = None,
        bucket: dict[str, str] | Bucket | None = None,
        provenance: str | Pramana | None = None,
    ) -> LedgerEvent:
        t = self._clock()
        if self.t_last and t < self.t_last:
            t = self.t_last
        body: dict[str, Any] = {
            "seq": self.seq + 1,
            "t": t,
            "epoch": epoch,
            "night": night,
            "cycle": cycle,
            "kind": kind,
            "actor": actor,
            "candidate_id": candidate_id,
            "surface": surface,
            "bucket": bucket if not isinstance(bucket, Bucket) else bucket.model_dump(),
            "provenance": provenance,
            "kernel_release": self.kernel_release,
            "payload": payload,
            "prev_hash": self.head_hash,
        }
        # validate everything but this_hash first so a refused event never touches the file
        probe = LedgerEvent.model_validate(body | {"this_hash": "0" * 64})
        canonical_body = json.loads(probe.model_dump_json(exclude={"this_hash"}))
        this_hash = chain_hash(self.head_hash, canonical_body)
        ev = LedgerEvent.model_validate(canonical_body | {"this_hash": this_hash})
        line = ev.model_dump_json() + "\n"
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o640)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        self.seq, self.head_hash, self.t_last = ev.seq, ev.this_hash, ev.t
        self.head_path.write_text(json.dumps({"seq": ev.seq, "this_hash": ev.this_hash}) + "\n")
        return ev
