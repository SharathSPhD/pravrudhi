---
name: pravrudhi-night
description: Run one budgeted Pravrudhi night in the current project (propose, deliberate, execute, dispose). Use when the user asks to improve their model or harness overnight, run a night, or start the loop.
---

# Run a Pravrudhi night

1. Confirm the project is initialised: `uv run pravrudhi status --root .` must report `initialised: true` and `chain_ok: true`. If not, run `uv run pravrudhi init --root .` and stop to let the user download the trainee and proposer weights named in `.pravrudhi/config.yaml`.
2. Confirm nothing else holds the GPU (`nvidia-smi`); a night refuses to start a job when free VRAM is below the measured need plus 2 GiB.
3. Run `uv run pravrudhi night --night <N> --root .` with `--budget <GPU-hours>` if the user set one; otherwise the pre-registered budget in `research/prereg/lora_night.yaml` applies.
4. When it closes, run `uv run pravrudhi status --root .` and `uv run pravrudhi inbox --root .` and report: candidates proposed, executed, promoted or pruned (with their hetvābhāsa labels), GPU-hours spent, and what awaits sign-off.

Rules: never edit `research/ledger.jsonl`, `gates/*.json` or anything under `.pravrudhi/kernel/`; never state a number that is not in the ledger or a gate; promotions listed in the inbox are proposals until the operator signs.
