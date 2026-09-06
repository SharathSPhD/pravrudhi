# candidate-evaluation (proposal)

Step `candidate-evaluation`, capability `evaluate`, for the objective:

> A legal-reasoning assistant for Indian jurisprudence that answers a
> question of law with the statute or precedent it relied on, and that
> says it does not know rather than inventing a citation. The reasoning
> runs over a typed Nyaya meaning graph rather than surface text, so a
> wrong answer can be traced to the inference step that produced it.

This directory is a **proposal**. Nothing under it writes to the ledger,
`research/`, `gates/`, or `pravrudhi_kernel/`, and no number produced by
running these scripts may be presented as a measured result — the
example configs are fabricated and are labeled as such.

## Approach

The step consumes four inputs — `objective`, `benchmarks`,
`baseline_results`, `retrieval_candidate` — and produces one output,
`candidate_comparison`. The comparison logic is deliberately
schema-driven rather than hard-coded to specific metric names, because
the actual metric set (citation accuracy, false-citation/fabrication
rate, correct-abstention rate, inference-step traceability, etc.) and
their pass/fail targets are declared by the `benchmarks` artifact, not
by this step. `candidate-evaluation` only has to:

1. For every metric each benchmark declares, read `(direction, target)`
   from `benchmarks` and `(value, n)` for that metric from both
   `baseline_results` and `retrieval_candidate`.
2. Decide **improved / regressed / inconclusive** per metric using a
   Wilson score interval at the objective's declared confidence level,
   so that a difference smaller than sampling noise (given how many
   items `n` the metric was scored over) is reported as inconclusive
   rather than as a win or a loss. This is the mechanical form of
   "apply the objective's existing uncertainty rule."
3. Apply the objective's `uncertainty_rule.hard_constraint_metrics`:
   metrics named there (for this objective, `false_citation_rate` — the
   fabrication/invented-citation rate) may never regress. If the
   candidate regresses one, the verdict is
   `reject_candidate_hard_constraint` regardless of how much it improves
   everything else. This encodes "say it does not know rather than
   invent a citation" as a non-negotiable gate on the comparison itself,
   not just as a property the model is trained to have.
4. Apply `target`, if a benchmark's metric declares one, as an
   independent pass/fail check on the candidate's value (separate from
   the baseline comparison).
5. Roll per-metric verdicts up into one `overall_verdict`:
   `prefer_candidate`, `prefer_baseline`, `mixed_inconclusive`,
   `inconclusive`, or `reject_candidate_hard_constraint`.

The script does not know what "statute_lookup" or "citation_accuracy"
mean; it only knows maximize/minimize, target, and the hard-constraint
list. That is intentional: the candidate-evaluation step should not
have to change when the benchmark suite for prabhasa-nyaya grows (e.g.
when a metric for "traceable to the correct Nyaya inference step" is
added), only when the comparison *policy* changes.

## evaluation_sample_count (proposed, not measured)

The objective leaves the per-benchmark evaluation sample count
unspecified. This proposal suggests **n = 200 items per benchmark**
(600 total across the three example benchmark categories: statute
lookup, precedent lookup, and an abstention-trap set of questions with
no correct citation), for the following reason, not as a measurement:

- Baseline citation-accuracy rates for a retrieval-augmented legal QA
  system plausibly sit in the 0.7-0.9 range. Detecting an absolute
  8-10 percentage point change between two proportions in that range at
  alpha = 0.05, power = 0.80 needs on the order of 150-250 items per
  arm under a standard two-proportion power calculation.
- 200 rounds up from that range with margin, and divides evenly for
  stratifying the abstention-trap benchmark (which specifically needs
  enough "no correct citation exists" items to estimate
  `correct_abstention_rate` and `false_citation_rate` at similar
  precision to the other two benchmarks).
- Because baseline and candidate are scored on the *same* item set
  (paired design), the effective power is higher than an unpaired
  calculation suggests — 200 is therefore a conservative floor, not a
  tight minimum, which matters more given the hard-constraint gate on
  `false_citation_rate`: a false "no regression" reading there is worse
  than a false "no improvement" reading elsewhere.

Any future step that actually runs benchmarks should treat 200/benchmark
as a starting proposal to revisit once real accuracy rates and
per-item scoring cost are known, not as a fixed requirement.

## Files

- `scripts/evaluate.py` — the comparison script described above. Takes
  `--objective`, `--benchmarks`, `--baseline`, `--candidate`, `--out`
  paths and writes a `candidate_comparison` JSON document.
- `configs/objective.example.json`, `configs/benchmarks.example.json`,
  `configs/baseline_results.example.json`,
  `configs/retrieval_candidate.example.json` — fabricated example
  inputs, shaped as this proposal expects the real
  candidate-evaluation inputs to be shaped. All numeric values in them
  are invented for exercising the script and are marked as such in an
  `_note` field.
- `run_example.sh` — the exact command to run the script against the
  example configs.

## Exact commands

```bash
cd proposals/prabhasa-nyaya/candidate-evaluation
uv run python scripts/evaluate.py \
  --objective configs/objective.example.json \
  --benchmarks configs/benchmarks.example.json \
  --baseline configs/baseline_results.example.json \
  --candidate configs/retrieval_candidate.example.json \
  --out /tmp/candidate_comparison.example.json
```

or simply:

```bash
bash proposals/prabhasa-nyaya/candidate-evaluation/run_example.sh
```

To use this against real inputs, point the four `--objective`,
`--benchmarks`, `--baseline`, `--candidate` flags at the real artifacts
produced upstream (matching the JSON shapes documented in the module
docstring of `scripts/evaluate.py`) and write `--out` to wherever the
step's actual output location is — that wiring is outside this
proposal's scope, since this proposal may not write to the ledger,
`gates/`, `research/`, or `pravrudhi_kernel/`.

## What would count as success

For this proposal to be accepted as the `candidate-evaluation` recipe:

- Given real `objective`/`benchmarks`/`baseline_results`/
  `retrieval_candidate` artifacts matching the documented shapes, the
  script produces a `candidate_comparison` whose per-metric verdicts
  are independently reproducible by hand from the same inputs (i.e. the
  Wilson-interval and hard-constraint logic is auditable, not a
  black box).
- A candidate that regresses `false_citation_rate` (invents a citation
  more often than the baseline) is never reported as
  `prefer_candidate`, even if it improves every other metric — this is
  the direct evaluation-side check on the objective's "say it does not
  know rather than invent a citation" requirement.
- A metric difference smaller than sampling noise at the stated
  `n` and confidence level is reported `inconclusive`, not as a win —
  so the recipe does not let a small `evaluation_sample_count` manufacture
  false confidence.
- The comparison generalizes to whatever metric set the real
  `benchmarks` artifact declares (including any future metric for
  tracing a wrong answer back to the Nyaya inference step that produced
  it) without code changes, because metrics are read from `benchmarks`
  rather than hard-coded.

## Validation

```bash
test -n "$(ls -A proposals/prabhasa-nyaya/candidate-evaluation)" && \
  uv run python -m compileall -q proposals/prabhasa-nyaya/candidate-evaluation
```
