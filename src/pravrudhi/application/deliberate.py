"""vimarśa: score the live pool with L2, run the decorative check, fill the budget, write `select` rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pravrudhi.application.citta_view import build_citta, keys_for
from pravrudhi_kernel.efe import (
    BeliefKeys,
    PrecisionView,
    Shares,
    decorative_check,
    efe,
    habit_prior,
    knapsack_batch,
    selection_probabilities,
)
from pravrudhi_kernel.ledger import LedgerWriter, replay
from pravrudhi_kernel.schema import AbstractionLevel, Candidate, EvidencePlan, Pramana, Prediction, Preferences, Residency, Stage


class DecorativeAbort(RuntimeError):
    pass


def live_candidates(state_candidates: dict[str, Any], meta: dict[str, dict[str, Any]], incumbent_id: str) -> list[str]:
    out = []
    for cid in meta:
        if cid == incumbent_id or cid.startswith("c-0000"):
            continue
        c = state_candidates.get(cid)
        if c is None or c.pruned or c.promoted or c.audit_high or c.skipped:
            continue
        if c.last_boundary in ("confirm", "prune"):
            continue
        out.append(cid)
    return out


def deliberate(
    root: Path,
    w: LedgerWriter,
    *,
    night: int,
    budget_gpu_h: float,
    sigma_seed: float,
    incumbent_id: str,
    harness_hash: str,
    model_hash: str,
    rng_seed: int,
    log: Any = print,
) -> list[str]:
    cfg = yaml.safe_load((root / "research" / "prereg" / "controller.yaml").read_text())
    sigma2_eval = max(sigma_seed, 1e-4) ** 2
    ledger = root / "research" / "ledger.jsonl"
    citta, meta = build_citta(
        ledger,
        root / ".pravrudhi" / "kernel" / "sealed" / "predictions",
        sigma2_eval=sigma2_eval,
        tau0_2=float(cfg["tau0_2"]),
    )
    st = replay(ledger)
    pool = live_candidates(st.candidates, meta, incumbent_id)
    if not pool:
        log("deliberate: no live candidates")
        return []
    prefs = Preferences.model_validate(
        {
            "beta": float(cfg["preferences"]["beta"]),
            "lambda": float(cfg["preferences"]["lambda"]),
            "eta": float(cfg["preferences"]["eta"]),
        }
    )
    post_var = [citta.candidates[c].sigma2 for c in pool if c in citta.candidates]
    rho = float(np.mean(list(citta.rho_pred.values()))) if citta.rho_pred else 0.0
    from pravrudhi_kernel.efe import infer_precision

    gamma = infer_precision(
        PrecisionView(
            pool_post_var=post_var,
            sigma2_eval=sigma2_eval,
            rho_pred=rho,
            f_epi=float(cfg["f_epi"]),
            rho_floor=float(cfg["rho_floor"]),
        )
    )
    cands: dict[str, Candidate] = {}
    keys: dict[str, BeliefKeys] = {}
    terms = {}
    habits = {}
    for cid in pool:
        m = meta[cid]
        n_obs = st.candidates[cid].n_obs if cid in st.candidates else 0
        k = keys_for(cid, m["surface"], m["bucket"], m["strategy"], m["family"])
        keys[cid] = k
        cand = Candidate(
            id=cid,
            surface=m["surface"],
            bucket=m["bucket"],
            edit_family=m["family"] or "-",
            strategy=m["strategy"],
            lineage=[incumbent_id],
            diff_ref="0" * 64,
            cost_est_gpu_h=float((m["recipe"] or {}).get("_cost", 0.0)) or _cost(m),
            residency_need=Residency.executor,
            predicted=Prediction(delta_in=0.0, delta_out=None, conf=0.0, hash="0" * 64),
            abstraction_level=AbstractionLevel.madhyama,
            provenance=Pramana.agama,
        )
        cands[cid] = cand
        plan = EvidencePlan(
            seeds=[n_obs],
            heldout_rotation_id=None,
            sensors_to_read=[],
            stage=Stage.screen,
            sequential_stage=n_obs,
        )
        terms[cid] = efe(
            citta,
            cand,
            plan,
            prefs,
            gamma,
            float(cfg["kappa"]),
            budget_gpu_h,
            sigma2_eval,
            float(cfg["tau0_2"]),
            keys=k,
        )
        habits[cid] = habit_prior(citta, k, float(cfg["tau0_2"]))
    G = {c: t.G for c, t in terms.items()}
    Q = selection_probabilities(G, habits)
    # C2 bootstrap: before any candidate in the pool has a kernel observation, near-uniform selection is the expected
    # behaviour, not a decorative controller; the identical-score and CV criteria still apply, the MI floor does not.
    bootstrap = not any((st.candidates[c].n_obs if c in st.candidates else 0) > 0 for c in pool)
    mi_min = 0.0 if bootstrap else float(cfg["decorative"]["mi_min_bits"])
    verdict = decorative_check(G, Q, float(cfg["decorative"]["cv_min"]), mi_min)
    (root / "research" / "last_select.json").write_text(
        json.dumps(
            {"night": night, "scores": G, "selection": Q, "verdict": verdict.model_dump()},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if verdict.verdict == "fail":
        w.append(
            "audit",
            "controller",
            {"kind": "decorative_controller", "severity": "high", "detail": verdict.model_dump()},
            epoch=0,
            night=night,
        )
        raise DecorativeAbort(verdict.reason or "decorative")
    shares = Shares(planted=float(cfg["shares"]["planted"]), sensors=float(cfg["shares"]["sensors"]), f_epi=float(cfg["f_epi"]))
    batch = knapsack_batch(Q, cands, {c: t.EIG for c, t in terms.items()}, budget_gpu_h, shares, np.random.default_rng(rng_seed))
    chosen = batch.deliberation + batch.execution
    order = sorted(chosen, key=lambda c: -Q[c])
    for i, cid in enumerate(order):
        t = terms[cid]
        w.append(
            "select",
            "controller",
            {
                "G": t.G,
                "EIG": t.EIG,
                "pragmatic": t.pragmatic,
                "cost_term": t.cost_term,
                "gamma": t.gamma.model_dump(),
                "kappa": t.kappa,
                "habit_prior": habits[cid],
                "Q": Q[cid],
                "strategy": meta[cid]["strategy"],
                "plan": {
                    "seeds": [st.candidates[cid].n_obs if cid in st.candidates else 0],
                    "heldout_rotation_id": None,
                    "sensors_to_read": [],
                    "stage": "screen",
                    "sequential_stage": st.candidates[cid].n_obs if cid in st.candidates else 0,
                },
                "decorative": {"cv_G": verdict.cv_G, "mi_bits": verdict.mi_bits, "verdict": "pass"},
                "night_mode": "bootstrap" if bootstrap else "exploit",
                "harness_hash": harness_hash,
                "model_hash": model_hash,
                "epistemic": cid in batch.epistemic_ids,
                "rank": i,
                "budget_effective": batch.budget_effective,
                "spent_planned": batch.spent_gpu_h,
            },
            epoch=0,
            night=night,
            cycle=i + 1,
            candidate_id=cid,
            surface=meta[cid]["surface"],
            bucket=meta[cid]["bucket"],
        )
    log(
        f"deliberate: pool={len(pool)} selected={len(order)} "
        f"gamma={gamma.model_dump()} cv_G={verdict.cv_G:.3f} mi={verdict.mi_bits:.3f}"
    )
    return order


def _cost(m: dict[str, Any]) -> float:
    from pravrudhi.targets import parse_recipe

    r = parse_recipe(m["recipe"] or {})
    return r.cost_est_gpu_h() if not isinstance(r, str) else 0.1
