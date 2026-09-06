"""A chat reply could assert any number, because prose has no store behind it the way a rendered screen does.

These tests hold the honesty boundary from both sides: a number a tool really returned survives and carries
the ledger row that admitted it, and a number the model invented does not reach the caller at all. They run
against a scripted fake model, because a guarantee that only holds when a particular endpoint is up is not a
guarantee.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pravrudhi.api.chat import build_chat_router
from pravrudhi.api.server import create_app
from pravrudhi.application.chat import TOOL_NAMES, converse
from pravrudhi.application.memory_store import FileMemoryStore
from pravrudhi.application.objectives import Benchmark, Objective, progress, write
from pravrudhi_kernel.ledger import LedgerWriter

OBJECTIVE = Objective(
    id="legal-intent",
    intent="Answer questions of law with the statute relied on.",
    track="nyaya",
    benchmarks=(Benchmark(id="law", tool="lm-eval", metric="law acc,none"),),
)


class FakeModel:
    """A scripted `Complete`: one canned answer per round, and a record of what it was shown."""

    def __init__(self, *script: dict[str, Any]) -> None:
        self.script = list(script)
        self.seen: list[list[dict[str, str]]] = []

    def __call__(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        self.seen.append(list(messages))
        return self.script.pop(0) if self.script else {"content": "", "tool_calls": []}


def _measured_workspace(root: Path) -> Path:
    """An objective with a baseline and one candidate scored against it, admitted as external-eval rows."""
    write(root, OBJECTIVE)
    ledger = root / "research" / "ledger.jsonl"
    writer = LedgerWriter.open(ledger, "0.1.0")
    for condition, value in (("base", 0.4), ("candidate", 0.5)):
        writer.append(
            "audit",
            "auditor",
            {
                "kind": "external_eval",
                "severity": "info",
                "tier": "external",
                "track": OBJECTIVE.track,
                "condition": condition,
                "tool": "lm-eval",
                "metrics": {"law": {"acc,none": value, "acc_stderr,none": 0.01}},
                "n_samples": {"law": 1000},
            },
            epoch=0,
            night=1,
        )
    return ledger


def test_a_number_a_tool_returned_survives_and_cites_its_ledger_row(tmp_path: Path) -> None:
    ledger = _measured_workspace(tmp_path)
    model = FakeModel(
        {"content": "", "tool_calls": [{"tool": "objective_progress", "args": {"id": OBJECTIVE.id}}]},
        {"content": "The candidate scores 0.5 on law acc,none against a baseline of 0.4.", "tool_calls": []},
    )

    outcome = converse(tmp_path, "how is the legal objective doing?", complete=model)

    assert "0.5" in outcome.reply and "0.4" in outcome.reply
    assert outcome.refusals == ()
    (standing,) = progress(OBJECTIVE, ledger)
    assert standing.baseline is not None and standing.latest is not None
    cited = {c["seq"] for c in outcome.citations}
    assert standing.baseline.seq in cited and standing.latest.seq in cited
    assert all(c["what"].startswith("objective_progress") for c in outcome.citations)
    assert [c.tool for c in outcome.tool_calls] == ["objective_progress"]


def test_a_chat_outcomes_citations_are_stored_on_the_assistant_turn(tmp_path: Path) -> None:
    _measured_workspace(tmp_path)
    model = FakeModel(
        {"content": "", "tool_calls": [{"tool": "objective_progress", "args": {"id": OBJECTIVE.id}}]},
        {"content": "The candidate scores 0.5 on law acc,none against a baseline of 0.4.", "tool_calls": []},
    )

    outcome = converse(tmp_path, "how is the legal objective doing?", complete=model)

    stored = FileMemoryStore(tmp_path).thread(outcome.thread_id)
    user_turn, assistant_turn = stored.turns
    assert user_turn.meta == {}
    assert assistant_turn.role == "assistant"
    assert assistant_turn.meta["citations"] == [dict(c) for c in outcome.citations]
    assert assistant_turn.meta["refusals"] == list(outcome.refusals)
    assert assistant_turn.meta["tool_calls"] == [c.to_dict() for c in outcome.tool_calls]


def test_an_invented_percentage_is_stripped_and_reported(tmp_path: Path) -> None:
    _measured_workspace(tmp_path)
    model = FakeModel(
        {"content": "", "tool_calls": [{"tool": "objectives", "args": {}}]},
        {
            "content": "The harness now passes 49% of the suite. Evidence accumulates on the nyaya track.",
            "tool_calls": [],
        },
    )

    outcome = converse(tmp_path, "how good is the harness?", complete=model)

    assert "49%" not in outcome.reply
    assert "nyaya track" in outcome.reply  # the sentence that claimed nothing numeric is untouched
    assert len(outcome.refusals) == 1
    assert "49%" in outcome.refusals[0] and "no tool call in this turn returned that number" in outcome.refusals[0]


def test_remembering_a_numeric_claim_is_refused_by_the_memory_guard(tmp_path: Path) -> None:
    _measured_workspace(tmp_path)
    model = FakeModel(
        {"content": "", "tool_calls": [{"tool": "memory_remember", "args": {"text": "we reached 49% on law"}}]},
        {"content": "I did not record that.", "tool_calls": []},
    )

    outcome = converse(tmp_path, "remember that we reached 49% on law", complete=model)

    assert any("refused to remember" in r for r in outcome.refusals)
    assert FileMemoryStore(tmp_path).recall("", limit=50) == []
    assert outcome.reply == "I did not record that."


def test_an_unknown_tool_name_is_refused_not_approximated(tmp_path: Path) -> None:
    _measured_workspace(tmp_path)
    model = FakeModel(
        {"content": "", "tool_calls": [{"tool": "ledger", "args": {"night": "1"}}]},
        {"content": "I cannot read the ledger directly.", "tool_calls": []},
    )

    outcome = converse(tmp_path, "dump the ledger", complete=model)

    (call,) = outcome.tool_calls
    assert call.tool == "ledger" and "refused the tool 'ledger'" in call.result_summary
    assert any("refused the tool 'ledger'" in r for r in outcome.refusals)
    assert outcome.citations == ()
    assert "ledger" not in TOOL_NAMES


def test_a_thread_round_trips_through_the_api(tmp_path: Path) -> None:
    _measured_workspace(tmp_path)
    model = FakeModel(
        {"content": "There are objectives in this workspace.", "tool_calls": []},
        {"content": "The second answer.", "tool_calls": []},
    )
    app = FastAPI()
    app.include_router(build_chat_router(tmp_path, complete=model))
    client = TestClient(app)

    first = client.post("/api/chat", json={"message": "hello", "thread_id": None}).json()
    thread_id = first["thread_id"]
    assert first["reply"] == "There are objectives in this workspace."

    second = client.post("/api/chat", json={"message": "and again", "thread_id": thread_id}).json()
    assert second["thread_id"] == thread_id
    assert any(m["content"] == "hello" for m in model.seen[-1])  # the second turn saw the first

    listing = client.get("/api/chat/threads").json()
    assert [t["id"] for t in listing["threads"]] == [thread_id]
    assert listing["threads"][0]["turns"] == 4 and listing["threads"][0]["updated"]

    detail = client.get(f"/api/chat/threads/{thread_id}").json()
    assert detail["id"] == thread_id
    assert [t["role"] for t in detail["turns"]] == ["user", "assistant", "user", "assistant"]
    assert detail["turns"][0]["content"] == "hello" and detail["turns"][0]["created"]
    assert client.get("/api/chat/threads/t-nothing").status_code == 404
    assert client.post("/api/chat", json={"message": "   ", "thread_id": None}).status_code == 422


def test_the_engine_serves_the_chat_routes(tmp_path: Path) -> None:
    paths = set(create_app(tmp_path).openapi()["paths"])
    assert {"/api/chat", "/api/chat/threads", "/api/chat/threads/{thread_id}"} <= paths
