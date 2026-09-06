#!/usr/bin/env python
"""Proposal script for the prabhasa-nyaya `finetune` step, recipe `sft-lora`.

Trains a LoRA adapter (the `finetune_candidate`) on top of a frozen
`base_model` using a `prepared_corpus` of (prompt, completion) examples where
the prompt embeds a linearized Nyaya meaning-graph context and the completion
either cites node ids present in that context or abstains.

This is a proposal artifact: running it produces a candidate adapter for the
`gates` step to evaluate, it does not itself certify anything.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base_model", required=True, help="Path or hub id of the base model.")
    parser.add_argument(
        "--prepared_corpus",
        required=True,
        help="Path to a JSONL file of {prompt, completion} training examples.",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the sft-lora YAML config (see configs/sft_lora.yaml).",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Directory to write the finetune_candidate adapter into.",
    )
    return parser.parse_args()


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_corpus(corpus_path: str) -> list[dict]:
    examples = []
    with open(corpus_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if "prompt" not in record or "completion" not in record:
                raise ValueError(
                    f"prepared_corpus record missing prompt/completion: {record!r}"
                )
            examples.append(record)
    if not examples:
        raise ValueError(f"prepared_corpus at {corpus_path} contained no examples")
    return examples


def build_lora_config(cfg: dict):
    from peft import LoraConfig

    lora_cfg = cfg["lora"]
    return LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        lora_dropout=lora_cfg["lora_dropout"],
        bias=lora_cfg["bias"],
        task_type=lora_cfg["task_type"],
        target_modules=lora_cfg["target_modules"],
    )


def build_training_args(cfg: dict, output_dir: str):
    from trl import SFTConfig

    train_cfg = cfg["training"]
    return SFTConfig(
        output_dir=output_dir,
        num_train_epochs=train_cfg["num_epochs"],
        max_steps=train_cfg["max_steps"],
        per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=train_cfg["learning_rate"],
        lr_scheduler_type=train_cfg["lr_scheduler_type"],
        warmup_ratio=train_cfg["warmup_ratio"],
        weight_decay=train_cfg["weight_decay"],
        save_steps=train_cfg["save_steps"],
        eval_steps=train_cfg["eval_steps"],
        logging_steps=train_cfg["logging_steps"],
        seed=train_cfg["seed"],
        max_seq_length=cfg["data"]["max_seq_length"],
        packing=cfg["data"]["packing"],
        bf16=True,
    )


def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)
    examples = load_corpus(args.prepared_corpus)

    import torch
    from datasets import Dataset
    from peft import get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTTrainer

    dataset = Dataset.from_list(examples)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.bfloat16,
    )
    model = get_peft_model(model, build_lora_config(cfg))

    def format_example(example: dict) -> str:
        return example["prompt"] + example["completion"]

    training_args = build_training_args(cfg, args.output_dir)

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        formatting_func=format_example,
        tokenizer=tokenizer,
    )
    trainer.train()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    print(f"finetune_candidate written to {output_dir}")


if __name__ == "__main__":
    main()
