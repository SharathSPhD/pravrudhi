# Finetune proposal — prabhasa-nyaya

Status: **proposal only**. Nothing here writes to the ledger, `research/`,
`gates/`, or `pravrudhi_kernel/`. No number in this document is a measured
result — every quantity is a proposed starting point, labeled as such.

## Objective this step serves

A legal-reasoning assistant for Indian jurisprudence that answers a question
of law with the statute or precedent it relied on, and says it does not know
rather than inventing a citation. Reasoning runs over a typed Nyaya meaning
graph rather than over surface text, so a wrong answer can be traced back to
the inference step that produced it.

This step (`finetune`, capability `finetune`) only produces the
`finetune_candidate` artifact — a LoRA adapter. It does not decide whether the
adapter is good enough; that is the `gates` step's job, run against the
success criterion below.

## What this step consumes and produces

- Consumes: `objective` (above), `base_model` (a path or hub id supplied by
  the pipeline, not chosen here), `prepared_corpus` (instruction-tuned
  examples supplied by an earlier corpus-prep step, not produced here).
- Produces: `finetune_candidate` — a PEFT LoRA adapter directory plus the
  training config and logs used to produce it.

Because `base_model` and `prepared_corpus` are inputs owned by other steps,
the scripts below take them as CLI arguments / config fields rather than
hardcoding a path. Nothing here should be read as asserting a specific model
or dataset exists at a specific path today.

## Why sft-lora, and what "grounded in the graph" means for training data

The candidate recipe is `sft-lora`: supervised fine-tuning with a LoRA
adapter on top of a frozen base model. Full fine-tuning is not proposed —
LoRA keeps the adapter small enough to A/B against a frozen baseline (the
success criterion below requires exactly that comparison), and keeps the
retention risk contained to the adapted attention/MLP projections rather than
the whole weight matrix.

The system reasons over a typed Nyaya meaning graph, not surface text. That
means the *finetune* step is not "teach the model Indian case law from raw
text" — it is "teach the model to condition its answer on a linearized graph
context it is handed, cite only nodes/edges present in that context, and
emit an explicit abstention token when the graph does not support an answer."
Concretely, each `prepared_corpus` example is expected to look like:

```
prompt:     <question of law> + <linearized subgraph: statute nodes, case
             nodes, holds/overrules/interprets edges, with stable node ids>
completion: <answer citing only node ids present in the prompt's subgraph>
            OR
            <abstention: "insufficient basis in the provided graph">
```

This step does not build that corpus — it is handed to us as
`prepared_corpus` — but the training config (prompt masking, max sequence
length, no packing) is chosen to preserve that structure, see
`configs/sft_lora.yaml`.

## Proposed quantities (not measured — starting points, with reasoning)

The objective leaves `training_steps` and `compute_budget` unspecified. This
proposal picks:

- **training_steps: 1200** (3 epochs over an assumed ~6,400-example
  `prepared_corpus`, effective batch size 16, i.e. ~400 steps/epoch).
  Rationale: LoRA SFT on instruction-style data with a citation/abstention
  format typically converges within 2-4 epochs; going further on a small
  domain corpus risks overfitting the adapter to surface phrasing of the
  training examples rather than the graph-grounding behavior we want to
  generalize. Treat 1200 as a ceiling with checkpoints every 200 steps
  (`configs/sft_lora.yaml: save_steps: 200`) so the actual corpus size can
  shift epoch count without changing the config — evaluate every checkpoint
  against held-out domain + retention sets and pick the best one rather than
  always taking the last.
- **compute_budget: ~4-6 GPU-hours on a single 32GB-class GPU** (matches the
  host this proposal was written against: one RTX 5090, PyTorch/TRL/PEFT
  stack, no Unsloth). Rationale: at 4-bit or bf16 LoRA with a 7-8B base model,
  seq_len 2048-4096, and batch/grad-accum tuned to fit in ~28GB of the 32GB
  card, 1200 steps is a few GPU-hours; 4-6 hours leaves headroom for the eval
  passes in `eval_compare.py` to run on the same box without a second
  allocation. This is a proposed ceiling to plan around, not a measured
  runtime.

If `prepared_corpus` turns out to be much larger or smaller than the ~6,400
examples assumed above, `training_steps` should scale with it (target 2-3
epochs) rather than staying fixed at 1200 — the config exposes `num_epochs`
as the primary knob and `max_steps` as a hard ceiling for exactly this
reason.

## Files in this proposal

- `configs/sft_lora.yaml` — LoRA + training hyperparameters (TRL `SFTConfig`
  shape) and the proposed step/epoch budget above.
- `scripts/train_sft_lora.py` — runs the `sft-lora` recipe: loads
  `base_model`, applies the LoRA config, trains on `prepared_corpus`, writes
  the adapter to `--output_dir` as `finetune_candidate`.
- `scripts/check_adapter_loads.py` — the first half of the success
  criterion: load the base model, attach the produced adapter, run one
  forward pass, exit non-zero on failure.
- `scripts/eval_compare.py` — the second half: run the adapter and the frozen
  baseline over a held-out domain set (citation-exactness + correct
  abstention rate) and a retention set (e.g. perplexity or accuracy on a
  general-purpose held-out slice unrelated to the legal domain), and print a
  side-by-side comparison. This script reports numbers when run — it does
  not assert what those numbers will be.

## Exact commands to run this recipe

```bash
# 1. Train the LoRA adapter (produces finetune_candidate)
uv run python proposals/prabhasa-nyaya/finetune/scripts/train_sft_lora.py \
    --base_model <base_model path or hub id> \
    --prepared_corpus <path to prepared_corpus jsonl> \
    --config proposals/prabhasa-nyaya/finetune/configs/sft_lora.yaml \
    --output_dir <path to write finetune_candidate adapter>

# 2. Confirm the adapter loads (first half of the success criterion)
uv run python proposals/prabhasa-nyaya/finetune/scripts/check_adapter_loads.py \
    --base_model <base_model path or hub id> \
    --adapter_dir <path to finetune_candidate adapter>

# 3. Compare held-out domain + retention results against the baseline
#    (second half of the success criterion)
uv run python proposals/prabhasa-nyaya/finetune/scripts/eval_compare.py \
    --base_model <base_model path or hub id> \
    --adapter_dir <path to finetune_candidate adapter> \
    --domain_eval_set <path to held-out domain eval jsonl> \
    --retention_eval_set <path to held-out retention eval jsonl>
```

## What counts as success

Per the step's success criterion, this proposal is satisfied when:

1. `check_adapter_loads.py` exits 0 — the adapter attaches to the declared
   `base_model` and produces a completion without error.
2. `eval_compare.py` produces a table showing, for both the adapter and the
   frozen baseline: domain citation-exactness, domain correct-abstention
   rate, and a retention metric — so a human (or the `gates` step) can judge
   whether the adapter improved domain performance without an unacceptable
   regression on retention. This proposal does not pre-judge what threshold
   counts as "acceptable" — that judgment belongs to the gate, not to the
   finetune step.

Nothing in this directory should be read as a completed run: no adapter has
been trained, no eval has been executed, and no number above is a result.
