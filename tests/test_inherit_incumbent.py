"""A night inherits the latest promoted adapter for its trainee as incumbent (recursion), else the base model."""
from pathlib import Path
from types import SimpleNamespace

from pravrudhi.application.execute import inherit_incumbent
from pravrudhi_kernel.ledger import LedgerWriter


def _ledger(root: Path, *, promote_model: str) -> None:
    (root / "research").mkdir()
    w = LedgerWriter.open(root / "research" / "ledger.jsonl", "0.1.0")
    bucket = {"task_family": "gsm8k-trainB", "target_model": promote_model, "corpus": "gsm8k"}
    w.append("propose", "proposer", {"op": "adapter", "recipe": {}}, epoch=0, night=4, candidate_id="c-0045",
             surface="W3.adapter", bucket=bucket, provenance="agama")
    w.append("spend", "executor", {"phase": "train", "steps": 10, "run_id": "n4-train-c-0045-1", "gpu_h": 0.1},
             epoch=0, night=4, candidate_id="c-0045")
    w.append("promote", "broker", {"tier": "T2"}, epoch=0, night=4, candidate_id="c-0045", surface="W3.adapter")


def test_inherits_promoted_adapter_for_same_trainee(tmp_path):
    _ledger(tmp_path, promote_model="Qwen/Qwen3-0.6B")
    jobs = tmp_path / "jobs"
    (jobs / "n4-train-c-0045-1" / "out" / "adapter").mkdir(parents=True)
    (jobs / "n4-train-c-0045-1" / "out" / "adapter" / "adapter_config.json").write_text("{}")
    cid, adapter = inherit_incumbent(tmp_path, SimpleNamespace(jobs_dir=str(jobs)), "Qwen/Qwen3-0.6B", log=lambda s: None)
    assert cid == "c-0045" and adapter == jobs / "n4-train-c-0045-1" / "out" / "adapter"


def test_other_trainee_or_missing_adapter_falls_back_to_base(tmp_path):
    _ledger(tmp_path, promote_model="Qwen/Qwen3-0.6B")
    jobs = tmp_path / "jobs"
    assert inherit_incumbent(tmp_path, SimpleNamespace(jobs_dir=str(jobs)), "Qwen/Qwen3-1.7B",
        log=lambda s: None) == ("c-0000", None)
    msgs = []
    assert inherit_incumbent(tmp_path, SimpleNamespace(jobs_dir=str(jobs)), "Qwen/Qwen3-0.6B", log=msgs.append) == ("c-0000",
        None)
    assert any("missing" in m for m in msgs)
