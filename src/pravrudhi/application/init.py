"""`pravrudhi init`: make a project ready for a night. Idempotent; never overwrites an existing config or ledger."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from pravrudhi import KERNEL_VERSION
from pravrudhi_kernel.ledger import LedgerWriter
from pravrudhi_kernel.sandbox import ensure_kernel_state
from pravrudhi_kernel.sandbox.runner import docker_available

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "target": {"kind": "lora", "model": "Qwen/Qwen3-4B", "bench": "gsm8k-test"},
    "proposer": {
        "backend": "llama-server",
        "gguf": "Qwen/Qwen3-30B-A3B-GGUF:Qwen3-30B-A3B-Q4_K_M.gguf",
        "base_url": "http://127.0.0.1:8080/v1",
    },
    "budget": {"night_gpu_h": 3.0},
    "isolation": "container",
}

PACKAGED_PREREG = Path(__file__).resolve().parents[1] / "assets" / "prereg"
PACKAGED_PROMPTS = Path(__file__).resolve().parents[1] / "assets" / "prompts"


def init_project(root: Path, *, model: str | None = None) -> dict[str, Any]:
    root = Path(root)
    state = ensure_kernel_state(root, docker_available=docker_available())
    cfg_path = root / ".pravrudhi" / "config.yaml"
    created: list[str] = []
    if not cfg_path.exists():
        cfg = dict(DEFAULT_CONFIG)
        if model:
            cfg["target"] = dict(cfg["target"], model=model)
        cfg["isolation"] = state.isolation
        cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
        created.append(str(cfg_path))
    for sub in ("research/prereg", "research/inbox", "harness/prompts", "docs/evidence"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    for src_dir, dst_dir in ((PACKAGED_PREREG, root / "research" / "prereg"), (PACKAGED_PROMPTS, root / "harness" / "prompts")):
        if src_dir.exists():
            for p in src_dir.rglob("*"):
                if p.is_file():
                    dst = dst_dir / p.relative_to(src_dir)
                    if not dst.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, dst)
                        created.append(str(dst))
    ledger = root / "research" / "ledger.jsonl"
    if not ledger.exists():
        LedgerWriter.open(ledger, KERNEL_VERSION)
        created.append(str(ledger))
    gi = root / ".gitignore"
    line = ".pravrudhi/\n"
    if not gi.exists() or line not in gi.read_text():
        with gi.open("a") as fh:
            fh.write(("\n" if gi.exists() else "") + "# pravrudhi kernel state (secret, pools, jobs)\n" + line)
        created.append(str(gi))
    return {
        "root": str(root),
        "isolation": state.isolation,
        "kernel_dir": state.kernel_dir,
        "created": created,
        "config": str(cfg_path),
        "ledger": str(ledger),
    }
