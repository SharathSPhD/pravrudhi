"""ADR-0016: sft.init=incumbent continues the incumbent adapter; falls back to base with an audit when there is none."""
from pathlib import Path
from types import SimpleNamespace

from pravrudhi.application.execute import init_args
from pravrudhi.targets.lora_grammar import parse_recipe

REC = {
    "strategy": "sft_rejection", "execution_family": "data_mixture",
    "lora": {"r": 8, "alpha": 16, "dropout": 0.1, "target_modules": "attention"},
    "sft": {"n_kept": 256, "teacher": "incumbent", "init": "incumbent", "filter": "all_correct", "epochs": 1,
            "lr": 5e-5, "warmup_ratio": 0.05, "max_seq_len": 1024, "batch_size": 8},
    "grpo": {"steps": 20, "group_size": 4, "prompts_per_step": 1, "max_completion_tokens": 128, "lr": 5e-6, "beta_kl": 0.0},
    "eval_template": "gsm8k_v1", "rationale": "continue the incumbent",
}


class W:
    def __init__(self):
        self.rows = []

    def append(self, kind, actor, payload, **kw):
        self.rows.append((kind, payload))


def test_grammar_accepts_init_and_defaults_to_base():
    rec = parse_recipe(REC)
    assert not isinstance(rec, str) and rec.sft.init == "incumbent"
    plain = parse_recipe({**REC, "sft": {k: v for k, v in REC["sft"].items() if k != "init"}})
    assert plain.sft.init == "base"
    assert isinstance(parse_recipe({**REC, "sft": {**REC["sft"], "init": "merged"}}), str)


def test_init_args_mounts_incumbent_or_falls_back():
    rec = parse_recipe(REC)
    w = W()
    ctx = SimpleNamespace(incumbent_adapter=Path("/jobs/n4/out/adapter"), night=5)
    assert init_args(ctx, w, "c-0060", rec) == (["--init-adapter", "/init"], {"/jobs/n4/out/adapter": "/init"})
    ctx_base = SimpleNamespace(incumbent_adapter=None, night=5)
    assert init_args(ctx_base, w, "c-0060", rec) == ([], None)
    assert w.rows and w.rows[-1][1]["kind"] == "init_fallback"
    base_rec = parse_recipe({**REC, "sft": {**REC["sft"], "init": "base"}})
    assert init_args(ctx, w, "c-0061", base_rec) == ([], None)
