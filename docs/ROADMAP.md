# Roadmap

This document separates current behavior, the next work needed to meet the [product requirements](PRD.md), and
open decisions. Move an item when its behavior is implemented and verified; retain the remaining limitation
alongside it. Evidence of availability and evidence of benchmark improvement are separate claims. This roadmap
makes no release-date or performance promise.

## In force now

The engine exposes local model and harness runs through the command line, with workspace preparation, readiness
checks, budget controls, inbox review and export. Candidate execution is disposable, evidence belongs to the
protected evaluator, and promotion to a canonical artefact remains an operator decision. External scorers supply
proof of benchmark improvement; the internal selection process supplies evidence at its own tier.

Objectives preserve user-authored intent and declare benchmarks, an evidence track, recipe references and an
optional target. The command line supports creation, listing, inspection and progress. The API and Objectives
page expose progress from external results in the ledger, distinguishing missing measurements from a baseline
awaiting comparison. The local page also provides objective creation. Recording intent does not yet direct a run:
the run form selects its target and benchmark separately, and the planned objective option on the night command
is not implemented.

The recipe catalogue ships with the engine and reports local skill availability. Objective detail in the API
resolves available, absent and unknown recipe references. This is discovery and reporting, not automatic recipe
execution or evidence that a technique works. The tool and connector catalogue and measured agent/model routing
are reported the same way: what exists and what is installed here, not a claim that it has been invoked.

An objective's plan can also be read as Loom source, and fanned out to coding agents as scoped subagent tasks,
from both the command line and the API. Either path produces a proposal in `proposals/`, not evidence; nothing
a subagent writes is admitted to the ledger by virtue of having run. A conversational endpoint answers questions
about an objective or a run from the same replayed data as the other routes, restricted to citing ledger rows: a
number the tools did not return is stripped from the reply and reported as a refusal rather than invented. A
separate memory store holds durable notes, kept apart from ledger evidence and addressed to the caller rather
than the workspace. Identity is optional and off by default; enabling it gives each signed-in user their own
workspaces, each with an independent ledger, without changing what a single local engine does unauthenticated.

The local app serves browser pages and API routes together. Improve provides run controls and status, Runs
provides history and event inspection, Machines reports capabilities, and Settings reports coding-agent
availability. Models currently lists candidates with a passing badge; it does not yet provide the complete
artefact comparison, download and use workflow. The hosted default presents a recording and installation guidance.
JSON API routes use the `/api` prefix.

## Next

Connect objective selection to execution. Carry the user's selected objective through the command line and run
form, validate that the chosen execution path can measure it, and make unsupported domain benchmarks explicit.
Completion means a user can follow the same objective from intent through execution to an external comparison
without treating an unrelated track result as proof that their request was carried out.

Complete objective inspection in the browser. Bring recipe resolution into the objective view, support the
benchmark's declared direction and metric format throughout the presentation, and make source measurements
accessible. Completion means that missing evidence, inconclusive change, improvement and regression remain
correctly distinguished for the objective being viewed.

Complete the artefact workflow across Runs and Models. Tie the selected output to its actual promotion state,
external comparison and provenance, then expose supported export and use actions. Completion means the user can
move from a run outcome to a usable artefact without inferring approval from a candidate badge.

Keep the local installation path and hosted recording aligned with supported behavior as these gaps close.
Verify browser navigation, unavailable-service states and the separation between playback and live controls.
Refresh recorded data from admitted evidence when there is a new result worth showing.

## Undecided

Intent interpretation, automatic recipe selection and support for domains without an existing benchmark require
separate decisions. The current objective format records a user's choices; it does not authorize the engine to
invent a measuring instrument or claim a capability that has not been evaluated.

Objectives can share an evidence track. This permits restating an intent while retaining history, but a matching
result does not establish which objective caused the run. Stronger attribution and rules for comparing results
across model configurations remain open design questions.

A hosted account flow for connecting private engines, remote deployment arrangements, and broader administration
controls remain separate from the recorded public site. Shared engine tenancy and billing
have no commitment here. Broader target support should be decided against a concrete evaluation contract.

What happens when a sealed pool runs out of unused items is undecided. Studies and nights draw repeatedly
against the same fixed, kernel-owned pool under an exposure cap; no policy yet governs what happens once that
pool is exhausted — reseal against fresh held-out data, rotate in a second pool, or refuse further runs until an
operator intervenes. This affects every track that seals a pool, not only the one that first exhausts it.

A desktop application is scheduled after the multi-user layer: a window onto a locally running engine, detected and guided rather than installed, with no bundled Python runtime; Tauri attempted first, Electron as the declared fallback, Linux before macOS.
