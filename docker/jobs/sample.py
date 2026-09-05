"""Rejection-sampling job: N completions per train prompt from the incumbent; the kernel keeps the verified ones.

Reads /in/prompts.jsonl (id, question) and /in/template.txt; writes /out/samples.jsonl (id, sample_index, completion)
and /out/job_meta.json. Never sees gold answers.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from common import chat_prompt, load_model, model_dir_hash, read_jsonl, sha256_file, write_jsonl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--adapter-dir", default=None)
    ap.add_argument("--prompts", default="/in/prompts.jsonl")
    ap.add_argument("--template", default="/in/template.txt")
    ap.add_argument("--out", default="/out")
    ap.add_argument("--n-samples", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--batch-size", type=int, default=32)
    a = ap.parse_args()
    import torch

    torch.manual_seed(a.seed)
    torch.cuda.manual_seed_all(a.seed)
    t0 = time.monotonic()
    model, tok = load_model(Path(a.model_dir), Path(a.adapter_dir) if a.adapter_dir else None)
    model.eval()
    template = Path(a.template).read_text()
    rows = read_jsonl(Path(a.prompts))
    prompts = [(r["id"], k, chat_prompt(tok, template, r["question"])) for r in rows for k in range(a.n_samples)]
    out = []
    n_tok = 0
    t1 = time.monotonic()
    pad = tok.pad_token_id or tok.eos_token_id
    for b in range(0, len(prompts), a.batch_size):
        batch = prompts[b : b + a.batch_size]
        enc = tok([p[2] for p in batch], return_tensors="pt", padding=True).to("cuda")
        with torch.no_grad():
            gen = model.generate(
                **enc, max_new_tokens=a.max_new_tokens, do_sample=True, temperature=a.temperature, top_p=0.95, pad_token_id=pad
            )
        new = gen[:, enc["input_ids"].shape[1] :]
        for (pid, k, _), row in zip(batch, new, strict=True):
            n_tok += int((row != pad).sum().item())
            out.append({"id": pid, "sample_index": k, "completion": tok.decode(row, skip_special_tokens=True)})
        print(f"batch {b // a.batch_size + 1}/{(len(prompts) + a.batch_size - 1) // a.batch_size}", file=sys.stderr)
    gen_s = time.monotonic() - t1
    outd = Path(a.out)
    outd.mkdir(parents=True, exist_ok=True)
    write_jsonl(outd / "samples.jsonl", out)
    meta = {
        "job": "sample",
        "model_sha256": model_dir_hash(Path(a.model_dir)),
        "prompts_sha256": sha256_file(Path(a.prompts)),
        "n_prompts": len(rows),
        "n_samples": a.n_samples,
        "tokens_generated": n_tok,
        "gen_s": gen_s,
        "tok_s": n_tok / gen_s if gen_s else None,
        "wall_s": time.monotonic() - t0,
        "temperature": a.temperature,
        "peak_gib_torch": torch.cuda.max_memory_allocated() / 2**30,
        "seed": a.seed,
    }
    (outd / "job_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: meta[k] for k in ("n_prompts", "tokens_generated", "tok_s", "wall_s")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
