"""Measure a machine's capabilities on the machine itself.

The probe is a single self-contained program with no dependencies beyond the standard library, because the host it
runs on may have nothing installed yet. It is shipped as source over the transport and executed with `python3 -`,
so enrolling a machine needs no prior deployment step. It reports only what it can observe; anything it cannot
determine stays at its default rather than being guessed.
"""

from __future__ import annotations

import json
from typing import Any

from pravrudhi.hosts.base import HostCapabilities

PROBE_SOURCE = r'''
import json, os, platform, shutil, subprocess, glob

def sh(cmd, timeout=15):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:
        return ""

out = {"os": platform.system(), "arch": platform.machine(), "python": platform.python_version()}
out["cpu_count"] = os.cpu_count() or 0

if out["os"] == "Darwin":
    mem = sh("sysctl -n hw.memsize")
    out["ram_gb"] = round(int(mem) / 2**30, 1) if mem.isdigit() else 0.0
    chip = sh("sysctl -n machdep.cpu.brand_string")
    out["gpu_name"] = chip
    # Apple Silicon exposes the GPU through Metal; the GPU draws on the same unified memory as the CPU.
    out["accelerator"] = "metal" if out["arch"] in ("arm64", "aarch64") else "none"
    out["gpu_vram_gb"] = 0.0
else:
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    out["ram_gb"] = round(int(line.split()[1]) / 2**20, 1)
                    break
    except Exception:
        out["ram_gb"] = 0.0
    smi = sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits")
    if smi:
        first = smi.splitlines()[0].split(",")
        out["gpu_name"] = first[0].strip()
        try:
            out["gpu_vram_gb"] = round(float(first[1].strip()) / 1024, 1)
        except Exception:
            out["gpu_vram_gb"] = 0.0
        out["accelerator"] = "cuda"
    else:
        out["gpu_name"] = ""
        out["gpu_vram_gb"] = 0.0
        out["accelerator"] = "none"

out["docker"] = bool(shutil.which("docker")) and bool(sh("docker info --format ok"))

# If llama.cpp is present it reports the accelerator's real usable memory, which beats any heuristic. Apple
# Silicon in particular shares memory between CPU and GPU, and the allocatable share is a policy of the OS, not
# a fixed fraction we should be guessing at.
srv = shutil.which("llama-server") or ""
if not srv:
    import glob as _g
    cands = _g.glob(os.path.expanduser("~/pravrudhi/llama/*/llama-server"))
    srv = cands[0] if cands else ""
if srv:
    for line in sh("%s --list-devices" % srv, timeout=60).splitlines():
        line = line.strip()
        if line.startswith(("MTL", "CUDA", "Vulkan", "ROCm")) and "MiB" in line:
            try:
                mib = float(line.split("(")[1].split("MiB")[0].strip())
                out["accel_mem_gb"] = round(mib / 1024, 1)
                if line.split(":")[0].startswith("MTL"):
                    out["gpu_name"] = line.split("(")[0].split(":", 1)[1].strip() or out.get("gpu_name", "")
            except (IndexError, ValueError):
                pass
            break
out["agents"] = [a for a in ("claude", "codex", "opencode", "orca-ide") if shutil.which(a)]
home = os.path.expanduser("~")
models = []
for pat in ("%s/.cache/huggingface/hub/models--*GGUF*" % home, "%s/models/*.gguf" % home, "%s/.cache/lm-studio/models/**/*.gguf" % home):
    for p in glob.glob(pat, recursive=True)[:40]:
        models.append(os.path.basename(p))
out["local_models"] = sorted(set(models))[:40]
print(json.dumps(out))
'''


def parse_probe(stdout: str) -> HostCapabilities:
    """Turn probe output into capabilities; a host that answered nothing usable is simply not reachable."""
    line = ""
    for cand in reversed(stdout.strip().splitlines()):
        if cand.strip().startswith("{"):
            line = cand.strip()
            break
    if not line:
        return HostCapabilities(reachable=False, error="probe produced no JSON")
    try:
        d: dict[str, Any] = json.loads(line)
    except ValueError as e:
        return HostCapabilities(reachable=False, error=f"probe JSON invalid: {e}")
    return HostCapabilities(
        os=str(d.get("os", "")),
        arch=str(d.get("arch", "")),
        cpu_count=int(d.get("cpu_count") or 0),
        ram_gb=float(d.get("ram_gb") or 0.0),
        gpu_name=str(d.get("gpu_name", "")),
        gpu_vram_gb=float(d.get("gpu_vram_gb") or 0.0),
        accelerator=str(d.get("accelerator", "none")),
        accel_mem_gb=float(d.get("accel_mem_gb") or 0.0),
        docker=bool(d.get("docker")),
        python=str(d.get("python", "")),
        agents=list(d.get("agents") or []),
        local_models=list(d.get("local_models") or []),
        reachable=True,
    )
