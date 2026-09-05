"""Where the proposer model runs.

The proposer is the largest model in the loop and, on a single-GPU host, it competes for the very memory the
trainee needs: a night must stop the proposer before it can train. When the fleet has another machine that can
serve open weights, the proposer belongs there instead, and the accelerator that does the training never has to
share. That is the first real dividend of a multi-machine engine rather than a decoration on it.

`remote` is any OpenAI-compatible endpoint, so a fleet host serving llama.cpp, a tunnelled port or an internal
service all work the same way and none of them is required: with no endpoint the proposer runs locally exactly as
before.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from pravrudhi.models.llama_server import LlamaServer
from pravrudhi.models.openai_compat import ChatClient


@contextmanager
def proposer_client(
    gguf: Path, *, ctx: int, endpoint: str = "", model: str = "local", log: Any = print
) -> Iterator[ChatClient]:
    """Yield a client for the proposer, started locally or borrowed from a remote endpoint.

    A remote endpoint is used as it is found: this does not start, stop or manage a process on another machine,
    because a night must not silently depend on being able to administer a second host.
    """
    if endpoint:
        client = ChatClient(endpoint.rstrip("/"), model=model)
        if not client.healthy():
            raise RuntimeError(f"proposer endpoint {endpoint} is not answering; start it or omit the endpoint")
        log(f"deliberation window: using the remote proposer at {endpoint} (this GPU stays free)")
        yield client
        return
    server = LlamaServer(gguf, ctx=ctx)
    log("deliberation window: starting proposer")
    try:
        yield server.start()
    finally:
        server.stop()
        log("deliberation window: proposer stopped")
