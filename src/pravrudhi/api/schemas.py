"""HTTP resources were opaque objects, leaving clients to guess the ledger's wire shapes."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, RootModel

from pravrudhi_kernel.ledger.replay import Badge, CandidateView, Locks
from pravrudhi_kernel.schema import LedgerEvent


class HealthResponse(BaseModel):
    """Service identity and ledger presence were invisible to generated clients."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"ok": True, "version": "0.1.0", "kernel": "0.1.0", "ledger": False}]}
    )

    ok: bool
    version: str
    kernel: str
    ledger: bool


class UninitialisedStatus(BaseModel):
    """A workspace without a ledger must not acquire invented replay fields."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"initialised": False}]})
    initialised: Literal[False]


class NightResult(BaseModel):
    """Night closure fields could be absent in audit payloads and surface as null."""

    spent_gpu_h: int | float | None
    outcomes: dict[str, JsonValue] | None
    incumbent: str | None


class InitialisedStatus(BaseModel):
    """Ledger replay, badges and locks previously had no discoverable response contract."""

    initialised: Literal[True]
    chain_ok: bool
    events: int
    ledger_head: str | None
    state_hash: str
    candidates: int
    badges: dict[Badge, int]
    promoted: dict[str, list[str]]
    pruned: int
    nights: dict[int, NightResult]
    inbox_pending: list[str]
    locks: Locks


class StatusResponse(RootModel[UninitialisedStatus | InitialisedStatus]):
    """Missing and replayed ledgers were conflated by an untyped status object."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"initialised": False}]})


class DoctorCheck(BaseModel):
    """Readiness failures had no declared place for their diagnostic explanation."""

    name: str
    ok: bool
    detail: str


class DoctorResponse(BaseModel):
    """Installation readiness and its individual checks were opaque to API consumers."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "ok": False,
                    "checks": [
                        {
                            "name": "initialised",
                            "ok": False,
                            "detail": "Missing: .pravrudhi/config.yaml, research/ledger.jsonl",
                        },
                        {
                            "name": "ledger",
                            "ok": False,
                            "detail": "Cannot read research/ledger.jsonl: No such file or directory",
                        },
                        {
                            "name": "docker",
                            "ok": False,
                            "detail": (
                                "Permission denied running 'docker info': add your user to the docker group "
                                "(then log out and back in) or use sudo."
                            ),
                        },
                        {"name": "gpu", "ok": True, "detail": "No GPU detected: 'nvidia-smi' failed (exited 9)."},
                        {
                            "name": "pools",
                            "ok": False,
                            "detail": "No sealed pool manifest under .pravrudhi/kernel/pools.",
                        },
                        {
                            "name": "prereg",
                            "ok": False,
                            "detail": (
                                "Missing pre-registration files: lora_night.yaml, harness_night.yaml, "
                                "controller.yaml, canaries.md"
                            ),
                        },
                    ],
                }
            ]
        }
    )

    ok: bool
    checks: list[DoctorCheck]


class HostSpecResponse(BaseModel):
    """Enrolled machine addresses and transports were hidden inside an untyped fleet."""

    name: str
    transport: str
    address: str
    user: str
    workdir: str
    orca_host_id: str


class HostCapabilitiesResponse(BaseModel):
    """Measured host capabilities, including derived capabilities, lacked a wire contract."""

    os: str
    arch: str
    cpu_count: int
    ram_gb: float
    gpu_name: str
    gpu_vram_gb: float
    accelerator: str
    accel_mem_gb: float
    docker: bool
    python: str
    agents: list[str]
    local_models: list[str]
    reachable: bool
    error: str
    can_train: bool
    can_serve_open_models: bool
    usable_model_gb: float


class HostResponse(BaseModel):
    """A fleet entry did not distinguish enrollment from measured capabilities in its schema."""

    host: HostSpecResponse
    capabilities: HostCapabilitiesResponse


class FleetResponse(BaseModel):
    """The fleet's machine collection was previously an opaque object."""

    hosts: list[HostResponse]


class AgentResponse(BaseModel):
    """Agent availability had no declared diagnostic reason for an unavailable agent."""

    name: str
    available: bool
    reason: str


class ExternalResponse(BaseModel):
    """External scorer records lost their contract and scorer-specific audit extensions."""

    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    seq: int
    night: int
    kind: str
    severity: str | None = None
    tier: str | None = None
    track: str | None = None
    condition: str | None = None
    model: str | None = None
    seed: int | None = None
    file: str | None = None
    sha256: str | None = None
    tool: str | None = None
    tool_version: str | None = None
    metrics: dict[str, dict[str, int | float]] | None = None
    n_samples: dict[str, int | None] | None = None
    transformers_version: str | None = None
    n_shot: dict[str, JsonValue] | None = None
    model_args: str | dict[str, JsonValue] | None = None
    dataset: str | None = None


class NightResponse(NightResult):
    """Completed nights had no declared link to their track and starting selection policy."""

    night: int
    track: str
    selection_policy: str | None


class MarkdownResponse(BaseModel):
    """Rendered evidence text was advertised only as an arbitrary string dictionary."""

    markdown: str


