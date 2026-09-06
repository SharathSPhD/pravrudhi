# Pravrudhi app

State what you want to improve, measure it against a benchmark and inspect the result. The local interface shows
your engine's work; the hosted site demonstrates the workflow with recorded results.

## Run locally

From the repository root, install and prepare the workspace:

```bash
uv sync
uv run pravrudhi init --root .
make exec-image
uv run pravrudhi doctor --root .
```

Resolve the readiness checks before running experiments. Follow the [engine quickstart](../README.md) for model
setup, benchmark preparation and the noise-floor study. The command line supports model and harness runs,
objective progress, inbox review and export.

Build the browser interface from the source checkout, then start the local app:

```bash
cd app/frontend
npm ci
npm run build
cd ../..
uv run pravrudhi app --root .
```

The command opens the browser and serves the interface with the engine API. Keep the terminal running while using
it. No account is required. Without a frontend build, the command serves the API only and reports the missing build.

## Hosted recorded site

The public deployment uses the same frontend with recorded engine output. Playback illustrates a past run;
it does not run experiments on the visitor's hardware. Use the installation page to start your own local engine.
Objectives and recipes in a recording describe the recorded workspace, not capabilities detected on your machine.

## API

Every JSON route lives under `/api`. Browser pages such as `/runs` and `/objectives` are distinct from
`/api/runs` and `/api/objectives`. Status is at `/api/status`, the recipe catalogue at `/api/recipes`, the tool
and connector catalogue at `/api/tools`, and evidence at `/api/evidence/{name}`. An objective's plan can be read
as Loom source at `/api/objectives/{id}/loom`, and fanned out to coding agents at `/api/objectives/{id}/subagents`;
either way the output is a proposal, never accepted evidence. The local frontend uses the engine's origin and
obtains its local token for mutations.

`POST /api/chat` is a conversational front door over the same replayed data as the routes above: a reply may only
state a number a tool call actually returned, citing the ledger rows behind it, and anything it cannot verify is
stripped out and reported as a refusal rather than invented. Its model endpoint is `PRAVRUDHI_CHAT_ENDPOINT`
(falling back to the proposer's own local llama.cpp). `/api/memory` holds durable notes kept apart from ledger
evidence, following the caller rather than the workspace.

Identity is optional. With `PRAVRUDHI_AUTH=required` and a Supabase project configured (see `supabase/`),
`/api/me` reports the signed-in account and `/api/workspaces` lists and creates that user's own workspaces, each
with its own ledger. Leave `PRAVRUDHI_AUTH` unset and every route answers to the local operator, no account
required.

The API is implemented in [server.py](../src/pravrudhi/api/server.py), with run controls in
[runs.py](../src/pravrudhi/api/runs.py) and the chat router in
[chat.py](../src/pravrudhi/api/chat.py). The browser client is [api.ts](frontend/src/lib/api.ts).
For a separately deployed frontend, `NEXT_PUBLIC_API_BASE` names the engine origin at build time, without the
`/api` suffix. The engine's allowed origins and authorization still apply; setting an address grants no access.
