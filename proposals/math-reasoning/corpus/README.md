# Math-reasoning corpus proposal

Step `corpus` (capability `corpus`) for the objective: a small model that solves
grade-school arithmetic word problems more reliably than the checkpoint it started
from, **without losing what it already knew**.

This is a **proposal**, not a ledger entry. Nothing here writes to `research/`,
`gates/`, `pravrudhi_kernel/`, or `.pravrudhi/`, and no number below is a
measurement — every quantity is a stated assumption, marked as such.

## Recipe choice: corpus-curation, not corpus-synthesis

We propose **corpus-curation** over corpus-synthesis, for two reasons specific to
this objective:

1. The objective's bar is "**more reliably**", not "more often" — that means the
   corpus has to exercise real reasoning failure modes (multi-step arithmetic,
   distractor numbers, phrasing that varies while the underlying operations do
   not), not just more examples of an easy pattern. LLM-synthesized grade-school
   word problems are exactly the case where a generator can produce a fluent
   problem with a *wrong or ambiguous* gold answer (a known failure mode of
   template-based math-problem generation), which would train the model on
   noise it cannot detect.
2. Pravrudhi's product direction is LoRA-first with no synthetic stand-ins for
   evaluation-shaped data (project memory `pravrudhi-product-direction`). Grade-
   school arithmetic word problems are an evaluation-shaped domain by
   construction — GSM8K itself is the field's standard benchmark for exactly this
   objective — so training on synthesized look-alikes risks contaminating the
   model's behavior on the very benchmark this objective will be judged against,
   without anyone being able to point to which synthetic item did it.

Every source in `config/sources.yaml` is a real, human-authored or
human-annotated public math-word-problem dataset with a published, versioned
train/test split — never text generated for this proposal.

## Corpus size (proposed, not measured)

**Proposed target: ~14,000 curated problems before cross-source dedup, settling
to an estimated 12,000–13,000 after it** (see `config/sources.yaml`
`target_count_train` per source):

| Source | Proposed train count | Rationale |
|---|---:|---|
| GSM8K (train) | 7,473 | The objective's target domain and standard benchmark; full published train split. |
| ASDiv (arithmetic/elementary subset) | ~2,300 | Broadens topic and grade-level coverage beyond GSM8K's crowdworker phrasing style. |
| SVAMP (train) | 1,000 | Structure-perturbed challenge problems — probes template pattern-matching specifically, which "more reliably" is aimed at. |
| MAWPS (train) | 3,320 | Older, differently-phrased single/multi-step arithmetic sets (AddSub, MultiArith, SingleOp lineage); broadens phrasing diversity. |

Why this size and not "every public word-problem dataset available": GSM8K
train alone (7,473 problems) is the standard, previously-shown-to-work scale for
fine-tuning a small model on this exact task, so it anchors the target rather
than an arbitrary multiple of it. The three supplementary sources roughly
double the pool specifically to broaden phrasing and topic coverage (see
"Domain coverage" below) without moving into a scale that would be hard to
audit by spot-check before anything downstream depends on it — consistent with
this being a first slice of a small-model, installable engine, not a
mass-scale pretraining corpus. The ~14,000→~12,000–13,000 shrinkage is the
expected cost of cross-source dedup (SVAMP is built *from* ASDiv seeds, and
MAWPS absorbs several older sets that circulate in more than one repackaging —
see the decontamination note in `config/sources.yaml`); the realized post-dedup
count is reported by `validate_corpus.py`, not assumed.

## Source provenance

All four sources are named with their exact Hugging Face dataset id, license,
and origin repository in `config/sources.yaml`:

- **GSM8K** (`openai/gsm8k`) — MIT license, OpenAI / grade-school-math repo.
- **ASDiv** (`EleutherAI/asdiv`) — CC-BY-NC-4.0, Academia Sinica.
- **SVAMP** (`ChilleD/SVAMP`) — MIT, Arkil Patel et al.
- **MAWPS** (`MU-NLPC/Calc-mawps`) — MIT, aggregated MAWPS lineage.

`scripts/build_manifest.py` writes one manifest row per problem with
`source_id`, `origin_split`, `item_id`, and a `sha256` of the normalized
question text. A problem with no manifest row is not part of the corpus — this
keeps every training example traceable to a named dataset and split, never an
unsourced or invented example.

