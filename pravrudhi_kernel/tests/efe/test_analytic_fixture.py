"""Domain gate: a hand-built three-candidate pool matches the analytic softmax to 1e-6."""

import math

import numpy as np

from pravrudhi_kernel.efe import (
    Precision,
    Shares,
    decorative_check,
    efe,
    knapsack_batch,
    selection_probabilities,
)
from pravrudhi_kernel.schema import Candidate, Citta, EvidencePlan, Prediction, Preferences
from pravrudhi_kernel.schema.citta import CandidateBelief

H = "0" * 64
BUCKET = {"task_family": "gsm8k", "target_model": "Qwen/Qwen3-4B", "corpus": "gsm8k-train"}


def _cand(cid: str, cost: float, fam: str, surface: str = "W3.adapter", need: str = "executor") -> Candidate:
    return Candidate(
        id=cid,
        surface=surface,
        bucket=BUCKET,
        edit_family=fam,
        strategy="sft_rejection",
        lineage=[],
        diff_ref=H,
        cost_est_gpu_h=cost,
        residency_need=need,
        predicted=Prediction(delta_in=0.0, delta_out=None, conf=0.0, hash=H),
        abstraction_level="madhyama",
        provenance="agama",
    )


def test_three_candidate_pool_matches_analytic_softmax() -> None:
    # posterior: c-0001 known-good (mu .03, tight), c-0002 unknown (wide), c-0003 known-bad
    citta = Citta(
        version=3,
        surfaces={},
        strategies={},
        buckets={},
        candidates={
            "c-0001": CandidateBelief(mu=0.03, sigma2=0.0001, n_obs=3),
            "c-0002": CandidateBelief(mu=0.0, sigma2=0.01, n_obs=0),
            "c-0003": CandidateBelief(mu=-0.02, sigma2=0.0001, n_obs=3),
        },
        rho_pred={},
    )
    prefs = Preferences(
        beta=40.0, lambda_=80.0, eta=5.0
    )  # research/prereg/controller.yaml preferences (provisional)
    gamma = Precision(epi=0.5, prag=1.0)
    plan = EvidencePlan(
        seeds=[1], heldout_rotation_id=None, sensors_to_read=[], stage="smoke", sequential_stage=0
    )
    cands = {
        c.id: c
        for c in (
            _cand("c-0001", 0.2, "optimiser"),
            _cand("c-0002", 0.2, "adapter"),
            _cand("c-0003", 0.2, "optimiser"),
        )
    }
    sigma2_eval, tau0_2, kappa, budget = 0.0004, 0.01, 1.0, 8.0

    terms = {
        cid: efe(citta, c, plan, prefs, gamma, kappa, budget, sigma2_eval, tau0_2) for cid, c in cands.items()
    }
    Q = selection_probabilities({k: t.G for k, t in terms.items()}, {k: 1.0 for k in terms})

    # analytic recomputation, independent of the module's internals
    def eig_hand(sig2: float) -> float:
        noise = sigma2_eval
        return 0.5 * math.log1p(sig2 / noise) + 3 * 0.5 * math.log1p(tau0_2 / (noise + sig2))

    def pref_hand(mu: float, sig2: float) -> float:
        s = math.sqrt(sig2)
        phi = math.exp(-0.5 * (mu / s) ** 2) / math.sqrt(2 * math.pi)
        Phi_neg = 0.5 * (1 + math.erf(-mu / s / math.sqrt(2)))
        e_neg = s * phi - mu * Phi_neg
        return prefs.beta * mu - prefs.lambda_ * e_neg

    G_hand = {}
    for cid, b in citta.candidates.items():
        G_hand[cid] = (
            -gamma.epi * eig_hand(b.sigma2) - gamma.prag * pref_hand(b.mu, b.sigma2) + kappa * 0.2 / budget
        )
    z = np.array([-G_hand[c] for c in cands])
    q_hand = np.exp(z - z.max())
    q_hand /= q_hand.sum()
    for cid, qh in zip(cands, q_hand, strict=True):
        assert abs(terms[cid].G - G_hand[cid]) < 1e-9
        assert abs(Q[cid] - qh) < 1e-6
    # the scores condition on the action: the decorative check passes and the known-bad candidate is last
    assert decorative_check({k: t.G for k, t in terms.items()}, Q, 0.05, 0.05).verdict == "pass"
    assert Q["c-0001"] == max(
        Q.values()
    )  # the known-good candidate is preferred under the prereg preferences
    batch = knapsack_batch(
        Q,
        cands,
        {k: t.EIG for k, t in terms.items()},
        budget,
        Shares(planted=0.1, sensors=0.1, f_epi=0.15),
        np.random.default_rng(0),
    )
    assert set(batch.execution) == set(cands) and batch.spent_gpu_h <= batch.budget_effective


def test_t0_touching_candidate_has_zero_probability() -> None:
    citta = Citta(version=0, surfaces={}, strategies={}, buckets={}, candidates={}, rho_pred={})
    prefs = Preferences(beta=1.0, lambda_=2.0, eta=1.0)
    plan = EvidencePlan(
        seeds=[1], heldout_rotation_id=None, sensors_to_read=[], stage="smoke", sequential_stage=0
    )
    good, bad = _cand("c-0001", 0.1, "f"), _cand("c-0002", 0.1, "f", surface="T0.kernel")
    tg = efe(citta, good, plan, prefs, Precision(epi=0.5, prag=1.0), 1.0, 8.0, 0.0004, 0.01)
    tb = efe(citta, bad, plan, prefs, Precision(epi=0.5, prag=1.0), 1.0, 8.0, 0.0004, 0.01)
    assert math.isinf(tb.G) and tb.pragmatic == -math.inf
    Q = selection_probabilities({"c-0001": tg.G, "c-0002": tb.G}, {"c-0001": 1.0, "c-0002": 1.0})
    assert Q == {"c-0001": 1.0, "c-0002": 0.0}


def test_game_llm_cycle27_ranking_and_verdict_reproduced() -> None:
    import json
    from pathlib import Path

    from pravrudhi_kernel.efe import rank_hypothesis_candidates

    fx = Path(__file__).parent / "fixtures"
    spec = json.loads((fx / "cycle27_candidates.json").read_text())
    want = json.loads((fx / "cycle27_ranking.json").read_text())
    got = rank_hypothesis_candidates(spec)
    assert got["degenerate"] == want["degenerate"]
    assert abs(got["entropy_nats"] - want["entropy_nats"]) < 1e-9
    for a, b in zip(got["ranking"], want["ranking"], strict=True):
        assert a["name"] == b["name"]
        for k in ("epistemic", "pragmatic", "cost", "total"):
            assert abs(a[k] - b[k]) < 1e-9, (a["name"], k)
    # planted: make every candidate's diagnosticity identical -> game-llm refuses, and so do we
    flat = json.loads(json.dumps(spec))
    for c in flat["candidates"]:
        c["diagnosticity"] = {"solve_is_affordable_at_serving": [0.5, 0.5]}
        c["payoff"] = {}
        c["cost"] = 0.0
    assert rank_hypothesis_candidates(flat)["degenerate"] is True