class EvidenceResponse(MarkdownResponse):
    """Named evidence documents lacked a declared document name beside their text."""

    name: str


class CandidateResponse(CandidateView):
    """Candidate replay fields had no API identity or badge in the generated schema."""

    id: str
    badge: Badge


class EventResponse(LedgerEvent):
    """Ledger envelopes were opaque despite having fixed metadata and extensible JSON payloads."""

    payload: dict[str, JsonValue]


class CandidateDetailResponse(BaseModel):
    """A candidate's replay view and supporting events were indistinguishable opaque objects."""

    id: str
    badge: Badge
    view: CandidateView
    events: list[EventResponse]


class BenchmarkResponse(BaseModel):
    """An objective's measuring instrument had no discoverable metric or direction."""

    id: str
    tool: str
    metric: str
    direction: str


class MeasurementResponse(BaseModel):
    """External measurements lacked declared provenance alongside their reported values."""

    value: float
    stderr: float
    n: int
    model: str
    night: int
    seq: int
    sha256: str


class ProgressResponse(BaseModel):
    """Unmeasured objectives could not be distinguished from measured progress in the schema."""

    benchmark: str
    state: Literal["unmeasured", "baseline_only", "measured"]
    reason: str
    baseline: MeasurementResponse | None
    latest: MeasurementResponse | None
    delta: float | None
    delta_lo: float | None
    delta_hi: float | None
    target_delta: float | None
    met: bool | None
    significant: bool


class ObjectiveResponse(BaseModel):
    """User intent, measuring instruments and replayed progress had no shared wire contract."""

    id: str
    intent: str
    track: str
    benchmarks: list[BenchmarkResponse]
    domain: str
    recipes: list[str]
    target_delta: float | None
    created: str
    notes: str
    progress: list[ProgressResponse]


class ObjectiveProblem(BaseModel):
    """Malformed objective files needed a visible filename and reason instead of disappearing."""

    file: str
    reason: str


class ObjectivesResponse(BaseModel):
    """The objective collection and load failures previously lacked a declared response shape."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"objectives": [], "problems": []}]})
    objectives: list[ObjectiveResponse]
    problems: list[ObjectiveProblem]


class RecipeResponse(BaseModel):
    """Catalogued recipes lacked a contract separating their description from local availability."""

    id: str
    capability: str
    title: str
    skill: str
    summary: str
    source: str
    available: bool


class RecipeResolution(BaseModel):
    """Absent and unknown objective recipes were not distinguishable in generated clients."""

    available: list[RecipeResponse]
    absent: list[RecipeResponse]
    unknown: list[str]


class ObjectiveDetailResponse(ObjectiveResponse):
    """An objective's resolved recipes were missing from its documented resource shape."""

    recipe_detail: RecipeResolution


class RecipesResponse(BaseModel):
    """The packaged recipe catalogue was hidden behind an arbitrary object response."""

    recipes: list[RecipeResponse]


class InboxResponse(BaseModel):
    """Review packs lacked a declared signature state and nullable candidate badge."""

    pack: str
    candidate: str
    badge: Badge | None
    night: str
    signed: bool


class SignResponse(BaseModel):
    """An operator decision's ledger receipt had no discoverable identity or hash fields."""

    seq: int
    this_hash: str
    decision: str
    by: str


class TokenResponse(BaseModel):
    """The local guard's token response was absent from the API's resource contracts."""

    token: str


class AgentsResponse(RootModel[list[AgentResponse]]):
    """The agent collection previously left its entries untyped."""


class ExternalResultsResponse(RootModel[list[ExternalResponse]]):
    """The external collection previously left its entries untyped."""


class NightsResponse(RootModel[list[NightResponse]]):
    """The night collection previously left its entries untyped."""


class CandidatesResponse(RootModel[list[CandidateResponse]]):
    """The candidate collection previously left its entries untyped."""


class ObservationsResponse(RootModel[list[EventResponse]]):
    """The event collection previously left its entries untyped."""


class InboxListingResponse(RootModel[list[InboxResponse]]):
    """The inbox collection previously left its entries untyped."""


class QuantityResponse(BaseModel):
    """A quantity a step needs that the objective did not supply. `value` is null because it is unspecified, not
    because it is zero; the compiler names what is missing rather than guessing it."""

    name: str
    value: float | None = None


class SuccessCheckResponse(BaseModel):
    """What would justify keeping a step's output."""

    criterion: str
    benchmarks: list[BenchmarkResponse] = []
    target_delta: float | None = None


class PlanStepResponse(BaseModel):
    """One proposed step. Nothing here has run; `availability` reports whether a recipe for it exists on this
    machine, not whether it was used."""

    id: str
    capability: str
    recipe_ids: list[str]
    available_recipe_ids: list[str]
    availability: str
    consumes: list[str]
    produces: list[str]
    check: SuccessCheckResponse
    quantities: list[QuantityResponse]
    reason: str


class PlanResponse(BaseModel):
    """A decomposition of an objective's intent into work. A proposal, never evidence."""

    objective: str
    steps: list[PlanStepResponse]
    external_inputs: list[str] = []
    unknown_recipes: list[str] = []
    assumptions: list[str] = []
    review_notes: list[str] = []
