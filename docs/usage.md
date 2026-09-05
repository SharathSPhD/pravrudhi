# Using Pravrudhi

## What a night does

A night is a budgeted batch of experiments on your own model or harness. In the deliberation window a local proposer model (served by llama.cpp) reads the ledger's evidence and emits candidate recipes as JSON inside a fixed grammar; a predictor emits a predicted effect and a confidence for each, which are hash-committed before anything runs. The controller rebuilds its posterior from the ledger, scores each live candidate by expected free energy (expected information gain, expected log-preference, cost), refuses to proceed if the scores do not condition on the action, and fills the budget by a Thompson-like knapsack with an epistemic floor. In the execution windows each selected candidate is trained in a disposable container, evaluated against the incumbent on the same held-out rotation with the same sampling seed, scored by the kernel, and disposed by an always-valid sequential test; a candidate that crosses the efficacy boundary must also pass the pre-registered canaries before it becomes the incumbent. The night closes with audit rows for the strategy-switch rate and any rethink checkpoints.

## What you can and cannot change

You may edit anything under `harness/` (prompts, templates), `research/prereg/*.yaml` (budgets, grammar bounds, thresholds; each change is a pre-registration change and should carry an ADR in your own project), and `.pravrudhi/config.yaml`. You may not edit `research/ledger.jsonl`, `research/state.json`, or anything under `.pravrudhi/kernel/`; the ledger writer refuses a file whose hash chain does not verify, and `pravrudhi replay --verify` names the first broken line.

## Reading the evidence

`pravrudhi status` summarises the ledger. `pravrudhi inbox` lists promotion packs with badges derived by replay: grey has no observation, amber is under test, green is promoted and not since pruned, red is pruned or audited. `pravrudhi evidence night1` renders a per-candidate account of a night from the ledger alone; `make reproduce` fails if a rendered document differs from the committed one. `pravrudhi serve` exposes the same views over HTTP. Numbers you quote elsewhere should come from these outputs; `make headline-check` flags any measurement-looking number in the README, paper or evidence documents that does not trace to a gate or pre-registration file.

## Sign-off and export

Promotion to incumbent inside a night is automatic and reversible by replay; merging an adapter into base weights, or shipping it, is a human act. Sign a pack through the API with the `X-Pravrudhi-Operator` header (agent identities are refused) or a gate with `pravrudhi gate sign`, then `pravrudhi export <dir>` copies the green adapter with a provenance manifest naming the candidate, the ledger head and the adapter hash.

## Targets

The first target is adapter-only self-improvement of a local model on GSM8K with a deterministic checker. The `Target` protocol in `src/pravrudhi/targets/base.py` is the extension point: a target declares its surfaces and edit families, materialises a candidate into a work directory, and returns a container job whose per-item outputs the kernel scores. Script and agent-harness targets follow the same protocol.
