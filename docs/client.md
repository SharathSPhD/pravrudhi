# Pravrudhi Python Client

Instead of running `pravrudhi` from the shell, you can now talk to a running engine from Python.

## Installation

The client is part of the `pravrudhi` package:

```bash
pip install pravrudhi
```

To use it, start an engine in one terminal:

```bash
pravrudhi app
```

Then import and use the client in your Python code.

## Authentication

When the client connects to `http://127.0.0.1:8008` (the default loopback address), it automatically reads the authentication token from `~/.pravrudhi/app_token`. For non-default addresses or when the file is not readable, pass the token explicitly:

```python
from pravrudhi.client import Client

client = Client(base_url="http://127.0.0.1:8008", token="your-token-here")
```

State-changing operations (POST requests) require the token. Read-only operations do not.

## Examples

### Example 1: Check engine health

```python
from pravrudhi.client import Client

client = Client()
health = client.health()
print(f"Service version: {health.version}")
print(f"Kernel version: {health.kernel}")
print(f"Ledger present: {health.ledger}")
```

### Example 2: List and inspect objectives

```python
from pravrudhi.client import Client

client = Client()
objectives_resp = client.objectives()

for objective in objectives_resp.objectives:
    print(f"Objective: {objective.id}")
    print(f"  Intent: {objective.intent}")
    print(f"  Track: {objective.track}")
    for progress in objective.progress:
        print(f"    {progress.benchmark}: {progress.delta}")

if objectives_resp.problems:
    print("Malformed objectives:")
    for problem in objectives_resp.problems:
        print(f"  {problem.file}: {problem.reason}")
```

### Example 3: Create an objective

```python
from pravrudhi.client import Client

client = Client()

objective = client.create_objective(
    id="gsm8k-accuracy",
    intent="improve model accuracy on GSM8K",
    track="model",
    benchmarks=[
        {
            "id": "gsm8k",
            "tool": "lm-eval",
            "metric": "accuracy",
            "direction": "up",
        }
    ],
    domain="reasoning",
    recipes=["lora-tune"],
    target_delta=0.05,
    notes="Baseline established; ready to optimize",
)

print(f"Created: {objective.id}")
print(f"Created at: {objective.created}")
```

### Example 4: Get a candidate's details

```python
from pravrudhi.client import Client, ClientError

client = Client()

try:
    candidate = client.candidate("c-42")
    print(f"Candidate: {candidate.id}")
    print(f"Badge: {candidate.badge}")
    print(f"Events: {len(candidate.events)}")
    for event in candidate.events[-5:]:
        print(f"  {event.kind}: {event.payload}")
except ClientError as e:
    print(f"Failed to fetch candidate: {e}")
```

### Example 5: Stream a run's progress

```python
from pravrudhi.client import Client

client = Client()

# Start a run
run = client.start_run(
    target="model",
    k=4,
    policy="efe",
    budget_gpu_h=2.0,
)
print(f"Started run {run['id']} (night {run['night']})")

# Stream its events
for event in client.stream_run(run["id"]):
    event_type = event.get("type")
    if event_type == "paired":
        print(f"  Paired: {event['candidate']}, delta={event['delta']:.4f}")
    elif event_type == "promoted":
        print(f"  PROMOTED: {event['candidate']}")
    elif event_type == "closed":
        print(f"  Night closed: {event['status']}")
    elif event_type == "end":
        print(f"  Run {event['status']} (exit code {event['exit_code']})")
```

## Error handling

The client raises `ClientError` for HTTP errors:

```python
from pravrudhi.client import Client, ClientError

client = Client()

try:
    objective = client.objective("no-such-id")
except ClientError as e:
    print(f"Status {e.status_code}: {e.detail}")
    print(f"Path: {e.path}")
```

## Full API

The client mirrors the engine's HTTP API. Methods return typed response objects from `pravrudhi.api.schemas`:

**Read-only:**
- `health()` → HealthResponse
- `status()` → StatusResponse
- `doctor()` → DoctorResponse
- `hosts()` → FleetResponse
- `agents()` → AgentsResponse
- `external()` → ExternalResultsResponse
- `nights()` → NightsResponse
- `h1(track, nights)` → MarkdownResponse
- `candidates()` → CandidatesResponse
- `candidate(cid)` → CandidateDetailResponse
- `observations(limit=200)` → ObservationsResponse
- `objectives()` → ObjectivesResponse
- `objective(oid)` → ObjectiveDetailResponse
- `objective_plan(oid)` → PlanResponse
- `recipes()` → RecipesResponse
- `inbox()` → InboxListingResponse
- `evidence(name)` → EvidenceResponse
- `list_runs()` → list[dict]
- `get_run(run_id)` → dict
- `models()` → list[dict]
- `stream_run(run_id)` → Iterator[dict] (server-sent events)

**State-changing (require token):**
- `create_objective(...)` → ObjectiveResponse
- `sign(pack, decision, operator, note="")` → SignResponse
- `start_run(...)` → dict
- `stop_run(run_id)` → dict

## What this client is not, yet

It imports its response models from `pravrudhi.api.schemas`, which imports from `pravrudhi_kernel`, so installing
the client today installs the kernel with it. That is the opposite of the point: a client should need nothing but a
way to make HTTP requests. Sharing the models is still the right choice while engine and client ship as one
distribution, because two hand-maintained copies of the same shapes drift and a drifted client is worse than a
heavy one. The separation happens when `pravrudhi-client` becomes its own distribution, which the multi-user
design schedules; until then, read the dependency as a known cost rather than an oversight.
