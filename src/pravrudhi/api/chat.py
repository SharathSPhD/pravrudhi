"""The chat surface over HTTP: three routes, and no place for the model to reach the client unfiltered.

The engine's other routes each answer one replayed question, which meant the only way to ask "is my objective
working, and what should I do next" was to know which three endpoints to call and how to read them. This
router is the conversational front door to the same replay functions - and deliberately nothing more than a
front door: every honesty rule lives in `application/chat.py`, so a second caller (a CLI turn, a scheduled
summary) gets the same guarantees without going through FastAPI.

`complete` is a parameter of the router rather than a module-level default so that the whole route, including
persistence and the response contract, can be exercised against a fake model with no endpoint running.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pravrudhi.api.identity import CurrentUserDep, User
from pravrudhi.api.schemas import ChatResponse, ChatThreadDetailResponse, ChatThreadsResponse
from pravrudhi.application.chat import Complete, converse
from pravrudhi.application.memory import MemoryError as MemoryStoreError
from pravrudhi.application.memory_store import store_for


class ChatRequest(BaseModel):
    """What the user said, and which conversation it belongs to. A null `thread_id` starts a new one rather
    than appending to whichever thread happened to be most recent."""

    message: str
    thread_id: str | None = None


def build_chat_router(root: Path, complete: Complete | None = None) -> APIRouter:
    workspace = Path(root)
    router = APIRouter(prefix="/api")

    @router.post("/chat", response_model=ChatResponse)
    async def chat_ep(req: ChatRequest, user: User | None = CurrentUserDep) -> dict[str, Any]:
        """Answer one turn. Any number the turn's tools did not return is stripped and reported under
        `refusals`, so a reply is either traceable to the ledger or visibly missing a sentence."""
        if not req.message.strip():
            raise HTTPException(422, "a chat turn with no message asks nothing")
        outcome = converse(workspace, req.message, thread_id=req.thread_id, user=user, complete=complete)
        return outcome.to_dict()

    @router.get("/chat/threads", response_model=ChatThreadsResponse)
    async def threads_ep(user: User | None = CurrentUserDep) -> dict[str, Any]:
        """The caller's conversations. A logged-in user's follow their account; a local engine's stay on disk."""
        store = store_for(workspace, user)
        return {
            "threads": [{"id": t.id, "updated": t.updated, "turns": len(t.turns)} for t in store.threads()]
        }

    @router.get("/chat/threads/{thread_id}", response_model=ChatThreadDetailResponse)
    async def thread_ep(thread_id: str, user: User | None = CurrentUserDep) -> dict[str, Any]:
        """One conversation in full. A thread that does not exist is a 404, not an empty conversation: the
        two are different facts and a client that conflates them will silently start writing into nothing."""
        store = store_for(workspace, user)
        try:
            thread = store.thread(thread_id)
        except MemoryStoreError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {
            "id": thread.id,
            "turns": [{"role": t.role, "content": t.content, "created": t.ts} for t in thread.turns],
        }

    return router
