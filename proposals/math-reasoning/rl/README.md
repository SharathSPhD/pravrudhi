# Proposal: RL post-training for grade-school arithmetic word problems

Step: `rl` (capability `rl`)
Consumes: `objective`, `finetune_candidate`, `prepared_corpus`
Produces: `rl_candidate`
Recipe: `rl-post-training`

Status: **proposal only**. Nothing here writes to the ledger, `research/`, `gates/`,
or `pravrudhi_kernel/`. No number quoted below is a measured result — every
quantity is either a proposed default (flagged as such) or the output of a
script the operator has chosen to run.

## Intent, restated

Take `finetune_candidate` (a small LoRA-tuned checkpoint that already does
reasonable arithmetic word-problem solving) and produce `rl_candidate`: a
checkpoint that solves more grade-school arithmetic word problems correctly,
without regressing on general capability the base/finetune checkpoint already
had. "More reliably" means measured on held-out problems, not on the training
signal itself — the training reward and the acceptance evidence must be two
different things, computed by two different code paths, on two different data
splits.

## Approach

GRPO (group relative policy optimization) via TRL, LoRA-on-top-of-LoRA against
`finetune_candidate`, with a **verifiable, rule-based reward** (no learned
reward model, no LLM-judge) so there is nothing in the reward path a policy can
plausibly learn to fool except by actually being correct or by exploiting a
parsing gap — which is exactly what `reward_audit.py` below is for.

Reward is the sum of two rule-based terms, computed by [`reward.py`](reward.py):

- **Correctness (dominant term)**: parse the model's final numeric answer out
  of a required `#### <number>` tail (GSM8K convention) and compare, with
  tolerance for formatting (commas, `$`, trailing `.0`), against the gold
  answer already present in `prepared_corpus`. Exact match on the parsed
  number: reward `1.0`, else `0.0`.
- **Format shaping (small term)**: reward `0.1` if the completion contains
  exactly one `####` marker followed by a parseable number, `0.0` otherwise.
  This exists only to give the policy gradient signal before it has learned
  the answer format; it is capped low enough that a reasoning-free "produce
  the format, guess a number" strategy cannot compete with getting the
  arithmetic right (max possible reward from format alone is 0.1, vs 1.0 for
  a correct answer).

No length bonus, no fluency/style term — those are exactly the kind of proxy
that gets exploited (verbosity or hedging) without moving the actual capability
the objective cares about.

### Why GRPO over PPO

No separate value/critic network to train (halves the model memory footprint,
material on a single consumer GPU), and it fits verifiable-reward, single-turn
math tasks well because the advantage is just the reward's z-score within a
group of rollouts on the *same* prompt — a natural fit for problems with an
objectively checkable answer. TRL ships `GRPOTrainer` in the versions already
present on this host per project convention (25.06 image: TRL + PEFT, no
Unsloth).

### LoRA, not full fine-tune

Consistent with the project's LoRA-first direction. RL adapters are trained
on top of the already-merged (or adapter-stacked) `finetune_candidate`,
keeping the update small and reversible, and making "did we lose what it
already knew" a tractable question — a small, low-rank update is much less
likely to have silently overwritten unrelated behavior than a full-parameter
update, which makes the retention check in the success criterion meaningful
rather than a formality.

## Files in this proposal

- `README.md` — this file.
- `rl_config.yaml` — GRPO hyperparameters and I/O paths (placeholders — see
  "Paths" below).
- `reward.py` — the reward function, importable and unit-testable on its own,
  independent of any trainer.
- `train_rl.py` — loads `finetune_candidate`, wraps `prepared_corpus`'s train
  split as prompts, runs `GRPOTrainer` with `reward.py`, writes `rl_candidate`.
- `reward_audit.py` — samples rollouts from a checkpoint and reports reward
  vs. independently-parsed correctness side by side, to catch reward/intent
  divergence (e.g. the format term firing without a correct answer, or the
  parser accepting something the grader would not).
- `eval_holdout.py` — the acceptance check. Computes exact-match accuracy on
  a held-out arithmetic split *never used as an RL prompt*, plus a small
  general-capability retention probe, for both the pre-RL checkpoint
  (`finetune_candidate`) and the post-RL checkpoint (`rl_candidate`), and
  reports a paired bootstrap confidence interval on the difference. This is
  intentionally a separate code path from `reward.py` (its own answer parser,
  written independently) so a bug in the training reward's parser cannot also
  show up as a false "held-out improvement."

## Paths (placeholders — fill in from the actual upstream step outputs)

All scripts take these as CLI args with the defaults below; there is no
repo-wide config file to edit.

- `--base-model`: HF hub id or local path of `finetune_candidate`
  (default placeholder: `artifacts/finetune_candidate`)
- `--train-data`: JSONL from `prepared_corpus`, one `{"question": ..., "answer": ...}`
  per line, train split (default placeholder: `artifacts/prepared_corpus/train.jsonl`)
- `--holdout-data`: JSONL, held-out split of the same corpus, disjoint from
  `--train-data`, never sampled during RL (default placeholder:
  `artifacts/prepared_corpus/holdout.jsonl`)
