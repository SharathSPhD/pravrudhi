"""An intent without inspectable work could never reach the loop on its own."""

from dataclasses import replace

import pytest

from pravrudhi.application.intent import compile_intent
from pravrudhi.application.objectives import PACKAGED_OBJECTIVES, Benchmark, Objective, examples, load
from pravrudhi.application.recipes import library


@pytest.mark.parametrize("name", examples())
def test_examples(name: str) -> None:
    obj = load(PACKAGED_OBJECTIVES / f"{name}.yaml")
    plan = compile_intent(obj, tuple(library()))
    assert plan.objective == obj
    assert plan.steps
    assert plan.review_required
    assert all(step.capability in {r.capability for r in library()} for step in plan.steps)
    assert all(step.consumes and step.produces and step.check.criterion for step in plan.steps)
    if obj.domain == "code":
        assert not {"finetune", "pretrain", "rl"} & {step.capability for step in plan.steps}


def objective() -> Objective:
    return Objective("new-domain", "Answer with supporting sources", "custom",
                     (Benchmark("custom", "external", "accuracy"),), domain="unseen", recipes=("sft-lora",))


def test_missing_corpus_and_uninstalled_recipes_are_retained() -> None:
    plan = compile_intent(objective(), tuple(library()), installed_skills=frozenset())
    caps = [step.capability for step in plan.steps]
    assert caps.index("corpus") < caps.index("finetune")
    assert all(step.availability == "uninstalled" for step in plan.steps)
    assert all(step.recipe_ids and not step.available_recipe_ids for step in plan.steps)


def test_known_corpus_and_installed_skill() -> None:
    plan = compile_intent(objective(), tuple(library()),
                          installed_skills=frozenset({"nemo-automodel-recipe-development"}),
                          corpus_domains=frozenset({"unseen"}))
    assert "corpus" not in [step.capability for step in plan.steps]
    training = next(step for step in plan.steps if step.capability == "finetune")
    assert training.availability == "available"
    assert training.available_recipe_ids == ("sft-lora",)


def test_stable_order_and_explicit_quantities() -> None:
    obj = replace(objective(), target_delta=0.03)
    recipes = tuple(library())
    plan = compile_intent(obj, recipes)
    assert plan == compile_intent(obj, tuple(reversed(recipes)))
    assert plan == compile_intent(obj, recipes)
    assert plan.steps[-1].check.target_delta == obj.target_delta
    assert plan.steps[-1].check.benchmarks == obj.benchmarks
    assert all(q.value is None for step in plan.steps for q in step.quantities)
    assert compile_intent(objective(), recipes).steps[-1].check.target_delta is None


def test_unknown_recipes_and_missing_catalogue() -> None:
    obj = replace(objective(), recipes=("not-a-recipe",))
    plan = compile_intent(obj, ())
    assert plan.unknown_recipe_ids == ("not-a-recipe",)
    assert all(step.availability == "no_recipe" for step in plan.steps)
    assert plan.steps[-1].capability == "evaluate"


def test_all_packaged_examples_and_dependency_order() -> None:
    for name in examples():
        obj = load(PACKAGED_OBJECTIVES / f"{name}.yaml")
        plan = compile_intent(obj, tuple(library()))
        produced = set(plan.external_inputs)
        for step in plan.steps:
            assert set(step.consumes) <= produced
            produced.update(step.produces)


def test_training_order_and_catalogue_validation() -> None:
    recipes = tuple(library())
    obj = replace(objective(), recipes=tuple(r.id for r in recipes))
    plan = compile_intent(obj, recipes)
    caps = [step.capability for step in plan.steps]
    assert caps.index("corpus") < caps.index("pretrain") < caps.index("finetune") < caps.index("rl")
    with pytest.raises(ValueError, match="unique"):
        compile_intent(obj, recipes + recipes)
    with pytest.raises(ValueError, match="unknown capability"):
        compile_intent(obj, (replace(recipes[0], capability="invented"),))


def test_empty_recipe_selection_records_assumption() -> None:
    plan = compile_intent(replace(objective(), recipes=()), tuple(library()))
    assert plan.assumptions
    caps = [step.capability for step in plan.steps]
    assert caps.index("corpus") < caps.index("finetune")
    assert plan.provenance == "agama"
