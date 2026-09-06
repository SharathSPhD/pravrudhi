"""Prepare and admit Loom milestone 4's first interpretation job: a linear probe of a named feature.

`probe_request` turns a declared Loom `monitor` term (see `pravrudhi.application.loom.MonitorSpec`) into the
/in payload `docker/jobs/probe_feature.py` needs: the feature it reads and, if the monitor carries one, its
`probe_r2` gate threshold. It never states a residual-stream `layer` -- LANGUAGE.md's `monitor` decl has no
layer term yet, so inventing one here would be exactly the kind of unmeasured number the ledger's rule forbids.
The operator supplies the layer before the container runs; `probe_feature.py` fails loudly if it is missing.

`admit_probe` records that job's /out/probe.json into the ledger as an `audit{kind: interp_probe}` row by file
hash, mirroring `pravrudhi.application.external.record_external`'s shape exactly. The tier is `"probe"`, not
`"external"`: `probe_feature.py` is Pravrudhi's own code, not third-party scoring tooling like lm-eval or
EvalPlus. But it is also not pratyaksha: the operator runs the container on GPU hardware outside the kernel's
own tracked sandbox execution, so the kernel never invoked the job and cannot replay it end-to-end -- it can
only verify, by hash, the output file the operator hands back.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pravrudhi.application.loom import MonitorSpec
from pravrudhi_kernel.ledger import LedgerWriter
from pravrudhi_kernel.sandbox.observe import sha256_file


def probe_request(spec: MonitorSpec, items_path: Path) -> dict[str, Any]:
    """The /in payload for `spec`: `items_path` passed through untouched, plus a monitor dict naming only what
    `spec` itself carries -- `feature`, and `threshold` when the monitor declares one."""
    monitor: dict[str, Any] = {"feature": spec.feature}
    if spec.threshold is not None:
        monitor["threshold"] = spec.threshold
    return {"items_path": str(items_path), "monitor": monitor}


def admit_probe(root: Path, out_dir: Path, track: str, night: int) -> dict[str, Any]:
    probe_path = out_dir / "probe.json"
    meta_path = out_dir / "job_meta.json"
    parsed = json.loads(probe_path.read_text())
    meta = json.loads(meta_path.read_text())
    ledger = root / "research" / "ledger.jsonl"
    w = LedgerWriter.open(ledger, "0.1.0")
    payload = {
        "kind": "interp_probe",
        "severity": "info",
        "tier": "probe",
        "track": track,
        "file": str(probe_path.relative_to(root)) if probe_path.is_relative_to(root) else str(probe_path),
        "sha256": sha256_file(probe_path),
        "model_sha256": meta.get("model_sha256"),
        "adapter_sha256": meta.get("adapter_sha256"),
        "items_sha256": meta.get("items_sha256"),
        "monitor_sha256": meta.get("monitor_sha256"),
        **parsed,
    }
    ev = w.append("audit", "auditor", payload, epoch=0, night=night)
    return {"seq": ev.seq, **payload}
