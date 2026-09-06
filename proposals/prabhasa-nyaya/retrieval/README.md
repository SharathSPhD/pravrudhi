# Retrieval step — proposal

Status: **PROPOSAL ONLY**. Nothing here writes to the ledger, `research/`, `gates/`,
or `pravrudhi_kernel/`. Every number below is a proposed default, not a measured result.

Step: `retrieval` (capability: `retrieval`)
Consumes: `objective`, `rl_candidate`, `prepared_corpus`
Produces: `retrieval_candidate`

## Objective this step serves

The parent objective is a legal-reasoning assistant for Indian jurisprudence that
answers a question of law with the statute or precedent it relied on, and says "I
don't know" rather than inventing a citation. Reasoning runs over a *typed* Nyaya
meaning graph rather than surface text, so a wrong answer can be traced back to the
inference step that produced it.

`retrieval` is the step that turns a question plus a candidate reasoning policy
(`rl_candidate`) into a small, source-checkable set of graph nodes
(`retrieval_candidate`) that the next step (grounded generation / abstention) will
read from. If retrieval cannot find support in the corpus, the downstream step must
be able to abstain — so retrieval's job includes surfacing "no support found", not
just top-k.

## Why retrieval over a typed graph, not over text chunks

Classical RAG retrieves text chunks ranked by embedding similarity. That is a poor
fit here for two reasons specific to this objective:

1. **Traceability.** The objective requires that a wrong answer be traceable to the
   inference step that produced it. A flat text chunk carries no notion of "this is
   the *reason* (hetu)" vs. "this is the *conclusion* (nigamana)" vs. "this is the
   *precedent being cited as example* (udaharana)". If retrieval only returns chunks,
   the trace stops at "these words were similar."
2. **Indian legal reasoning has a natural typed structure.** The classical Nyaya
   five-membered syllogism (pañcāvayava) — pratijñā (proposition), hetu (reason),
   udāharaṇa (example / precedent), upanaya (application), nigamana (conclusion) —
   maps naturally onto how a judgment or a statute-plus-precedent argument is
   actually built. `prepared_corpus` is assumed to already be structured into this
   typed graph (that structuring is a different step's job, not this one's); this
   step's job is to search it well.

Corpus graph, assumed schema (see `scripts/schemas.py` for the concrete typed
contract this recipe expects from `prepared_corpus`):

- **Node types**: `Statute`, `Precedent`, `Fact`, `Pratijna`, `Hetu`, `Udaharana`,
  `Upanaya`, `Nigamana`. Every node carries a `source_id` (resolvable citation, e.g.
  `"IPC-1860-s302"` or `"AIR-1978-SC-597"`), a text span, and a text embedding.
- **Edge types**: `cites`, `supports`, `contradicts`, `applies_to`, `derived_from`.
  Edges are typed and directed, e.g. `Hetu --supports--> Nigamana`,
  `Udaharana --cites--> Precedent`.

## Approach

Hybrid retrieval, combining two signals that are individually weak on legal corpora:

1. **Dense retrieval** over node text-span embeddings (cosine similarity between the
   query embedding and every node's stored embedding). This finds nodes that are
   *topically* relevant even when they don't share vocabulary with the query — the
   standard RAG failure mode legal text is especially prone to (statutes and
   judgments paraphrase each other constantly).
2. **Typed graph traversal** seeded from the dense hits: expand up to
   `max_hops` edges along `cites` / `supports` / `applies_to` to pull in the
   statute or precedent that a strong Hetu/Nigamana node actually depends on, even
   if that source node's own text embedding scores lower. This is what lets the
   final candidate set contain an actual citable `Statute`/`Precedent` node, not
   just the reasoning-step node that mentions it in passing.

Scores from both signals are combined via **reciprocal rank fusion (RRF)**, which
is used here specifically because it needs no score calibration between the two
very differently-distributed signal types (cosine similarity vs. hop-distance) —
calibrating that jointly would itself require held-out data this proposal doesn't
have.

`rl_candidate` (the reasoning-policy candidate under evaluation) is consumed as the
source of the **query decomposition**: it is asked to break the input question into
one or more sub-queries corresponding to the syllogism members it expects to need
(e.g. "what is the Hetu here" vs. "what precedent would serve as Udaharana"). This
keeps retrieval coupled to the reasoning policy being evaluated, per the step
contract, without retrieval itself doing any reasoning.

**Abstention signal**: if the best raw dense-similarity score for a query (before
fusion — RRF scores are rank-based and not on a threshold-comparable scale) falls
below `min_support_score`, the candidate is emitted with `abstain: true` and an
empty citation list, rather than padding out to `retrieval_count` with weak
matches. This
is the retrieval-side half of "say it does not know rather than inventing a
citation" — generation still needs its own abstention check downstream, but
retrieval must not manufacture false confidence by always returning `k` results.

### Unspecified quantity: `retrieval_count`

**Proposed value: `retrieval_count = 8`**, split as up to 5 dense hits and up to 3
graph-expansion hits (configurable in `configs/retrieval.yaml`).

Rationale (a proposal, not a measurement):
- The five-membered Nyaya syllogism has exactly 5 slots; a well-formed retrieval
  for one question plausibly needs to fill several of them (statute, precedent,
  supporting fact) simultaneously, so `k` should comfortably exceed 5.
- Indian appellate judgments routinely chain 2–3 precedents for a single point of
  law (a precedent citing a precedent). `max_hops = 2` graph expansion adds a
  handful of nodes beyond the direct dense hits, so `8` leaves headroom for that
  without ballooning past what a downstream verifier can check against the graph
  per query.
- `8` is small enough that a human or an automated citation-resolution check
  (see below) can afford to verify every returned node against the corpus for
  every held-out query in an evaluation run, which is exactly what the success
  criterion below requires.

This is a starting point to tune against the held-out set once one exists, not a
claimed-optimal value.

## Files

- `configs/retrieval.yaml` — the recipe's tunable parameters (`retrieval_count`,
  hop limit, fusion weights, abstention threshold).
