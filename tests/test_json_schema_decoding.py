"""Schema-constrained proposer decoding: the request carries the schema; the harness schema is grammar-friendly."""
import json
from unittest import mock

from pravrudhi.models.openai_compat import ChatClient
from pravrudhi.targets.harness_grammar import HarnessRecipe, harness_array_schema


def test_chat_sends_json_schema_response_format():
    c = ChatClient("http://x/v1", model="m")
    captured = {}

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "[]"}, "finish_reason": "stop"}], "usage": {}}).encode()

    def fake_open(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return Resp()

    with mock.patch("urllib.request.urlopen", fake_open):
        r = c.chat([{"role": "user", "content": "hi"}], json_schema={"type": "array"})
    assert r.text == "[]" and r.finish_reason == "stop"
    assert captured["body"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "out", "schema": {"type": "array"}},
    }
    assert captured["body"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_harness_array_schema_is_closed_and_bounded():
    s = harness_array_schema(8)
    assert s["minItems"] == s["maxItems"] == 8
    item = s["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(HarnessRecipe.model_json_schema()["properties"])
    assert item["properties"]["strategy"]["enum"] == ["prompt_only", "retry_policy", "sampling_policy"]
    assert "maximum" not in item["properties"]["retries"] and item["properties"]["retries"]["type"] == "integer"


def test_harness_template_placeholders_are_validated():
    from pravrudhi.targets.harness_grammar import parse_harness

    base = {"strategy": "prompt_only", "execution_family": "template"}
    ok = parse_harness({**base, "template": "Task:\n{question}\nReturn one ```python block."})
    assert not isinstance(ok, str)
    bad = parse_harness({**base, "template": "Solve {question}\nExample: assert {example}"})
    assert isinstance(bad, str) and "unsupported placeholders" in bad
    missing = parse_harness({**base, "template": "Write the function in one block."})
    assert isinstance(missing, str) and "{question}" in missing
    fb = parse_harness({**base, "feedback_template": "Try again."})
    assert isinstance(fb, str) and "{feedback}" in fb
