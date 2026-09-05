"""Runs: the app's verb. Press Run, a night starts, and its progress streams back live.

The engine already knows how to run a night from the command line; the app should not reimplement that. A run is
therefore a supervised subprocess of the same CLI, so a night started from the browser is byte-for-byte the night
a user would start from a terminal, writes to the same ledger, and obeys the same pre-registration. What this module
adds is only what a person watching needs: a run id, live events, a stop button, and a list of what was produced.

Events are parsed from the night's own log lines rather than invented, so the app can only show what the engine
actually said. Anything the parser does not recognise is still delivered as a plain `log` event, never dropped.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from pravrudhi.application.external import external_rows
from pravrudhi_kernel.ledger.verify import iter_events

_SEED = re.compile(
    r"^(?P<cid>c-\d+): seed (?P<seed>\d+) incumbent=(?P<inc>[\d.]+) candidate=(?P<cand>[\d.]+) "
    r"delta=(?P<delta>[+-]?[\d.]+) boundary=(?P<decision>\w+) \(n=(?P<n>\d+)"
)
_PROMOTED = re.compile(r"^(?P<cid>c-\d+): PROMOTED")
_PROPOSER = re.compile(r"^proposer: (?P<raw>\d+) raw, (?P<accepted>\d+) accepted")
_ROUND = re.compile(r"^round (?P<round>\d+): (?P<selected>\d+) selected, (?P<remaining>[\d.]+) GPU-h remaining")
_CLOSED = re.compile(r"^(?:harness )?night (?P<night>\d+) (?P<status>closed|aborted)")


class RunRequest(BaseModel):
    target: str = Field(pattern="^(model|harness)$")
    bench: str = ""
    budget_gpu_h: float | None = Field(default=None, gt=0, le=48)
    k: int = Field(default=8, ge=1, le=32)
    policy: str = Field(default="efe", pattern="^(efe|greedy|thompson|random)$")
    proposer_gguf: str = ""
    proposer_endpoint: str = ""


@dataclass
class Run:
    id: str
    target: str
    night: int
    request: dict[str, Any]
    started_at: float
    proc: subprocess.Popen[str] | None = None
    status: str = "running"
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=5000))
    best_delta: float | None = None
    promoted: list[str] = field(default_factory=list)
    finished_at: float | None = None

    def view(self) -> dict[str, Any]:
        return {
            "id": self.id, "target": self.target, "night": self.night, "status": self.status,
            "request": self.request, "started_at": self.started_at, "finished_at": self.finished_at,
            "best_delta": self.best_delta, "promoted": self.promoted, "events": len(self.events),
        }


def parse_line(line: str) -> dict[str, Any]:
    """One log line to one event. Unrecognised lines are `log` events, so nothing the engine said is lost."""
    s = line.strip()
    if m := _SEED.match(s):
        d = m.groupdict()
        return {"type": "paired", "candidate": d["cid"], "seed": int(d["seed"]), "incumbent": float(d["inc"]),
                "candidate_score": float(d["cand"]), "delta": float(d["delta"]), "decision": d["decision"], "n": int(d["n"])}
    if m := _PROMOTED.match(s):
        return {"type": "promoted", "candidate": m.group("cid")}
    if m := _PROPOSER.match(s):
        return {"type": "proposed", "raw": int(m.group("raw")), "accepted": int(m.group("accepted"))}
    if m := _ROUND.match(s):
        return {"type": "round", "round": int(m.group("round")), "selected": int(m.group("selected")),
                "remaining_gpu_h": float(m.group("remaining"))}
    if m := _CLOSED.match(s):
        return {"type": "closed", "night": int(m.group("night")), "status": m.group("status")}
    return {"type": "log", "text": s}


def next_night(root: Path, track: str) -> int:
    ledger = root / "research" / "ledger.jsonl"
    last = 0
    if ledger.exists():
        for ev in iter_events(ledger):
            p = ev.payload
            if ev.kind == "audit" and p.get("kind") == "night_start" and (p.get("track") or "lora") == track:
                last = max(last, ev.night)
    return last + 1


class RunManager:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    def _cli(self) -> list[str]:
        override = os.environ.get("PRAVRUDHI_CLI")
        if override:
            return shlex.split(override)
        return [sys.executable, "-m", "pravrudhi"]

    def _command(self, req: RunRequest, night: int) -> list[str]:
        if req.target == "model":
            cmd = self._cli() + ["night", "--night", str(night), "--k", str(req.k), "--policy", req.policy,
                                 "--root", str(self.root)]
            train_parquet = (self.root / ".pravrudhi" / "data" / "gsm8k-train.parquet").resolve()
            if train_parquet.exists():
                cmd += ["--train-parquet", str(train_parquet)]
        else:
            cmd = self._cli() + ["harness-night", "--night", str(night), "--k", str(req.k),
                   "--policy", req.policy, "--root", str(self.root)]
        if req.budget_gpu_h:
            cmd += ["--budget", str(req.budget_gpu_h)]
        if req.proposer_gguf:
            cmd += ["--gguf", req.proposer_gguf]
        if req.proposer_endpoint:
            cmd += ["--proposer-endpoint", req.proposer_endpoint]
        return cmd

    def start(self, req: RunRequest) -> Run:
        with self._lock:
            if any(r.status == "running" for r in self.runs.values()):
                raise HTTPException(status_code=409, detail="a run is already in progress on this engine")
            track = "lora" if req.target == "model" else "harness"
            night = next_night(self.root, track)
            run = Run(id=uuid.uuid4().hex[:12], target=req.target, night=night, request=req.model_dump(),
                      started_at=time.time())
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            run.proc = subprocess.Popen(
                self._command(req, night), cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env, start_new_session=True,
            )
            self.runs[run.id] = run
        threading.Thread(target=self._pump, args=(run,), daemon=True).start()
        return run

    def _pump(self, run: Run) -> None:
        assert run.proc is not None and run.proc.stdout is not None
        for line in run.proc.stdout:
            if "Warning" in line or "warn" in line:
                continue
            ev = parse_line(line)
            ev["t"] = time.time()
            if ev["type"] == "paired":
                run.best_delta = ev["delta"] if run.best_delta is None else max(run.best_delta, ev["delta"])
            if ev["type"] == "promoted":
                run.promoted.append(ev["candidate"])
            run.events.append(ev)
        code = run.proc.wait()
        run.finished_at = time.time()
        if run.status == "stopping":
            run.status = "stopped"
        else:
            run.status = "finished" if code == 0 else "failed"
        run.events.append({"type": "end", "status": run.status, "exit_code": code, "t": time.time()})

    def stop(self, run_id: str) -> Run:
        run = self.get(run_id)
        if run.proc and run.status == "running":
            run.status = "stopping"
            os.killpg(os.getpgid(run.proc.pid), signal.SIGTERM)
        return run

    def get(self, run_id: str) -> Run:
        if run_id not in self.runs:
            raise HTTPException(status_code=404, detail="no such run")
        return self.runs[run_id]

    def stream(self, run_id: str) -> Iterator[str]:
        run = self.get(run_id)
        sent = 0
        while True:
            events = list(run.events)
            for ev in events[sent:]:
                yield f"data: {json.dumps(ev)}\n\n"
            sent = len(events)
            if run.status not in ("running", "stopping") and sent >= len(run.events):
                return
            time.sleep(0.5)


def models_listing(root: Path) -> list[dict[str, Any]]:
    """What the loop produced: each promotion with the external before/after that exists for it."""
    ledger = root / "research" / "ledger.jsonl"
    if not ledger.exists():
        return []
    ext = external_rows(ledger)
    base: dict[str, dict[str, Any]] = {}
    after: dict[str, dict[str, Any]] = {}
    for r in ext:
        cond = str(r.get("condition", ""))
        if cond == "base":
            base[str(r.get("track"))] = r
        elif ":" in cond:
            after[cond.split(":", 1)[1]] = r
    recipes: dict[str, dict[str, Any]] = {}
    out: list[dict[str, Any]] = []
    withdrawn = {int(ev.payload.get("target_seq", -1)) for ev in iter_events(ledger)
                 if ev.kind == "sublate" and ev.payload.get("kind") == "promotion_withdrawn"}
    for ev in iter_events(ledger):
        if ev.kind == "propose" and ev.candidate_id:
            recipes[ev.candidate_id] = ev.payload.get("recipe") or ev.payload.get("harness") or {}
        if ev.kind == "promote" and ev.candidate_id and ev.seq not in withdrawn:
            cid = ev.candidate_id
            track = "H" if ev.surface == "H3.prompt" else "M"
            out.append({
                "id": cid, "track": "harness" if track == "H" else "model", "night": ev.night,
                "recipe": recipes.get(cid, {}), "artefact": ev.payload.get("from_worktree"),
                "external_before": (base.get(track) or {}).get("metrics"),
                "external_after": (after.get(cid) or {}).get("metrics"),
            })
    return out


def build_router(root: Path) -> APIRouter:
    mgr = RunManager(root)
    r = APIRouter(prefix="/api")

    @r.post("/runs")
    def start(req: RunRequest) -> dict[str, Any]:
        return mgr.start(req).view()

    @r.get("/runs")
    def list_runs() -> list[dict[str, Any]]:
        return [run.view() for run in sorted(mgr.runs.values(), key=lambda x: -x.started_at)]

    @r.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = mgr.get(run_id)
        return {**run.view(), "recent": list(run.events)[-50:]}

    @r.post("/runs/{run_id}/stop")
    def stop_run(run_id: str) -> dict[str, Any]:
        return mgr.stop(run_id).view()

    @r.get("/runs/{run_id}/events")
    def events(run_id: str) -> StreamingResponse:
        return StreamingResponse(mgr.stream(run_id), media_type="text/event-stream")

    @r.get("/models")
    def models() -> list[dict[str, Any]]:
        return models_listing(root)

    return r
