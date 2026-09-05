"""Report installation readiness so callers can diagnose missing setup without starting a run."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from pravrudhi_kernel.ledger.verify import verify
from pravrudhi_kernel.sandbox.runner import docker_available

PREREG_FILES = ("lora_night.yaml", "harness_night.yaml", "controller.yaml", "canaries.md")


def run_doctor(root: Path) -> dict[str, Any]:
    """Check required files, ledger integrity, Docker, and sealed pool presence without changing state."""
    checks: list[dict[str, Any]] = []
    missing = [name for name in (".pravrudhi/config.yaml", "research/ledger.jsonl") if not (root / name).is_file()]
    checks.append({
        "name": "initialised",
        "ok": not missing,
        "detail": "Missing: " + ", ".join(missing) if missing else "Config and ledger exist.",
    })

    ledger = root / "research" / "ledger.jsonl"
    try:
        result = verify(ledger)
        ledger_ok = result.ok
        ledger_detail = f"Verified {result.n} ledger events." if result.ok else f"Ledger verification failed: {result.reason}"
    except (OSError, UnicodeError) as exc:
        ledger_ok = False
        ledger_detail = f"Cannot read research/ledger.jsonl: {exc.strerror if isinstance(exc, OSError) else 'invalid encoding'}"
    checks.append({"name": "ledger", "ok": ledger_ok, "detail": ledger_detail})

    docker_path = shutil.which("docker")
    if docker_path is None:
        docker_ok = False
        docker_detail = "Docker binary not installed: 'docker' executable is missing from PATH."
    elif docker_available():
        docker_ok = True
        docker_detail = f"Docker available at {docker_path}."
    else:
        info = subprocess.run(["docker", "info"], capture_output=True, text=True)
        stderr = info.stderr.strip()
        docker_ok = False
        if "permission denied" in stderr.lower():
            docker_detail = (
                "Permission denied running 'docker info': add your user to the docker group "
                "(then log out and back in) or use sudo."
            )
        else:
            docker_detail = "Docker daemon is not running: " + (stderr or f"'docker info' exited {info.returncode}.")
    checks.append({"name": "docker", "ok": docker_ok, "detail": docker_detail})

    gpu_path = shutil.which("nvidia-smi")
    if gpu_path is None:
        gpu_detail = "No GPU detected: 'nvidia-smi' is not on PATH."
    else:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            gpu_detail = f"No GPU detected: 'nvidia-smi' could not be run ({exc})."
        else:
            lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
            if result.returncode == 0 and lines:
                gpu_detail = "; ".join(lines)
            else:
                reason = result.stderr.strip() or f"exited {result.returncode}"
                gpu_detail = f"No GPU detected: 'nvidia-smi' failed ({reason})."
    checks.append({"name": "gpu", "ok": True, "detail": gpu_detail})

    pools = root / ".pravrudhi" / "kernel" / "pools"
    pool_ok = any(path.is_file() for path in pools.glob("*/manifest.json"))
    checks.append({
        "name": "pools",
        "ok": pool_ok,
        "detail": "A sealed pool manifest exists." if pool_ok else "No sealed pool manifest under .pravrudhi/kernel/pools.",
    })

    missing = [name for name in PREREG_FILES if not (root / "research" / "prereg" / name).is_file()]
    checks.append({
        "name": "prereg",
        "ok": not missing,
        "detail": "Missing pre-registration files: " + ", ".join(missing) if missing else "All pre-registration files exist.",
    })
    return {"ok": all(check["ok"] for check in checks), "checks": checks}
