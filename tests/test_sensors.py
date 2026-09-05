"""The H6 sensor screen, including the confound check that must be able to fail."""
import numpy as np

from pravrudhi.application.sensors import SensorReport, auroc, collect, evaluate
from pravrudhi_kernel.ledger import LedgerWriter

B = {"task_family": "gsm8k", "target_model": "m", "corpus": "c"}


def test_auroc_is_rank_based_and_ties_score_chance():
    assert auroc(np.array([1.0, 2.0, 3.0, 4.0]), np.array([0, 0, 1, 1])) == 1.0
    assert auroc(np.array([4.0, 3.0, 2.0, 1.0]), np.array([0, 0, 1, 1])) == 0.0
    assert auroc(np.array([1.0, 1.0, 1.0, 1.0]), np.array([0, 0, 1, 1])) == 0.5, "a constant feature is chance"
    assert auroc(np.array([1.0, 2.0]), np.array([1, 1])) == 0.5, "one class only is undefined, reported as chance"


def _ledger(tmp_path, rows):
    (tmp_path / "research").mkdir(exist_ok=True)
    p = tmp_path / "research" / "ledger.jsonl"
    w = LedgerWriter.open(p, "0.1.0")
    for cid, strategy, steps, delta in rows:
        w.append("propose", "proposer",
                 {"op": "adapter", "recipe": {"strategy": strategy, "sft": {"n_kept": 512, "epochs": 1},
                                              "lora": {"r": 8}}},
                 epoch=0, night=1, candidate_id=cid, surface="W3.adapter", bucket=B, provenance="agama")
        w.append("spend", "executor", {"phase": "train", "steps": steps, "run_id": f"r-{cid}",
                                       "train_loss": 0.5, "gpu_h": 0.02, "peak_gib": 10.0},
                 epoch=0, night=1, candidate_id=cid)
        w.append("observe", "kernel",
                 {"arm": "candidate", "stage": "screen",
                  "observed": {"metric": "pass_rate", "value": 0.5 + delta, "n_items": 100, "seeds": [0],
                               "delta_in": delta, "value_ref": 0.5},
                  "hashes": {}},
                 epoch=0, night=1, candidate_id=cid, surface="W3.adapter", bucket=B, provenance="pratyaksha")
    return p


def test_collect_pairs_training_with_outcome(tmp_path):
    p = _ledger(tmp_path, [("c-0001", "sft_rejection", 90, 0.05), ("c-0002", "grpo_verifiable", 20, -0.05)])
    X, y, ids = collect(p)
    assert X.shape == (2, 8) and list(y) == [1, 0] and ids == ["c-0001", "c-0002"]


def test_a_sensor_that_is_only_the_family_effect_does_not_survive_stratification(tmp_path):
    """Steps perfectly encodes family, and family perfectly encodes the outcome: pooled AUROC is 1.0, but inside
    each family the feature is constant and therefore chance. The report must not call this a sensor."""
    rows = [(f"c-{i:04d}", "sft_rejection", 90, 0.05) for i in range(22)]
    rows += [(f"c-{i:04d}", "grpo_verifiable", 20, -0.05) for i in range(22, 44)]
    r = evaluate(_ledger(tmp_path, rows), n_shuffle=200)
    assert r.auroc == 1.0 and r.n == 44
    assert not r.survives_stratification, "a pure family effect must not pass as an internal sensor"
    assert r.stratification_verdict == "no", "with enough points in each family this is a verdict, not ignorance"


def test_a_genuine_within_family_signal_does_survive(tmp_path):
    """Here steps predicts the outcome inside both families, which is what a real sensor looks like."""
    rows = []
    for i in range(24):
        rows.append((f"c-{i:04d}", "sft_rejection", 50 + i * 4, 0.05 if i >= 12 else -0.05))
        rows.append((f"c-{i + 100:04d}", "grpo_verifiable", 50 + i * 4, 0.05 if i >= 12 else -0.05))
    r = evaluate(_ledger(tmp_path, rows), n_shuffle=200)
    assert r.survives_stratification and min(v["auroc"] for v in r.stratified.values()) > 0.6


def test_an_empty_ledger_reports_chance_rather_than_failing(tmp_path):
    p = _ledger(tmp_path, [])
    r = evaluate(p, n_shuffle=50)
    assert isinstance(r, SensorReport) and r.n == 0 and r.auroc == 0.5 and not r.beats_charter_floor


def test_too_few_candidates_in_a_family_is_undetermined_not_a_failure(tmp_path):
    """Absence of evidence and evidence of absence must not look alike."""
    rows = [(f"c-{i:04d}", "sft_rejection", 50 + i * 4, 0.05 if i >= 3 else -0.05) for i in range(6)]
    rows += [(f"c-{i + 100:04d}", "grpo_verifiable", 50 + i * 4, 0.05 if i >= 3 else -0.05) for i in range(6)]
    r = evaluate(_ledger(tmp_path, rows), n_shuffle=100)
    assert r.stratification_verdict == "undetermined" and not r.survives_stratification
