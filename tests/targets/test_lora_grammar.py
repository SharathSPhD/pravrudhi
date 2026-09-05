from pravrudhi.targets import LoraRecipe, parse_recipe


def test_default_recipe_is_valid_and_costed() -> None:
    r = parse_recipe({"strategy": "sft_rejection", "execution_family": "optimiser", "sft": {"lr": 2e-4}})
    assert isinstance(r, LoraRecipe) and r.sft.lr == 2e-4 and 0.0 < r.cost_est_gpu_h() < 1.0


def test_out_of_grammar_is_refused_with_reason() -> None:
    assert isinstance(parse_recipe({"strategy": "full_finetune", "execution_family": "optimiser"}), str)
    r = parse_recipe({"strategy": "sft_rejection", "execution_family": "adapter", "lora": {"r": 4096}})
    assert isinstance(r, str) and "lora.r" in r
    assert isinstance(parse_recipe({"strategy": "sft_rejection", "execution_family": "grpo"}), str)
    assert isinstance(parse_recipe({"strategy": "grpo_verifiable", "execution_family": "data_mixture"}), str)
    assert isinstance(parse_recipe({"strategy": "sft_rejection", "execution_family": "optimiser", "extra": 1}), str)


def test_grpo_recipe_costs_more_with_steps() -> None:
    a = parse_recipe({"strategy": "grpo_verifiable", "execution_family": "grpo", "grpo": {"steps": 10}})
    b = parse_recipe({"strategy": "grpo_verifiable", "execution_family": "grpo", "grpo": {"steps": 40}})
    assert isinstance(a, LoraRecipe) and isinstance(b, LoraRecipe) and b.cost_est_gpu_h() > a.cost_est_gpu_h()
