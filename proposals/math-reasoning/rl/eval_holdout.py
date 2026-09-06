"""Independent held-out comparison of finetune_candidate vs rl_candidate.

This is the acceptance evidence for the `rl` step, deliberately separate from
both the training reward (reward.py) and the reward audit (reward_audit.py):
- it runs on --holdout-data, which must never have been used as an RL prompt
- it uses its own correctness check (`grade`), not reward.py's parser
- it also runs a retention probe on --retention-data to check the objective's
  "without losing what it already knew" clause, not just the arithmetic gain

Prints exact-match accuracy for both checkpoints on both datasets, plus a
paired bootstrap confidence interval on the holdout accuracy delta. Nothing
here is written to the ledger; this script only prints to stdout and is
meant to be read by a human deciding whether to accept rl_candidate.

Usage:
    uv run python eval_holdout.py \
        --baseline artifacts/finetune_candidate \
        --candidate artifacts/rl_candidate \
        --holdout-data artifacts/prepared_corpus/holdout.jsonl \
        --retention-data artifacts/retention_probe.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def grade(completion: str, gold_answer: str) -> bool:
    """Correctness check for held-out scoring.

    Independent implementation from both reward.py and reward_audit.py's
    checks: looks for a '####' tail first (preferred, matches task
    convention), falls back to the last number in the text if absent.
    """
    tagged = re.findall(r"####\s*([\-+]?[\d,]*\.?\d+)", completion)
    candidate_str = tagged[-1] if tagged else None
    if candidate_str is None:
        loose = re.findall(r"[\-+]?\d[\d,]*\.?\d*", completion)
        candidate_str = loose[-1] if loose else None
    if candidate_str is None:
        return False
    try:
        predicted = float(candidate_str.replace(",", "").replace("$", ""))
    except ValueError:
        return False

    gold_numbers = re.findall(r"[\-+]?\d[\d,]*\.?\d*", str(gold_answer))
    if not gold_numbers:
        return False
    gold = float(gold_numbers[-1].replace(",", ""))
    return abs(predicted - gold) < 1e-6


def generate_completions(model_path: str, prompts: list[str]) -> list[str]:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path)

    completions = []
    for prompt in prompts:
        inputs = tokenizer(prompt, return_tensors="pt")
        output_ids = model.generate(**inputs, max_new_tokens=256, do_sample=False)
        text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        completions.append(text[len(prompt):])
    return completions


def build_math_prompt(question: str) -> str:
    return (
        "Solve the following grade-school math word problem. "
        "Show your reasoning, then give the final numeric answer on its own "
        "line prefixed with '####'.\n\n"
        f"Question: {question}\nAnswer:"
    )


@dataclass
class ScoreResult:
    accuracy: float
    correct_flags: list[bool]


def score_model(model_path: str, records: list[dict], prompt_field: str, answer_field: str) -> ScoreResult:
    prompts = [build_math_prompt(r[prompt_field]) for r in records]
    completions = generate_completions(model_path, prompts)
    flags = [grade(c, r[answer_field]) for c, r in zip(completions, records)]
    accuracy = sum(flags) / len(flags) if flags else 0.0
    return ScoreResult(accuracy=accuracy, correct_flags=flags)


def paired_bootstrap_ci(
    baseline_flags: list[bool],
    candidate_flags: list[bool],
    num_resamples: int = 10_000,
    seed: int = 0,
) -> tuple[float, float]:
    """95% CI on (candidate accuracy - baseline accuracy) via paired bootstrap."""
    rng = random.Random(seed)
    n = len(baseline_flags)
    deltas = []
    indices = list(range(n))
    for _ in range(num_resamples):
        sample = [rng.choice(indices) for _ in range(n)]
        base_acc = sum(baseline_flags[i] for i in sample) / n
        cand_acc = sum(candidate_flags[i] for i in sample) / n
        deltas.append(cand_acc - base_acc)
    deltas.sort()
    lo = deltas[int(0.025 * num_resamples)]
    hi = deltas[int(0.975 * num_resamples)]
    return lo, hi


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="finetune_candidate path")
    parser.add_argument("--candidate", required=True, help="rl_candidate path")
    parser.add_argument("--holdout-data", required=True)
    parser.add_argument("--retention-data", required=True)
    parser.add_argument("--question-field", default="question")
    parser.add_argument("--answer-field", default="answer")
    args = parser.parse_args()

    holdout_records = load_jsonl(args.holdout_data)
    retention_records = load_jsonl(args.retention_data)

    print(f"Scoring baseline ({args.baseline}) on holdout ({len(holdout_records)} examples)...")
    baseline_holdout = score_model(args.baseline, holdout_records, args.question_field, args.answer_field)
    print(f"Scoring candidate ({args.candidate}) on holdout...")
    candidate_holdout = score_model(args.candidate, holdout_records, args.question_field, args.answer_field)

    print(f"Scoring baseline on retention probe ({len(retention_records)} examples)...")
    baseline_retention = score_model(args.baseline, retention_records, args.question_field, args.answer_field)
    print("Scoring candidate on retention probe...")
    candidate_retention = score_model(args.candidate, retention_records, args.question_field, args.answer_field)

    holdout_ci = paired_bootstrap_ci(baseline_holdout.correct_flags, candidate_holdout.correct_flags)
    retention_ci = paired_bootstrap_ci(baseline_retention.correct_flags, candidate_retention.correct_flags)

    print("\n=== Held-out arithmetic accuracy (this is the acceptance metric) ===")
    print(f"baseline (finetune_candidate): {baseline_holdout.accuracy:.3f}")
    print(f"candidate (rl_candidate):      {candidate_holdout.accuracy:.3f}")
    print(f"paired bootstrap 95% CI on delta: [{holdout_ci[0]:+.3f}, {holdout_ci[1]:+.3f}]")
    print("-> success requires this interval to exclude zero on the positive side")

    print("\n=== Retention probe accuracy (checks 'without losing what it knew') ===")
    print(f"baseline (finetune_candidate): {baseline_retention.accuracy:.3f}")
    print(f"candidate (rl_candidate):      {candidate_retention.accuracy:.3f}")
    print(f"paired bootstrap 95% CI on delta: [{retention_ci[0]:+.3f}, {retention_ci[1]:+.3f}]")
    print("-> success requires this interval to NOT exclude zero on the negative side")


if __name__ == "__main__":
    main()
