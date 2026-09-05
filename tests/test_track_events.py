"""Track scoping of the evidence renderers: harness blocks and LoRA rows never mix."""
from pathlib import Path

from pravrudhi.application.evidence import render_first_night, track_events
from pravrudhi_kernel.ledger import LedgerWriter

B_M = {"task_family": "gsm8k-trainB", "target_model": "Qwen/Qwen3-0.6B", "corpus": "gsm8k"}
B_H = {"task_family": "mbppplus", "target_model": "Qwen/Qwen3-1.7B", "corpus": "mbpp"}


def _ledger(tmp_path: Path) -> Path:
    (tmp_path / "research").mkdir()
    p = tmp_path / "research" / "ledger.jsonl"
    w = LedgerWriter.open(p, "0.1.0")
    w.append("audit", "kernel", {"kind": "night_start", "track": "lora"}, epoch=0, night=1)
    w.append("propose", "proposer", {"op": "adapter", "strategy": "sft_rejection", "edit_family": "optimiser"},
             epoch=0, night=1, candidate_id="c-0001", surface="W3.adapter", bucket=B_M, provenance="agama")
    w.append("audit", "kernel", {"kind": "night_end", "spent_gpu_h": 0.1, "outcomes": {"c-0001": "pruned"}}, epoch=0, night=1)
    w.append("audit", "kernel", {"kind": "night_start", "track": "harness"}, epoch=0, night=1)
    w.append("propose", "proposer", {"op": "harness", "strategy": "retry_policy", "edit_family": "retries"},
             epoch=0, night=1, candidate_id="c-0002", surface="H3.prompt", bucket=B_H, provenance="agama")
    w.append("audit", "controller", {"kind": "strategy_switch_rate", "switches": 1, "n": 1, "wilson": [0, 1]}, epoch=0, night=1)
    w.append("audit", "kernel", {"kind": "night_end", "spent_gpu_h": 0.0, "outcomes": {}, "track": "harness"}, epoch=0, night=1)
    w.append("audit", "auditor", {"kind": "external_eval", "track": "H", "tool": "evalplus"}, epoch=0, night=1)
    return p


def test_tracks_are_disjoint_and_complete(tmp_path):
    p = _ledger(tmp_path)
    lora = [e.seq for e in track_events(p, "lora")]
    harness = [e.seq for e in track_events(p, "harness")]
    assert set(lora) & set(harness) == set()
    assert sorted(lora + harness) == list(range(9))
    assert lora == [0, 1, 2, 3]
    assert harness == [4, 5, 6, 7, 8]


def test_renders_do_not_bleed(tmp_path):
    p = _ledger(tmp_path)
    m = render_first_night(p, 1)
    h = render_first_night(p, 1, track="harness")
    assert "c-0001" in m and "c-0002" not in m and "Harness" not in m
    assert "c-0002" in h and "c-0001" not in h and "Harness track night 1" in h
