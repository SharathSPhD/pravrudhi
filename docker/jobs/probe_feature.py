"""Probe job: linear probe of the residual stream at a named layer against item labels. Reads /in/items.jsonl
(id, text, label) and /in/monitor.json {feature, layer, ...}; writes /out/probe.json {feature, layer, n_train,
n_test, metric, r2 or accuracy, weights_sha256} and job_meta.json with model/items/monitor hashes.

The fit is a closed-form ridge regression -- no numpy, no sklearn, just the torch tensors `common.load_model`
already pulls in. A label set of exactly {0, 1} is scored by held-out accuracy (the probe is a classifier); any
other label set is scored by held-out r2 (the probe is a regressor). Nothing here is defaulted: `feature` and
`layer` must be present in monitor.json, and the split sizes and metric are read back from what was actually
computed, not asserted up front.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

from common import load_model, model_dir_hash, read_jsonl, sha256_file


def _mean_pool(hidden: Any, mask: Any) -> Any:
    """Residual stream at one layer, averaged over the real (non-pad) tokens of each sequence."""
    m = mask.unsqueeze(-1).to(hidden.dtype)
    return (hidden * m).sum(dim=1) / m.sum(dim=1).clamp_min(1.0)


def collect_features(model: Any, tok: Any, texts: list[str], layer: int, batch_size: int) -> Any:
    import torch

    feats = []
    for b in range(0, len(texts), batch_size):
        chunk = texts[b : b + batch_size]
        enc = tok(chunk, return_tensors="pt", padding=True, truncation=True, max_length=1024).to("cuda")
        with torch.no_grad():
            out = model(**enc, output_hidden_states=True)
        hidden = out.hidden_states[layer].float()
        feats.append(_mean_pool(hidden, enc["attention_mask"]).cpu())
    return torch.cat(feats, dim=0)


def ridge_fit(x_train: Any, y_train: Any, ridge_lambda: float) -> tuple[Any, Any, Any]:
    """Closed-form ridge with an intercept, via mean-centering: w minimizes ||Xc w - yc||^2 + lambda ||w||^2."""
    import torch

    mean_x = x_train.mean(dim=0)
    mean_y = y_train.mean()
    xc = x_train - mean_x
    yc = y_train - mean_y
    d = xc.shape[1]
    a = xc.T @ xc + ridge_lambda * torch.eye(d, dtype=xc.dtype)
    w = torch.linalg.solve(a, xc.T @ yc)
    return w, mean_x, mean_y


def ridge_predict(x: Any, w: Any, mean_x: Any, mean_y: Any) -> Any:
    return (x - mean_x) @ w + mean_y


def split_indices(n: int, test_frac: float, seed: int) -> tuple[list[int], list[int]]:
    """A deterministic held-out split: shuffle indices under `seed`, take the first share as the test set."""
    perm = list(range(n))
    random.Random(seed).shuffle(perm)
    n_test = int(n * test_frac)
    return perm[n_test:], perm[:n_test]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--adapter-dir", default=None)
    ap.add_argument("--items", default="/in/items.jsonl")
    ap.add_argument("--monitor", default="/in/monitor.json")
    ap.add_argument("--out", default="/out")
    ap.add_argument("--batch-size", type=int, default=8)
    a = ap.parse_args()
    import torch

    t0 = time.monotonic()
    monitor = json.loads(Path(a.monitor).read_text())
    feature = monitor["feature"]
    layer = int(monitor["layer"])
    test_frac = float(monitor.get("test_frac", 0.2))
    ridge_lambda = float(monitor.get("ridge_lambda", 1.0))
    seed = int(monitor.get("seed", 0))

    model, tok = load_model(Path(a.model_dir), Path(a.adapter_dir) if a.adapter_dir else None)
    model.eval()
    tok.padding_side = "right"

    rows = read_jsonl(Path(a.items))
    texts = [r["text"] for r in rows]
    labels = torch.tensor([float(r["label"]) for r in rows], dtype=torch.float32)
    is_binary = set(labels.tolist()) <= {0.0, 1.0}

    x = collect_features(model, tok, texts, layer, a.batch_size)
    train_idx, test_idx = split_indices(len(rows), test_frac, seed)
    x_train, y_train = x[train_idx], labels[train_idx]
    x_test, y_test = x[test_idx], labels[test_idx]

    w, mean_x, mean_y = ridge_fit(x_train, y_train, ridge_lambda)
    pred_test = ridge_predict(x_test, w, mean_x, mean_y)

    if is_binary:
        acc = float((pred_test.round().clamp(0, 1) == y_test).float().mean().item())
        metric_name, metric_value = "accuracy", acc
    else:
        ss_res = float(((y_test - pred_test) ** 2).sum().item())
        ss_tot = float(((y_test - y_test.mean()) ** 2).sum().item())
        metric_name, metric_value = "r2", 1.0 - ss_res / ss_tot

    weights_sha256 = hashlib.sha256(json.dumps(w.tolist()).encode()).hexdigest()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = {
        "feature": feature,
        "layer": layer,
        "n_train": len(train_idx),
        "n_test": len(test_idx),
        "metric": metric_name,
        metric_name: metric_value,
        "weights_sha256": weights_sha256,
    }
    (out / "probe.json").write_text(json.dumps(res, indent=2, sort_keys=True) + "\n")
    meta = {
        "job": "probe_feature",
        "model_sha256": model_dir_hash(Path(a.model_dir)),
        "adapter_sha256": model_dir_hash(Path(a.adapter_dir)) if a.adapter_dir else None,
        "items_sha256": sha256_file(Path(a.items)),
        "monitor_sha256": sha256_file(Path(a.monitor)),
        "wall_s": time.monotonic() - t0,
        **res,
    }
    (out / "job_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
