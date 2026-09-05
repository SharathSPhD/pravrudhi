# Pravrudhi — प्रवृद्धि

Pravrudhi is a recursive self-improvement engine for language-model systems that you run on your own hardware, over your own model and your own harness. You install one package, initialise it inside a project, point the configuration at a local model and a target, and run a budgeted night. The night proposes changes, selects among them with an expected-free-energy controller over a posterior that lives outside the language model, executes each selected candidate in a disposable sandbox, scores it with an evaluator kernel the mutated process cannot reach, and disposes of it by a sequential test. In the morning the inbox lists what the night wants promoted; you accept or reject; `pravrudhi export` hands back the improved artefact.

Nothing on this page states a measurement. Measurements live in the paper under `paper/` and in evidence documents rendered from the ledger, and only once a gate has produced them.

## Quickstart (one GPU, Linux, Docker with the NVIDIA runtime)

```bash
git clone https://github.com/SharathSPhD/pravrudhi.git && cd pravrudhi
uv sync
uv run pravrudhi init --root .                       # kernel state dir, config, pre-registrations, prompts, genesis ledger
make exec-image                                       # execution image (derived from a local NVIDIA PyTorch image)
uvx --from huggingface_hub hf download Qwen/Qwen3-4B  # trainee
uvx --from huggingface_hub hf download Qwen/Qwen3-30B-A3B-GGUF --include "Qwen3-30B-A3B-Q4_K_M.gguf"   # proposer
docker pull ghcr.io/ggml-org/llama.cpp:server-cuda
uv run pravrudhi pool seal-gsm8k path/to/gsm8k-test.parquet --root .   # seal the held-out pool (kernel-owned)
uv run pravrudhi preflight --root .                   # measure VRAM and throughput on your card
uv run pravrudhi study noise-floor --root .           # the noise floor of your unmodified model (required before a night)
uv run pravrudhi night --night 1 --root .             # one budgeted night
uv run pravrudhi inbox --root .                       # what the night wants promoted
uv run pravrudhi export ./adapter --root .            # the green adapter, with provenance
uv run pravrudhi serve --root .                       # HTTP: /status /candidates /observations /inbox /evidence

# harness track (fixed model, mutable scaffold, MBPP+ hidden tests in the sandbox; HumanEval+ as external proof)
uv run pravrudhi pool seal-mbppplus --root .
uv run pravrudhi study harness-noise-floor --root .
uv run pravrudhi harness-night --night 1 --root .
scripts/ext_humaneval.sh Qwen/Qwen3-1.7B harness/agent/harness.json ./research/ext/humaneval-after
```

`pravrudhi replay --verify` rebuilds the state view from the ledger and verifies the hash chain; `make reproduce` regenerates every evidence document from the ledger and fails on any difference.

## What runs where

`pravrudhi_kernel/` is the evaluator kernel: schema, hash-chained ledger, vendored statistics, controller mathematics, sealed pools, scorers, and the sandbox runner. It has no model client and no network access; it is the only writer of evidence. `src/pravrudhi/` is the engine: targets, model backends, the proposer, the night orchestrator, CLI, API, and the Claude Code plugin under `plugin/`. The kernel is a dependency of the engine, never the reverse.

## Claude Code plugin

`plugin/` carries skills `pravrudhi-night`, `pravrudhi-inbox`, `pravrudhi-status`, `pravrudhi-export`. Install it as a local plugin to drive a project from an agent session; sign-off stays a human act (the API refuses agent identities).

## Licence

Apache-2.0.
