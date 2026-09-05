"""Container job: generate completions for a list of questions with a base model (+ optional LoRA adapter).

Runs inside the exec image with no network. Reads /in/items.jsonl (id, question) and /in/template.txt; writes
/out/completions.jsonl and /out/job_meta.json (what it loaded and what it measured).
It never sees gold answers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_dir_hash(model_dir: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(model_dir.glob("*")):
        if p.is_file() and (p.suffix in {".safetensors", ".json"} or p.name.endswith(".model")):
            h.update(p.name.encode())
            h.update(sha256_file(p).encode())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--adapter-dir", default=None)
    ap.add_argument("--items", default="/in/items.jsonl")
    ap.add_argument("--template", default="/in/template.txt")
    ap.add_argument("--out", default="/out")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(a.seed)
    model_dir = Path(a.model_dir)
    items = [json.loads(line) for line in Path(a.items).read_text().splitlines() if line.strip()]
    if a.limit:
        items = items[: a.limit]
    template = Path(a.template).read_text()
    t_load = time.monotonic()
    tok = AutoTokenizer.from_pretrained(model_dir, padding_side="left")
    dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16}[a.dtype]
    model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=dtype, device_map="cuda", attn_implementation="sdpa")
    adapter_hash = None
    if a.adapter_dir:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, a.adapter_dir)
        adapter_hash = model_dir_hash(Path(a.adapter_dir))
    model.eval()
    load_s = time.monotonic() - t_load
    torch.cuda.reset_peak_memory_stats()

    prompts = []
    for it in items:
        msgs = [{"role": "user", "content": template.replace("{question}", it["question"])}]
        prompts.append(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False))
    out_rows = []
    n_tok = 0
    t_gen = time.monotonic()
    torch.manual_seed(a.seed)
    torch.cuda.manual_seed_all(a.seed)
    for b in range(0, len(prompts), a.batch_size):
        batch = prompts[b : b + a.batch_size]
        enc = tok(batch, return_tensors="pt", padding=True).to("cuda")
        with torch.no_grad():
            out = model.generate(
                **enc,
                max_new_tokens=a.max_new_tokens,
                do_sample=a.temperature > 0,
                temperature=max(a.temperature, 1e-5),
                top_p=a.top_p,
                pad_token_id=tok.pad_token_id or tok.eos_token_id,
            )
        new = out[:, enc["input_ids"].shape[1] :]
        for j, row in enumerate(new):
            text = tok.decode(row, skip_special_tokens=True)
            n_tok += int((row != (tok.pad_token_id or tok.eos_token_id)).sum().item())
            out_rows.append({"id": items[b + j]["id"], "completion": text})
        print(
            f"batch {b // a.batch_size + 1}/{(len(prompts) + a.batch_size - 1) // a.batch_size} done",
            file=sys.stderr,
        )
    gen_s = time.monotonic() - t_gen
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "completions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in out_rows))
    meta = {
        "model": model_dir.name,
        "model_sha256": model_dir_hash(model_dir),
        "adapter_sha256": adapter_hash,
        "items_sha256": sha256_file(Path(a.items)),
        "template_sha256": sha256_file(Path(a.template)),
        "n_items": len(items),
        "seed": a.seed,
        "temperature": a.temperature,
        "top_p": a.top_p,
        "max_new_tokens": a.max_new_tokens,
        "batch_size": a.batch_size,
        "dtype": a.dtype,
        "template": Path(a.template).name,
        "tokens_generated": n_tok,
        "gen_s": gen_s,
        "load_s": load_s,
        "wall_s": gen_s + load_s,
        "tok_s": n_tok / gen_s if gen_s > 0 else None,
        "peak_gib_torch": torch.cuda.max_memory_allocated() / 2**30,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "transformers": __import__("transformers").__version__,
    }
    (out_dir / "job_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: meta[k] for k in ("n_items", "tokens_generated", "tok_s", "peak_gib_torch", "wall_s")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
