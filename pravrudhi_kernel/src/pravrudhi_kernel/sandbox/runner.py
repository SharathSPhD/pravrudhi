"""Run one disposable container job: read-only mounts, no network, GPU on request, wall clock and peak VRAM
measured.

The kernel is the launcher; the job writes into exactly one output directory that the kernel created for it.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from pathlib import Path

from pydantic import Field

from pravrudhi_kernel.schema.common import KernelModel


class JobSpec(KernelModel):
    image: str
    command: list[str]
    mounts_ro: dict[str, str] = Field(default_factory=dict)  # host path -> container path
    output_dir: str  # host path, mounted rw at /out
    env: dict[str, str] = Field(default_factory=dict)
    gpu: bool = False
    network: bool = False
    timeout_s: int = Field(default=3600, ge=1)
    user: str | None = None  # "uid:gid"


class JobResult(KernelModel):
    exit_code: int
    wall_s: float
    peak_gib_smi: float | None
    stdout_tail: str
    stderr_tail: str
    timed_out: bool


def docker_available() -> bool:
    return shutil.which("docker") is not None and subprocess.run(["docker", "info"], capture_output=True).returncode == 0


def _smi_poll(stop: threading.Event, peak: list[float]) -> None:
    while not stop.is_set():
        try:
            out = (
                subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                .stdout.strip()
                .splitlines()
            )
            used = max(float(x) for x in out) / 1024.0 if out else 0.0
            peak[0] = max(peak[0], used)
        except (subprocess.SubprocessError, ValueError, OSError):
            pass
        stop.wait(0.5)


def run_job(spec: JobSpec) -> JobResult:
    out = Path(spec.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", "-v", f"{out}:/out:rw"]
    for host, cont in spec.mounts_ro.items():
        cmd += ["-v", f"{host}:{cont}:ro"]
    if not spec.network:
        cmd += ["--network", "none"]
    if spec.gpu:
        cmd += ["--gpus", "all"]
    if spec.user:
        cmd += ["--user", spec.user]
    for k, v in spec.env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += [spec.image, *spec.command]
    stop, peak = threading.Event(), [0.0]
    t = threading.Thread(target=_smi_poll, args=(stop, peak), daemon=True) if spec.gpu else None
    if t:
        t.start()
    t0 = time.monotonic()
    timed_out = False
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=spec.timeout_s)
        code, so, se = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        timed_out, code = True, 124
        so, se = (
            (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""),
            (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or ""),
        )
    wall = time.monotonic() - t0
    if t:
        stop.set()
        t.join(timeout=2)
    return JobResult(
        exit_code=code,
        wall_s=wall,
        peak_gib_smi=(peak[0] if spec.gpu else None),
        stdout_tail=so[-4000:],
        stderr_tail=se[-4000:],
        timed_out=timed_out,
    )
