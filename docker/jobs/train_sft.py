"""LoRA SFT job on kernel-verified samples. Reads /in/train.jsonl (prompt, completion) and /in/recipe.json;
writes the adapter to /out/adapter and /out/job_meta.json."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from common import model_dir_hash, read_jsonl, sha256_file


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--train", default="/in/train.jsonl")
    ap.add_argument("--recipe", default="/in/recipe.json")
    ap.add_argument("--out", default="/out")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    recipe = json.loads(Path(a.recipe).read_text())
    lora, sft = recipe["lora"], recipe["sft"]
    torch.manual_seed(a.seed)
    t0 = time.monotonic()
    tok = AutoTokenizer.from_pretrained(a.model_dir)
    rows = read_jsonl(Path(a.train))
    ds = Dataset.from_list(
        [
            {"messages": [{"role": "user", "content": r["prompt"]}, {"role": "assistant", "content": r["completion"]}]}
            for r in rows
        ]
    )
    targets = {
        "all-linear": "all-linear",
        "attention": ["q_proj", "k_proj", "v_proj", "o_proj"],
        "mlp": ["gate_proj", "up_proj", "down_proj"],
    }[lora["target_modules"]]
    peft_cfg = LoraConfig(
        r=lora["r"], lora_alpha=lora["alpha"], lora_dropout=lora["dropout"], target_modules=targets, task_type="CAUSAL_LM"
    )
    out = Path(a.out)
    # memory arithmetic: at most 8192 tokens per micro-batch (measured 17 GiB at 8 x 1024); accumulate to the recipe's batch
    micro = max(1, min(int(sft["batch_size"]), 8192 // int(sft["max_seq_len"])))
    accum = max(1, -(-int(sft["batch_size"]) // micro))
    cfg = SFTConfig(
        output_dir=str(out / "trainer"),
        num_train_epochs=sft["epochs"],
        per_device_train_batch_size=micro,
        gradient_accumulation_steps=accum,
        learning_rate=sft["lr"],
        warmup_ratio=sft["warmup_ratio"],
        lr_scheduler_type="cosine",
        logging_steps=5,
        save_strategy="no",
        bf16=True,
        max_length=sft["max_seq_len"],
        gradient_checkpointing=True,
        report_to=[],
        seed=a.seed,
        dataloader_num_workers=0,
        assistant_only_loss=False,
    )
    trainer = SFTTrainer(model=a.model_dir, args=cfg, train_dataset=ds, processing_class=tok, peft_config=peft_cfg)
    trainer.model.config.use_cache = False
    result = trainer.train()
    trainer.model.save_pretrained(str(out / "adapter"))
    tok.save_pretrained(str(out / "adapter"))
    logs = [{k: v for k, v in log.items() if isinstance(v, int | float)} for log in trainer.state.log_history]
    meta = {
        "job": "train_sft",
        "model_sha256": model_dir_hash(Path(a.model_dir)),
        "train_sha256": sha256_file(Path(a.train)),
        "recipe_sha256": sha256_file(Path(a.recipe)),
        "n_train": len(rows),
        "steps": int(trainer.state.global_step),
        "train_loss": float(result.training_loss),
        "wall_s": time.monotonic() - t0,
        "peak_gib_torch": torch.cuda.max_memory_allocated() / 2**30,
        "log_history": logs,
        "seed": a.seed,
        "adapter_sha256": model_dir_hash(out / "adapter"),
    }
    (out / "job_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: meta[k] for k in ("n_train", "steps", "train_loss", "wall_s", "peak_gib_torch")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
