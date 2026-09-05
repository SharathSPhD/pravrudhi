"""GSM8K scorer: deterministic final-answer match. Gold is the number after '####'; prediction is the last
number
in the completion (or the content of the last \\boxed{}), with commas and currency stripped."""

from __future__ import annotations

import re
from collections.abc import Mapping

NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
BOXED = re.compile(r"\\boxed\{([^{}]*)\}")
FINAL = re.compile(r"(?i)final answer\s*[:=]?\s*\$?\s*(-?\d[\d,]*(?:\.\d+)?)")


def _norm(s: str) -> str:
    s = s.strip().replace(",", "").replace("$", "").rstrip(".")
    try:
        f = float(s)
    except ValueError:
        return s
    return str(int(f)) if f == int(f) else repr(f)


def gold_answer(answer_text: str) -> str:
    if "####" not in answer_text:
        raise ValueError("gold answer lacks '####' marker")
    return _norm(answer_text.rsplit("####", 1)[1].splitlines()[0])


def extract_prediction(completion: str) -> str | None:
    m = FINAL.findall(completion)
    if m:
        return _norm(m[-1])
    b = BOXED.findall(completion)
    if b:
        nums = NUM.findall(b[-1])
        if nums:
            return _norm(nums[-1])
    nums = NUM.findall(completion)
    return _norm(nums[-1]) if nums else None


def score_item(completion: str, gold: str) -> int:
    pred = extract_prediction(completion)
    return int(pred is not None and pred == _norm(gold))


def score_completions(completions: Mapping[str, str], golds: Mapping[str, str]) -> dict[str, int]:
    """Per-item 0/1 scores keyed by item id. Missing completions score 0 (a crash is a miss, not an
    exclusion)."""
    return {i: (score_item(completions[i], g) if i in completions else 0) for i, g in golds.items()}
