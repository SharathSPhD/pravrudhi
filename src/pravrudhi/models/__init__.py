"""Model backends: one OpenAI-compatible client, and the lifecycle of the local llama.cpp server container."""

from pravrudhi.models.llama_server import LlamaServer
from pravrudhi.models.openai_compat import ChatClient, ChatResult

__all__ = ["ChatClient", "ChatResult", "LlamaServer"]
