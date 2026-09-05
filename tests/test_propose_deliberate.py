"""Proposal and deliberation against a scripted chat endpoint (test double, tests only) and a scratch ledger."""

import json
from pathlib import Path

import yaml

from pravrudhi.application.deliberate import DecorativeAbort, deliberate
from pravrudhi.application.propose import ledger_summary, propose, strategy_switch_rate
from pravrudhi.models.openai_compat import ChatResult
from pravrudhi_kernel.ledger import LedgerWriter, replay, verify

BUCKET = {"task_family": "gsm8k-test", "target_model": "Qwen/Qwen3-4B", "corpus": "gsm8k-test-train"}
CANDS = [
    {"strategy": "sft_rejection", "execution_family": "optimiser", "sft": {"lr": 2e-4}, "rationale": "higher lr"},
    {"strategy": "sft_rejection", "execution_family": "adapter", "lora": {"r": 16, "alpha": 32}, "rationale": "wider adapter"},
    {"strategy": "grpo_verifiable", "execution_family": "grpo", "grpo": {"steps": 10}, "rationale": "on-policy"},
    {"strategy": "full_finetune", "execution_family": "optimiser", "rationale": "out of grammar"},
    {"strategy": "sft_rejection", "execution_family": "optimiser", "sft": {"lr": 2e-4}, "rationale": "duplicate of the first"},
]
PREDS = [
    {"candidate_index": 0, "delta_in": 0.02, "conf": 0.6},
    {"candidate_index": 1, "delta_in": -0.01, "conf": 0.5},
    {"candidate_index": 2, "delta_in": 0.05, "conf": 0.7},
]


class ScriptedClient:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, **kw) -> ChatResult:  # type: ignore[no-untyped-def]
        self.calls += 1
        text = json.dumps(CANDS) if self.calls == 1 else json.dumps(PREDS)
        return ChatResult(
            text="<think>reasoning</think>" + text, model="scripted", prompt_tokens=10, completion_tokens=20, wall_s=0.01
        )


def _root(tmp_path: Path) -> tuple[Path, LedgerWriter]:
    (tmp_path / "research" / "prereg").mkdir(parents=True)
    (tmp_path / "harness" / "prompts" / "proposer").mkdir(parents=True)
    (tmp_path / "harness" / "prompts" / "predictor").mkdir(parents=True)
    src = Path(__file__).resolve().parents[1] / "harness" / "prompts"
    (tmp_path / "harness" / "prompts" / "proposer" / "v1.md").write_text((src / "proposer" / "v1.md").read_text())
    (tmp_path / "harness" / "prompts" / "predictor" / "v1.md").write_text((src / "predictor" / "v1.md").read_text())
    cfg = {
        "tau0_2": 0.01,
        "kappa": 1.0,
        "f_epi": 0.15,
        "rho_floor": 0.05,
        "shares": {"planted": 0.0, "sensors": 0.0, "f_epi": 0.15},
        "decorative": {"cv_min": 0.05, "mi_min_bits": 0.05},
        "preferences": {"beta": 40.0, "lambda": 80.0, "eta": 5.0, "zeta": 1.0},
    }
    (tmp_path / "research" / "prereg" / "controller.yaml").write_text(yaml.safe_dump(cfg))
    w = LedgerWriter.open(tmp_path / "research" / "ledger.jsonl", "0.1.0")
    w.append(
        "propose",
        "kernel",
        {"op": "baseline", "edit_family": "baseline", "strategy": "none"},
        epoch=0,
        night=0,
        cycle=0,
        candidate_id="c-0000",
        surface="W3.adapter",
        bucket=BUCKET,
        provenance="agama",
    )
    return tmp_path, w


def test_propose_validates_seals_and_writes_rows(tmp_path: Path) -> None:
    root, w = _root(tmp_path)
    client = ScriptedClient()
    accepted = propose(
        root,
        w,
        client,
        night=1,
        k=4,
        model="Qwen/Qwen3-4B",
        bucket=BUCKET,
        prompts_dir=root / "harness" / "prompts",
        sealed_dir=root / ".pravrudhi" / "kernel" / "sealed" / "predictions",
        incumbent_id="c-0000",
        sigma_seed=0.03,
        temperature=0.7,
        max_tokens=512,
        rethink_m=6,
        log=lambda s: None,
    )
    ids = [c for c, _ in accepted]
    assert ids == ["c-0001", "c-0002", "c-0003"]  # grammar refusal and duplicate dropped
    st = replay(root / "research" / "ledger.jsonl")
    kinds = [json.loads(line)["kind"] for line in (root / "research" / "ledger.jsonl").read_text().splitlines()]
    assert kinds.count("propose") == 4 and kinds.count("predict") == 3
    bad = [
        json.loads(line) for line in (root / "research" / "ledger.jsonl").read_text().splitlines() if '"bad_candidate"' in line
    ]
    assert len(bad) == 1 and "strategy" in bad[0]["payload"]["detail"]
    sealed = root / ".pravrudhi" / "kernel" / "sealed" / "predictions" / "night_1.jsonl"
    assert sealed.stat().st_mode & 0o777 == 0o600
    rows = [json.loads(line) for line in sealed.read_text().splitlines()]
    assert {r["candidate_id"] for r in rows} == set(ids) and all(len(r["hash"]) == 64 for r in rows)
    assert verify(root / "research" / "ledger.jsonl").ok and set(st.badges) >= set(ids)
    summary, inc, consecutive = ledger_summary(root / "research" / "ledger.jsonl", "c-0000")
    assert "c-0001" in summary and inc is None and consecutive == 0


