#!/usr/bin/env python3
"""Fetch raw problems for each source in config/sources.yaml.

Writes one JSONL file per source under --out, named `<source_id>.jsonl`,
with rows `{"item_id", "split", "question", "answer"}`. This is a runnable
scaffold against the Hugging Face datasets named in sources.yaml, not a
record of documents already fetched - see README.md "Explicit non-goals".

Requires the `datasets` and `pyyaml` packages (scripts/requirements.txt);
neither is installed as part of this proposal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from datasets import load_dataset  # extra dependency, not vendored here

from common import classify_topic, normalize_text


def fetch_one_split(hf_dataset: str, hf_config: str | None, split: str):
    if split is None:
        return []
    if hf_config:
        return load_dataset(hf_dataset, hf_config, split=split)
    return load_dataset(hf_dataset, split=split)


def field_filter(source_id: str, row: dict) -> bool:
    """Per-source inclusion filter applied before a row is written out.

    Only ASDiv needs this today: it mixes arithmetic, algebra and geometry
    items under one split, and only the arithmetic/elementary subset is in
    scope for this corpus (see sources.yaml `asdiv` description).
    """
    if source_id == "asdiv":
        problem_type = str(row.get("type", "")).lower()
        grade = row.get("grade")
        return "arithmetic" in problem_type or ("+" in problem_type or "-" in problem_type) and (
            grade is None or int(grade) <= 6
        )
    return True


def extract_question_answer(source_id: str, row: dict) -> tuple[str, str]:
    """Map each source's native column names to (question, answer) text."""
    if source_id == "gsm8k":
        return row["question"], row["answer"]
    if source_id == "asdiv":
        body = row.get("body", "")
        question = row.get("question", "")
        return f"{body} {question}".strip(), str(row.get("answer", ""))
    if source_id == "svamp":
        body = row.get("Body", "")
        question = row.get("Question", "")
        return f"{body} {question}".strip(), str(row.get("Answer", ""))
    if source_id == "mawps":
        return row.get("question", row.get("Question", "")), str(
            row.get("answer", row.get("Answer", ""))
        )
    raise ValueError(f"no question/answer mapping registered for source_id={source_id!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)

    for source in config["sources"]:
        source_id = source["source_id"]
        out_path = args.out / f"{source_id}.jsonl"
        rows_written = 0
        with out_path.open("w", encoding="utf-8") as handle:
            for split_key in ("train_split", "heldout_split"):
                split = source.get(split_key)
                if not split:
                    continue
                dataset = fetch_one_split(source["hf_dataset"], source.get("hf_config"), split)
                for i, row in enumerate(dataset):
                    if not field_filter(source_id, row):
                        continue
                    question, answer = extract_question_answer(source_id, row)
                    if not normalize_text(question):
                        continue
                    handle.write(
                        json.dumps(
                            {
                                "item_id": f"{source_id}-{split}-{i:06d}",
                                "split": split,
                                "question": question,
                                "answer": answer,
                            },
                            sort_keys=True,
                        )
                    )
                    handle.write("\n")
                    rows_written += 1
        print(f"{source_id}: wrote {rows_written} rows to {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
