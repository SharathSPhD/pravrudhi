"""LoRA GRPO job with a verifiable reward. Reads /in/prompts.jsonl (id, question, gold) — the gold here is from
the TRAIN split (never the sealed pool) — /in/template.txt and /in/recipe.json; writes /out/adapter and job_meta."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from common import model_dir_hash, read_jsonl, sha256_file

NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
FINAL = re.compile(r"(?i)final answer\s*[:=]?\s*\$?\s*(-?\d[\d,]*(?:\.\d+)?)")


def _norm(s: str) -> str:
    s = s.strip().replace(",", "").replace("$", "").rstrip(".")
    try:
        f = float(s)
    except ValueError:
        return s
    return str(int(f)) if f == int(f) else repr(f)


def predict(text: str) -> str | None:
    m = FINAL.findall(text)
    if m:
        return _norm(m[-1])
    n = NUM.findall(text)
    return _norm(n[-1]) if n else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--prompts", default="/in/prompts.jsonl")
    ap.add_argument("--template", default="/in/template.txt")
    ap.add_argument("--recipe", default="/in/recipe.json")
    ap.add_argument("--out", default="/out")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fp32", action="store_true", help="fp32 master weights (fallback when bf16 LoRA-GRPO produces NaN gradients)")
    a = ap.parse_args()
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    recipe = json.loads(Path(a.recipe).read_text())
    lora, g = recipe["lora"], recipe["grpo"]
    torch.manual_seed(a.seed)
    t0 = time.monotonic()
    tok = AutoTokenizer.from_pretrained(a.model_dir)
    template = Path(a.template).read_text()
    rows = read_jsonl(Path(a.prompts))
    ds = Dataset.from_list(
        [
            {"prompt": [{"role": "user", "content": template.replace("{question}", r["question"])}], "gold": _norm(r["gold"])}
            for r in rows
        ]
    )

    def reward(completions, gold, **kw):  # type: ignore[no-untyped-def]
        out = []
        for c, gd in zip(completions, gold, strict=True):
            text = c[0]["content"] if isinstance(c, list) else str(c)
            out.append(1.0 if predict(text) == gd else 0.0)
        return out

    targets = {
        "all-linear": "all-linear",
        "attention": ["q_proj", "k_proj", "v_proj", "o_proj"],
        "mlp": ["gate_proj", "up_proj", "down_proj"],
    }[lora["target_modules"]]
    peft_cfg = LoraConfig(
        r=lora["r"], lora_alpha=lora["alpha"], lora_dropout=lora["dropout"], target_modules=targets, task_type="CAUSAL_LM"
    )
    out = Path(a.out)
    cfg = GRPOConfig(
        output_dir=str(out / "trainer"),
        max_steps=g["steps"],
        num_generations=g["group_size"],
        per_device_train_batch_size=g["group_size"] * g["prompts_per_step"],
        gradient_accumulation_steps=1,
        max_completion_length=g["max_completion_tokens"],
        learning_rate=g["lr"],
        beta=g["beta_kl"],
        bf16=not a.fp32,
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        seed=a.seed,
        gradient_checkpointing=False,
        temperature=0.8,
        max_grad_norm=1.0,
        loss_type="dr_grpo",
        scale_rewards="none",
        chat_template_kwargs={"enable_thinking": False},
        model_init_kwargs={"dtype": torch.float32 if a.fp32 else torch.bfloat16, "attn_implementation": "sdpa"},
    )
    trainer = GRPOTrainer(
        model=a.model_dir, reward_funcs=reward, args=cfg, train_dataset=ds, processing_class=tok, peft_config=peft_cfg
    )
    result = trainer.train()
    trainer.model.save_pretrained(str(out / "adapter"))
    tok.save_pretrained(str(out / "adapter"))
    logs = [{k: v for k, v in log.items() if isinstance(v, int | float)} for log in trainer.state.log_history]
    meta = {
        "job": "train_grpo",
        "model_sha256": model_dir_hash(Path(a.model_dir)),
        "prompts_sha256": sha256_file(Path(a.prompts)),
        "recipe_sha256": sha256_file(Path(a.recipe)),
        "n_prompts": len(rows),
        "steps": int(trainer.state.global_step),
        "train_loss": float(result.training_loss),
        "wall_s": time.monotonic() - t0,
        "peak_gib_torch": torch.cuda.max_memory_allocated() / 2**30,
        "log_history": logs,
        "seed": a.seed,
        "adapter_sha256": model_dir_hash(out / "adapter"),
    }
    (out / "job_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: meta[k] for k in ("n_prompts", "steps", "train_loss", "wall_s", "peak_gib_torch")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
