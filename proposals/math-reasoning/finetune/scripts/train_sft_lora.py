#!/usr/bin/env python
"""Train a LoRA adapter (recipe: sft-lora) for the `finetune` step.

Consumes base_model + prepared_corpus (as described in config/sft_lora.yaml
or via CLI flags), produces the finetune_candidate LoRA adapter at
output_dir. This is a proposal script: no hyperparameter here has been
measured, they are documented starting points (see README.md).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from matheval_utils import Example, format_example, load_config, load_jsonl_examples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to sft_lora.yaml")
    parser.add_argument("--base-model", default=None, help="Override config base_model")
    parser.add_argument(
        "--prepared-corpus",
        nargs="*",
        default=None,
        help="Override config prepared_corpus (one or more JSONL paths)",
    )
    parser.add_argument("--output-dir", default=None, help="Override config output_dir")
    return parser.parse_args()


def build_training_text(example: Example) -> str:
    return f"{format_example(example)} {example.reference}"


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    base_model = args.base_model or config["base_model"]
    prepared_corpus = args.prepared_corpus or config["prepared_corpus"]
    output_dir = args.output_dir or config["output_dir"]

    dataset_cfg = config.get("dataset", {})
    lora_cfg = config.get("lora", {})
    train_cfg = config.get("training", {})

    examples = load_jsonl_examples(
        prepared_corpus,
        prompt_field=dataset_cfg.get("prompt_field", "question"),
        answer_field=dataset_cfg.get("answer_field", "answer"),
    )
    if not examples:
        raise SystemExit(f"No training examples found in {prepared_corpus!r}")

    texts = [build_training_text(ex) for ex in examples]

    # Imports deferred so `python -m compileall` (syntax check only) does
    # not require torch/transformers/trl/peft to be importable.
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(base_model)

    train_dataset = Dataset.from_dict({"text": texts})

    peft_config = LoraConfig(
        r=lora_cfg.get("r", 16),
        lora_alpha=lora_cfg.get("alpha", 32),
        lora_dropout=lora_cfg.get("dropout", 0.05),
        target_modules=lora_cfg.get(
            "target_modules",
            ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        ),
        bias="none",
        task_type="CAUSAL_LM",
    )

    sft_config = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=train_cfg.get("num_train_epochs", 3),
        max_steps=train_cfg.get("max_steps", 1200),
        per_device_train_batch_size=train_cfg.get("per_device_train_batch_size", 4),
        gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 4),
        learning_rate=train_cfg.get("learning_rate", 2.0e-4),
        lr_scheduler_type=train_cfg.get("lr_scheduler_type", "cosine"),
        warmup_ratio=train_cfg.get("warmup_ratio", 0.03),
        max_seq_length=train_cfg.get("max_seq_length", 1024),
        bf16=train_cfg.get("bf16", True),
        logging_steps=train_cfg.get("logging_steps", 20),
        save_strategy=train_cfg.get("save_strategy", "epoch"),
        seed=train_cfg.get("seed", 42),
        dataset_text_field="text",
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_dataset,
        peft_config=peft_config,
        processing_class=tokenizer,
    )

    trainer.train()

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    print(f"Saved finetune_candidate LoRA adapter to {output_dir}")


if __name__ == "__main__":
    main()
