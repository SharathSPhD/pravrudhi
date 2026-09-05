"""propose_generic must use the prompt file and grammar it is handed (the harness track passes its own)."""
from pathlib import Path

from pravrudhi.application import propose as P


def test_propose_generic_uses_given_prompt_and_grammar(tmp_path, monkeypatch):
    prompts = tmp_path / "harness" / "prompts" / "x"
    prompts.mkdir(parents=True)
    (prompts / "v9.md").write_text("MARK {model} {grammar} {state_summary} {k} {incumbent_strategy} {rethink_note}")
    seen = {}

    class Client:
        def chat(self, messages, **kw):
            seen["prompt"] = messages[0]["content"]

            class R:
                text = "[]"
                prompt_tokens = completion_tokens = 0
                wall_s = 0.0
                model = "m"
                finish_reason = "stop"

            return R()

    class W:
        def append(self, *a, **k):
            return None

    monkeypatch.setattr(P, "ledger_summary", lambda *a, **k: ("S", "none", 0))
    out = P.propose_generic(
        tmp_path, W(), Client(), night=1, k=2, model="M", bucket={}, prompts_dir=prompts.parent, sealed_dir=tmp_path,
        incumbent_id="c-0000", sigma_seed=0.01, temperature=0.5, max_tokens=10, rethink_m=3, log=lambda *a: None,
        grammar_doc="GRAMMAR-H", prompt_file="x/v9.md",
    )
    assert out == []
    assert seen["prompt"].startswith("MARK M GRAMMAR-H")


def test_extract_salvages_truncated_array():
    text = '<think>x</think>\n[\n{"a": 1, "s": "q]"},\n{"a": 2},\n{"a": 3, "s": "unfinished'
    assert P._extract_json_array(text) == [{"a": 1, "s": "q]"}, {"a": 2}]
    assert P._extract_json_array('[{"a": 1}]') == [{"a": 1}]


def test_extract_skips_malformed_objects_and_bad_escapes():
    text = (
        '[\n{"a": 1, "template": "Solve {question}", "s": "the problem\\\'s"},\n'
        '{"a": 2, "b": 2, "c": "unterminated,\n{"a": 3, "b": 3, "c": "ok"}'
    )
    out = P._extract_json_array(text)
    assert out[0]["s"] == "the problem's" and out[0]["template"] == "Solve {question}"
    assert out[-1] == {"a": 3, "b": 3, "c": "ok"}
