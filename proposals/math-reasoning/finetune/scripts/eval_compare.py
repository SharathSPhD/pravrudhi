#!/usr/bin/env python
"""Success criterion, part 2: compare finetune_candidate against baseline.

Runs base_model alone and base_model+adapter over the held-out domain eval
set and the retention eval set, and reports accuracy for both models on
both sets. This script only measures and reports; it does not decide
pass/fail — that judgment belongs to whichever gate consumes the report.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from matheval_utils import accuracy, format_example, load_config, load_jsonl_examples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Path to sft_lora.yaml")
    parser.add_argument("--base-model", default=None)
    parser.add_argument("--adapter-dir", default=None)
    parser.add_argument("--domain-eval", default=None)
    parser.add_argument("--retention-eval", default=None)
    parser.add_argument(
        "--output",
        default="proposals/math-reasoning/finetune/eval_report.json",
        help="Where to write the comparison report",
    )
    return parser.parse_args()


@dataclass
class ComparisonReport:
    base_model: str
    adapter_dir: str
    domain_accuracy_base: float
    domain_accuracy_candidate: float
    retention_accuracy_base: float
    retention_accuracy_candidate: float
    domain_eval_size: int
    retention_eval_size: int


def generate_predictions(model, tokenizer, prompts: list[str], eval_cfg: dict) -> list[str]:
    predictions = []
    batch_size = eval_cfg.get("batch_size", 8)
    max_new_tokens = eval_cfg.get("max_new_tokens", 256)
    for start in range(0, len(prompts), batch_size):
        batch = prompts[start : start + batch_size]
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True)
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=eval_cfg.get("temperature", 0.0) > 0,
        )
        decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        predictions.extend(decoded)
    return predictions


def main() -> None:
    args = parse_args()
    config = load_config(args.config) if args.config else {}

    base_model = args.base_model or config.get("base_model")
    adapter_dir = args.adapter_dir or config.get("output_dir")
    domain_eval_path = args.domain_eval or config.get("domain_eval_path")
    retention_eval_path = args.retention_eval or config.get("retention_eval_path")
    dataset_cfg = config.get("dataset", {})
    eval_cfg = config.get("eval", {})

    if not all([base_model, adapter_dir, domain_eval_path, retention_eval_path]):
        raise SystemExit(
            "base_model, adapter_dir, domain_eval_path, retention_eval_path are all required "
            "(via --config or the individual flags)"
        )

    domain_examples = load_jsonl_examples(
        domain_eval_path,
        prompt_field=dataset_cfg.get("prompt_field", "question"),
        answer_field=dataset_cfg.get("answer_field", "answer"),
    )
    retention_examples = load_jsonl_examples(
        retention_eval_path,
        prompt_field=dataset_cfg.get("prompt_field", "question"),
        answer_field=dataset_cfg.get("answer_field", "answer"),
    )

    domain_prompts = [format_example(ex) for ex in domain_examples]
    domain_refs = [ex.reference for ex in domain_examples]
    retention_prompts = [format_example(ex) for ex in retention_examples]
    retention_refs = [ex.reference for ex in retention_examples]

    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    base = AutoModelForCausalLM.from_pretrained(base_model)
    base.eval()

    base_domain_preds = generate_predictions(base, tokenizer, domain_prompts, eval_cfg)
    base_retention_preds = generate_predictions(base, tokenizer, retention_prompts, eval_cfg)

    candidate = PeftModel.from_pretrained(base, adapter_dir)
    candidate.eval()

    candidate_domain_preds = generate_predictions(candidate, tokenizer, domain_prompts, eval_cfg)
    candidate_retention_preds = generate_predictions(
        candidate, tokenizer, retention_prompts, eval_cfg
    )

    report = ComparisonReport(
        base_model=base_model,
        adapter_dir=adapter_dir,
        domain_accuracy_base=accuracy(base_domain_preds, domain_refs),
        domain_accuracy_candidate=accuracy(candidate_domain_preds, domain_refs),
        retention_accuracy_base=accuracy(base_retention_preds, retention_refs),
        retention_accuracy_candidate=accuracy(candidate_retention_preds, retention_refs),
        domain_eval_size=len(domain_examples),
        retention_eval_size=len(retention_examples),
    )

    report_dict = asdict(report)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(report_dict, fh, indent=2)

    print(json.dumps(report_dict, indent=2))


if __name__ == "__main__":
    main()
