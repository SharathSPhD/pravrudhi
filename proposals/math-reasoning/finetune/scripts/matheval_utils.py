"""Shared helpers for the sft-lora finetune proposal scripts.

Kept dependency-light (stdlib + yaml) so it can be imported by the
training script and both eval scripts without pulling in torch/transformers
just to load a config or score an answer.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

_NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")


@dataclass
class Example:
    prompt: str
    reference: str


def load_config(config_path: str | Path) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_jsonl_examples(
    paths: Iterable[str] | str,
    prompt_field: str = "question",
    answer_field: str = "answer",
) -> list[Example]:
    """Load one or more JSONL files into a flat list of (prompt, reference)."""
    if isinstance(paths, (str, Path)):
        paths = [paths]

    examples: list[Example] = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                examples.append(
                    Example(
                        prompt=str(row[prompt_field]),
                        reference=str(row[answer_field]),
                    )
                )
    return examples


def format_example(example: Example) -> str:
    """Render an Example as a single instruction-style prompt string.

    This is the one place to adjust if prepared_corpus turns out to use a
    chat-turns schema instead of flat question/answer fields.
    """
    return f"Question: {example.prompt}\nAnswer:"


def extract_final_number(text: str) -> str | None:
    """Pull the last number-looking token out of free-form model output.

    Grade-school arithmetic word problem answers conventionally end in a
    single final numeric value (GSM8K-style "#### <n>" or a trailing
    number in prose); this is a permissive fallback extractor for
    whatever format the actual base model/adapter produces.
    """
    if "####" in text:
        text = text.split("####")[-1]
    matches = _NUMBER_RE.findall(text)
    if not matches:
        return None
    return matches[-1].replace(",", "")


def is_correct(prediction: str, reference: str) -> bool:
    pred_num = extract_final_number(prediction)
    ref_num = extract_final_number(reference)
    if pred_num is None or ref_num is None:
        return prediction.strip() == reference.strip()
    try:
        return float(pred_num) == float(ref_num)
    except ValueError:
        return pred_num == ref_num


def accuracy(predictions: list[str], references: list[str]) -> float:
    if not predictions:
        return 0.0
    correct = sum(
        1 for pred, ref in zip(predictions, references) if is_correct(pred, ref)
    )
    return correct / len(predictions)
