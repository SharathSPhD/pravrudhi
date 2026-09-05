"""An objective named the desired result, but supplied no work the loop could inspect.

Recipes and benchmarks were disconnected from that intent. These proposals bridge those records without
claiming that a recipe ran or that a benchmark covers every sentence of the intent. Missing resources and
quantities stay visible; only execution elsewhere can turn a proposed check into evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pravrudhi.application.objectives import Benchmark, Objective
from pravrudhi.application.recipes import Recipe

Capability = Literal["corpus", "finetune", "pretrain", "performance", "rl", "evaluate", "retrieval", "safety", "agents"]
Availability = Literal["available", "uninstalled", "no_recipe"]

# A dependency order, not a score or a claim about which technique works best.
WORK_ORDER: tuple[Capability, ...] = (
    "corpus", "pretrain", "finetune", "rl", "performance", "retrieval", "safety", "agents",
)


@dataclass(frozen=True)
class QuantityProposal:
    """A missing budget used to disappear into an executor's defaults."""

    name: str
    value: float | None = None


@dataclass(frozen=True)
class SuccessCheckProposal:
    """Naming a technique never specified what would justify keeping its output."""

    criterion: str
    benchmarks: tuple[Benchmark, ...] = ()
    target_delta: float | None = None


@dataclass(frozen=True)
class IntentStepProposal:
    """An absent skill used to hide required work instead of exposing the missing prerequisite."""

    id: str
    capability: Capability
    recipe_ids: tuple[str, ...]
    available_recipe_ids: tuple[str, ...]
    availability: Availability
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    check: SuccessCheckProposal
    quantities: tuple[QuantityProposal, ...]
    reason: str


@dataclass(frozen=True)
class IntentPlanProposal:
    """A plausible decomposition could otherwise be mistaken for fulfilled intent."""

    objective: Objective
    steps: tuple[IntentStepProposal, ...]
    external_inputs: tuple[str, ...]
    unknown_recipe_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    review_required: tuple[str, ...]
    provenance: Literal["agama"] = "agama"


_CRITERIA: dict[Capability, str] = {
    "corpus": "Review source provenance, domain coverage, deduplication and separation from held-out evaluation.",
    "pretrain": "Check the checkpoint loads and compare held-out domain and retention results with the baseline.",
    "finetune": "Check the adapter loads and compare held-out domain and retention results with the baseline.",
    "rl": "Audit the reward against the intent and compare held-out results independently of the training reward.",
    "performance": "Measure resource use and throughput while checking the objective's quality is preserved.",
    "retrieval": "Check retrieved source identifiers resolve and cited passages support answers on held-out queries.",
    "safety": "Check declared behaviour on held-out cases, including legitimate requests that must still work.",
    "agents": "Check the harness obeys the intent's constraints and validate outputs with independent task checks.",
    "evaluate": "Compare external candidate and baseline results using each declared metric and direction; "
    "apply the supplied target, if any, and the objective's existing uncertainty rule.",
}
_QUANTITIES: dict[Capability, tuple[str, ...]] = {
    "corpus": ("corpus_size",),
    "pretrain": ("training_steps", "compute_budget"),
    "finetune": ("training_steps", "compute_budget"),
    "rl": ("rollout_count", "compute_budget"),
    "performance": ("resource_budget",),
    "retrieval": ("retrieval_count",),
    "safety": ("evaluation_sample_count",),
    "agents": ("execution_budget",),
    "evaluate": ("evaluation_sample_count",),
}


