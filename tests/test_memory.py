"""Tests for the memory subsystem: what belongs to the user, kept apart from the ledger."""

from __future__ import annotations

from pathlib import Path

import pytest

from pravrudhi.application.memory import (
    MemoryError,
    append_turn,
    forget,
    memory_dir,
    preferences,
    recall,
    remember,
    set_preference,
    thread,
    threads,
)


def test_remember_recall_forget_roundtrip(tmp_path: Path) -> None:
    note = remember(tmp_path, "building a legal-domain LoRA for contract review", source="user")
    assert note.text == "building a legal-domain LoRA for contract review"
    assert note.source == "user"
    assert note.created

    found = recall(tmp_path, "legal-domain")
    assert [n.id for n in found] == [note.id]

    assert forget(tmp_path, note.id) is True
    assert recall(tmp_path, "legal-domain") == []
    # forgetting a note that is no longer there is reported, not fatal
    assert forget(tmp_path, note.id) is False


def test_recall_ranks_matching_note_above_a_stale_one(tmp_path: Path) -> None:
    older = remember(tmp_path, "wants a legal-domain model", source="user")
    # a newer note that has nothing to do with the query
    newer = remember(tmp_path, "prefers the 5090 host for GPU work", source="user")

    # the older note matches the query and outranks the newer, non-matching one
    ranked = recall(tmp_path, "legal-domain")
    assert [n.id for n in ranked] == [older.id, newer.id]

    # with no query, plain recency applies: the newer note leads
    everything = recall(tmp_path, limit=10)
    assert everything[0].text == "prefers the 5090 host for GPU work"
    assert everything[-1].id == older.id


def test_numeric_claim_guard_refuses_bare_result_claims(tmp_path: Path) -> None:
    with pytest.raises(MemoryError):
        remember(tmp_path, "GSM8K is now 49%", source="assistant")
    with pytest.raises(MemoryError):
        remember(tmp_path, "the candidate reached 0.4898 on the eval", source="assistant")
    # a note is still refused for being empty, distinctly from the numeric guard
    with pytest.raises(MemoryError):
        remember(tmp_path, "   ", source="user")
    # a plain fact that happens to contain a small integer is not a results claim
    note = remember(tmp_path, "GPU budget is 8 hours per night", source="user")
    assert note.text == "GPU budget is 8 hours per night"


def test_forget_survives_a_corrupt_line(tmp_path: Path) -> None:
    good = remember(tmp_path, "targets the harness track for now", source="user")
    path = memory_dir(tmp_path) / "notes.jsonl"
    with path.open("a") as f:
        f.write("{not json\n")

    assert recall(tmp_path, "harness") != []
    assert forget(tmp_path, good.id) is True
    # the corrupt line did not resurrect or crash the store
    assert recall(tmp_path, "harness") == []


def test_preference_set_and_read_roundtrip(tmp_path: Path) -> None:
    set_preference(tmp_path, "base_model", "qwen2.5-7b", source="user")
    set_preference(tmp_path, "gpu_budget_hours", 8, source="user")
    # a later write to the same key wins, and carries fresh provenance
    updated = set_preference(tmp_path, "base_model", "qwen2.5-14b", source="user")

    prefs = preferences(tmp_path)
    assert prefs["base_model"].value == "qwen2.5-14b"
    assert prefs["base_model"].set_at == updated.set_at
    assert prefs["gpu_budget_hours"].value == 8
    assert prefs["base_model"].source == "user"


def test_preference_survives_a_corrupt_line(tmp_path: Path) -> None:
    set_preference(tmp_path, "default_track", "model", source="user")
    path = memory_dir(tmp_path) / "preferences.jsonl"
    with path.open("a") as f:
        f.write("not even json\n")

    prefs = preferences(tmp_path)
    assert prefs["default_track"].value == "model"


def test_chat_thread_roundtrip(tmp_path: Path) -> None:
    append_turn(tmp_path, "t-1", "user", "why was c-0045 pruned?")
    append_turn(tmp_path, "t-1", "assistant", "it was pruned for a statistically flat delta [ledger rows 12-13].")
    append_turn(tmp_path, "t-2", "user", "unrelated thread")

    t1 = thread(tmp_path, "t-1")
    assert [turn.role for turn in t1.turns] == ["user", "assistant"]
    assert t1.turns[0].content == "why was c-0045 pruned?"
    assert t1.created <= t1.updated

    all_threads = threads(tmp_path)
    assert {t.id for t in all_threads} == {"t-1", "t-2"}


def test_chat_turn_meta_round_trips(tmp_path: Path) -> None:
    meta = {
        "citations": [{"seq": 12, "what": "objective_progress: law"}],
        "refusals": [],
        "tool_calls": [{"tool": "objective_progress", "args": {"id": "legal-intent"}, "result_summary": "ok"}],
    }
    append_turn(tmp_path, "t-1", "user", "how is the legal objective doing?")
    append_turn(tmp_path, "t-1", "assistant", "it scores 0.5 [ledger row 12].", meta=meta)

    t1 = thread(tmp_path, "t-1")
    assert t1.turns[0].meta == {}
    assert t1.turns[1].meta == meta


def test_chat_turn_rejects_unknown_role(tmp_path: Path) -> None:
    with pytest.raises(MemoryError):
        append_turn(tmp_path, "t-1", "system", "not a role this store accepts")


def test_unknown_thread_raises(tmp_path: Path) -> None:
    with pytest.raises(MemoryError):
        thread(tmp_path, "no-such-thread")
