"""Kernel state directory: `<root>/.pravrudhi/kernel/` (0700) with the HMAC secret (0600) and the pools."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from pravrudhi_kernel.schema.common import KernelModel


class KernelState(KernelModel):
    root: str
    kernel_dir: str
    secret_path: str
    pools_dir: str
    jobs_dir: str
    isolation: str  # process | container | user — what this host can actually provide


def ensure_kernel_state(root: Path, *, docker_available: bool) -> KernelState:
    kd = Path(root) / ".pravrudhi" / "kernel"
    kd.mkdir(parents=True, exist_ok=True)
    os.chmod(kd, 0o700)
    sp = kd / "secret"
    if not sp.exists():
        sp.write_bytes(secrets.token_bytes(32))
        os.chmod(sp, 0o600)
    (kd / "pools").mkdir(exist_ok=True)
    (kd / "jobs").mkdir(exist_ok=True)
    return KernelState(
        root=str(root),
        kernel_dir=str(kd),
        secret_path=str(sp),
        pools_dir=str(kd / "pools"),
        jobs_dir=str(kd / "jobs"),
        isolation="container" if docker_available else "process",
    )


def read_secret(state: KernelState) -> bytes:
    return Path(state.secret_path).read_bytes()
