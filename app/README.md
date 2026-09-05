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
`/api/runs` and `/api/objectives`. Status is at `/api/status`, the recipe catalogue at `/api/recipes`, and evidence
at `/api/evidence/{name}`. The local frontend uses the engine's origin and obtains its local token for mutations.

The API is implemented in [server.py](../src/pravrudhi/api/server.py), with run controls in
[runs.py](../src/pravrudhi/api/runs.py). The browser client is [api.ts](frontend/src/lib/api.ts).
For a separately deployed frontend, `NEXT_PUBLIC_API_BASE` names the engine origin at build time, without the
`/api` suffix. The engine's allowed origins and authorization still apply; setting an address grants no access.