def compile_intent(
    objective: Objective,
    recipes: tuple[Recipe, ...],
    *,
    installed_skills: frozenset[str] = frozenset(),
    corpus_domains: frozenset[str] = frozenset(),
) -> IntentPlanProposal:
    """A recipe list omitted prerequisites and never distinguished a plan from measured progress.

    Callers supply a catalogue and resource snapshot, so compilation needs no filesystem, model or network.
    Corpus domains identify caller-declared usable corpora, not domains this compiler claims to have checked.
    Recipe availability means skill presence only. All steps still require review and execution configuration.
    """
    catalogue = {recipe.id: recipe for recipe in recipes}
    if len(catalogue) != len(recipes):
        raise ValueError("recipe ids must be unique")
    known_capabilities = {*WORK_ORDER, "evaluate"}
    if any(recipe.capability not in known_capabilities for recipe in recipes):
        raise ValueError("recipe catalogue contains an unknown capability")
    selected = {catalogue[rid].capability for rid in objective.recipes if rid in catalogue}
    assumptions: list[str] = []
    if not objective.recipes and objective.domain:
        selected.add("finetune")
        assumptions.append("No recipes declared; domain fine-tuning is a suggested starting point requiring review.")
    have_corpus = bool(objective.domain) and objective.domain in corpus_domains
    if selected & {"pretrain", "finetune", "rl", "retrieval"} and not have_corpus:
        selected.add("corpus")
        assumptions.append("No usable corpus declared for this domain; propose acquiring or curating one first.")

    external = ("objective", "benchmarks", "base_model") + (("domain_corpus",) if have_corpus else ())
    steps: list[IntentStepProposal] = []

    def step(
        ident: str, capability: Capability, consumes: tuple[str, ...], produces: tuple[str, ...],
        criterion: str, reason: str,
    ) -> IntentStepProposal:
        matches = sorted((r for r in recipes if r.capability == capability), key=lambda r: r.id)
        preferred = [r for r in matches if r.id in objective.recipes]
        candidates = preferred or matches
        available = tuple(r.id for r in candidates if r.skill in installed_skills)
        status: Availability = "available" if available else "uninstalled" if candidates else "no_recipe"
        return IntentStepProposal(
            ident, capability, tuple(r.id for r in candidates), available, status, consumes, produces,
            SuccessCheckProposal(criterion, objective.benchmarks if capability == "evaluate" else (),
                                 objective.target_delta if ident == "candidate-evaluation" else None),
            tuple(QuantityProposal(name) for name in _QUANTITIES[capability]), reason,
        )

    steps.append(step(
        "baseline-evaluation", "evaluate", ("objective", "benchmarks", "base_model"), ("baseline_results",),
        "Obtain a baseline result from each declared external tool reporting its exact metric on this track.",
        "Candidate improvement needs a baseline; this proposal does not assert one is absent from the ledger.",
    ))
    candidate = "base_model"
    corpus = "domain_corpus"
    for capability in WORK_ORDER:
        if capability not in selected:
            continue
        consumes: tuple[str, ...] = ("objective",)
        if capability != "corpus":
            consumes += (candidate,)
        if capability in {"pretrain", "finetune", "rl", "retrieval"}:
            consumes += (corpus,)
        output = "prepared_corpus" if capability == "corpus" else f"{capability}_candidate"
        steps.append(step(
            capability, capability, consumes, (output,), _CRITERIA[capability],
            "Required by declared recipes or their data prerequisites; alternatives remain proposals.",
        ))
        if capability == "corpus":
            corpus = output
        else:
            candidate = output
    steps.append(step(
        "candidate-evaluation", "evaluate", ("objective", "benchmarks", "baseline_results", candidate),
        ("candidate_comparison",), _CRITERIA["evaluate"],
        "The declared benchmarks are instruments, not proof of complete intent coverage.",
    ))
    return IntentPlanProposal(
        objective, tuple(steps), external,
        tuple(sorted(set(objective.recipes) - catalogue.keys())), tuple(assumptions),
        ("Review every clause of the verbatim intent against this decomposition; recipe matching is not semantics.",
         "Specify checks for intent requirements the declared benchmarks do not measure; preserve the objective notes.",
         "Resolve unspecified quantities, resource inputs and recipe installation before execution."),
    )
