# Pravrudhi — प्रवृद्धि

Pravrudhi is a recursive self-improvement engine for language-model systems that you run on your own hardware, over your own model and your own harness. You install one package, initialise it inside a project, point the configuration at a local model and a target (a LoRA-tunable model, a metric-emitting script, or an agent harness directory), and run a budgeted night. The night proposes changes, selects among them with an expected-free-energy controller over a posterior that lives outside the language model, executes each selected candidate in a disposable sandbox, scores it with an evaluator kernel the mutated process cannot reach, and disposes of it by a sequential test. In the morning the inbox lists what the night wants promoted; you accept or reject; `pravrudhi export` hands back the improved artefact.

Status: under construction. Nothing on this page states a measurement; measurements appear only in the paper under `paper/` and only when a gate has produced them.

## Install

```bash
uv sync
uv run pravrudhi --help
```

## Layout

`pravrudhi_kernel/` is the evaluator kernel: schema, hash-chained ledger, statistics, controller mathematics, scorers. It has no model client and no network access. `src/pravrudhi/` is the engine: targets, model backends, proposer, night orchestrator, CLI, API and the Claude Code plugin. The kernel is a dependency of the engine, never the reverse.

## Licence

Apache-2.0.
