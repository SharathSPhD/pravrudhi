"""Reward function for RL post-training on grade-school arithmetic word problems.

Rule-based and verifiable on purpose: no learned reward model, no LLM judge.
The only way to score well is to produce the correct final numeric answer in
the expected format. Kept import-light and dependency-free so it can be
unit-tested (--self-test) without a GPU or any RL framework installed, and so
train_rl.py and reward_audit.py can both import the same function and never
drift apart.

Convention follows GSM8K: gold answers and model completions both end with a
line of the form "#### <number>".
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

_ANSWER_TAG_RE = re.compile(r"####\s*([\-+]?[\d,]*\.?\d+)")
_NUMERIC_CLEAN_RE = re.compile(r"[,$\s]")

FORMAT_REWARD = 0.1
CORRECTNESS_REWARD = 1.0


def extract_final_answer(text: str) -> float | None:
    """Pull the number after the last '####' marker out of `text`.

    Returns None if there is no such marker or the captured text is not a
    parseable number. Tolerates commas, a leading '$', and a trailing '.0'.
    """
    matches = _ANSWER_TAG_RE.findall(text)
    if not matches:
        return None
    raw = matches[-1]
    cleaned = _NUMERIC_CLEAN_RE.sub("", raw)
    try:
        return float(cleaned)
    except ValueError:
        return None


def has_single_well_formed_tag(text: str) -> bool:
    matches = _ANSWER_TAG_RE.findall(text)
    return len(matches) == 1 and extract_final_answer(text) is not None


@dataclass
class RewardBreakdown:
    correctness: float
    format: float

    @property
    def total(self) -> float:
        return self.correctness + self.format


def compute_reward(completion: str, gold_answer: str | float) -> RewardBreakdown:
    """Score one completion against the gold answer for one prompt.

    `gold_answer` may be a raw gold string (itself possibly containing a
    '#### <number>' tail, as in GSM8K) or a bare number.
    """
    gold_value = (
        extract_final_answer(f"#### {gold_answer}")
        if not isinstance(gold_answer, (int, float))
        else float(gold_answer)
    )
    well_formed = has_single_well_formed_tag(completion)
    predicted_value = extract_final_answer(completion) if well_formed else None

    # Correctness requires exactly one '####' tag: a completion with two or
    # more (e.g. repeating a lucky guess) is a degenerate pattern, not a
    # solved problem, and must not score as if it were.
    correctness = 0.0
    if well_formed and gold_value is not None and predicted_value is not None:
        if abs(predicted_value - gold_value) < 1e-6:
            correctness = CORRECTNESS_REWARD

    format_score = FORMAT_REWARD if well_formed else 0.0
    return RewardBreakdown(correctness=correctness, format=format_score)


def reward_fn(completions: list[str], gold_answers: list[str], **_) -> list[float]:
    """TRL-style batched reward function: list of completions in, list of scalars out."""
    return [
        compute_reward(completion, gold).total
        for completion, gold in zip(completions, gold_answers)
    ]


def _self_test() -> None:
    cases = [
        ("She has 3 apples.\n#### 3", "3", 1.1),
        ("The total is #### 42.0", "#### 42", 1.1),
        ("Roughly $1,200 in total.\n#### 1,200", "1200", 1.1),
        ("I think the answer is 5.", "5", 0.0),  # no tag at all -> no reward
        ("#### 4", "5", 0.1),  # well-formed but wrong -> format only
        ("#### 4 and also #### 4", "4", 0.0),  # two tags -> format check fails
    ]
    failures = []
    for completion, gold, expected_total in cases:
        result = compute_reward(completion, gold)
        if abs(result.total - expected_total) > 1e-9:
            failures.append((completion, gold, expected_total, result))
    if failures:
        for completion, gold, expected_total, result in failures:
            print(
                f"FAIL: completion={completion!r} gold={gold!r} "
                f"expected={expected_total} got={result.total} "
                f"(correctness={result.correctness}, format={result.format})"
            )
        raise SystemExit(1)
    print(f"reward.py self-test: {len(cases)} cases passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        _self_test()
    else:
        parser.print_help()
