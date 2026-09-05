"""Report installation readiness so callers can diagnose missing setup without starting a run."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pravrudhi_kernel.ledger.verify import verify

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

    docker = shutil.which("docker")
    checks.append({
        "name": "docker",
        "ok": docker is not None,
        "detail": f"Docker available at {docker}." if docker else "Docker executable is missing from PATH.",
    })

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