## Domain coverage

`config/domain_coverage.yaml` floors two independent axes so the corpus does
not silently collapse onto whichever story shape is easiest to source:

- **Topic buckets** (money/shopping, time/scheduling, rate/distance,
  counting/grouping, age/comparison, measurement/units, other) — each with a
  `min_share` floor, because money and counting problems dominate raw counts
  in GSM8K/ASDiv/MAWPS alike and would otherwise crowd out topics that are
  just as much "grade-school arithmetic."
- **Step-count buckets** (single-step, 2–4 step, 5+ step) — floored on the
  multi-step buckets and *capped* on single-step, because the objective names
  "reasoning" reliability explicitly, and a pool dominated by one-step
  arithmetic would barely exercise that.

`scripts/common.py::classify_topic` and `::classify_step_count` are simple,
auditable keyword/structure heuristics (not a learned classifier) so a human
reviewer can check the coverage numbers `validate_corpus.py` reports, rather
than trusting a black box. `validate_corpus.py` exits non-zero if any floor or
cap is missed.

## Deduplication

Three layers, cheapest/most-precise first (`scripts/dedupe.py`):

1. **Exact duplicate**: `sha256` of normalized question text. Catches the same
   problem appearing verbatim in more than one source.
2. **Template duplicate**: `sha256_template` — the same hash computed with all
   numeric literals masked to `<NUM>` first. Catches the same story template
   with different numbers plugged in, which is common here specifically
   because SVAMP is *constructed* by perturbing ASDiv seed problems, and
   several MAWPS-lineage sets recycle earlier templates under new numbers.
3. **Near duplicate**: MinHash + LSH over 5-gram shingles
   (`scripts/common.py::shingles`), Jaccard threshold 0.8
   (`config/sources.yaml: holdout.near_dup_jaccard_threshold`), using the
   `datasketch` library (declared, not vendored — see
   `scripts/requirements.txt`). Catches paraphrases the first two layers miss.

All three layers feed one union-find merge (`dedupe.py::merge_groups`), so an
item that is an exact duplicate under layer 1 and also flagged near-duplicate
under layer 3 lands in a single cluster, not two overlapping ones. Within a
cluster, the external-heldout member (if any) is preferred as canonical, so
that a train-pool duplicate of a held-out problem is visibly linked to it —
this is the join `split_holdout.py` uses to keep near-duplicates of held-out
items out of training (see below).

## Separation from held-out evaluation

This objective will ultimately be judged against GSM8K's official test set
(1,319 problems) — the standard benchmark for "solves grade-school arithmetic
word problems." Three layers keep that judgment honest:

1. **Official test splits are authoritative and unconditional.** Every item
   whose origin split matches a source's `heldout_split` in
   `config/sources.yaml` (GSM8K test, SVAMP test, MAWPS test) is marked
   `is_external_heldout=True` at manifest time and can never be reclassified
   into the training pool by any later step.
2. **Cross-source near-duplicate propagation.** Because SVAMP is built from
   ASDiv seeds and MAWPS absorbs recycled templates, a training-pool item can
   be a near-duplicate of a held-out item without being drawn from the same
   dataset. `split_holdout.py` reads `dedupe.py`'s clusters and moves *every*
   member of a cluster that contains an external-heldout item into
   `heldout.jsonl` — this is the mechanism that stops "the test problem, with
   the numbers changed" from leaking into training.
3. **Internal, stratified dev holdout.** From what remains, a seeded 5%
   (`config/sources.yaml: holdout.internal_dev_fraction/seed`) is carved out
   per dedup-cluster (so near-duplicate siblings always land together) into
   `internal_dev.jsonl`, for early-stopping/model-selection during fine-tuning
   — so the external test splits above are never touched until the objective's
   final reported evaluation.

`validate_corpus.py` asserts `train ∩ internal_dev ∩ heldout = ∅` pairwise and
that no dedup cluster spans `heldout` and `train ∪ internal_dev`.

## What this corpus does not solve: retention

