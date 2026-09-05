"""Rebuild the controller's belief state from the ledger (plus the kernel's sealed predictions) with L2's pure
functions. Nothing here is stored; it is recomputed at every deliberation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pravrudhi_kernel.efe import BeliefKeys, posterior_update, posterior_update_prediction
from pravrudhi_kernel.ledger.verify import iter_events
from pravrudhi_kernel.schema import Citta


def keys_for(cid: str, surface: str, bucket: dict[str, str] | None, strategy: str | None, family: str | None) -> BeliefKeys:
    b = bucket or {"task_family": "?", "target_model": "?", "corpus": "?"}
    return BeliefKeys(
        surface=surface,
        strategy=strategy,
        bucket=f"{b['task_family']}|{b['target_model']}|{b['corpus']}|{family or '-'}",
        candidate_id=cid,
    )


def load_sealed(sealed_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(Path(sealed_dir).glob("*.jsonl")) if Path(sealed_dir).exists() else []:
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["candidate_id"]] = r
    return out


def build_citta(ledger: Path, sealed_dir: Path, *, sigma2_eval: float, tau0_2: float) -> tuple[Citta, dict[str, dict[str, Any]]]:
    """Fold propose/predict/observe rows into a Citta.

    Returns (citta, candidate meta {cid: {surface, bucket, strategy, family, recipe}}).
    """
    citta = Citta(version=0, surfaces={}, strategies={}, buckets={}, candidates={}, rho_pred={})
    sealed = load_sealed(sealed_dir)
    meta: dict[str, dict[str, Any]] = {}
    for ev in iter_events(ledger):
        cid = ev.candidate_id
        if ev.kind == "propose" and cid:
            meta[cid] = {
                "surface": str(ev.surface),
                "bucket": ev.bucket.model_dump() if ev.bucket else None,
                "strategy": ev.payload.get("strategy"),
                "family": ev.payload.get("edit_family"),
                "recipe": ev.payload.get("recipe"),
                "night": ev.night,
            }
        elif ev.kind == "predict" and cid and cid in sealed and cid in meta:
            m = meta[cid]
            k = keys_for(cid, m["surface"], m["bucket"], m["strategy"], m["family"])
            s = sealed[cid]
            citta = posterior_update_prediction(citta, k, float(s["delta_in"]), float(s["conf"]), sigma2_eval, tau0_2)
        elif ev.kind == "observe" and cid and cid in meta and ev.payload.get("arm", "candidate") == "candidate":
            m = meta[cid]
            k = keys_for(cid, m["surface"], m["bucket"], m["strategy"], m["family"])
            d = ev.payload.get("observed", {}).get("delta_in")
            if d is not None and ev.payload.get("study") != "noise_floor":
                citta = posterior_update(citta, k, float(d), sigma2_eval, tau0_2)
            if ev.payload.get("brier") is not None and ev.surface:
                rp = dict(citta.rho_pred)
                prev = rp.get(str(ev.surface), 0.5)
                rp[str(ev.surface)] = 0.8 * prev + 0.2 * (1.0 - float(ev.payload["brier"]))
                citta = citta.model_copy(update={"rho_pred": rp})
    return citta, meta
