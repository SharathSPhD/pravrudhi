"""ADR-0015: a withdrawn observation leaves the candidate's posterior on replay; the chain is untouched."""
from pravrudhi_kernel.ledger import LedgerWriter, replay
from pravrudhi_kernel.ledger.verify import verify

B = {"task_family": "gsm8k", "target_model": "m", "corpus": "c"}


def _obs(w, cid, delta, seq_hint):
    return w.append(
        "observe", "kernel",
        {"arm": "candidate", "stage": "screen", "observed": {"metric": "pass_rate", "value": 0.5 + delta, "n_items": 100,
         "seeds": [0], "delta_in": delta, "value_ref": 0.5}, "hashes": {}},
        epoch=0, night=1, candidate_id=cid, surface="W3.adapter", bucket=B, provenance="pratyaksha",
    )


def test_withdrawn_observation_is_dropped(tmp_path):
    p = tmp_path / "ledger.jsonl"
    w = LedgerWriter.open(p, "0.1.0")
    w.append("propose", "proposer", {"op": "adapter", "recipe": {}}, epoch=0, night=1, candidate_id="c-0001",
             surface="W3.adapter", bucket=B, provenance="agama")
    bad = _obs(w, "c-0001", 0.015, 1)
    _obs(w, "c-0001", -0.055, 2)
    before = replay(p)
    assert before.candidates["c-0001"].n_obs == 2
    w.append("sublate", "auditor", {"kind": "observation_withdrawn", "target_seq": bad.seq, "reason": "wrong reference arm"},
             epoch=0, night=1, candidate_id="c-0001", surface="W3.adapter", provenance="anumana")
    after = replay(p)
    assert after.candidates["c-0001"].n_obs == 1 and after.candidates["c-0001"].xs == [-0.055]
    assert after.sublations == 1 and verify(p).ok


def test_withdrawn_promotion_is_not_a_promotion(tmp_path):
    p = tmp_path / "ledger.jsonl"
    w = LedgerWriter.open(p, "0.1.0")
    w.append("propose", "proposer", {"op": "harness"}, epoch=0, night=1, candidate_id="c-0060",
             surface="H3.prompt", bucket=B, provenance="agama")
    pr = w.append("promote", "broker", {"tier": "T2"}, epoch=0, night=1, candidate_id="c-0060", surface="H3.prompt")
    assert replay(p).candidates["c-0060"].promoted
    w.append("sublate", "auditor", {"kind": "promotion_withdrawn", "target_seq": pr.seq, "reason": "external tier"},
             epoch=0, night=1, candidate_id="c-0060", surface="H3.prompt", provenance="pratyaksha")
    st = replay(p)
    assert not st.candidates["c-0060"].promoted and st.promoted == {} and verify(p).ok
