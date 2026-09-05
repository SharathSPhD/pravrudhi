"""Shared helpers for container jobs: hashing, prompt building, model loading."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_dir_hash(model_dir: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(model_dir.glob("*")):
        if p.is_file() and (p.suffix in {".safetensors", ".json"} or p.name.endswith(".model")):
            h.update(p.name.encode())
            h.update(sha256_file(p).encode())
    return h.hexdigest()


def read_jsonl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(p).read_text().splitlines() if line.strip()]


def write_jsonl(p: Path, rows: list[dict[str, Any]]) -> None:
    Path(p).write_text("".join(json.dumps(r) + "\n" for r in rows))


def chat_prompt(tok: Any, template: str, question: str) -> str:
    msgs = [{"role": "user", "content": template.replace("{question}", question)}]
    return str(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False))


def load_model(model_dir: Path, adapter_dir: Path | None, dtype: str = "bfloat16", trainable: bool = False) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_dir, padding_side="left")
    dt = {"bfloat16": torch.bfloat16, "float16": torch.float16}[dtype]
    model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=dt, device_map="cuda", attn_implementation="sdpa")
    if adapter_dir is not None:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter_dir, is_trainable=trainable)
    return model, tok
