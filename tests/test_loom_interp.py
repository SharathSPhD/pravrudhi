"""Milestone 1 gave Loom pretraining and evaluation; nothing in it could name a feature, a monitor, or a control.

These tests hold the milestone 2 interpretation terms -- `feature`/`circuit`/`monitor`/`control` decls, the
install/amplify/suppress/read verbs, and `assert` on a monitor's member -- to the same standard as milestone 1:
the weave demo's own monitor and control must parse as hand-written Loom, a monitor's gate must round-trip
through `interpretation_terms` and `lower_interpretation`, and an unspecified threshold must render as a
comment, never a guessed number.
"""

from __future__ import annotations

from pravrudhi.application import loom

# demo_loom.weave.yaml's monitor (belief_state_monitor, probe_r2 > 0.9) and control (suppress_token_1, kind
# suppress, strength 1.0, gated by suppression_ratio > 0.9 and side_effect < 0.1), written by hand in Loom.
WEAVE_DEMO_LOOM = """\
// demo_loom -- belief-state monitor and a token-suppression control, built from nothing.

feature belief_state = std.features.belief_state;
feature token_1 = std.features.token_1;

monitor belief_state_monitor = read(std.features.belief_state);
assert belief_state_monitor.probe_r2 > 0.9;

control suppress_token_1 = suppress(std.features.token_1) {
    strength = 1.0;
};
assert suppression_ratio(suppress_token_1) > 0.9;
assert side_effect(suppress_token_1) < 0.1;
"""


def test_weave_demo_monitor_and_control_parse() -> None:
    program = loom.lift(WEAVE_DEMO_LOOM)
    kinds = [type(s).__name__ for s in program.stmts]
    assert kinds == [
        "Decl", "Decl", "Decl", "Assert", "Decl", "Assert", "Assert",
    ]
    monitor_decl = program.stmts[2]
    assert isinstance(monitor_decl, loom.Decl)
    assert monitor_decl.type_ == "monitor"
    assert isinstance(monitor_decl.value, loom.Call)
    assert isinstance(monitor_decl.value.callee, loom.Ident)
    assert monitor_decl.value.callee.name == "read"

    control_decl = program.stmts[4]
    assert isinstance(control_decl, loom.Decl)
    assert control_decl.type_ == "control"
    assert isinstance(control_decl.value, loom.Call)
    assert isinstance(control_decl.value.callee, loom.Ident)
    assert control_decl.value.callee.name == "suppress"


def test_assert_on_monitor_member_parses() -> None:
    program = loom.lift(WEAVE_DEMO_LOOM)
    monitor_assert = program.stmts[3]
    assert isinstance(monitor_assert, loom.Assert)
    assert isinstance(monitor_assert.left, loom.Member)
    assert monitor_assert.left.name == "probe_r2"
    assert isinstance(monitor_assert.left.target, loom.Ident)
    assert monitor_assert.left.target.name == "belief_state_monitor"
    assert monitor_assert.op == ">"


def test_interpretation_terms_recovers_weave_demo() -> None:
    program = loom.lift(WEAVE_DEMO_LOOM)
    terms = loom.interpretation_terms(program)

    features = [t for t in terms if isinstance(t, loom.FeatureSpec)]
    monitors = [t for t in terms if isinstance(t, loom.MonitorSpec)]
    controls = [t for t in terms if isinstance(t, loom.ControlSpec)]

    assert {f.name for f in features} == {"belief_state", "token_1"}

    assert monitors == [loom.MonitorSpec(name="belief_state_monitor", feature="belief_state", threshold=0.9)]

    assert controls == [
        loom.ControlSpec(
            name="suppress_token_1",
            feature="token_1",
            kind="suppress",
            strength=1.0,
            gates=(
                loom.GateSpec(metric="suppression_ratio", op=">", threshold=0.9),
                loom.GateSpec(metric="side_effect", op="<", threshold=0.1),
            ),
        )
    ]


def test_monitor_assert_round_trips() -> None:
    spec = loom.MonitorSpec(name="belief", feature="belief_state", threshold=0.9)
    source = loom.lower_interpretation([spec])
    assert "assert belief.probe_r2 > 0.9;" in source

    program = loom.lift(source)
    recovered = loom.interpretation_terms(program)
    assert recovered == (spec,)


def test_unspecified_threshold_renders_as_comment_not_a_number() -> None:
    spec = loom.MonitorSpec(name="belief", feature="belief_state", threshold=None)
    source = loom.lower_interpretation([spec])

    assert "// belief.probe_r2 threshold unspecified" in source
    assert "assert belief.probe_r2" not in source
    for line in source.splitlines():
        if "probe_r2" in line:
            assert line.strip().startswith("//")

    program = loom.lift(source)
    recovered = loom.interpretation_terms(program)
    assert recovered == (spec,)


def test_unspecified_control_strength_and_gate_render_as_comments() -> None:
    spec = loom.ControlSpec(
        name="suppress_token_1",
        feature="token_1",
        kind="suppress",
        strength=None,
        gates=(loom.GateSpec(metric="suppression_ratio", op=">", threshold=None),),
    )
    source = loom.lower_interpretation([spec])

    assert "// strength unspecified" in source
    assert "strength =" not in source
    assert "// suppression_ratio(suppress_token_1) > threshold unspecified" in source
    assert "assert suppression_ratio" not in source
