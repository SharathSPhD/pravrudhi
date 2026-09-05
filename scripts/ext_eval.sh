#!/usr/bin/env bash
# External proof-tier scoring with lm-evaluation-harness inside pravrudhi/ext-scorers, offline, datasets pre-cached.
# usage: scripts/ext_eval.sh <hf-repo-id> <tasks,comma> <out-dir> [adapter-dir] [limit]
# Produces <out-dir>/results.json (lm-eval's own output) and prints the accuracy lines. Never touches the ledger.
set -euo pipefail
MODEL="$1"; TASKS="$2"; OUT="$3"; ADAPTER="${4:-}"; LIMIT="${5:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HFH="${HF_HOME:-$HOME/.cache/huggingface}"
SNAP="$(ls -d "$HFH/hub/models--${MODEL//\//--}/snapshots/"*/ | head -1)"
REL="/models/${SNAP#$HFH/}"
mkdir -p "$OUT"
ARGS="pretrained=$REL,dtype=bfloat16,trust_remote_code=False"
MOUNTS=(-v "$HFH:/models:ro" -v "$ROOT/.pravrudhi/ext_cache:/cache:ro" -v "$OUT:/out:rw")
if [[ -n "$ADAPTER" ]]; then MOUNTS+=(-v "$ADAPTER:/adapter:ro"); ARGS="$ARGS,peft=/adapter"; fi
LIM=(); [[ -n "$LIMIT" ]] && LIM=(--limit "$LIMIT")
docker run --rm --gpus all --network none --user "$(id -u):$(id -g)" "${MOUNTS[@]}" \
  -e HF_HOME=/cache -e HF_DATASETS_CACHE=/cache/datasets -e HF_HUB_OFFLINE=1 -e HF_DATASETS_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  pravrudhi/ext-scorers:latest lm_eval --model hf --model_args "$ARGS" --tasks "$TASKS" --batch_size 32 \
  --output_path /out --log_samples "${LIM[@]}" 2>&1 | grep -vE "Warning|warn" | tail -25
f="$(find "$OUT" -name 'results_*.json' | sort | tail -1)"; [[ -n "$f" ]] && cp "$f" "$OUT/results.json" && python3 - "$OUT/results.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))["results"]
for t, m in r.items():
    keys = [k for k in m if k.endswith(",none") and not k.endswith("_stderr,none")]
    print("EXT", t, {k.split(",")[0]: round(m[k], 4) for k in keys}, {k.split(",")[0]: round(m[k], 4) for k in m if k.endswith("_stderr,none")})
PY
