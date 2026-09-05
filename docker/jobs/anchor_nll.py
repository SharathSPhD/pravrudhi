"""Canary job: mean per-token NLL of a frozen anchor set under base (+ optional adapter). Reads /in/anchors.jsonl
(text); writes /out/anchor.json {nll_mean, n_tokens} and job_meta."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from common import load_model, model_dir_hash, read_jsonl, sha256_file


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--adapter-dir", default=None)
    ap.add_argument("--anchors", default="/in/anchors.jsonl")
    ap.add_argument("--out", default="/out")
    ap.add_argument("--batch-size", type=int, default=8)
    a = ap.parse_args()
    import torch

    t0 = time.monotonic()
    model, tok = load_model(Path(a.model_dir), Path(a.adapter_dir) if a.adapter_dir else None)
    model.eval()
    tok.padding_side = "right"
    rows = read_jsonl(Path(a.anchors))
    total_nll, total_tok = 0.0, 0
    for b in range(0, len(rows), a.batch_size):
        texts = [r["text"] for r in rows[b : b + a.batch_size]]
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=1024).to("cuda")
        with torch.no_grad():
            logits = model(**enc).logits[:, :-1].float()
        labels = enc["input_ids"][:, 1:]
        mask = enc["attention_mask"][:, 1:].bool()
        nll = torch.nn.functional.cross_entropy(
            logits.reshape(-1, logits.size(-1)), labels.reshape(-1), reduction="none"
        ).view_as(labels)
        total_nll += float(nll[mask].sum().item())
        total_tok += int(mask.sum().item())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = {"nll_mean": total_nll / max(1, total_tok), "n_tokens": total_tok, "n_texts": len(rows)}
    (out / "anchor.json").write_text(json.dumps(res, indent=2) + "\n")
    meta = {
        "job": "anchor_nll",
        "model_sha256": model_dir_hash(Path(a.model_dir)),
        "anchors_sha256": sha256_file(Path(a.anchors)),
        "adapter_sha256": model_dir_hash(Path(a.adapter_dir)) if a.adapter_dir else None,
        "wall_s": time.monotonic() - t0,
        **res,
    }
    (out / "job_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
