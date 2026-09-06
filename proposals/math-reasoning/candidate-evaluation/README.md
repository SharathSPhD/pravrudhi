# candidate-evaluation (proposal)

Status: **proposal only**. Nothing under this directory writes to the
ledger, `research/`, `gates/`, or `pravrudhi_kernel/`, and no number
printed by these scripts is a measured result — the files under
`example_inputs/` are hand-picked dummy numbers used only to exercise the
script, not output from any real checkpoint or benchmark run.

## Objective this step serves

> A small model that solves grade-school arithmetic word problems more
> reliably than the checkpoint it started from, without losing what it
> already knew.

Step: `candidate-evaluation`, capability `evaluate`, recipe id
`evaluation`. Consumes `objective`, `benchmarks`, `baseline_results`,
`rl_candidate`; produces `candidate_comparison`.

## Approach

A pure comparison step: given the objective, the declared benchmark list
(each with a metric and an optimization direction), and two already-computed
result sets (baseline checkpoint, RL candidate checkpoint), decide whether
the candidate is a real improvement.

Two questions have to be answered per benchmark, and one has to be answered
across all of them:

1. **Point estimate**: did the metric move in the declared-good direction?
2. **Distinguishable from noise**: given the objective's own uncertainty
   rule, is that movement large enough that it isn't explained by sampling
   noise in a finite eval set? (Grade-school arithmetic accuracy is a
   proportion over discrete items, so this is answered with a proportion
   confidence interval, not a raw point-estimate diff.)
3. **Across the whole suite**: "without losing what it already knew" means
   a regression on any *other* declared benchmark that is distinguishable
   from noise should fail the comparison even if the target benchmark
   improved. A target, if the objective/benchmark declares one, must also
   be met.

`compare_candidates.py` implements this as a small, dependency-free CLI:
it loads the four input JSON files, computes a per-benchmark verdict, and
writes `candidate_comparison.json`. `stats.py` holds the statistics (Wilson
score interval for a single proportion, Newcombe's interval for the
difference of two proportions) with no numpy/scipy dependency, so the
script runs anywhere the standard library does.

### Applying "the objective's existing uncertainty rule"

The step description says to apply the objective's *existing* uncertainty
rule rather than inventing one. This proposal was scoped to not survey the
repository for that rule's real schema, so `compare_candidates.py` instead
defines an explicit, minimal contract for it
(`objective.uncertainty_rule = {"type": ..., "confidence": ...}`,
see the docstring at the top of `compare_candidates.py`) and implements the
one rule type this task's evidence supports needing: `wilson_diff`
(Newcombe's proportion-difference interval at a stated confidence level).
If the real objective record uses a different `type`, the script logs a
visible warning and falls back to `wilson_diff` when correct/n counts are
available, or to a point-estimate-only comparison when they are not — it
never silently invents a pass/fail verdict. Whoever wires this into the
real pipeline should either confirm the real objective already matches
this contract, or extend `SUPPORTED_UNCERTAINTY_RULES` in
`compare_candidates.py` with the real rule's logic.

### Proposed quantity: `evaluation_sample_count`

The objective leaves the number of eval items unspecified. This proposal
recommends **385 items per benchmark as a floor**, with the full official
test split preferred whenever it is larger (GSM8K's test split has 1319
problems, well above the floor).

Rationale (see `config/evaluation_config.yaml` and
`stats.required_n_for_margin`): 385 = ceil(z² · p(1−p) / margin²) with
z = 1.96 (95% confidence), p = 0.5 (worst-case variance for a proportion),
margin = 0.05 (a Wilson interval half-width of ±5 percentage points). That
is the smallest sample size for which a single benchmark's accuracy
estimate can resolve a 5-point swing at 95% confidence in the worst case.
This is presented as a **recommendation with a stated method**, not a
measured or previously agreed value — pick a tighter margin (more items)
if the target improvement declared for GSM8K is smaller than ~5pp, since
otherwise the eval can't statistically distinguish the target from noise.

## Files

- `compare_candidates.py` — the comparison CLI. Entry point.
- `stats.py` — Wilson / Newcombe interval helpers, plus the sample-size
  formula used to justify `evaluation_sample_count`.
- `config/evaluation_config.yaml` — proposed run configuration:
  benchmark roles, `evaluation_sample_count`, confidence level.
- `example_inputs/*.json` — illustrative, hand-picked dummy input files
  shaped to match the input contract documented in
  `compare_candidates.py`'s docstring. Used only to demonstrate the script
  runs end to end; the numbers in them are not real benchmark results.

## Exact commands

Run the comparison against the real four inputs once they exist as files
(paths are examples; substitute wherever the pipeline materializes them):

```bash
uv run python proposals/math-reasoning/candidate-evaluation/compare_candidates.py \
  --objective   path/to/objective.json \
  --benchmarks  path/to/benchmarks.json \
  --baseline    path/to/baseline_results.json \
  --candidate   path/to/rl_candidate.json \
  --out         path/to/candidate_comparison.json
```

The script exits 0 if `overall_pass` is true, 1 otherwise, and also prints
the full comparison JSON to stdout.

Exercise it against the bundled illustrative example (dummy numbers, not a
real result):

```bash
cd proposals/math-reasoning/candidate-evaluation
uv run python compare_candidates.py \
  --objective  example_inputs/objective.json \
  --benchmarks example_inputs/benchmarks.json \
  --baseline   example_inputs/baseline_results.json \
  --candidate  example_inputs/rl_candidate.json \
  --out        /tmp/example_candidate_comparison.json
```

## What would count as success

`candidate_comparison.overall_pass == true`, meaning:

- every benchmark the objective declares a `target` for meets that target
  (direction-aware: an accuracy target is a lower bound on the
  direction-corrected delta or absolute value, per `target_type`), **and**
- no other declared benchmark regressed by an amount the uncertainty rule
  judges distinguishable from noise (`distinguishable_from_noise == true`
  and `improved_with_confidence == false` for that benchmark).

A candidate that improves GSM8K accuracy but is indistinguishable-from-noise
worse on the regression-guard benchmark should still be reported as a pass
(noise, not evidence of forgetting); a candidate that is *distinguishably*
worse on the regression guard should fail even if GSM8K improved, because
that is exactly the "lost what it already knew" failure mode the objective
calls out. Benchmarks without a stated target and without a distinguishable
regression are treated as neutral, not blocking.

## Validate

```bash
test -n "$(ls -A proposals/math-reasoning/candidate-evaluation)" && \
  uv run python -m compileall -q proposals/math-reasoning/candidate-evaluation
```
