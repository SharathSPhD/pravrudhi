"""`pravrudhi serve`: FastAPI over the ledger. Everything shown is replayed; nothing is hand-set.

Endpoints: /health, /status, /candidates, /candidates/{id}, /observations, /inbox, /evidence/{name},
POST /inbox/sign (operator identity required; refused for agent identities)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException
from fastapi.routing import APIRoute
from pydantic import BaseModel

from pravrudhi import KERNEL_VERSION, __version__
from pravrudhi.agents.registry import survey
from pravrudhi.api.localguard import install as install_local_guard
from pravrudhi.api.schemas import (
    AgentsResponse,
    CandidateDetailResponse,
    CandidatesResponse,
    DispatchResponse,
    DoctorResponse,
    EvidenceResponse,
    ExternalResultsResponse,
    FleetResponse,
    HealthResponse,
    InboxListingResponse,
    LoomResponse,
    MarkdownResponse,
    MemoryNoteResponse,
    MemoryResponse,
    NightsResponse,
    ObjectiveDetailResponse,
    ObjectiveResponse,
    ObjectivesResponse,
    ObservationsResponse,
    PlanResponse,
    RecipesResponse,
    SignResponse,
    StatusResponse,
    SubagentsResponse,
    TokenResponse,
    ToolsResponse,
)
from pravrudhi.application.doctor import run_doctor
from pravrudhi.application.evidence import render_h1
from pravrudhi.application.external import external_rows
from pravrudhi.application.night import inbox_listing
from pravrudhi.application.status import status
from pravrudhi.hosts.fleet import fleet_report
from pravrudhi_kernel.ledger import LedgerWriter, replay
from pravrudhi_kernel.ledger.verify import iter_events

AGENT_IDENTITIES = frozenset({"pravrudhi-agent", "agent", "claude"})


class BenchmarkRequest(BaseModel):
    id: str = ""
    tool: str = "lm-eval"
    metric: str
    direction: str = "up"


class ObjectiveRequest(BaseModel):
    """What the user wants, stated by the user. The engine records it verbatim and does not interpret it."""

    id: str
    intent: str
    track: str
    benchmarks: list[BenchmarkRequest]
    domain: str = ""
    recipes: list[str] = []
    target_delta: float | None = None
    notes: str = ""


class RememberRequest(BaseModel):
    """A durable fact to store, with where it came from."""

    text: str
    source: str = ""


class SignRequest(BaseModel):
    pack: str
    decision: str  # approve | reject | defer
    note: str = ""


def create_app(root: Path) -> FastAPI:
    root = Path(root)
    app = FastAPI(title="pravrudhi", version=__version__)
    # Every JSON route lives under /api. The interface is a static export mounted at the root, and the two
    # namespaces collided: a browser navigating to /runs or /models was answered with JSON rather than the
    # page, because the API route matched first. Separating them is also what makes the API addressable on
    # its own, which a client library needs.
    api = APIRouter(prefix="/api")
    # A local engine that can start GPU work must not answer any page the user happens to be visiting: see
    # api/localguard.py. Cross-origin access is off unless the operator names the origins.
    install_local_guard(app, root, enforce=os.environ.get("PRAVRUDHI_DISABLE_LOCAL_GUARD") != "1")
    # The guard returns a JSONResponse directly; declaring its resource leaves token handling intact.
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == "/api/app-token":
            app.router.routes.remove(route)
            app.add_api_route(route.path, route.endpoint, methods=["GET"], response_model=TokenResponse)
            break
    ledger = root / "research" / "ledger.jsonl"

    @api.get("/doctor")
    def doctor() -> DoctorResponse:
        return DoctorResponse.model_validate(run_doctor(root))

    @api.get("/hosts")
    def hosts() -> FleetResponse:
        return FleetResponse.model_validate(fleet_report(root))

    @api.get("/agents")
    def agents() -> AgentsResponse:
        return AgentsResponse.model_validate(
            [{"name": agent.name, "available": agent.available, "reason": agent.reason} for agent in survey(root)]
        )

    @api.get("/external", response_model_exclude_unset=True)
    def external() -> ExternalResultsResponse:
        return ExternalResultsResponse.model_validate(external_rows(ledger))

    @api.get("/nights")
    def nights_ep() -> NightsResponse:
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
                rows.append(
                    {
                        "night": event.night,
                        "track": track,
                        "selection_policy": start.get("selection_policy"),
                        "spent_gpu_h": payload.get("spent_gpu_h"),
                        "outcomes": payload.get("outcomes"),
                        "incumbent": payload.get("incumbent"),
                    }
                )
        return NightsResponse.model_validate(rows)

    @api.get("/h1/{track}/{nights}")
    def h1(track: str, nights: str) -> MarkdownResponse:
        if not re.fullmatch(r"[0-9]+(?:-[0-9]+)*", nights):
            raise HTTPException(400, "nights must be dash-separated non-negative integers")
        try:
            parsed_nights = tuple(int(night) for night in nights.split("-"))
        except ValueError as exc:
            raise HTTPException(400, "invalid night number") from exc
        return MarkdownResponse.model_validate({"markdown": render_h1(ledger, parsed_nights, track)})

    @api.get("/health")
    def health() -> HealthResponse:
        return HealthResponse.model_validate(
            {"ok": True, "version": __version__, "kernel": KERNEL_VERSION, "ledger": ledger.exists()}
        )

    @api.get("/status")
    def status_ep() -> StatusResponse:
        return StatusResponse.model_validate(status(root))

    @api.get("/candidates")
    def candidates() -> CandidatesResponse:
        st = replay(ledger)
        return CandidatesResponse.model_validate(
            [{"id": cid, "badge": st.badges[cid], **c.model_dump()} for cid, c in st.candidates.items()]
        )

    @api.get("/candidates/{cid}")
    def candidate(cid: str) -> CandidateDetailResponse:
        st = replay(ledger)
        if cid not in st.candidates:
            raise HTTPException(404, "unknown candidate")
        events = [ev.model_dump() for ev in iter_events(ledger) if ev.candidate_id == cid]
        return CandidateDetailResponse.model_validate(
            {"id": cid, "badge": st.badges[cid], "view": st.candidates[cid].model_dump(), "events": events}
        )

    @api.get("/observations")
    def observations(limit: int = 200) -> ObservationsResponse:
        rows = [ev.model_dump() for ev in iter_events(ledger) if ev.kind == "observe"]
        return ObservationsResponse.model_validate(rows[-limit:])

    @api.get("/objectives")
    def objectives_ep() -> ObjectivesResponse:
        """Every objective in this workspace with its standing. A file that will not load is reported, not hidden."""
        from pravrudhi.application.objectives import load_all, problems, summary

        return ObjectivesResponse.model_validate(
            {
                "objectives": [summary(root, o) for o in load_all(root)],
                "problems": [{"file": f, "reason": r} for f, r in problems(root)],
            }
        )

    @api.get("/objectives/{oid}")
    def objective_ep(oid: str) -> ObjectiveDetailResponse:
        from pravrudhi.application.objectives import load_all, summary
        from pravrudhi.application.recipes import resolve

        for o in load_all(root):
            if o.id == oid:
                return ObjectiveDetailResponse.model_validate(
                    {**summary(root, o), "recipe_detail": resolve(o.recipes)}
                )
        raise HTTPException(404, "no such objective")

    @api.post("/objectives")
    def create_objective(req: ObjectiveRequest) -> ObjectiveResponse:
        """Record an objective. Refused if it could not be measured, because an unmeasurable goal is a wish."""
        from pravrudhi.application.objectives import ObjectiveError, parse, summary, write

        try:
            obj = parse(
                {
                    "id": req.id,
                    "intent": req.intent,
                    "track": req.track,
                    "domain": req.domain,
                    "recipes": req.recipes,
                    "target_delta": req.target_delta,
                    "notes": req.notes,
                    "benchmarks": [
                        {
                            "id": b.id or b.metric.split()[0],
                            "tool": b.tool,
                            "metric": b.metric,
                            "direction": b.direction,
                        }
                        for b in req.benchmarks
                    ],
                }
            )
        except ObjectiveError as e:
            raise HTTPException(422, str(e)) from e
        write(root, obj)
        return ObjectiveResponse.model_validate(summary(root, obj))

    @api.get("/objectives/{oid}/plan", response_model=PlanResponse)
    def objective_plan(oid: str) -> dict[str, Any]:
        """A proposed decomposition of the intent into work. A proposal, never evidence: nothing here has run."""
        from dataclasses import asdict

        from pravrudhi.application.intent import compile_intent
        from pravrudhi.application.objectives import load_all
        from pravrudhi.application.recipes import installed, library

        for o in load_all(root):
            if o.id == oid:
                plan = compile_intent(o, tuple(library()), installed_skills=frozenset(installed()))
                out = asdict(plan)
                out["objective"] = o.id  # the full objective is already available at /api/objectives/{oid}
                return out
        raise HTTPException(404, "no such objective")

    @api.get("/memory", response_model=MemoryResponse)
    def memory_ep() -> dict[str, Any]:
        """What belongs to the user in this workspace. Kept apart from the ledger, which owns what the loop learned."""
        from dataclasses import asdict

        from pravrudhi.application.memory import preferences, recall, threads

        return {
            "preferences": [{"key": k, **{kk: vv for kk, vv in asdict(p).items() if kk != "key"}}
                            for k, p in preferences(root).items()],
            "notes": [asdict(n) for n in recall(root, "", limit=50)],
            "threads": [t.id for t in threads(root)],
        }

    @api.post("/memory/notes", response_model=MemoryNoteResponse)
    def remember_ep(req: RememberRequest) -> dict[str, Any]:
        """Record a durable fact. Refused if it reads as a bare numeric claim about a result."""
        from dataclasses import asdict

        from pravrudhi.application.memory import MemoryError as MemErr
        from pravrudhi.application.memory import remember

        try:
            return asdict(remember(root, req.text, source=req.source or "api"))
        except MemErr as e:
            raise HTTPException(422, str(e)) from e

    @api.get("/tools", response_model=ToolsResponse)
    def tools_ep() -> dict[str, Any]:
        """The tools, connectors and plugins this engine can draw on, each marked available or not on this machine.
        A catalogue, not an execution layer: listing a tool is not a claim it has been invoked."""
        from pravrudhi.application.tools import availability

        return {"tools": availability()}

    def _objective_and_plan(oid: str) -> tuple[Any, Any]:
        from pravrudhi.application.intent import compile_intent
        from pravrudhi.application.objectives import load_all
        from pravrudhi.application.recipes import installed, library

        for o in load_all(root):
            if o.id == oid:
                return o, compile_intent(o, tuple(library()), installed_skills=frozenset(installed()))
        raise HTTPException(404, "no such objective")

    @api.get("/objectives/{oid}/loom", response_model=LoomResponse)
    def objective_loom(oid: str) -> dict[str, Any]:
        """The plan as Loom source. Readable and editable by a person; nothing in it has run."""
        from pravrudhi.application.loom import lift, lower, to_plan_steps

        o, plan = _objective_and_plan(oid)
        source = lower(plan)
        return {"objective": o.id, "source": source, "steps": list(to_plan_steps(lift(source)))}

    @api.get("/objectives/{oid}/subagents", response_model=SubagentsResponse)
    def objective_subagents(oid: str) -> dict[str, Any]:
        """What the engine would dispatch for this plan, and what it has dispatched so far."""
        from dataclasses import asdict

        from pravrudhi.application.subagents import preview, runs

        o, plan = _objective_and_plan(oid)
        return {"preview": preview(o, plan, root), "runs": [asdict(r) for r in runs(root, o.id)]}

    @api.post("/objectives/{oid}/subagents", response_model=DispatchResponse)
    def objective_dispatch(oid: str) -> dict[str, Any]:
        """Hand the plan's tasks to the swarm in the background. Everything they produce is a proposal."""
        import threading

        from pravrudhi.agents.registry import build_agent
        from pravrudhi.application.subagents import dispatch_plan, tasks_from_plan

        o, plan = _objective_and_plan(oid)
        n = len(tasks_from_plan(o, plan, root=root))
        threading.Thread(
            target=dispatch_plan, args=(o, plan),
            kwargs={"root": root, "build_agent": lambda name, model: build_agent(root, name, model), "log": print},
            daemon=True,
        ).start()
        return {"objective": o.id, "started": n}

    @api.get("/recipes")
    def recipes_ep() -> RecipesResponse:
        """The recipe catalogue, each entry marked available or not on this machine. Not evidence: naming a recipe
        does not claim it has been run."""
        from pravrudhi.application.recipes import availability

        return RecipesResponse.model_validate({"recipes": availability()})

    @api.get("/inbox")
    def inbox() -> InboxListingResponse:
        return InboxListingResponse.model_validate(inbox_listing(root))

    @api.get("/evidence/{name}")
    def evidence(name: str) -> EvidenceResponse:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
            raise HTTPException(404, "no such evidence document")
        base = (root / "docs" / "evidence").resolve()
        p = (base / f"{name}.md").resolve()
        if p.parent != base or not p.is_file():
            raise HTTPException(404, "no such evidence document")
        return EvidenceResponse.model_validate({"name": name, "markdown": p.read_text()})

    @api.post("/inbox/sign")
    def sign(req: SignRequest, x_pravrudhi_operator: str | None = Header(default=None)) -> SignResponse:
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
        return SignResponse.model_validate(
            {"seq": ev.seq, "this_hash": ev.this_hash, "decision": req.decision, "by": who}
        )

    app.include_router(api)
    return app


def serve(root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    uvicorn.run(create_app(root), host=host, port=port, log_level="info")


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)
