"""A plan and a source file could drift the moment either was edited by hand, with nothing to notice.

These tests hold the Loom parser and the intent<->source round trip to that: the grammar's own example must
parse, unit-suffixed numbers must resolve to the magnitude they name, a malformed program must fail at a
reported line and column, and every shipped objective's compiled plan must survive lower -> lift -> to_plan_steps
with its capability order intact and no invented quantity ever standing in for a number the plan never had.
"""

from __future__ import annotations

import pytest

from pravrudhi.application import intent, loom, objectives, recipes

SMALLTALK_LOOM = """\
// smalltalk.loom -- a small conversational model, built from nothing.

target arch = decoder(layers=12, width=768, heads=12, ctx=1024);

corpus speech = data.text("babylm:childes") + data.text("babylm:switchboard");
corpus prose  = data.text("babylm:simple_wiki").filter(len > 64);
corpus mix    = speech * 0.7 + prose * 0.3;

tokenizer tk = tokenizer.bpe(mix, vocab=16000);

model m = pretrain(arch, mix, tk) {
    tokens    = 800M;
    optimizer = adamw(lr=6e-4, wd=0.1);
    schedule  = cosine(warmup=2%);
};

assert perplexity(m, mix.heldout) < 60;      // measured, or the build fails

m = finetune(m, data.chat("dialogues.jsonl")) {
    epochs = 2;
    lr     = 2e-5;
};

m = align(m, data.prefs("preferences.jsonl")) {
    algo = dpo;
    beta = 0.1;
};

assert winrate(m, baseline=m.before_align) > 0.55;

export m to "smalltalk-v1";
"""


def test_language_example_parses() -> None:
    program = loom.lift(SMALLTALK_LOOM)
    assert len(program.stmts) == 11
    kinds = [type(s).__name__ for s in program.stmts]
    assert kinds == [
        "Decl", "Decl", "Decl", "Decl", "Decl", "Decl", "Assert", "Assign", "Assign", "Assert", "Export",
    ]


def test_language_example_corpus_algebra_and_member_access() -> None:
    program = loom.lift(SMALLTALK_LOOM)
    mix_decl = program.stmts[3]
    assert isinstance(mix_decl, loom.Decl)
    assert isinstance(mix_decl.value, loom.BinOp)
    assert mix_decl.value.op == "+"

    prose_decl = program.stmts[2]
    assert isinstance(prose_decl, loom.Decl)
    assert isinstance(prose_decl.value, loom.Call)
    assert isinstance(prose_decl.value.callee, loom.Member)
    assert prose_decl.value.callee.name == "filter"

    assert_stmt = program.stmts[9]
    assert isinstance(assert_stmt, loom.Assert)
    assert assert_stmt.op == ">"
    winrate_call = assert_stmt.left
    assert isinstance(winrate_call, loom.Call)
    baseline_arg = winrate_call.args[1]
    assert baseline_arg.name == "baseline"
    assert isinstance(baseline_arg.value, loom.Member)
    assert baseline_arg.value.name == "before_align"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("800M", 800_000_000.0),
        ("1.5B", 1_500_000_000.0),
        ("2%", 0.02),
        ("3e-4", 0.0003),
        ("0.7", 0.7),
        ("16000", 16000.0),
    ],
)
def test_number_units_parse_to_right_magnitude(text: str, expected: float) -> None:
    program = loom.lift(f"unit x = {text};")
    decl = program.stmts[0]
    assert isinstance(decl, loom.Decl)
    assert isinstance(decl.value, loom.NumberLit)
    assert decl.value.value == pytest.approx(expected)


def test_parse_error_reports_line_and_column() -> None:
    source = "target arch = decoder(layers=12);\ncorpus mix = data.text(\"x\")\n"  # missing ';'
    with pytest.raises(loom.ParseError) as exc_info:
        loom.lift(source)
    assert exc_info.value.line == 3
    assert exc_info.value.col == 1


def test_parse_error_on_unknown_character() -> None:
    with pytest.raises(loom.ParseError) as exc_info:
        loom.lift("target arch = decoder(layers=12) $;\n")
    assert exc_info.value.line == 1
    assert exc_info.value.col == 34


def _quantity_names(plan: intent.IntentPlanProposal) -> set[str]:
    return {q.name for step in plan.steps for q in step.quantities}


@pytest.mark.parametrize("name", objectives.examples())
def test_shipped_objective_round_trips_through_loom(name: str) -> None:
    obj = objectives.load(objectives.PACKAGED_OBJECTIVES / f"{name}.yaml")
    plan = intent.compile_intent(obj, tuple(recipes.library()))

    source = loom.lower(plan)
    program = loom.lift(source)
    recovered = loom.to_plan_steps(program)

    expected = tuple(step.capability for step in plan.steps)
    assert recovered == expected

    for qname in _quantity_names(plan):
        assert f"{qname} =" not in source
        assert f"// {qname} unspecified" in source


def test_lower_never_invents_a_baseline_number() -> None:
    obj = objectives.load(objectives.PACKAGED_OBJECTIVES / "math-reasoning.yaml")
    plan = intent.compile_intent(obj, tuple(recipes.library()))
    source = loom.lower(plan)
    assert "unmeasured" in source
    assert "> baseline;" in source
