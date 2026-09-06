---
name: pravrudhi-operator
description: Drive the Pravrudhi RSI engine day to day - status, objectives, heartbeat, updates, evidence export. Use when a fresh session needs to operate this repo's running engine rather than edit its code.
---

# Pravrudhi operator

Pravrudhi is a recursive self-improvement engine that runs budgeted nights
over its own model and harness. This skill is for *operating* an already
installed engine, not for editing `pravrudhi_kernel/` (T0, not yours to
touch) or fabricating results.

## The one rule that overrides everything else

**Never state a number the ledger does not contain.** If you don't know a
score, a token count, or a pass rate, say so and point at where it would be
recorded instead of estimating. Gates, evidence, and the ledger are the only
source of truth for claims about engine performance.

## Daily commands

- `pravrudhi status` - current engine state: what night (if any) is running,
  last heartbeat, last gate result.
- `pravrudhi objective list` - the objective ledger: what's proposed,
  in-progress, done, and each objective's undone steps.
- `pravrudhi heartbeat` - manually trigger a beat outside its schedule: picks
  the most neglected undone objective step and dispatches it under the
  proposal sandbox policy. The same logic backs `GET /api/heartbeat` and the
  Heartbeat page in the web UI.
- `pravrudhi update --apply --if-due` - apply a pending update only if one is
  due on the engine's configured channel; safe to run unconditionally on a
  schedule since it no-ops when nothing is due.
- `pravrudhi demo-export` - export a evidence bundle suitable for showing
  someone the engine's actual state (not a synthetic stand-in).

Run `pravrudhi <command> --help` for the full flag set before assuming one -
flags evolve and this skill does not chase them.

## Where evidence lives

- **Gates**: `gates/` holds the pass/fail record a claim of "this improved"
  must cite. Do not summarize a gate result you have not read.
- **Objective ledger**: backs `objective list`; each entry's undone steps are
  what `heartbeat` dispatches against.
- **`.pravrudhi/`**: engine-local state (config, run state). Read it to
  understand what's configured; never commit it (see the guard hook in
  `deploy/hooks/`).
- Both `gates/` and `.pravrudhi/` are operator state, not code - useful for
  diagnosis, off limits for `git add`.

## Update channels

The engine has two channels: a **dev** channel for tracking active work
closely, and a **release** channel for stable cuts. `pravrudhi update` reads
whichever channel is configured and only applies a version once it clears
the release-check safeguards - it will not reinstall a version it is already
running. The Updates panel in the web settings UI exposes the same
config/apply/rollback flow as the CLI; use whichever is at hand, they read
the same state.

## Reading the swarm and Pages views

The Pages index leads with the live dashboard and real commit history - a
faster way to sanity-check "what has this engine actually done" than
re-deriving it from raw logs. The swarm console (also mirrored into the
public snapshot) shows concurrent agent activity if multiple engines or
agents are running against the same objective ledger.

## Working autonomously

This engine is meant to be driven card-to-card without hand-holding, but
every gate you report on needs a functional transcript or ledger entry
behind it - a green test suite alone is not a claim about the engine's
behavior, only about its code. When a card's acceptance criteria ask for a
number, quote it from the ledger or gate output, verbatim, or say it isn't
there yet.
