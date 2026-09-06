"""Minimal OpenAI-compatible chat client (stdlib only). Local llama.cpp by default; any endpoint by config."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel, ConfigDict


class ChatResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    wall_s: float
    finish_reason: str | None = None


class ChatClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080/v1",
        model: str = "local",
        api_key: str | None = None,
        timeout_s: int = 600,
        thinking: bool | None = False,
    ) -> None:
        self.thinking = thinking
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        seed: int | None = None,
        json_mode: bool = False,
        json_schema: dict[str, Any] | None = None,
    ) -> ChatResult:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if seed is not None:
            body["seed"] = seed
        if json_schema is not None:
            # llama.cpp compiles the schema to a grammar: the sampler cannot emit EOS before the array closes
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": json_schema}}
        elif json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.thinking is not None:
            body["chat_template_kwargs"] = {"enable_thinking": self.thinking}
        req = urllib.request.Request(self.base_url + "/chat/completions", data=json.dumps(body).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            # A night once died on "HTTP Error 400: Bad Request" and nothing more: the server's explanation was in
            # the body the exception discards. Surface it, with the endpoint, so the cause is readable in the log.
            detail = exc.read().decode(errors="replace")[:600] if exc.fp else ""
            raise RuntimeError(f"{self.base_url}/chat/completions answered {exc.code}: {detail or exc.reason}") from exc
        usage = data.get("usage") or {}
        return ChatResult(
            text=data["choices"][0]["message"]["content"],
            model=str(data.get("model", self.model)),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            wall_s=time.monotonic() - t0,
            finish_reason=data["choices"][0].get("finish_reason"),
        )

    def healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url.removesuffix("/v1") + "/health", timeout=5) as r:
                return bool(r.status == 200)
        except (urllib.error.URLError, OSError, ValueError):
            return False
