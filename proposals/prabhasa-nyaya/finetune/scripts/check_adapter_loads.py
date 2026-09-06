#!/usr/bin/env python
"""First half of the finetune step's success criterion: check that the
finetune_candidate adapter loads on top of base_model and produces a
completion without error.

Exits 0 on success, non-zero on any failure. Prints nothing that should be
read as a benchmark result -- this is a load/smoke check only.
"""

from __future__ import annotations

import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base_model", required=True, help="Path or hub id of the base model.")
    parser.add_argument(
        "--adapter_dir",
        required=True,
        help="Path to the finetune_candidate adapter directory to check.",
    )
    parser.add_argument(
        "--smoke_prompt",
        default="Under Indian law, what limitation period applies?",
        help="A short prompt used only to confirm the model can generate.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        print(f"FAIL: required package not available: {exc}", file=sys.stderr)
        return 1

    try:
        tokenizer = AutoTokenizer.from_pretrained(args.base_model)
        base_model = AutoModelForCausalLM.from_pretrained(
            args.base_model,
            torch_dtype=torch.bfloat16,
        )
        model = PeftModel.from_pretrained(base_model, args.adapter_dir)
        model.eval()

        inputs = tokenizer(args.smoke_prompt, return_tensors="pt")
        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=8)
        completion = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    except Exception as exc:  # noqa: BLE001 - this script's job is to catch and report
        print(f"FAIL: adapter did not load or generate: {exc}", file=sys.stderr)
        return 1

    print("OK: adapter loaded and produced a completion")
    print(f"smoke completion: {completion!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
