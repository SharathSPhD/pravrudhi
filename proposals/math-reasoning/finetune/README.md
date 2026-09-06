# finetune / math-reasoning — sft-lora proposal

Status: **proposal only**. Nothing here has been run. No number in this
document is a measured result — every figure is a proposed starting point
to be replaced by whatever the actual training/eval run produces.

## Step contract

- Step: `finetune`, capability: `finetune`
- Consumes: `objective`, `base_model`, `prepared_corpus`
- Produces: `finetune_candidate`
- Recipe: `sft-lora` (LoRA adapter over a frozen base model, trained with
  supervised fine-tuning on the prepared corpus)

## Objective (verbatim intent)

> A small model that solves grade-school arithmetic word problems more
> reliably than the checkpoint it started from, without losing what it
> already knew.

That sentence fixes the shape of the deliverable: (1) a LoRA adapter, not a
full-weight checkpoint, so the base model stays intact and swappable; (2) a
**held-out domain eval** (grade-school arithmetic word problems the adapter
never trained on) to check the "more reliably" half; (3) a **retention
eval** (general-purpose, non-arithmetic prompts) to check the "without
losing what it already knew" half. Both are required — a recipe that only
reports the domain score cannot support this objective's claim.

## Why sft-lora

- Matches the product direction: LoRA-first, installable, no full
  fine-tune of base weights.
- The host stack (TRL + PEFT, no Unsloth) supports SFT-with-LoRA directly
  via `trl.SFTTrainer` + `peft.LoraConfig`; nothing exotic is required.
- LoRA adapters are cheap to load/unload/compare against the base model,
  which is exactly what the success criterion ("check the adapter loads
  and compare... results with the baseline") needs.

## Inputs this proposal assumes

`base_model` and `prepared_corpus` are supplied by the pipeline that runs
this step, not chosen here. The scripts take them as arguments/config
fields rather than hardcoding a specific model or dataset path.

`prepared_corpus` is assumed to be one or more JSONL files where each line
has a prompt field and a target field (field names configurable — defaults
`question` / `answer`, matching common grade-school arithmetic word-problem
formats such as GSM8K). If the actual prepared corpus uses different field
names or a chat-turns schema, adjust `config/sft_lora.yaml`'s
`dataset.prompt_field` / `dataset.answer_field` (or add a mapping in
`scripts/train_sft_lora.py::format_example`) rather than reshaping the
corpus.

For the retention eval, use a real held-out slice of general
(non-arithmetic) prompts the base model already handles — e.g. a slice of
whatever general instruction/eval data this project already has on hand.
Per project direction, do not substitute a synthetic stand-in for this set;
if no such set exists yet, that is a gap to flag back to the pipeline, not
something for this step to fabricate.

## Quantities left unspecified by the objective (proposed, not measured)

The objective text does not fix `training_steps` or `compute_budget`.
Proposed defaults, encoded in `config/sft_lora.yaml`:

- **`num_train_epochs: 3`** over `prepared_corpus`, capped by
  **`max_steps: 1200`** (whichever is reached first). Grade-school
  arithmetic word-problem corpora in this size class (GSM8K-like, on the
  order of several thousand examples) typically saturate SFT-LoRA gains
  within 2-3 epochs; capping at 1200 steps keeps a single run bounded even
  if the actual corpus turns out larger than expected. Treat this as a
  starting point to shorten (if eval saturates early) or extend (if
  held-out domain accuracy is still climbing at the cap).
- **Compute budget: ≤ 2 GPU-hours on a single RTX 5090** (the host this
  runs on). Rationale: a small base model (≲3B params) + rank-16 LoRA +
  a few-thousand-example corpus + the step cap above fits comfortably
  inside that window with room for the eval passes; it is a ceiling to
  stop a misconfigured run, not a target to spend in full.
- **LoRA rank 16, alpha 32, dropout 0.05** on attention + MLP projection
  modules — a standard, well-tested starting configuration for small
  causal LMs; not tuned for this specific base model.
- **Effective batch size 16** (`per_device_train_batch_size: 4` ×
  `gradient_accumulation_steps: 4`), **learning rate 2e-4** with cosine
  decay and a short warmup — standard LoRA SFT defaults, chosen to be a
  safe first attempt rather than a searched optimum.

All of the above are exposed as fields in `config/sft_lora.yaml` so they
can be revised without touching code.

## Files

- `config/sft_lora.yaml` — recipe config (paths, LoRA hyperparameters,
  training schedule, eval file paths). Fill in `base_model`,
  `prepared_corpus`, `domain_eval_path`, `retention_eval_path` before
  running.
- `scripts/train_sft_lora.py` — loads `base_model`, applies a PEFT
  `LoraConfig`, runs `trl.SFTTrainer` over `prepared_corpus`, saves the
  LoRA adapter (the `finetune_candidate`) to `output_dir`.
- `scripts/matheval_utils.py` — shared helpers: JSONL loading, prompt
  formatting, and final-numeric-answer extraction/exact-match scoring used
  by both eval scripts.
- `scripts/check_adapter_loads.py` — success-criterion check #1: loads
  `base_model` with the trained adapter attached via PEFT and runs one
  smoke generation, to confirm the adapter is structurally loadable before
  spending eval compute on it.
- `scripts/eval_compare.py` — success-criterion check #2: runs the base
  model and the base+adapter model over the held-out domain eval set and
  the retention eval set, and reports accuracy for both models on both
  sets side by side (no verdict is baked in — the comparison is the
  deliverable, the decision belongs to whoever reads the pipeline's gate).

## Exact commands

```bash
# 1. Train the LoRA adapter (produces finetune_candidate at output_dir)
uv run python proposals/math-reasoning/finetune/scripts/train_sft_lora.py \
  --config proposals/math-reasoning/finetune/config/sft_lora.yaml

# 2. Confirm the adapter loads (first half of the success criterion)
uv run python proposals/math-reasoning/finetune/scripts/check_adapter_loads.py \
  --config proposals/math-reasoning/finetune/config/sft_lora.yaml

# 3. Compare held-out domain and retention results against the baseline
#    (second half of the success criterion)
uv run python proposals/math-reasoning/finetune/scripts/eval_compare.py \
  --config proposals/math-reasoning/finetune/config/sft_lora.yaml \
  --output proposals/math-reasoning/finetune/eval_report.json
```

All three scripts also accept the individual `--base-model`,
`--adapter-dir`, `--prepared-corpus`, `--domain-eval`, `--retention-eval`
flags directly, so they can be pointed at paths without editing the YAML.

## What would count as success

Per the step's stated success criterion, success is:

1. **The adapter loads.** `check_adapter_loads.py` exits 0 and produces a
   non-empty generation from base+adapter. If this fails, the candidate is
   rejected before any eval spend.
2. **The comparison is favorable.** `eval_compare.py`'s report shows, for
   the same held-out domain set and the same retention set:
   - `domain_accuracy(base+adapter) > domain_accuracy(base)` — the model
     solves held-out grade-school arithmetic word problems more reliably
     than it did before finetuning.
   - `retention_accuracy(base+adapter)` not meaningfully below
     `retention_accuracy(base)` — no material regression on what the base
     model already knew. This proposal does not fix a numeric tolerance
     (e.g. "no more than 1 point drop") because that threshold is a gate
     decision, not something this step should presume; `eval_report.json`
     reports both numbers so the gate can apply whatever threshold it
     chooses.

This step does not itself decide pass/fail — it produces the adapter and
the comparison numbers that a downstream gate evaluates. Nothing in this
proposal writes to the ledger, `research/`, `gates/`, or
`pravrudhi_kernel/`.
