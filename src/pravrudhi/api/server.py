"""`pravrudhi serve`: FastAPI over the ledger. Everything shown is replayed; nothing is hand-set.

Endpoints: /health, /status, /candidates, /candidates/{id}, /observations, /inbox, /evidence/{name}, /swarm,
/swarm/live, POST /inbox/sign (operator identity required; refused for agent identities)."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Header, HTTPException
from fastapi.routing import APIRoute
from pydantic import BaseModel

from pravrudhi import KERNEL_VERSION, __version__
from pravrudhi.agents.registry import survey
from pravrudhi.api.chat import build_chat_router
from pravrudhi.api.identity import CurrentUserDep, User, auth_mode
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
    LiveAgentsResponse,
    LoomResponse,
    MarkdownResponse,
    MemoryNoteResponse,
    MemoryResponse,
    MeResponse,
    NightsResponse,
    ObjectiveDetailResponse,
    ObjectiveResponse,
    ObjectivesResponse,
    ObservationsResponse,
    PlanResponse,
    ProviderKeyRemovedResponse,
    ProviderKeyResponse,
    ProvidersResponse,
    RecipesResponse,
    SignResponse,
    StatusResponse,
    SubagentsResponse,
    SwarmResponse,
    TokenResponse,
    ToolsResponse,
    UpdateStatusResponse,
    WorkspaceResponse,
    WorkspacesResponse,
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

# The three ways this engine launches a coding agent as a subprocess. Matched against a process's argv so a live
# dispatch can be told apart from a stalled one; see `_scan_live_agents`.
_LIVE_AGENT_PATTERNS: dict[str, str] = {"claude -p": "claude", "codex exec": "codex", "agent_code": "agent_code"}


def _scan_live_agents() -> list[dict[str, Any]]:
    """The API had no way to show which agent processes were actually running on this machine: the routing log
    and the subagent/self-build run logs record what was dispatched and what came back, but nothing in between,
    so an operator watching a long dispatch could not tell a live worker from a stalled one. This reads the
    process table once and keeps only pid, elapsed time, which launch pattern matched, and (if the process's
    cwd is a `.worktrees/` checkout) that path -- never the full command line, which could carry a secret."""
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True, timeout=5, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows: list[dict[str, Any]] = []
    for line in out.splitlines()[1:]:
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        pid_s, etimes_s, args = parts
        kind = next((k for pattern, k in _LIVE_AGENT_PATTERNS.items() if pattern in args), None)
        if kind is None:
            continue
        try:
            pid, elapsed_s = int(pid_s), int(etimes_s)
        except ValueError:
            continue
        worktree: str | None = None
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
            if "/.worktrees/" in cwd:
                worktree = cwd
        except OSError:
            pass
        rows.append({"pid": pid, "elapsed_s": elapsed_s, "kind": kind, "worktree": worktree})
    return rows


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


class WorkspaceRequest(BaseModel):
    slug: str


class SignRequest(BaseModel):
    pack: str
    decision: str  # approve | reject | defer
    note: str = ""


class ProviderKeyRequest(BaseModel):
    """A bring-your-own key to validate and store, with an optional base URL for an OpenAI-compatible endpoint."""

    key: str
    base_url: str | None = None


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

    @api.get("/swarm", response_model=SwarmResponse)
    def swarm_ep() -> dict[str, Any]:
        """Nothing in the API showed the swarm itself: which agents are routed where, what has been dispatched,
        what was accepted. Agent availability, the routing table's live per-tier choice, and the last 100 runs
        of both the objective swarm and the self-build swarm, newest first."""
        from dataclasses import asdict

        from pravrudhi.application import routing, selfbuild, subagents

        return {
            "agents": [{"name": a.name, "available": a.available, "reason": a.reason} for a in survey(root)],
            "routing": routing.report(root),
            "subagent_runs": [asdict(r) for r in reversed(subagents.runs(root)[-100:])],
            "selfbuild_runs": [asdict(r) for r in reversed(selfbuild.runs(root)[-100:])],
        }

    @api.get("/swarm/live", response_model=LiveAgentsResponse)
    def swarm_live_ep() -> list[dict[str, Any]]:
        """The agent processes actually running on this machine right now, not what the run logs say happened."""
        return _scan_live_agents()

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

    @api.get("/update")
    def update_ep() -> UpdateStatusResponse:
        from pravrudhi.application.updates import status as update_status

        return UpdateStatusResponse.model_validate(update_status())

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
    async def memory_ep(user: User | None = CurrentUserDep) -> dict[str, Any]:
        """What belongs to the caller. A logged-in user's memory lives in Supabase; a local engine's on disk. Either
        way it is kept apart from the ledger, which owns what the loop learned."""
        from dataclasses import asdict

        from pravrudhi.application.memory_store import store_for

        store = store_for(root, user)
        return {
            "preferences": [{"key": k, **{kk: vv for kk, vv in asdict(p).items() if kk != "key"}}
                            for k, p in store.preferences().items()],
            "notes": [asdict(n) for n in store.recall("", limit=50)],
            "threads": [t.id for t in store.threads()],
        }

    @api.post("/memory/notes", response_model=MemoryNoteResponse)
    async def remember_ep(req: RememberRequest, user: User | None = CurrentUserDep) -> dict[str, Any]:
        """Record a durable fact. Refused if it reads as a bare numeric claim about a result."""
        from dataclasses import asdict

        from pravrudhi.application.memory import MemoryError as MemErr
        from pravrudhi.application.memory_store import store_for

        try:
            return asdict(store_for(root, user).remember(req.text, source=req.source or "api"))
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

    @api.get("/me", response_model=MeResponse)
    async def me(user: User | None = CurrentUserDep) -> dict[str, Any]:
        """Who is asking. Says so plainly when identity is disabled rather than inventing an anonymous user."""
        base = {"mode": str(auth_mode()), "authenticated": user is not None}
        return base if user is None else {**base, "id": user.id, "email": user.email, "role": user.role}

    @api.get("/workspaces", response_model=WorkspacesResponse)
    async def workspaces_ep(user: User | None = CurrentUserDep) -> dict[str, Any]:
        """The caller's workspaces. Each is a separate directory with its own ledger; none shares evidence."""
        from pravrudhi.application.workspaces import list_workspaces, workspace_dir

        if user is None:
            return {"owner": "local", "workspaces": [{"slug": "local", "path": str(root)}]}
        return {"owner": user.id, "workspaces": [
            {"slug": s, "path": str(workspace_dir(user.id, s))} for s in list_workspaces(user.id)
        ]}

    @api.post("/workspaces", response_model=WorkspaceResponse)
    async def create_workspace(req: WorkspaceRequest, user: User | None = CurrentUserDep) -> dict[str, Any]:
        """Create (idempotently) a workspace for the caller. Refused without an identity: a workspace has an owner."""
        from pravrudhi.application.workspaces import ensure_workspace

        if user is None:
            raise HTTPException(400, "a workspace has an owner; identity is disabled or no token was sent")
        try:
            return {"slug": req.slug, "path": str(ensure_workspace(user.id, req.slug))}
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @api.get("/providers", response_model=ProvidersResponse)
    async def providers_ep(user: User | None = CurrentUserDep) -> list[dict[str, Any]]:
        """The bring-your-own-key registry, marked configured or not for this caller. Never the key or a
        prefix of it — only the shape a valid key for that provider is expected to have."""
        from pravrudhi.application.credentials import PROVIDERS
        from pravrudhi.application.credentials import store_for as credential_store_for

        configured = set(credential_store_for(root, user).configured())
        return [
            {"id": p.id, "title": p.title, "configured": p.id in configured, "key_prefix": p.key_prefix}
            for p in PROVIDERS.values()
        ]

    @api.post("/providers/{provider_id}/key", response_model=ProviderKeyResponse)
    async def set_provider_key(
        provider_id: str, req: ProviderKeyRequest, user: User | None = CurrentUserDep
    ) -> dict[str, Any]:
        """Validate a bring-your-own key against the provider and store it. The validation reason is redacted
        before it leaves the process, since a probe failure can otherwise echo the key back in its message."""
        from pravrudhi.application.credentials import PROVIDERS, redact, validate
        from pravrudhi.application.credentials import store_for as credential_store_for

        if provider_id not in PROVIDERS:
            raise HTTPException(404, "unknown provider")
        validated, reason = validate(provider_id, req.key, base_url=req.base_url)
        credential_store_for(root, user).put(provider_id, req.key)
        return {"provider": provider_id, "configured": True, "validated": validated, "reason": redact(reason)}

    @api.delete("/providers/{provider_id}/key", response_model=ProviderKeyRemovedResponse)
    async def delete_provider_key(provider_id: str, user: User | None = CurrentUserDep) -> dict[str, Any]:
        """Remove a stored bring-your-own key."""
        from pravrudhi.application.credentials import PROVIDERS
        from pravrudhi.application.credentials import store_for as credential_store_for

        if provider_id not in PROVIDERS:
            raise HTTPException(404, "unknown provider")
        credential_store_for(root, user).delete(provider_id)
        return {"provider": provider_id, "configured": False}

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
    app.include_router(build_chat_router(root))
    return app


def serve(root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    uvicorn.run(create_app(root), host=host, port=port, log_level="info")


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)
