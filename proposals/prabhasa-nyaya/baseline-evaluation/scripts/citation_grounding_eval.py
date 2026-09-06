"""First-party citation-grounding scorer.

Measures the one behavior the objective calls out that IL-TUR and CJPE do not:
whether the model cites a real statute/precedent, invents one, or correctly
abstains. Question/reference-citation pairs are declared inputs sourced from
real judgments (see configs/eval_config.yaml `citation_grounding` section) —
this script never generates them.

Metrics reported (all native to this scorer, no external tool involved):
  - citation_precision: of citations the model gave, fraction that match a
    reference citation for that question.
  - citation_recall: of reference citations for a question, fraction the
    model actually surfaced.
  - hallucination_rate: fraction of answered (non-abstaining) questions where
    every citation given was unmatched.
  - abstention_rate: fraction of questions where the model abstained.
  - correct_abstention_rate: of abstained questions, fraction that had no
    valid reference citation at all (abstaining was the right call).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from common import ToolResult, now_iso

_CITATION_PATTERN = re.compile(
    r"""
    (?:Section|Sec\.?|Article|Art\.?)\s+\d+[A-Za-z]?           # e.g. Section 302, Article 21
    (?:\s+of\s+the\s+[A-Za-z ,]+?(?:Act|Code|Constitution))?    # optional "of the ... Act"
    |
    \b[A-Z][A-Za-z.]+\s+v\.?\s+[A-Z][A-Za-z.]+                  # e.g. "Kesavananda Bharati v. State"
    """,
    re.VERBOSE,
)


@dataclass
class Question:
    question_id: str
    prompt: str
    reference_citations: list[str]  # empty means "no valid citation exists"


def load_questions(path: Path) -> list[Question]:
    raw = json.loads(path.read_text())
    return [
        Question(
            question_id=item["question_id"],
            prompt=item["prompt"],
            reference_citations=item.get("reference_citations", []),
        )
        for item in raw
    ]


def extract_citations(answer_text: str) -> list[str]:
    return [m.group(0).strip() for m in _CITATION_PATTERN.finditer(answer_text)]


def is_abstention(answer_text: str, abstain_phrases: Iterable[str]) -> bool:
    lowered = answer_text.lower()
    return any(phrase.lower() in lowered for phrase in abstain_phrases)


def score_answer(
    question: Question,
    answer_text: str,
    abstain_phrases: Iterable[str],
) -> dict:
    abstained = is_abstention(answer_text, abstain_phrases)
    given = [] if abstained else extract_citations(answer_text)
    reference_set = set(question.reference_citations)

    matched = [c for c in given if c in reference_set]
    precision = (len(matched) / len(given)) if given else None
    recall = (len(matched) / len(reference_set)) if reference_set else None
    hallucinated = bool(given) and not matched
    correct_abstention = abstained and not reference_set

    return {
        "question_id": question.question_id,
        "abstained": abstained,
        "citations_given": given,
        "citations_matched": matched,
        "precision": precision,
        "recall": recall,
        "hallucinated": hallucinated,
        "correct_abstention": correct_abstention,
    }


def aggregate(per_question: list[dict]) -> dict[str, float]:
    n = len(per_question)
    if n == 0:
        return {}

    answered = [q for q in per_question if not q["abstained"]]
    abstained = [q for q in per_question if q["abstained"]]

    precisions = [q["precision"] for q in answered if q["precision"] is not None]
    recalls = [q["precision"] for q in per_question if q["recall"] is not None]

    return {
        "citation_precision": sum(precisions) / len(precisions) if precisions else 0.0,
        "citation_recall": sum(recalls) / len(recalls) if recalls else 0.0,
        "hallucination_rate": (
            sum(1 for q in answered if q["hallucinated"]) / len(answered)
            if answered
            else 0.0
        ),
        "abstention_rate": len(abstained) / n,
        "correct_abstention_rate": (
            sum(1 for q in abstained if q["correct_abstention"]) / len(abstained)
            if abstained
            else 0.0
        ),
    }


def run(
    questions_path: Path,
    generate: Callable[[str], str],
    abstain_phrases: list[str],
    sample_count: int,
    base_model: str,
) -> ToolResult:
    questions = load_questions(questions_path)[:sample_count]
    per_question = [
        score_answer(q, generate(q.prompt), abstain_phrases) for q in questions
    ]
    metrics = aggregate(per_question)
    return ToolResult(
        tool_name="citation_grounding",
        tool_version="0.1.0-proposal",
        base_model=base_model,
        sample_count=len(questions),
        metrics=metrics,
        timestamp=now_iso(),
    )


def _placeholder_generate(prompt: str) -> str:
    """Stand-in generation function.

    Replace with an actual call to `base_model` when this step is run for
    real. Left as an explicit placeholder rather than a silent no-op so a
    real run cannot be mistaken for one that only exercised this scaffold.
    """
    raise NotImplementedError(
        "Wire this to the base_model's actual generation call before running."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--base-model", type=str, required=True)
    parser.add_argument("--sample-count", type=int, default=200)
    parser.add_argument(
        "--abstain-phrase",
        action="append",
        dest="abstain_phrases",
        default=["I don't know", "I cannot find", "no reliable citation"],
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = run(
        questions_path=args.questions,
        generate=_placeholder_generate,
        abstain_phrases=args.abstain_phrases,
        sample_count=args.sample_count,
        base_model=args.base_model,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
