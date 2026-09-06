#!/usr/bin/env python
"""Success criterion, part 1: confirm the finetune_candidate adapter loads.

Loads base_model, attaches the LoRA adapter at adapter_dir via PEFT, and
runs one smoke generation. Exits non-zero if either step fails, so a
pipeline gate can treat this as a hard pass/fail check before spending any
eval compute on the candidate.
"""
from __future__ import annotations

import argparse
import sys

from matheval_utils import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Path to sft_lora.yaml")
    parser.add_argument("--base-model", default=None, help="Override config base_model")
    parser.add_argument("--adapter-dir", default=None, help="Override config output_dir")
    parser.add_argument(
        "--prompt",
        default="Question: If a train travels 60 miles in 2 hours, how fast is it going?\nAnswer:",
        help="Smoke-test prompt to generate from",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config) if args.config else {}

    base_model = args.base_model or config.get("base_model")
    adapter_dir = args.adapter_dir or config.get("output_dir")
    if not base_model or not adapter_dir:
        print("base_model and adapter_dir must be set via --config or flags", file=sys.stderr)
        return 2

    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    try:
        tokenizer = AutoTokenizer.from_pretrained(adapter_dir)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(base_model)

    base = AutoModelForCausalLM.from_pretrained(base_model)
    model = PeftModel.from_pretrained(base, adapter_dir)
    model.eval()

    inputs = tokenizer(args.prompt, return_tensors="pt")
    outputs = model.generate(**inputs, max_new_tokens=32, do_sample=False)
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)

    if not generated.strip():
        print("Adapter loaded but produced empty generation", file=sys.stderr)
        return 1

    print("Adapter loaded successfully. Smoke generation:")
    print(generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
