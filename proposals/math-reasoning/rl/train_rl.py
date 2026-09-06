"""RL post-training entry point for the `rl-post-training` recipe.

Loads `finetune_candidate`, wraps `prepared_corpus`'s train split as GRPO
prompts, and trains with the verifiable reward in reward.py. Writes the
resulting LoRA adapter to --output-dir (rl_candidate).

This is a proposal-stage script: it declares the intended training loop
against TRL's GRPOTrainer. It intentionally does not read, write, or assume
anything about the ledger, research/, gates/, or pravrudhi_kernel/ — its only
concern is turning (finetune_candidate, prepared_corpus, config) into a
checkpoint directory.

Usage:
    uv run python train_rl.py --config rl_config.yaml \
        --base-model artifacts/finetune_candidate \
        --train-data artifacts/prepared_corpus/train.jsonl \
        --output-dir artifacts/rl_candidate
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from reward import reward_fn


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_prompt(question: str) -> str:
    return (
        "Solve the following grade-school math word problem. "
        "Show your reasoning, then give the final numeric answer on its own "
        "line prefixed with '####'.\n\n"
        f"Question: {question}\nAnswer:"
    )


def load_config(config_path: str | Path) -> dict[str, Any]:
    with open(config_path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_grpo_trainer(config: dict[str, Any], base_model: str, train_data_path: str):
    """Construct the TRL GRPOTrainer described by `config`.

    Imports TRL/PEFT/transformers lazily so this module can be imported (and
    reward.py exercised) without those heavy dependencies installed, e.g. in
    a lightweight lint/compile check.
    """
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    lora_cfg = config["lora"]
    peft_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        lora_dropout=lora_cfg["lora_dropout"],
        target_modules=lora_cfg["target_modules"],
        task_type=lora_cfg["task_type"],
    )

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(base_model)

    raw_records = load_jsonl(train_data_path)
    question_field = config["data"]["question_field"]
    answer_field = config["data"]["answer_field"]
    dataset = [
        {
            "prompt": build_prompt(record[question_field]),
            "gold_answer": record[answer_field],
        }
        for record in raw_records
    ]

    proposed = config["proposed_quantities"]
    training = config["training"]
    grpo_config = GRPOConfig(
        output_dir=config["output"]["output_dir"],
        num_generations=proposed["rollout_count"],
        per_device_train_batch_size=proposed["prompts_per_step"],
        max_steps=proposed["max_steps"],
        eval_steps=proposed["eval_steps"],
        save_steps=config["output"]["save_steps"],
        learning_rate=training["learning_rate"],
        beta=training["kl_coef"],
        temperature=training["temperature"],
        top_p=training["top_p"],
        seed=training["seed"],
        gradient_checkpointing=training["gradient_checkpointing"],
        bf16=training["bf16"],
        max_prompt_length=config["data"]["max_prompt_length"],
        max_completion_length=config["data"]["max_completion_length"],
    )

    def wrapped_reward_fn(completions: list[str], **kwargs) -> list[float]:
        gold_answers = kwargs["gold_answer"]
        return reward_fn(completions, gold_answers)

    return GRPOTrainer(
        model=model,
        args=grpo_config,
        train_dataset=dataset,
        reward_funcs=wrapped_reward_fn,
        peft_config=peft_config,
        processing_class=tokenizer,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to rl_config.yaml")
    parser.add_argument("--base-model", required=True, help="Path/id of finetune_candidate")
    parser.add_argument("--train-data", required=True, help="JSONL train split of prepared_corpus")
    parser.add_argument("--output-dir", required=True, help="Where to write rl_candidate")
    args = parser.parse_args()

    config = load_config(args.config)
    config["output"]["output_dir"] = args.output_dir

    trainer = build_grpo_trainer(config, args.base_model, args.train_data)
    trainer.train()
    trainer.save_model(args.output_dir)
    print(f"rl_candidate written to {args.output_dir}")


if __name__ == "__main__":
    main()
