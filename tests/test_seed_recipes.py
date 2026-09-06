"""Operator-supplied harness recipes must use the same door the proposer uses: parsed by the grammar, then
admitted onto the ledger as an ordinary propose row (paired eval, boundary, prune, inbox pack are untouched).
This is what stops a recipe that only beat baseline externally from being promoted by anything but a human act.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pravrudhi.application.harness_track import _admit_seed, load_seed_recipes
from pravrudhi.targets.harness_grammar import HarnessRecipe
from pravrudhi_kernel.ledger import LedgerWriter
from pravrudhi_kernel.ledger.verify import iter_events

BUCKET = {"task_family": "mbppplus", "target_model": "Qwen/Qwen3-1.7B", "corpus": "mbppplus"}


def test_load_seed_recipes_rejects_unsupported_placeholder_naming_the_file(tmp_path: Path) -> None:
    bad = tmp_path / "aggressive-retry.json"
    bad.write_text(
        json.dumps(
            {
                "strategy": "prompt_only",
                "execution_family": "template",
                "template": "{question} also fix {bogus}",
            }
        )
    )
    with pytest.raises(ValueError) as exc:
        load_seed_recipes((bad,))
    assert str(bad) in str(exc.value)
    assert "bogus" in str(exc.value)


def test_load_seed_recipes_parses_a_valid_recipe(tmp_path: Path) -> None:
    good = tmp_path / "seed.json"
    good.write_text(
        json.dumps(
            {
                "strategy": "retry_policy",
                "execution_family": "retries",
                "retries": 2,
                "rationale": "beat baseline best-of-4 plus retry-3 on external benchmarks",
            }
        )
    )
    recipes = load_seed_recipes((good,))
    assert len(recipes) == 1
    assert isinstance(recipes[0], HarnessRecipe)
    assert recipes[0].retries == 2


def test_admit_seed_writes_a_propose_row_marked_operator_seed(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    w = LedgerWriter.open(ledger, "0.1.0")
    rec = HarnessRecipe(
        strategy="retry_policy",
        execution_family="retries",
        retries=3,
        n_samples=4,
        rationale="beat baseline best-of-4 plus retry-3 on external benchmarks",
    )
    _admit_seed(w, night=1, cid="c-0000", rec=rec, incumbent_id="c-9999", bucket=BUCKET, surface="H3.prompt")

    events = [e for e in iter_events(ledger) if e.kind == "propose"]
    assert len(events) == 1
    ev = events[0]
    assert ev.candidate_id == "c-0000"
    assert ev.surface == "H3.prompt"
    assert ev.payload["source"] == "operator-seed"
    assert ev.payload["rationale"] == rec.rationale
    assert ev.payload["recipe"] == rec.model_dump()
    assert ev.payload["strategy"] == "retry_policy"
    assert ev.payload["edit_family"] == "retries"
    assert ev.payload["lineage"] == ["c-9999"]