def test_deliberate_selects_within_budget_and_writes_select_rows(tmp_path: Path) -> None:
    root, w = _root(tmp_path)
    propose(
        root,
        w,
        ScriptedClient(),
        night=1,
        k=4,
        model="Qwen/Qwen3-4B",
        bucket=BUCKET,
        prompts_dir=root / "harness" / "prompts",
        sealed_dir=root / ".pravrudhi" / "kernel" / "sealed" / "predictions",
        incumbent_id="c-0000",
        sigma_seed=0.03,
        temperature=0.7,
        max_tokens=512,
        rethink_m=6,
        log=lambda s: None,
    )
    order = deliberate(
        root,
        w,
        night=1,
        budget_gpu_h=3.0,
        sigma_seed=0.03,
        incumbent_id="c-0000",
        harness_hash="h" * 64,
        model_hash="m" * 64,
        rng_seed=1,
        log=lambda s: None,
    )
    assert set(order) <= {"c-0001", "c-0002", "c-0003"} and order
    sel = json.loads((root / "research" / "last_select.json").read_text())
    assert sel["verdict"]["verdict"] == "pass" and set(sel["scores"]) == {"c-0001", "c-0002", "c-0003"}
    rows = [json.loads(line) for line in (root / "research" / "ledger.jsonl").read_text().splitlines()]
    selects = [r for r in rows if r["kind"] == "select"]
    assert len(selects) == len(order) and all(r["payload"]["decorative"]["verdict"] == "pass" for r in selects)
    assert all("strategy" in r["payload"] and r["payload"]["plan"]["stage"] == "screen" for r in selects)
    sw, n, ci = strategy_switch_rate(root / "research" / "ledger.jsonl")
    assert n == len(order) - 1 and 0 <= sw <= n


def test_deliberate_aborts_when_scores_do_not_condition_on_the_action(tmp_path: Path) -> None:
    root, w = _root(tmp_path)
    # three identical recipes cannot be proposed (dedup), so plant identical posteriors by proposing one candidate twice
    # with different rationale-only differences is also deduped; instead craft propose rows directly with identical recipes
    rec = {
        "strategy": "sft_rejection",
        "execution_family": "optimiser",
        "lora": {"r": 8, "alpha": 16, "dropout": 0.0, "target_modules": "all-linear"},
        "sft": {
            "n_kept": 512,
            "filter": "all_correct",
            "epochs": 1,
            "lr": 1e-4,
            "warmup_ratio": 0.03,
            "max_seq_len": 1024,
            "batch_size": 8,
        },
        "grpo": {"steps": 20, "group_size": 4, "prompts_per_step": 4, "max_completion_tokens": 256, "lr": 5e-6, "beta_kl": 0.04},
        "eval_template": "gsm8k_v1",
        "rationale": "",
    }
    for i in (1, 2, 3):
        w.append(
            "propose",
            "proposer",
            {"op": "adapter", "recipe": rec, "strategy": "sft_rejection", "edit_family": "optimiser"},
            epoch=0,
            night=1,
            cycle=i,
            candidate_id=f"c-{i:04d}",
            surface="W3.adapter",
            bucket=BUCKET,
            provenance="agama",
        )
    try:
        deliberate(
            root,
            w,
            night=1,
            budget_gpu_h=3.0,
            sigma_seed=0.03,
            incumbent_id="c-0000",
            harness_hash="h" * 64,
            model_hash="m" * 64,
            rng_seed=1,
            log=lambda s: None,
        )
    except DecorativeAbort:
        pass
    else:
        raise AssertionError("expected DecorativeAbort")
    rows = [json.loads(line) for line in (root / "research" / "ledger.jsonl").read_text().splitlines()]
    assert any(r["kind"] == "audit" and r["payload"].get("kind") == "decorative_controller" for r in rows)