- `scripts/schemas.py` — typed dataclasses for corpus nodes/edges, the
  `RetrievalCandidate` output contract, and the three consumed artifacts
  (`objective`, `rl_candidate`, `prepared_corpus`) as this recipe expects to read
  them.
- `scripts/graph_index.py` — builds an in-memory typed index (adjacency by edge
  type, embedding matrix) from a `prepared_corpus` payload; typed traversal query.
- `scripts/hybrid_retrieve.py` — the recipe entry point: loads the three consumed
  artifacts, runs dense + graph-traversal retrieval with RRF fusion and the
  abstention check, and writes a `retrieval_candidate` JSON document to a local
  output path given on the command line (never to the ledger).
- `scripts/eval_retrieval.py` — implements the stated success criterion offline:
  for a set of held-out queries with known gold citations, checks (a) every
  `source_id` in a `retrieval_candidate` resolves against the corpus's citation
  registry, and (b) the cited node's text span lexically supports the expected
  answer (a cheap entailment proxy — substring/keyword overlap — standing in for
  a real NLI or human check, flagged as such in the code).

## How to run (once real corpus/model artifacts exist)

These are the intended invocations; they require a real `prepared_corpus` and
`rl_candidate` artifact, which this proposal does not fabricate:

```bash
uv run python proposals/prabhasa-nyaya/retrieval/scripts/hybrid_retrieve.py \
  --objective path/to/objective.json \
  --rl-candidate path/to/rl_candidate.json \
  --prepared-corpus path/to/prepared_corpus.json \
  --config proposals/prabhasa-nyaya/retrieval/configs/retrieval.yaml \
  --queries path/to/held_out_queries.json \
  --out /tmp/retrieval_candidate.json
```

```bash
uv run python proposals/prabhasa-nyaya/retrieval/scripts/eval_retrieval.py \
  --retrieval-candidate /tmp/retrieval_candidate.json \
  --prepared-corpus path/to/prepared_corpus.json \
  --gold path/to/held_out_queries_with_gold.json
```

## What would count as success

Per the step's stated success criterion — "check retrieved source identifiers
resolve and cited passages support answers on held-out queries" — concretely:

1. **Resolution**: every `source_id` emitted in a `retrieval_candidate` for a
   held-out query is present in the corpus's citation registry (no hallucinated
   `AIR-...` or section numbers). `eval_retrieval.py` reports this as a hard
   pass/fail per query — any unresolved id is a failure of this step, full stop.
2. **Support**: for queries with a known gold answer, the passage(s) behind the
   returned `source_id`s must actually support that answer, not merely mention
   related vocabulary. The script's lexical-overlap proxy is a weak placeholder for
   this; a real evaluation should replace it with either human legal-expert review
   or an NLI/entailment model, and that replacement should happen before this
   recipe is treated as validated rather than proposed.
3. **Abstention correctness** (checked against the best raw dense-similarity
   score, per `min_support_score`, not the RRF-fused score — see the README's
   "Approach" section): on held-out queries that have *no* good answer in
   the corpus (an intentionally-unanswerable subset should exist in the held-out
   set for this reason), the step should emit `abstain: true` rather than forcing
   `retrieval_count` results. A retrieval recipe that never abstains cannot support
   the objective's "say it does not know" requirement no matter how good its top-k
   accuracy is — so an eval that only measures precision/recall at k, without a
   dedicated unanswerable slice, would be measuring the wrong thing.

None of the above has been run; there is no `prepared_corpus` or `rl_candidate` in
this worktree to run it against. This README and the scripts are the proposed
recipe and its own evaluation harness, ready to run once those artifacts exist.
