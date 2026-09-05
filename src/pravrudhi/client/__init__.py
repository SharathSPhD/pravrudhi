"""Typed HTTP client for a running Pravrudhi engine.

Without this, users had to shell out to the CLI to drive an engine. Now they can
`pip install pravrudhi` and talk to the engine from Python with full type safety.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast, overload

import httpx

from pravrudhi.api.schemas import (
    AgentsResponse,
    CandidateDetailResponse,
    CandidatesResponse,
    DoctorResponse,
    EvidenceResponse,
    ExternalResultsResponse,
    FleetResponse,
    HealthResponse,
    InboxListingResponse,
    MarkdownResponse,
    NightsResponse,
    ObjectiveDetailResponse,
    ObjectiveResponse,
    ObjectivesResponse,
    ObservationsResponse,
    PlanResponse,
    RecipesResponse,
    SignResponse,
    StatusResponse,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T", bound="BaseModel")

__all__ = ["Client", "ClientError"]


class ClientError(Exception):
    """An API call returned a non-2xx response."""

    def __init__(
        self, path: str, status_code: int, detail: str | None = None
    ) -> None:
        self.path = path
        self.status_code = status_code
        self.detail = detail
        message = f"{status_code} {path}"
        if detail:
            message += f": {detail}"
        super().__init__(message)


class Client:
    """Typed HTTP client for a running Pravrudhi engine.

    Addresses an engine at base_url, sending required headers and the local token
    for state-changing calls. When token is None and base_url is loopback, reads
    it from the file localguard names.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8008",
        token: str | None = None,
        _http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._http_client = _http_client
        if self.token is None and self._is_loopback():
            self.token = self._read_local_token()

    def _is_loopback(self) -> bool:
        """Whether base_url addresses a loopback interface."""
        from urllib.parse import urlsplit

        parts = urlsplit(self.base_url)
        hostname = (parts.hostname or "").lower()
        return hostname in ("127.0.0.1", "localhost", "::1")

    def _read_local_token(self) -> str | None:
        """Read the token from .pravrudhi/app_token if readable, else None."""
        try:
            home = Path.home()
            token_file = home / ".pravrudhi" / "app_token"
            if token_file.exists():
                return token_file.read_text().strip()
        except (OSError, ValueError):
            pass
        return None

    def _get_host_header(self) -> str:
        """Extract the Host header value from base_url."""
        from urllib.parse import urlsplit

        parts = urlsplit(self.base_url)
        host = parts.hostname or "localhost"
        if parts.port:
            host = f"{host}:{parts.port}"
        return host

    def _headers(self, *, require_token: bool = False) -> dict[str, str]:
        """Build request headers, including the local token for state changes."""
        headers = {"Host": self._get_host_header()}
        if require_token:
            if not self.token:
                raise ClientError(
                    "(local token required)",
                    401,
                    "state-changing call requires a token; "
                    "read it from .pravrudhi/app_token or pass token=... to Client()",
                )
            headers["x-pravrudhi-token"] = self.token
        return headers

    @overload
    def _request(
        self,
        method: str,
        path: str,
        response_model: None = None,
        **kwargs: Any,
    ) -> Any:
        ...

    @overload
    def _request(
        self,
        method: str,
        path: str,
        response_model: type[T],
        **kwargs: Any,
    ) -> T:
        ...

    def _request(
        self,
        method: str,
        path: str,
        response_model: type[T] | None = None,
        **kwargs: Any,
    ) -> T | Any:
        """Make an HTTP request and parse the response."""
        require_token = method not in ("GET", "HEAD", "OPTIONS")
        headers = self._headers(require_token=require_token)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        url = f"{self.base_url}/api{path}"
        try:
            if self._http_client is not None:
                resp = self._http_client.request(method, url, headers=headers, **kwargs)
            else:
                with httpx.Client() as client:
                    resp = client.request(method, url, headers=headers, **kwargs)
            if not (200 <= resp.status_code < 300):
                try:
                    detail = resp.json().get("detail")
                except (ValueError, AttributeError):
                    detail = resp.text or None
                raise ClientError(path, resp.status_code, detail)
            if response_model is None:
                return resp.json() if resp.text else None
            return response_model.model_validate(resp.json())
        except httpx.RequestError as e:
            raise ClientError(path, 0, str(e)) from e

    def _stream_request(self, path: str) -> Iterator[dict[str, Any]]:
        """Stream server-sent events from an endpoint."""
        headers = self._headers(require_token=False)
        url = f"{self.base_url}/api{path}"
        try:
            with httpx.stream("GET", url, headers=headers) as resp:
                if not (200 <= resp.status_code < 300):
                    try:
                        detail = resp.json().get("detail")
                    except (ValueError, AttributeError):
                        detail = resp.text or None
                    raise ClientError(path, resp.status_code, detail)
                for line in resp.iter_lines():
                    line = line.strip()
                    if line.startswith("data: "):
                        with contextlib.suppress(json.JSONDecodeError, ValueError):
                            yield json.loads(line[6:])
        except httpx.RequestError as e:
            raise ClientError(path, 0, str(e)) from e

    def health(self) -> HealthResponse:
        """Service identity and ledger presence."""
        return self._request("GET", "/health", HealthResponse)

    def status(self) -> StatusResponse:
        """Ledger replay state and validation status."""
        return self._request("GET", "/status", StatusResponse)

    def doctor(self) -> DoctorResponse:
        """Installation readiness and its individual checks."""
        return self._request("GET", "/doctor", DoctorResponse)

    def hosts(self) -> FleetResponse:
        """Enrolled machines, their capabilities, and reachability."""
        return self._request("GET", "/hosts", FleetResponse)

    def agents(self) -> AgentsResponse:
        """Available agent implementations and why unavailable ones are blocked."""
        return self._request("GET", "/agents", AgentsResponse)

    def external(self) -> ExternalResultsResponse:
        """External scorer records and scorer-specific audit extensions."""
        return self._request("GET", "/external", ExternalResultsResponse)

    def nights(self) -> NightsResponse:
        """Completed nights with track, selection policy, and outcomes."""
        return self._request("GET", "/nights", NightsResponse)

    def h1(self, track: str, nights: str) -> MarkdownResponse:
        """Rendered evidence text for a track's nights, as markdown.

        nights is a dash-separated sequence of integers, e.g. "0-5" or "3".
        """
        return self._request("GET", f"/h1/{track}/{nights}", MarkdownResponse)

    def candidates(self) -> CandidatesResponse:
        """Every candidate in the ledger with its badge and replay fields."""
        return self._request("GET", "/candidates", CandidatesResponse)

    def candidate(self, cid: str) -> CandidateDetailResponse:
        """A candidate's replay view, badge, and supporting events."""
        return self._request("GET", f"/candidates/{cid}", CandidateDetailResponse)

    def observations(self, limit: int = 200) -> ObservationsResponse:
        """Recent observe events from the ledger."""
        return self._request(
            "GET", "/observations", ObservationsResponse, params={"limit": limit}
        )

    def objectives(self) -> ObjectivesResponse:
        """Every objective in this workspace with its standing."""
        return self._request("GET", "/objectives", ObjectivesResponse)

    def objective(self, oid: str) -> ObjectiveDetailResponse:
        """An objective with its standing and resolved recipes."""
        return self._request("GET", f"/objectives/{oid}", ObjectiveDetailResponse)

    def create_objective(
        self,
        id: str,
        intent: str,
        track: str,
        benchmarks: list[dict[str, str | float]],
        domain: str = "",
        recipes: list[str] | None = None,
        target_delta: float | None = None,
        notes: str = "",
    ) -> ObjectiveResponse:
        """Record an objective. Refused if unmeasurable."""
        payload = {
            "id": id,
            "intent": intent,
            "track": track,
            "benchmarks": benchmarks,
            "domain": domain,
            "recipes": recipes or [],
            "target_delta": target_delta,
            "notes": notes,
        }
        return self._request("POST", "/objectives", ObjectiveResponse, json=payload)

    def objective_plan(self, oid: str) -> PlanResponse:
        """A proposed decomposition of an objective's intent into work."""
        return self._request("GET", f"/objectives/{oid}/plan", PlanResponse)

    def recipes(self) -> RecipesResponse:
        """The recipe catalogue, each entry marked available or not."""
        return self._request("GET", "/recipes", RecipesResponse)

    def inbox(self) -> InboxListingResponse:
        """Review packs pending operator sign-off."""
        return self._request("GET", "/inbox", InboxListingResponse)

    def evidence(self, name: str) -> EvidenceResponse:
        """A named evidence document from docs/evidence/{name}.md."""
        return self._request("GET", f"/evidence/{name}", EvidenceResponse)

    def sign(
        self,
        pack: str,
        decision: str,
        operator: str,
        note: str = "",
    ) -> SignResponse:
        """Record an operator's sign-off decision on a review pack.

        decision must be one of: approve, reject, defer.
        operator is the name of the human making the decision.
        """
        payload = {"pack": pack, "decision": decision, "note": note}
        headers = {"x-pravrudhi-operator": operator}
        return self._request(
            "POST", "/inbox/sign", SignResponse, json=payload, headers=headers
        )

    def start_run(
        self,
        target: str,
        bench: str = "",
        budget_gpu_h: float | None = None,
        k: int = 8,
        policy: str = "efe",
        proposer_gguf: str = "",
        proposer_endpoint: str = "",
    ) -> dict[str, Any]:
        """Start a model or harness night run. Returns run metadata.

        target must be one of: model, harness.
        policy must be one of: efe, greedy, thompson, random.
        """
        payload = {
            "target": target,
            "bench": bench,
            "budget_gpu_h": budget_gpu_h,
            "k": k,
            "policy": policy,
            "proposer_gguf": proposer_gguf,
            "proposer_endpoint": proposer_endpoint,
        }
        return cast(dict[str, Any], self._request("POST", "/runs", None, json=payload))

    def list_runs(self) -> list[dict[str, Any]]:
        """List all runs, newest first."""
        return cast(list[dict[str, Any]], self._request("GET", "/runs", None))

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Get a run's metadata and recent event history."""
        return cast(dict[str, Any], self._request("GET", f"/runs/{run_id}", None))

    def stop_run(self, run_id: str) -> dict[str, Any]:
        """Stop a running night."""
        return cast(dict[str, Any], self._request("POST", f"/runs/{run_id}/stop", None))

    def stream_run(self, run_id: str) -> Iterator[dict[str, Any]]:
        """Stream server-sent events from a run's progress."""
        return self._stream_request(f"/runs/{run_id}/events")

    def models(self) -> list[dict[str, Any]]:
        """What the loop produced: each promotion with external before/after."""
        return cast(list[dict[str, Any]], self._request("GET", "/models", None))
