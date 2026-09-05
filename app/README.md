# Pravrudhi app — design

provenance / honesty stuff in the app; real app, useful, live/recorded."

## Job to be done
A person with a GPU (or a Mac) installs Pravrudhi and says: **improve this model, or this coding-agent harness, on
this benchmark, with this budget** — and watches it happen. Everything else serves that sentence.

## Shape
One Next.js frontend, two deployments:
1. **Local** — `pravrudhi app` serves the built frontend from the engine's own FastAPI at `http://localhost:8008`.
   No account, no cloud. This is the product a user installs. (Pattern: Orca, OpenCode `web`.)
2. **Hosted** — the same frontend on Vercel at the public URL, pointed at a demo backend. Landing, live/recorded
   demo of the admin's engine, install instructions, and "connect your engine". Auth via Supabase only here, only
   for connecting a user's own engine to their account. (Pattern: kundali / CINS.)

Backend = the existing FastAPI (`src/pravrudhi/api/server.py`), extended. In the first release the demo backend is
the 5090 exposed through a tunnel; it moves to the Oracle VM (sage's `deploy/docker-compose.yml`: caddy + api)
when the image is published.

## Pages (first release, in build order)
| route | name | what the user does |
|---|---|---|
| `/` | Improve | THE page. Pick target (a local model from the machine's cache, or an agent harness), pick benchmark, set budget (GPU-hours), pick proposer model, press **Run**. Live progress: candidates tried, current best, improvement so far as one big number. Stop button. On the hosted demo this is a recorded run playing back. |
| `/runs` | Runs | Every run: when, target, benchmark, budget spent, result. Click → timeline of that run (proposals, paired scores, prunes, promotion). |
| `/models` | Models | What the loop produced: each promoted model/harness with before → after score on its benchmark, the recipe in one line, **Download** (adapter + manifest) and **Use** (start serving it locally). |
| `/machines` | Machines | This machine and any others: GPU, memory, what can run where, what is running now. **Add machine** over SSH. |
| `/settings` | Settings | Proposer model, coding agents available (Claude Code, Codex, local), budgets, API keys for the hosted agents, allowed origins. |
| `/install` (hosted only) | Get it running | Hardware check, copy-paste quickstart, "connect your engine" (login → token → paste into local settings). |

No page shows ledger internals, hash chains, pramāṇa tags, ADRs or hypotheses. Evidence documents stay reachable at
`/api/evidence/...` for people who want them, unlinked from the main navigation.

## Tech (mirror mfoil-cst/app/frontend exactly)
Next.js 16 (App Router), React 19, TypeScript 5, Tailwind 4, `@supabase/ssr` (hosted only, feature-flagged off when
`NEXT_PUBLIC_SUPABASE_URL` is unset — kundali's local-mode pattern). `lucide-react` icons. No component library.
API client in `app/frontend/src/lib/api.ts` reading `NEXT_PUBLIC_API_BASE` (default `http://localhost:8008`).
Static export (`output: "export"`) so the engine can serve it; the Vercel build uses the same output.

## Backend additions (FastAPI)
- `POST /runs` start a night: `{target: "model"|"harness", model, bench, budget_gpu_h, proposer, policy}` → run id.
- `GET /runs`, `GET /runs/{id}`, `POST /runs/{id}/stop`.
- `GET /runs/{id}/events` server-sent events of progress (proposal, paired score, prune, promote, close).
- `GET /models` promoted artefacts with before/after scores; `GET /models/{id}/download`.
- `GET /machines`, `POST /machines` (enrol over SSH); `GET /agents`; `GET/PUT /settings`.
- `GET /doctor`, `/hosts`, `/external`, `/nights`, `/h1/...` (being added by the api-console task).
- `pravrudhi app` CLI: serve frontend build + API on one port; open the browser.

## Supabase (hosted only)
Tables: `engines(id, user_id, name, base_url, token_hash, created_at)`; RLS: users see their own. Nothing else.

## Non-goals (first release)
Electron/desktop packaging (a local web app is the installable app for now), multi-user on one engine, billing.
