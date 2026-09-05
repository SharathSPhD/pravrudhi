"""`pravrudhi serve`: FastAPI over the ledger. Everything shown is replayed; nothing is hand-set.

Endpoints: /health, /status, /candidates, /candidates/{id}, /observations, /inbox, /evidence/{name},
POST /inbox/sign (operator identity required; refused for agent identities)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from pravrudhi import KERNEL_VERSION, __version__
from pravrudhi.agents.registry import survey
from pravrudhi.api.localguard import install as install_local_guard
from pravrudhi.application.doctor import run_doctor
from pravrudhi.application.evidence import render_h1
from pravrudhi.application.external import external_rows
from pravrudhi.application.night import inbox_listing
from pravrudhi.application.status import status
from pravrudhi.hosts.fleet import fleet_report
from pravrudhi_kernel.ledger import LedgerWriter, replay
from pravrudhi_kernel.ledger.verify import iter_events

AGENT_IDENTITIES = frozenset({"pravrudhi-agent", "agent", "claude"})


class SignRequest(BaseModel):
    pack: str
    decision: str  # approve | reject | defer
    note: str = ""


def create_app(root: Path) -> FastAPI:
    root = Path(root)
    app = FastAPI(title="pravrudhi", version=__version__)
    # A local engine that can start GPU work must not answer any page the user happens to be visiting: see
    # api/localguard.py. Cross-origin access is off unless the operator names the origins.
    install_local_guard(app, root, enforce=os.environ.get("PRAVRUDHI_DISABLE_LOCAL_GUARD") != "1")
    ledger = root / "research" / "ledger.jsonl"

    @app.get("/doctor")
    def doctor() -> dict[str, Any]:
        return run_doctor(root)

    @app.get("/hosts")
    def hosts() -> dict[str, Any]:
        return fleet_report(root)

    @app.get("/agents")
    def agents() -> list[dict[str, Any]]:
        return [{"name": agent.name, "available": agent.available, "reason": agent.reason} for agent in survey(root)]

    @app.get("/external")
    def external() -> list[dict[str, Any]]:
        return external_rows(ledger)

    @app.get("/nights")
    def nights_ep() -> list[dict[str, Any]]:
        starts: dict[tuple[int, str], dict[str, Any]] = {}
        rows: list[dict[str, Any]] = []
        for event in iter_events(ledger):
            if event.kind != "audit":
                continue
            payload = event.payload
            track = payload.get("track", "lora")
            key = (event.night, track)
            if payload.get("kind") == "night_start":
                starts[key] = payload
            elif payload.get("kind") == "night_end":
                start = starts.get(key, {})
                rows.append({
                    "night": event.night,
                    "track": track,
                    "selection_policy": start.get("selection_policy"),
                    "spent_gpu_h": payload.get("spent_gpu_h"),
                    "outcomes": payload.get("outcomes"),
                    "incumbent": payload.get("incumbent"),
                })
        return rows

    @app.get("/h1/{track}/{nights}")
    def h1(track: str, nights: str) -> dict[str, str]:
        if not re.fullmatch(r"[0-9]+(?:-[0-9]+)*", nights):
            raise HTTPException(400, "nights must be dash-separated non-negative integers")
        try:
            parsed_nights = tuple(int(night) for night in nights.split("-"))
        except ValueError as exc:
            raise HTTPException(400, "invalid night number") from exc
        return {"markdown": render_h1(ledger, parsed_nights, track)}

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__, "kernel": KERNEL_VERSION, "ledger": ledger.exists()}

    @app.get("/status")
    def status_ep() -> dict[str, Any]:
        return status(root)

    @app.get("/candidates")
    def candidates() -> list[dict[str, Any]]:
        st = replay(ledger)
        return [{"id": cid, "badge": st.badges[cid], **c.model_dump()} for cid, c in st.candidates.items()]

    @app.get("/candidates/{cid}")
    def candidate(cid: str) -> dict[str, Any]:
        st = replay(ledger)
        if cid not in st.candidates:
            raise HTTPException(404, "unknown candidate")
        events = [ev.model_dump() for ev in iter_events(ledger) if ev.candidate_id == cid]
        return {"id": cid, "badge": st.badges[cid], "view": st.candidates[cid].model_dump(), "events": events}

    @app.get("/observations")
    def observations(limit: int = 200) -> list[dict[str, Any]]:
        rows = [ev.model_dump() for ev in iter_events(ledger) if ev.kind == "observe"]
        return rows[-limit:]

    @app.get("/inbox")
    def inbox() -> list[dict[str, Any]]:
        return inbox_listing(root)

    @app.get("/evidence/{name}")
    def evidence(name: str) -> dict[str, str]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
            raise HTTPException(404, "no such evidence document")
        base = (root / "docs" / "evidence").resolve()
        p = (base / f"{name}.md").resolve()
        if p.parent != base or not p.is_file():
            raise HTTPException(404, "no such evidence document")
        return {"name": name, "markdown": p.read_text()}

    @app.post("/inbox/sign")
    def sign(req: SignRequest, x_pravrudhi_operator: str | None = Header(default=None)) -> dict[str, Any]:
        who = (x_pravrudhi_operator or os.environ.get("PRAVRUDHI_OPERATOR") or "").strip()
        if not who or who.lower() in AGENT_IDENTITIES:
            raise HTTPException(403, "sign-off is a human act: set X-Pravrudhi-Operator to the operator's name")
        if req.decision not in ("approve", "reject", "defer"):
            raise HTTPException(400, "decision must be approve | reject | defer")
        packs = {r["pack"] for r in inbox_listing(root)}
        if req.pack not in packs:
            raise HTTPException(404, "unknown pack")
        w = LedgerWriter.open(ledger, KERNEL_VERSION)
        import hashlib

        ev = w.append(
            "signoff",
            f"human:{who}",
            {
                "pack": req.pack,
                "decision": req.decision,
                "scope": "promote_T2",
                "note": req.note,
                "pack_hash": hashlib.sha256(Path(req.pack, "README.md").read_bytes()).hexdigest(),
            },
            epoch=0,
            night=replay(ledger).night,
        )
        return {"seq": ev.seq, "this_hash": ev.this_hash, "decision": req.decision, "by": who}

    return app


def serve(root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    uvicorn.run(create_app(root), host=host, port=port, log_level="info")


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)
