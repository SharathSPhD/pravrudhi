"""anusaṁdhāna: rebuild the state view from the ledger alone. A pure fold; byte-stable output."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pravrudhi_kernel.ledger.jcs import canonicalize
from pravrudhi_kernel.ledger.verify import iter_events
from pravrudhi_kernel.schema import LedgerEvent

Badge = Literal["grey", "amber", "green", "red"]
HIGH = ("high", "critical")


class CandidateView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    surface: str | None
    bucket: dict[str, str] | None
    proposed_seq: int
    edit_family: str | None = None
    xs: list[float] = Field(default_factory=list)
    n_obs: int = 0
    cost_gpu_h: float = 0.0
    last_boundary: str | None = None
    promoted: bool = False
    pruned: str | None = None
    audit_high: bool = False
    skipped: bool = False
    rebased: int = 0
    incumbent_hash: str | None = None


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spent_gpu_h: float = 0.0
    runs: int = 0


class Locks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reflection_owed: int | None = None
    paused: bool = False
    frozen_surfaces: list[str] = Field(default_factory=list)


class State(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ledger_head: str | None = None
    seq: int = -1
    t_last: str = ""
    kernel_release: str = ""
    epoch: int = 0
    night: int = 0
    candidates: dict[str, CandidateView] = Field(default_factory=dict)
    badges: dict[str, Badge] = Field(default_factory=dict)
    budgets: dict[str, Budget] = Field(default_factory=dict)
    tau: dict[str, float] = Field(default_factory=dict)
    locks: Locks = Field(default_factory=Locks)
    promoted: dict[str, list[str]] = Field(default_factory=dict)
    pruned: dict[str, str] = Field(default_factory=dict)
    skipped: list[str] = Field(default_factory=list)
    blocklist: list[str] = Field(default_factory=list)
    audits: int = 0
    sublations: int = 0
    reflections: int = 0
    sensors: dict[str, int] = Field(default_factory=dict)
    inbox_pending: list[str] = Field(default_factory=list)
    signoffs: list[dict[str, Any]] = Field(default_factory=list)
    rho_pred: dict[str, float] = Field(default_factory=dict)
    harness_head: str | None = None
    theta_surprise: float | None = None
    state_hash: str = ""

    def public_view(self) -> dict[str, Any]:
        d = self.model_dump(mode="json")
        d.pop("state_hash", None)
        return d


def badge(c: CandidateView) -> Badge:
    if c.pruned is not None or c.audit_high:
        return "red"
    if c.promoted:
        return "green"
    if c.n_obs >= 1:
        return "amber"
    return "grey"


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _apply(st: State, ev: LedgerEvent) -> None:
    p = ev.payload
    cid = ev.candidate_id
    st.epoch, st.night = max(st.epoch, ev.epoch), max(st.night, ev.night)
    if cid is not None and cid not in st.candidates and ev.kind == "propose":
        st.candidates[cid] = CandidateView(
            surface=ev.surface,
            bucket=ev.bucket.model_dump() if ev.bucket else None,
            proposed_seq=ev.seq,
            edit_family=p.get("edit_family"),
        )
    c = st.candidates.get(cid) if cid else None
    match ev.kind:
        case "propose":
            pass
        case "predict":
            pass
        case "select":
            if c is not None:
                c.last_boundary = None
        case "spend":
            b = st.budgets.setdefault(str(ev.night), Budget())
            b.spent_gpu_h += _f(p.get("gpu_h"))
            b.runs += 1
            if c is not None:
                c.cost_gpu_h += _f(p.get("gpu_h"))
        case "observe":
            if c is not None:
                hashes = p.get("hashes") or {}
                parent = hashes.get("harness_parent")
                if parent is not None and c.incumbent_hash is not None and parent != c.incumbent_hash:
                    c.rebased += 1
                    c.xs = []
                if parent is not None:
                    c.incumbent_hash = parent
                observed = p.get("observed") or {}
                c.xs.append(_f(observed.get("delta_in")))
                c.n_obs += 1
                c.last_boundary = (p.get("stats") or {}).get("boundary")
                if ev.surface and p.get("brier") is not None:
                    st.rho_pred[ev.surface] = 1.0 - _f(p.get("brier"))
                if st.theta_surprise is not None and _f(p.get("surprise")) > st.theta_surprise:
                    st.locks.reflection_owed = ev.seq
        case "skip":
            if c is not None:
                c.skipped = True
            if cid and cid not in st.skipped:
                st.skipped.append(cid)
            if p.get("never_repropose") and p.get("diff_sha256"):
                st.blocklist.append(str(p["diff_sha256"]))
        case "promote":
            if c is not None:
                c.promoted = True
            st.promoted.setdefault(str(ev.night), []).append(cid or "")
            if ev.surface and p.get("tau_after") is not None:
                st.tau[ev.surface] = min(1.0, max(0.0, _f(p.get("tau_after"))))
            if p.get("merge_commit"):
                st.harness_head = str(p["merge_commit"])
        case "prune":
            label = str(p.get("hetvabhasa", "asiddha"))
            if c is not None:
                c.pruned = label
            if cid:
                st.pruned[cid] = label
        case "sublate":
            st.sublations += 1
        case "audit":
            st.audits += 1
            if p.get("kind") == "genesis":
                st.kernel_release = ev.kernel_release
            if p.get("severity") in HIGH and c is not None:
                c.audit_high = True
            if p.get("kind") == "paused_by_operator":
                st.locks.paused = True
            if (
                p.get("kind") == "surface_frozen"
                and ev.surface
                and ev.surface not in st.locks.frozen_surfaces
            ):
                st.locks.frozen_surfaces.append(ev.surface)
            if p.get("kind") == "theta_surprise" and p.get("value") is not None:
                st.theta_surprise = _f(p.get("value"))
        case "reflect":
            st.reflections += 1
            if st.locks.reflection_owed is not None and p.get("trigger") == "surprise":
                st.locks.reflection_owed = None
        case "signoff":
            pack = str(p.get("pack", ""))
            st.signoffs.append({"pack": pack, "decision": p.get("decision"), "by": ev.actor, "seq": ev.seq})
            if pack in st.inbox_pending:
                st.inbox_pending.remove(pack)
        case "sensor":
            name = str(p.get("sensor", "unknown"))
            st.sensors[name] = st.sensors.get(name, 0) + 1
    if p.get("inbox_pack") and ev.kind in ("promote", "audit"):
        pack = str(p["inbox_pack"])
        if pack not in st.inbox_pending:
            st.inbox_pending.append(pack)
    st.seq, st.t_last, st.ledger_head = ev.seq, ev.t, ev.this_hash


def replay(path: Path) -> State:
    st = State()
    for ev in iter_events(Path(path)):
        _apply(st, ev)
    st.badges = {cid: badge(c) for cid, c in st.candidates.items()}
    st.state_hash = hashlib.sha256(canonicalize(st.public_view()).encode()).hexdigest()
    return st


def state_bytes(st: State) -> str:
    return json.dumps(st.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_state(st: State, path: Path) -> Path:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(state_bytes(st))
    return Path(path)
