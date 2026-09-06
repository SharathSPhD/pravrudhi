# Baseline Evaluation — Prabhasa-Nyaya (proposal)

Step: `baseline-evaluation` · capability: `evaluate` · recipe candidate: `evaluation`

Status: **proposal only**. Nothing here writes to the ledger, `research/`, `gates/`, or
`pravrudhi_kernel/`, and no number in this directory may be treated as a measured result —
every figure below is either a proposed default or a placeholder to be filled in by an
actual run, and is labeled as such.

## Objective this step serves

> A legal-reasoning assistant for Indian jurisprudence that answers a question of law with
> the statute or precedent it relied on, and that says it does not know rather than
> inventing a citation. Reasoning runs over a typed Nyaya meaning graph rather than surface
> text, so a wrong answer can be traced to the inference step that produced it.

This step only concerns the **baseline** — a floor measured on the plain `base_model`
(no Nyaya graph, no retrieval scaffolding) against declared benchmarks. It exists so that
later graph-reasoning candidates have something concrete to beat, and so the abstention
behavior ("say you don't know") has a number attached before anyone tries to improve it.

## Approach

Three declared external tools are run against the same `base_model`, each reporting its
own native metric. The step does not invent a blended score — `baseline_results` is a
per-tool record, not a single number.

| # | Tool | What it measures | Native metric(s) reported |
|---|------|-------------------|----------------------------|
| 1 | **IL-TUR** (Indian Legal Text Understanding and Reasoning benchmark, Kapoor et al. 2024, `Exploration-Lab/IL-TUR` on Hugging Face) | General Indian-legal-NLP competence: statute identification, legal reasoning QA, summarization sub-tasks | Whatever each IL-TUR sub-task's official script reports (macro-F1 for classification sub-tasks, ROUGE-L for summarization sub-tasks) — taken as-is, not renormalized |
| 2 | **ILDC / CJPE** (Court Judgment Prediction with Explanation, Malik et al. 2021, `Exploration-Lab/CJPE`) | Outcome prediction + explanation quality on real Indian Supreme Court judgments | Accuracy / macro-F1 (prediction) and the paper's explanation-overlap metric (explanation) |
| 3 | **Citation-grounding probe** (this proposal's own script — see below) | The specific behavior the objective calls out: does the model cite a real statute/precedent, or invent one, or correctly abstain? | Citation precision, citation recall, hallucination rate, abstention rate — defined in `scripts/citation_grounding_eval.py` |

Tools 1 and 2 are pre-existing published benchmarks with their own harnesses; this proposal
does not reimplement their scoring, it wraps their official evaluation entry points so their
exact metric is what gets reported (see "Why a wrapper, not a reimplementation" below).
Tool 3 does not exist as a published benchmark yet — the objective's central claim
("says it does not know rather than inventing a citation") is not something IL-TUR or CJPE
measures, so a small first-party scorer is proposed. It is a *scorer* over model output
against a reference citation table, not a synthetic stand-in for the Nyaya graph engine
itself, and not a benchmark dataset — the questions and reference citations it scores
against are declared inputs (`benchmarks` on this step), sourced from real judgments, not
generated.

### Why a wrapper, not a reimplementation

Re-deriving IL-TUR's or CJPE's metric math independently would (a) drift from what the
published leaderboard means by "F1 on this task," defeating the point of using an external
tool as a check, and (b) be redundant work. `scripts/iltur_eval.py` and
`scripts/ildc_cjpe_eval.py` are thin CLI wrappers: they install/import the official package,
call its evaluation entry point on the model's generations, and pass the reported metric
through unchanged into `baseline_results`.

### Sample count (unspecified by the objective — proposed value)

**Proposed: `evaluation_sample_count = 200` per task**, or the full test split if it has
fewer than 200 examples, sampled with a fixed seed (`42`) for reproducibility.

Why 200:
- For a proportion-type metric (accuracy, precision/recall, abstention rate) with p≈0.5,
  n=200 gives a 95% CI half-width of ≈7 percentage points — tight enough to tell a
  meaningfully-different candidate recipe apart from the baseline in later comparison
  steps, without requiring a full-corpus run for what is explicitly a *floor* measurement.
- A baseline is expected to be re-run once per candidate recipe as a sanity check, not
  once total, so cost compounds — 200 keeps a single pass under a few minutes on IL-TUR's
  smaller sub-tasks and a few tens of minutes on CJPE's longer judgments, which is what
  actually gates iteration speed here, not statistical power alone.
- This is a proposal, not a measured requirement: the `configs/eval_config.yaml` value
  is a single field (`sample_count`) precisely so whoever runs this can override it without
  touching code.

## Files in this proposal

```
proposals/prabhasa-nyaya/baseline-evaluation/
├── README.md                          this file
├── configs/
│   └── eval_config.yaml               benchmarks, sample_count, base_model placeholder
├── scripts/
│   ├── common.py                      shared types + JSON result writer
│   ├── run_baseline.py                orchestrator: reads config, runs the 3 tools, writes baseline_results.json
│   ├── iltur_eval.py                  wrapper around the IL-TUR official harness
│   ├── ildc_cjpe_eval.py              wrapper around the ILDC/CJPE official harness
│   └── citation_grounding_eval.py     first-party citation precision/recall/abstention scorer
└── output/
    └── .gitkeep                       local-only run output lands here (never the ledger)
```

## Exact commands to run this

All commands assume `uv` and are run from the repo root, in this worktree.

```bash
# 1. Install the two external benchmark packages (declared external tools).
#    Pinned versions are placeholders — fill in the versions actually vendored
#    when this step is promoted out of proposal status.
uv pip install il-tur==<PIN_ME>          # provides the IL-TUR official eval entry point
uv pip install ildc-cjpe-eval==<PIN_ME>  # provides the CJPE official eval entry point

# 2. Point the config at a concrete base_model and dataset cache dir.
#    Edit proposals/prabhasa-nyaya/baseline-evaluation/configs/eval_config.yaml:
#      base_model: <hf-model-id-or-local-path>
#      dataset_cache_dir: <path with room for IL-TUR + CJPE + citation-grounding data>

# 3. Run the baseline.
uv run python proposals/prabhasa-nyaya/baseline-evaluation/scripts/run_baseline.py \
    --config proposals/prabhasa-nyaya/baseline-evaluation/configs/eval_config.yaml \
    --out proposals/prabhasa-nyaya/baseline-evaluation/output/baseline_results.json
```

`run_baseline.py` calls each of the three tool wrappers, catches failures per-tool (one
tool being unavailable should not block the other two from reporting), and writes one
JSON record per tool into `output/baseline_results.json`. That output directory is local to
this proposal; promoting a real run's results into the ledger is explicitly out of scope
for this step and this directory.

## What would count as success

Per the step's stated success criterion — *"Obtain a baseline result from each declared
external tool reporting its exact metric on this track"* — this step's `baseline_results`
is complete when `output/baseline_results.json` contains, for **all three** declared tools:

- the tool's name and version,
- its exact native metric name(s) (no renaming/blending),
- the metric value(s) it reported,
- the `base_model` identifier evaluated,
- the sample count actually used (may differ from the proposed 200 if a task's test split
  is smaller),
- a timestamp.

A tool that fails to run (missing dependency, unreachable dataset) is recorded as a failed
entry with its error, not silently omitted — three result rows, not up to three, is the bar.
Whether the *values* are good enough to justify a Nyaya-graph candidate recipe is a
downstream comparison question for a later step, not something this baseline-evaluation
step judges.

## Explicit non-goals of this proposal

- No Nyaya meaning graph, no typed-inference tracing — this step measures the base model
  alone, on purpose, as the thing the graph-reasoning approach must beat.
- No synthetic questions or synthetic reference citations — the citation-grounding probe's
  question/citation pairs must be sourced from real Indian judgments (e.g. via the same
  corpora IL-TUR/CJPE already draw from), never generated, per the project's no-synthetic
  rule.
- No numbers in this directory are results. `output/` is empty until someone actually runs
  the commands above; `.gitkeep` is a placeholder, not evidence.
