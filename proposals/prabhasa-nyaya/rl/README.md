# rl step proposal: prabhasa-nyaya

Step `rl`, capability `rl`, recipe `rl-post-training`.
Consumes: `objective`, `finetune_candidate`, `prepared_corpus`. Produces: `rl_candidate`.

**This directory is a proposal.** Nothing here has been run against the real
`finetune_candidate` / `prepared_corpus` artifacts (they were not read in
producing this proposal — see "Assumed interfaces" below). No number in
this README or its configs is a measured result; every quantity is
explicitly a suggestion with its reasoning attached.

## Objective, restated as a training target

The assistant must, for a question of law: (a) answer with the statute or
precedent it relied on, (b) say it does not know rather than invent a
citation, and (c) do its reasoning over a typed Nyaya meaning graph so a
wrong answer traces back to the inference step that produced it. That's
three separate behaviors, and a naive "reward = did you get the right
answer" signal would not distinguish a lucky guess from a properly-traced
one, nor would it punish a hallucinated-but-plausible citation any more
than an honest wrong one. The reward function here is built around that
distinction rather than around raw accuracy.

## Approach

RL post-training on top of `finetune_candidate` using **GRPO** (group-relative
policy optimization, via TRL's `GRPOTrainer`) with a **LoRA** adapter, per
this project's LoRA-first direction. GRPO is chosen over PPO because it
needs no separate value model — cheaper per step, which matters given this
runs on a single local GPU — and its group-relative advantage is a natural
fit for a reward that is a hand-built composite (not a learned/scalar
reward model), where per-group normalization absorbs scale drift across
question difficulty.

The policy is trained to emit a structured completion (trace → citation →
answer, or an explicit abstention), and the reward function
(`scripts/reward_function.py`) scores that structure directly against the
question's graph slice:

1. **Grounding gate**: any cited id that is not a real node in the graph
   handed to the model for that question is a hallucination — hard penalty,
   applied on top of everything else, not a soft deduction.
2. **Trace validity**: the claimed inference path must be a real path
   (real nodes, real edges, correct direction) in the typed graph. This is
   what makes a wrong answer traceable to the step that produced it: an
   answer with an invalid trace is penalized even when its citation happens
   to be correct.
3. **Abstention**: rewarded when the graph does not support an answer,
   mildly penalized (not hallucination-level) when used to dodge a
   question the graph does support.
4. **Task correctness**: only contributes once grounding and trace validity
   have both passed, so a hallucinated-but-textually-correct-looking answer
   cannot outscore a properly grounded one.

See `scripts/reward_function.py` for the exact combination and
`scripts/output_parser.py` for the expected completion format.

## Assumed interfaces

This task scoped me to `proposals/prabhasa-nyaya/rl/` only, so the real
schemas of `finetune_candidate` and `prepared_corpus` were not read. The
scripts here assume:

- `finetune_candidate`: a JSON file with `base_model`, optional
  `adapter_path`, and `tokenizer_path` (`scripts/data_contracts.py:FinetuneCandidateRef`).
- `prepared_corpus`: JSONL, one example per line, each with `id`,
  `question`, a `graph` (`nodes`: `{id, type, text}`, `edges`:
  `{src, dst, relation}`), `gold_citations`, `gold_answer` (nullable), and
  `answerable` (bool) — plus a `split` field distinguishing `train` from a
  `held_out` split that GRPO never trains on
  (`scripts/data_contracts.py:PreparedExample`).
- `objective`: a JSON file with at least an `id` (used only for logging).

**Whoever wires this against the real artifacts must reconcile these
assumptions with the actual producer schemas before running anything.**

## Files

```
proposals/prabhasa-nyaya/rl/
├── README.md                       this file
├── configs/
│   └── rl_grpo.yaml                 all hyperparameters, reward weights, compute budget
└── scripts/
    ├── data_contracts.py            assumed I/O schemas (dataclasses)
    ├── reward_function.py           the composite reward (grounding / trace / abstention / correctness)
    ├── output_parser.py             raw completion -> structured ModelOutput
    ├── audit_reward.py              reward-vs-intent probes (run this first)
    ├── held_out_eval.py             independent held-out scorer (does NOT import reward_function.py)
    └── train_rl.py                  GRPO + LoRA training entry point (TRL / PEFT / transformers)
```

## Commands

1. **Audit the reward before trusting any training run.** This is the
   step's own success criterion's first half — a set of hand-built probes
   asserting the reward orders desired behavior above undesired behavior
   (grounded+traced beats abstention on answerable questions, abstention
   beats hallucination on unanswerable ones, a valid trace beats a
   fabricated edge over the same nodes, etc.):

   ```bash
   uv run python proposals/prabhasa-nyaya/rl/scripts/audit_reward.py
   ```

2. **Run RL post-training** (once the real artifacts and a model-serving
   `generate` function exist; requires `trl`, `peft`, `transformers`, `torch`
   in the environment — not installed as part of this proposal):

   ```bash
   uv run python proposals/prabhasa-nyaya/rl/scripts/train_rl.py \
       --config proposals/prabhasa-nyaya/rl/configs/rl_grpo.yaml \
       --finetune-candidate path/to/finetune_candidate.json \
       --prepared-corpus path/to/prepared_corpus.jsonl \
       --objective path/to/objective.json \
       --output-dir outputs/prabhasa-nyaya-rl
   ```

3. **Evaluate the resulting `rl_candidate` independently of the training
   reward** — the second half of the success criterion. This script does
   not import `reward_function.py`; it re-derives grounding, trace
   faithfulness, hallucination rate, and abstention accuracy from scratch
   with different extraction logic (bracketed-citation regex instead of
   the training output tags, adjacency-in-generated-text instead of the
   model's self-reported trace), and it compares `rl_candidate` against
   the pre-RL `finetune_candidate` on the same held-out split GRPO never
   trained on:

   ```bash
   uv run python proposals/prabhasa-nyaya/rl/scripts/held_out_eval.py \
       --held-out-corpus path/to/held_out.jsonl \
       --candidate path/to/rl_candidate \
       --baseline path/to/finetune_candidate \
       --generate-fn my_serving_module:generate
   ```

## Proposed quantities (not measured)

The objective leaves `rollout_count` and `compute_budget` unspecified.
Proposed values, in `configs/rl_grpo.yaml`:

- **`rollout_count`**: group size 8 rollouts/prompt × 32 prompts/step = 256
  rollouts/step, for up to 500 steps (≤128,000 rollouts total, but see
  below — 500 is a ceiling, not a target).
  - Group size 8 is the low end of what GRPO needs for a low-variance
    within-group advantage estimate; going lower makes the relative-reward
    signal noisy, going much higher wastes rollouts on a composite reward
    that is cheap to compute (no reward model forward pass) and thus
    doesn't need extra averaging to control cost.
  - 500 steps is a conservative first-pass ceiling for a first RL run on
    top of an already-instruction-tuned candidate: legal citation/trace
    reward is easy to reward-hack shallowly (e.g. "cite the most-frequent
    real node id"; "always abstain"), so the actual stopping point should
    be gated on `held_out_eval.py` metrics regressing or plateauing, not
    on reaching step 500.

- **`compute_budget`**: 24 GPU-hours on a single local GPU (per the host
  stack notes for this box, a 5090).
  - This is sized as "enough for the 500-step ceiling above at a LoRA
    adapter's per-step cost with ~768-token completions, on one GPU,
    without requiring multi-day wall-clock" — a first-pass budget to see
    whether the reward's shape produces any improvement at all before
    committing more compute, not a tuned or benchmarked figure.

Both numbers should be treated as the starting point for the first
experiment, to be revised once `held_out_eval.py` results exist to revise
them against.

## What counts as success

Per the step's stated success criterion, success has two independent
parts, and **both** must hold — a good held-out result from a reward that
doesn't match intent isn't trustworthy, and a well-audited reward with no
held-out improvement hasn't demonstrated anything:

1. **`audit_reward.py` passes all probes** — the reward, as code, actually
   rewards the three target behaviors (cite what it relied on, abstain
   over inventing a citation, keep the trace valid) in the right order.
2. **`held_out_eval.py`**, run on a held-out split GRPO never trained on,
   using extraction logic independent of the training reward's parser,
   shows the `rl_candidate` improving over the pre-RL `finetune_candidate`
   on:
   - `hallucination_rate` — should decrease (this is the objective's core
     ask: "says it does not know rather than inventing a citation").
   - `trace_faithful_rate` — should not regress; ideally increases.
   - `abstention_accuracy_on_unanswerable` — should not regress.
   - `mean_citation_precision` / `mean_citation_recall` — should not
     regress; a drop here alongside a hallucination-rate improvement would
     indicate the policy learned to abstain its way to a better score
     rather than actually reasoning better, which is itself a useful
     (negative) finding, not a success.

A run that improves the training reward curve but fails (2) — especially
one where `hallucination_rate` looks great only because
`abstention_accuracy` on *answerable* questions collapsed — should be
treated as reward hacking, not progress, and is exactly what the
independent held-out script is for.

## Known reward-hacking risks in this specific reward

- **Frequency hacking**: always citing whatever node id is most common in
  training graphs. Mitigated by the grounding gate being per-question
  (must be a node in *that* question's graph), but watch
  `mean_citation_precision` on held-out for this pattern.
- **Abstention collapse**: abstaining on everything to bank the small
  negative-but-safe score instead of the larger reward for a correct
  grounded answer. The reward weights answerable-abstention as mildly
  negative specifically to counter this; `held_out_eval.py`'s
  `abstention_accuracy_on_unanswerable` combined with citation
  precision/recall on the answerable subset is the tripwire.
- **Trace theater**: emitting a syntactically well-formed `<trace>` block
  whose nodes are real but whose narrative doesn't actually correspond to
  why the citation was chosen. `reward_function.py`'s trace check only
  verifies structural validity (real nodes/edges), not semantic relevance
  to the question — this is a known gap, and `held_out_eval.py`'s
  adjacency-in-text check is a coarse, independent proxy for it, not a
  full fix. A future iteration should consider an independent judge model
  for semantic trace relevance.
