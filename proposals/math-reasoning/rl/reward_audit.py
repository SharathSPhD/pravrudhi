"""Audit the RL reward against the intent — not a benchmark of the model.

Success criterion for the `rl` step requires auditing the reward against the
intent, separately from comparing held-out results. This script samples
rollouts from a checkpoint and checks whether reward.py's score agrees with
an independently-written correctness check (`independent_is_correct` below,
deliberately not sharing code with reward.py's parser). Systematic
disagreement means the training reward was not actually measuring "solved
the problem," regardless of what the held-out numbers later show.

Usage:
    uv run python reward_audit.py --model artifacts/rl_candidate \
        --data artifacts/prepared_corpus/train.jsonl --num-samples 200
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass

from reward import compute_reward


def independent_is_correct(completion: str, gold_answer: str) -> bool | None:
    """A second, independently-written check that a completion is correct.

    Intentionally uses a different extraction strategy than reward.py
    (last standalone number in the text, rather than requiring a '####'
    marker) so the two don't share a bug. Returns None if no number can be
    found at all (treated as "not comparable", not as a disagreement).
    """
    numbers = re.findall(r"[\-+]?\d[\d,]*\.?\d*", completion)
    if not numbers:
        return None
    try:
        predicted = float(numbers[-1].replace(",", ""))
    except ValueError:
        return None
    gold_numbers = re.findall(r"[\-+]?\d[\d,]*\.?\d*", str(gold_answer))
    if not gold_numbers:
        return None
    gold = float(gold_numbers[-1].replace(",", ""))
    return abs(predicted - gold) < 1e-6


@dataclass
class AuditRow:
    question: str
    completion: str
    reward_says_correct: bool
    independent_says_correct: bool | None

    @property
    def disagrees(self) -> bool:
        if self.independent_says_correct is None:
            return False
        return self.reward_says_correct != self.independent_says_correct


def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def generate_completions(model_path: str, questions: list[str]) -> list[str]:
    """Lazy-imports transformers so this module stays importable without it."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path)

    completions = []
    for question in questions:
        prompt = (
            "Solve the following grade-school math word problem. "
            "Show your reasoning, then give the final numeric answer on its "
            "own line prefixed with '####'.\n\n"
            f"Question: {question}\nAnswer:"
        )
        inputs = tokenizer(prompt, return_tensors="pt")
        output_ids = model.generate(**inputs, max_new_tokens=256, do_sample=True)
        text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        completions.append(text[len(prompt):])
    return completions


def audit(model_path: str, data_path: str, num_samples: int) -> list[AuditRow]:
    records = load_jsonl(data_path)[:num_samples]
    questions = [r["question"] for r in records]
    gold_answers = [r["answer"] for r in records]
    completions = generate_completions(model_path, questions)

    rows = []
    for question, completion, gold in zip(questions, completions, gold_answers):
        reward_result = compute_reward(completion, gold)
        rows.append(
            AuditRow(
                question=question,
                completion=completion,
                reward_says_correct=reward_result.correctness > 0,
                independent_says_correct=independent_is_correct(completion, gold),
            )
        )
    return rows


def summarize(rows: list[AuditRow]) -> None:
    comparable = [r for r in rows if r.independent_says_correct is not None]
    disagreements = [r for r in comparable if r.disagrees]
    print(f"total sampled rollouts: {len(rows)}")
    print(f"comparable rollouts (independent check found a number): {len(comparable)}")
    print(f"reward/independent-check disagreements: {len(disagreements)}")
    if comparable:
        rate = len(disagreements) / len(comparable)
        print(f"disagreement rate: {rate:.1%}")
    for row in disagreements[:10]:
        print("---")
        print(f"question: {row.question}")
        print(f"completion: {row.completion[:300]}")
        print(
            f"reward says correct={row.reward_says_correct}, "
            f"independent check says correct={row.independent_says_correct}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--num-samples", type=int, default=200)
    args = parser.parse_args()

    rows = audit(args.model, args.data, args.num_samples)
    summarize(rows)


if __name__ == "__main__":
    main()