- `--retention-data`: a small general-capability JSONL (non-arithmetic
  prompts with a checkable property, e.g. short factual QA or the original
  SFT eval set) used only to check for regression, not for reward
  (default placeholder: `artifacts/retention_probe.jsonl`)
- `--output-dir`: where the LoRA adapter for `rl_candidate` is written
  (default placeholder: `artifacts/rl_candidate`)

None of these paths are assumed to exist in this worktree; they are the
contract this proposal expects the upstream steps to satisfy.

## Commands

```bash
# 1. Sanity-check the reward function in isolation (no model, no GPU).
uv run python proposals/math-reasoning/rl/reward.py --self-test

# 2. Run RL post-training.
uv run python proposals/math-reasoning/rl/train_rl.py \
  --config proposals/math-reasoning/rl/rl_config.yaml \
  --base-model artifacts/finetune_candidate \
  --train-data artifacts/prepared_corpus/train.jsonl \
  --output-dir artifacts/rl_candidate

# 3. Audit the reward against the intent (not the trained model's score —
#    whether reward and correctness actually agree on real rollouts).
uv run python proposals/math-reasoning/rl/reward_audit.py \
  --model artifacts/rl_candidate \
  --data artifacts/prepared_corpus/train.jsonl \
  --num-samples 200

# 4. Independent held-out comparison (this is the acceptance evidence, not step 2's logs).
uv run python proposals/math-reasoning/rl/eval_holdout.py \
  --baseline artifacts/finetune_candidate \
  --candidate artifacts/rl_candidate \
  --holdout-data artifacts/prepared_corpus/holdout.jsonl \
  --retention-data artifacts/retention_probe.jsonl
```

## Proposed quantities (unspecified by the objective)

The objective leaves `rollout_count` and `compute_budget` open. Proposed
values, and why — these are starting points for the operator to adjust, not
measured facts:

- **`rollout_count` (GRPO group size, i.e. completions sampled per prompt for
  the relative-advantage estimate): 8.** GRPO's advantage signal is a z-score
  within the group, so it needs enough samples per prompt to have a
  non-degenerate variance estimate — too few (e.g. 2-4) makes the advantage
  noisy; the published GRPO/DeepSeekMath work uses group sizes in the 8-64
  range. 8 is the low end of that range, chosen because grade-school
  arithmetic word problems have low answer entropy relative to open-ended
  generation, so fewer samples per prompt are needed to get a mix of
  correct/incorrect in the group than for harder or more open-ended tasks —
  and a smaller group keeps rollout cost down on a single-GPU host.
- **Prompts per training step: 64** (so 64 x 8 = 512 completions generated
  per step). Chosen to keep one step's generation batch small enough to fit
  comfortably alongside a small (<=3B parameter) LoRA policy's activations on
  a single consumer GPU (the host is described as a single 5090 in project
  notes), while still giving a reasonably low-variance policy gradient
  estimate per step.
- **`compute_budget`: 300 GRPO steps (~150K prompt-completions total,
  roughly 2-4 hours of wall-clock on a single high-end consumer GPU for a
  model in the 0.5B-3B range).** Proposed as a fixed stopping point rather
  than "train until convergence," because (a) RL on a small verifiable-reward
  task tends to plateau or start reward-hacking well before typical PPO/GRPO
  paper step counts, and (b) a fixed, small budget keeps this a cheap,
  repeatable experiment that can be rerun if the first attempt does not clear
  the held-out bar, rather than a long unmonitored run. `rl_config.yaml`
  exposes this as `max_steps` and also sets `eval_steps` so intermediate
  checkpoints can be probed with `eval_holdout.py` before committing to the
  full budget.

Both numbers should be treated as the first thing to revisit if
`reward_audit.py` shows reward/correctness disagreement (lower group size
first) or if `eval_holdout.py` shows the held-out score still rising at step
300 (raise the step budget before concluding the recipe doesn't work).

## What would count as success

Two independent checks, both required — matching the success criterion's
"audit the reward" + "compare held-out results independently of the training
reward":

1. **Reward audit (`reward_audit.py`) shows the reward tracks the intent.**
   On a sample of rollouts, the fraction where `reward == 1.0` but an
   independently-implemented correctness check disagrees should be
   effectively zero (a handful of parser edge cases is fine; systematic
   disagreement means the reward is measuring the wrong thing and the run's
   results are not trustworthy regardless of what `eval_holdout.py` says).
2. **Held-out comparison (`eval_holdout.py`) shows a real, non-training-reward
   improvement with no capability loss:**
   - Exact-match accuracy on `--holdout-data` for `rl_candidate` is higher
     than for `finetune_candidate` (`--baseline`), with the paired bootstrap
     CI on the difference excluding zero — not just a point-estimate win,
     since held-out sets here are expected to be small enough that a few
     flipped examples could otherwise look like signal.
   - Accuracy/pass-rate on `--retention-data` for `rl_candidate` is not
     meaningfully lower than for `finetune_candidate` (no CI-excludes-zero
     regression). This is the "without losing what it already knew" half of
     the objective — arithmetic gains that come with a measurable retention
     regression do not satisfy the intent.

If either check fails, the recipe parameters (reward shaping, group size,
step budget) are the first things to revisit, not the acceptance bar.
