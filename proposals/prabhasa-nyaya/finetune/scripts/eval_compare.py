#!/usr/bin/env python
"""Second half of the finetune step's success criterion: compare the
finetune_candidate adapter against the frozen base_model baseline on a
held-out domain set and a held-out retention set.

Domain set format (JSONL): {"prompt": <question + linearized graph context>,
"valid_citations": [<node ids allowed by the prompt's graph context>],
"expect_abstain": <bool>}

Retention set format (JSONL): {"text": <a passage from a general-purpose,
non-legal held-out corpus>} -- used to compute perplexity as a coarse
regression check, since the intent is only to catch the adapter breaking
general capability, not to fully re-benchmark it.

This script prints a comparison table. It does not decide pass/fail --
that judgment belongs to the gates step, not to this proposal.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base_model", required=True, help="Path or hub id of the base model.")
    parser.add_argument(
        "--adapter_dir",
        required=True,
        help="Path to the finetune_candidate adapter directory to evaluate.",
    )
    parser.add_argument(
        "--domain_eval_set",
        required=True,
        help="Path to the held-out domain eval JSONL (see module docstring for format).",
    )
    parser.add_argument(
        "--retention_eval_set",
        required=True,
        help="Path to the held-out retention eval JSONL (see module docstring for format).",
    )
    parser.add_argument(
        "--abstain_marker",
        default="insufficient basis in the provided graph",
        help="Substring that marks an abstention in a generated completion.",
    )
    parser.add_argument("--max_new_tokens", type=int, default=256)
    return parser.parse_args()


def read_jsonl(path: str) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


@dataclass
class DomainScore:
    citation_exactness: float
    abstention_accuracy: float
    n_examples: int


@dataclass
class RetentionScore:
    perplexity: float
    n_examples: int


def extract_citations(text: str) -> set[str]:
    # Node ids are expected in the linearized graph format used by the
    # corpus-prep step, e.g. "[[node:statute:ipc-420]]". Adjust this pattern
    # if that format changes upstream.
    return set(re.findall(r"\[\[node:[^\]]+\]\]", text))


def score_domain(model, tokenizer, examples: list[dict], abstain_marker: str, max_new_tokens: int) -> DomainScore:
    import torch

    correct_citations = 0
    total_citations = 0
    correct_abstentions = 0

    for example in examples:
        inputs = tokenizer(example["prompt"], return_tensors="pt")
        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)
        completion = tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )

        abstained = abstain_marker in completion.lower()
        if example.get("expect_abstain", False):
            correct_abstentions += int(abstained)
        elif not abstained:
            cited = extract_citations(completion)
            valid = set(example.get("valid_citations", []))
            total_citations += max(len(cited), 1)
            correct_citations += len(cited & valid)

    n = len(examples)
    citation_exactness = (correct_citations / total_citations) if total_citations else 0.0
    n_abstain_expected = sum(1 for e in examples if e.get("expect_abstain", False))
    abstention_accuracy = (correct_abstentions / n_abstain_expected) if n_abstain_expected else 0.0
    return DomainScore(citation_exactness=citation_exactness, abstention_accuracy=abstention_accuracy, n_examples=n)


def score_retention(model, tokenizer, examples: list[dict]) -> RetentionScore:
    import torch

    total_loss = 0.0
    total_tokens = 0
    for example in examples:
        inputs = tokenizer(example["text"], return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs, labels=inputs["input_ids"])
        n_tokens = inputs["input_ids"].shape[1]
        total_loss += outputs.loss.item() * n_tokens
        total_tokens += n_tokens

    import math

    perplexity = math.exp(total_loss / total_tokens) if total_tokens else float("inf")
    return RetentionScore(perplexity=perplexity, n_examples=len(examples))


def load_models(base_model: str, adapter_dir: str | None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=torch.bfloat16)

    if adapter_dir is not None:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter_dir)

    model.eval()
    return model, tokenizer


def main() -> None:
    args = parse_args()
    domain_examples = read_jsonl(args.domain_eval_set)
    retention_examples = read_jsonl(args.retention_eval_set)

    results = {}
    for label, adapter_dir in (("baseline", None), ("finetune_candidate", args.adapter_dir)):
        model, tokenizer = load_models(args.base_model, adapter_dir)
        domain_score = score_domain(
            model, tokenizer, domain_examples, args.abstain_marker, args.max_new_tokens
        )
        retention_score = score_retention(model, tokenizer, retention_examples)
        results[label] = (domain_score, retention_score)

    print(f"{'metric':<28}{'baseline':>15}{'finetune_candidate':>22}")
    base_domain, base_retention = results["baseline"]
    cand_domain, cand_retention = results["finetune_candidate"]
    print(f"{'domain citation-exactness':<28}{base_domain.citation_exactness:>15.3f}{cand_domain.citation_exactness:>22.3f}")
    print(f"{'domain abstention-accuracy':<28}{base_domain.abstention_accuracy:>15.3f}{cand_domain.abstention_accuracy:>22.3f}")
    print(f"{'retention perplexity':<28}{base_retention.perplexity:>15.3f}{cand_retention.perplexity:>22.3f}")
    print(f"\n(n_domain={base_domain.n_examples}, n_retention={base_retention.n_examples})")
    print(
        "\nThese are eval outputs from an actual run when executed; "
        "this script does not itself judge pass/fail."
    )


if __name__ == "__main__":
    main()