"Without losing what it already knew" is a claim about the *fine-tuning* step
(replay mixing, LR/rank choice, regularization), not about this corpus — a
corpus of arithmetic word problems has nothing to say about the checkpoint's
general capability. What this step *does* do in service of that goal: it keeps
`prepared_corpus` narrowly scoped to the target domain (no incidental algebra
or geometry items smuggled in via ASDiv's mixed split — see the `asdiv` field
filter in `fetch_sources.py`) and honestly reports its own size and coverage,
so whoever designs the fine-tuning recipe knows exactly what distribution they
are training on and can choose an appropriate replay/regularization strategy
against it. Sizing or curating a general-capability replay set is a downstream
concern for the fine-tuning step, not this one.

## What would count as success

- Every manifest row has a non-empty `question`, `answer`, and `source_id`,
  each traceable to a named dataset + split.
- Realized topic coverage meets every `min_share` floor, and step-count
  coverage meets its floors and respects the single-step cap, in
  `config/domain_coverage.yaml`.
- `train.jsonl`, `internal_dev.jsonl`, and `heldout.jsonl` are pairwise
  disjoint, and no dedup cluster spans `heldout` and `train ∪ internal_dev`.
- The realized post-dedup corpus size is reported next to the ~12,000–13,000
  proposed target above with a written reason for any material gap (e.g. a
  source dataset revision changing row counts), not presented as having met
  the target by default.

None of the above is asserted as already true in this proposal — the scripts
below are how a future run would produce and check it.

## How to run this (as configured, not yet executed)

```bash
# 1. Fetch raw problems per config/sources.yaml (GSM8K, ASDiv, SVAMP, MAWPS).
uv run python proposals/math-reasoning/corpus/scripts/fetch_sources.py \
    --config proposals/math-reasoning/corpus/config/sources.yaml \
    --out proposals/math-reasoning/corpus/manifest/raw/

# 2. Build the provenance manifest from the raw fetched files.
uv run python proposals/math-reasoning/corpus/scripts/build_manifest.py \
    --config proposals/math-reasoning/corpus/config/sources.yaml \
    --raw-dir proposals/math-reasoning/corpus/manifest/raw/ \
    --out proposals/math-reasoning/corpus/manifest/manifest.jsonl

# 3. Deduplicate (exact + template + near-duplicate clustering).
uv run python proposals/math-reasoning/corpus/scripts/dedupe.py \
    --manifest proposals/math-reasoning/corpus/manifest/manifest.jsonl \
    --config proposals/math-reasoning/corpus/config/sources.yaml \
    --out proposals/math-reasoning/corpus/manifest/dedup_clusters.jsonl

# 4. Split train / internal-dev / heldout, propagating dedup clusters.
uv run python proposals/math-reasoning/corpus/scripts/split_holdout.py \
    --manifest proposals/math-reasoning/corpus/manifest/manifest.jsonl \
    --dedup-clusters proposals/math-reasoning/corpus/manifest/dedup_clusters.jsonl \
    --config proposals/math-reasoning/corpus/config/sources.yaml \
    --out-dir proposals/math-reasoning/corpus/manifest/

# 5. Validate against the success criteria above; exits non-zero on any violation.
uv run python proposals/math-reasoning/corpus/scripts/validate_corpus.py \
    --manifest proposals/math-reasoning/corpus/manifest/manifest.jsonl \
    --domain-coverage proposals/math-reasoning/corpus/config/domain_coverage.yaml \
    --train proposals/math-reasoning/corpus/manifest/train.jsonl \
    --internal-dev proposals/math-reasoning/corpus/manifest/internal_dev.jsonl \
    --heldout proposals/math-reasoning/corpus/manifest/heldout.jsonl \
    --dedup-clusters proposals/math-reasoning/corpus/manifest/dedup_clusters.jsonl
```

`scripts/requirements.txt` lists the extra dependencies (`datasets`, `pyyaml`,
`datasketch`) this recipe would need beyond the base environment; none are
installed as part of this proposal.

## Explicit non-goals of this step

- This step does not fine-tune or evaluate a model, and does not decide the
  replay/regularization strategy that keeps the fine-tuned model from
  regressing on general capability — that belongs to the fine-tuning step
  that consumes `prepared_corpus`.
- This step does not claim network access has been exercised;
  `fetch_sources.py` is a runnable scaffold against the Hugging Face datasets
  named above, not a record of problems already fetched.
- This step does not itself run the GSM8K test-set evaluation that will judge
  the objective — it only guarantees that evaluation set stays uncontaminated
  by anything in `prepared_corpus`.
