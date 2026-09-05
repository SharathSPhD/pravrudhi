# Architecture

This page orients a new contributor: what the two halves of the repository are for, what a night is, why the
sealed pool and paired evaluation matter, why a candidate needs two seeds before promotion, and where to read
next. It states no measurement; every number belongs in the ledger, never here.

## The kernel and the engine

The repository splits into two packages with a strict, one-directional dependency: `pravrudhi_kernel/` is a
dependency of `src/pravrudhi/`, never the reverse.

`pravrudhi_kernel/` is the evaluator. It holds the ledger schema, the hash-chained ledger writer and verifier, a
vendored statistics library, the expected-free-energy controller mathematics, the sealed held-out pools, the
benchmark scorers, and the sandbox runner that executes a job in a disposable container. The kernel has no model
client and no network access; it can only read what a job wrote to disk and decide, from that alone, what the
evidence is. It is also the only writer of the ledger: nothing else, in the engine or in a coding agent working in
the repository, appends to `research/ledger.jsonl` directly; only `LedgerWriter` does, and it checks hash
continuity on every append, refusing a line that would break the chain.

`src/pravrudhi/` is the engine: it proposes, orchestrates, and serves. It talks to the proposer and the trainee's
backend, declares what may be edited and materialises a candidate into a job for the kernel to run, runs the
night and the other CLI verbs, and carries the optional multi-machine and coding-agent layers. A model client, a
subprocess, the network — all live here, none of it is available to the kernel. A component able to both propose
and score is one bug away from grading its own homework; keeping that boundary in the package structure rather
than in a convention makes the failure mode harder to reach.

## What a night is

A night is one budgeted batch of experiment, run as three phases in order.

The deliberation window loads the proposer model alone. It reads the ledger's evidence and emits candidate recipes
as JSON constrained by a fixed grammar; alongside each recipe a predictor emits a predicted effect and a
confidence, both hash-committed before any candidate trains. Committing the prediction first is what lets the
night's information-gain accounting mean anything: a candidate is only worth running if its outcome could move the
controller's belief, which can only be checked against a prediction locked in before the outcome existed.

Selection follows. The controller rebuilds its posterior entirely from the ledger, keeping no state of its own
between nights, scores every live candidate by expected free energy, refuses to proceed if a score does not
condition on the action proposed, and fills the budget with a Thompson-like knapsack that reserves an epistemic
floor against collapsing onto one confident guess.

The execution windows then run one candidate at a time: train in a disposable container, evaluate against the
current incumbent, score with the kernel, and dispose of the candidate by the sequential test described below. A
candidate crossing the efficacy boundary must also clear the pre-registered canaries before becoming incumbent.
The night closes with an audit event recording the strategy-switch rate and any rethink checkpoints, so a later
reader can tell, from the ledger alone, whether the controller stayed consistent across the night.

## The sealed pool and paired evaluation

A model scored on data it has already trained on, or has seen scored before under conditions it can infer, is not
being measured, it is being flattered. The sealed pool closes that door: sealing writes the evaluation items once
and refuses to overwrite an existing manifest, since refreshing a pool changes what "held out" has meant and is
treated as an epoch boundary, not a routine act. Drawing a rotation for a given night and candidate is
deterministic rather than sampled at the point of use — the kernel HMACs the night and candidate identifiers with
a pool-local secret to choose a stable subset, reproducible for audit without ever storing which items were shown.
An exposure cap tracks how often each item has been drawn, and the pool refuses to draw once eligible items run
short rather than reusing overexposed ones.

Paired evaluation is the other half of the same concern: a candidate is never scored against a historical number,
but evaluated against the current incumbent on the same rotation and sampling seed, in the same execution window
— which is what makes the resulting difference attributable to the candidate rather than to which items were
drawn or how the model happened to run that day. It is the paired difference, not either arm's raw score, that
feeds the sequential test.

## The sequential boundary and the two-seed rule

A candidate is not judged on a single evaluation pass. Its per-seed paired effects feed one at a time into an
always-valid sequential test — a Gaussian-mixture e-process against a prior over the true effect — which after
each seed decides to prune, continue, or confirm, readable at any point without the inflated false-positive rate
that repeated peeking at a fixed-sample test would cause.

Because the test is checked after every seed, an unlucky or lucky first seed alone could in principle satisfy the
efficacy threshold on its own. The engine additionally requires a minimum of two seeds before a confirmation may
stand, whatever the first seed's e-value looks like: a single seed carries no information about whether an effect
is real or an artefact of that draw, and a second, independent seed turns "this looked good once" into "this looks
good across draws." The requirement sits on the same footing as the efficacy and futility bounds.

## The coding-agent layer and the multi-machine fleet

Both are optional: a fresh install has neither a fleet file nor a configured agent, and runs correctly with one
host and none.

The coding-agent layer is the extension point for a proposer of changes to the harness or the engine itself, as
opposed to the `Target` protocol, which is the extension point for a benchmark. A provider under this layer runs
inside its own git worktree, and the boundary that matters is enforced in code, not left to instruction: a diff
touching the kernel, the ledger, the sealed pools, or the pre-registration files is rejected whole, since an agent
able to edit its own evaluator is not improving the system, it is disabling the thing that would have caught a
false improvement. A related rule bounds what a hosted assistant's output may become: these agents may write
code, but their output must never be distilled into training data for the trainee, since a trainee partly trained
on a hosted model's completions would no longer be measuring the loop this repository exists to measure.

The fleet lets more than one machine take part. A fresh install has exactly one host, `local`, needing no
configuration file; a second machine is enrolled over SSH and recorded only once it answers a capability probe,
since capability is measured fresh each time, not trusted from a stale declaration. The practical reason to add a
second host is the proposer, the largest model in the loop, which on a single GPU competes with the trainee for
memory it would rather not share — pointing it at another host serving an OpenAI-compatible endpoint frees the
training accelerator from that contention.

## Where to start reading

Start with the ledger writer in `pravrudhi_kernel`, whose docstring explains what it means for the ledger to be
the only channel evidence enters through, then `night.py` in `src/pravrudhi/application/`, which walks the three
phases in the order they execute. `pool.py` and `sequential.py`, under the kernel's metrics and stats modules,
cover the rotation draw and the sequential boundary in the same terse-rationale style. `docs/usage.md` covers the
same ground from the perspective of someone running commands rather than reading code, and is worth reading
alongside this page.
