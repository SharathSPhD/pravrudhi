# Proposal: baseline-evaluation for `math-reasoning`

Step: `baseline-evaluation` (capability: `evaluate`, recipe: `evaluation`)
Objective: a small model that solves grade-school arithmetic word problems more
reliably than the checkpoint it started from, without losing what it already knew.

Status: **proposal only**. Nothing here writes to the ledger, `research/`, `gates/`
or `pravrudhi_kernel/`, and no number produced by these scripts may be cited as a
measured result until an authorized run records it through those channels.

## Approach

Use an external, third-party evaluation harness rather than a hand-rolled scorer,
so the "exact metric" the success criterion asks for is the metric that tool
itself defines and computes — not a re-implementation that could silently diverge
from the published definition.

**Declared external tool: [`lm-evaluation-harness`](https://github.com/EleutherAI/lm-evaluation-harness)
(package `lm-eval`, CLI `lm_eval`).** It is the de facto standard harness for this
kind of comparison, ships the `gsm8k` task out of the box, and reports a metric
name (`exact_match`) and per-filter breakdown directly in its own output — nothing
in this proposal recomputes or reinterprets that number.

Two benchmark families are evaluated, because the objective has two halves:

1. **Target capability — grade-school arithmetic word problems.**
   Task: `gsm8k` (GSM8K, Cobbe et al. 2021), 8-shot, as shipped by lm-eval.
   Reported metric: `exact_match` (lm-eval reports both `strict-match` and
   `flexible-extract` filter variants; both are recorded, `flexible-extract` is
   the one usually treated as primary in published GSM8K numbers because it is
   robust to answer-formatting differences that are not reasoning errors).

2. **Retention — "without losing what it already knew."**
   A baseline number is only useful for a retention check if it exists *before*
   any tuning happens, so this step also runs two small, cheap, general-purpose
   tasks from the same harness to serve as a pre-tuning reference point:
   - `arc_easy` (AI2 Reasoning Challenge, easy split) — metric `acc_norm`
   - `hellaswag` — metric `acc_norm`
   These are not math tasks; they exist so that a later step can detect if
   fine-tuning on GSM8K degraded general competence, which is exactly the
   failure mode the objective rules out. Swap or extend this list if the
   objective's `benchmarks` input later names specific retention tasks — the
   scripts take the task list as a parameter, not a hardcoded constant.

All three tasks are run in one `lm_eval` invocation against the declared
`base_model`, and the harness's own JSON output is the baseline artifact.

## Unspecified quantity: `evaluation_sample_count`

The objective does not pin this down. Proposed values, not measured, and why:

- **GSM8K: full test split (n = 1319, no `--limit`).** The GSM8K test set is
  small enough that running it in full is cheap even on modest hardware for a
  "small model," and because this baseline number will later be diffed against
  a post-training number, removing sampling variance from that comparison
  matters more than saving a few minutes of wall-clock time. A subsampled
  baseline would put sampling noise on both ends of the delta being measured.

- **Retention tasks (`arc_easy`, `hellaswag`): `--limit 500` each, fixed seed.**
  Their native splits are larger (2.4k / 10k+) and they are a secondary check,
  not the target metric, so full runs aren't worth the cost here. At n=500 and
  an expected accuracy near 0.5, the binomial margin of error is
  `1.96 * sqrt(0.25/500) ≈ 4.4` points at 95% confidence — tight enough to
  flag a real regression (the kind of drop that would indicate catastrophic
  forgetting) without paying for a full-split run on every candidate
  checkpoint. If a later step needs tighter bounds, raise `--limit` or drop it.

These are defaults in `tasks.yaml` and can be overridden per invocation; they
are proposed starting points, not conclusions.

## Files

- `tasks.yaml` — declares the task list, few-shot counts, and the proposed
  sample-count (`limit`) per task, so the script has no hardcoded benchmark
  list to drift out of sync with this README.
- `run_baseline_eval.sh` — invokes `lm_eval` once per the tasks in
  `tasks.yaml` against `$BASE_MODEL`, writing raw harness JSON output under
  `./results/` (inside this proposal directory — never under `research/` or
  the ledger).
- `summarize_results.py` — reads the harness's own JSON output files and
  prints the exact metric name/value pairs lm-eval reported, with no
  recomputation. Marks its own output as a proposal-stage summary.

## Commands to run this

```bash
# from repo root, with lm-eval installed (pip install lm-eval) and BASE_MODEL
# pointing at the checkpoint under evaluation:
export BASE_MODEL=/path/to/base/checkpoint   # HF-format model dir or hub id
bash proposals/math-reasoning/baseline-evaluation/run_baseline_eval.sh

# then, to see what the harness reported without touching its output:
uv run python proposals/math-reasoning/baseline-evaluation/summarize_results.py \
    proposals/math-reasoning/baseline-evaluation/results
```

`run_baseline_eval.sh` shells out to `lm_eval`; it does not vendor or reimplement
any scoring logic. If `lm_eval` is not installed, the script prints how to
install it (`pip install lm-eval`) and exits non-zero rather than falling back
to a private scorer.

## What would count as success

Per the step's stated success criterion — "obtain a baseline result from each
declared external tool reporting its exact metric on this track" — this step is
successful once:

1. `lm_eval` (the one declared external tool) has been run against
   `$BASE_MODEL` for `gsm8k`, `arc_easy`, and `hellaswag`, and
2. each run's own JSON output file exists under `results/` and contains that
   task's metric exactly as lm-eval names and computes it
   (`exact_match` for gsm8k, `acc_norm` for the other two) — with no
   post-hoc renaming, rounding-then-forgetting, or hand-computed substitute.

That JSON is the baseline. It still has to be carried into the actual ledger by
whatever authorized process consumes this proposal — nothing produced here is
itself that record.
