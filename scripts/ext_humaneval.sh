#!/usr/bin/env bash
# External proof for the harness track: run the agent harness on HumanEval+ (never in the loop) with a fixed model,
# then score with EvalPlus's own evaluator. usage: scripts/ext_humaneval.sh <hf-repo-id> <harness.json> <out-dir> [seed]
set -euo pipefail
MODEL="$1"; HARNESS="$2"; OUT="$3"; SEED="${4:-0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HFH="${HF_HOME:-$HOME/.cache/huggingface}"
SNAP="$(ls -d "$HFH/hub/models--${MODEL//\//--}/snapshots/"*/ | head -1)"; REL="/models/${SNAP#$HFH/}"
mkdir -p "$OUT/in" "$OUT/out"
python3 - "$ROOT/.pravrudhi/ext_cache/humanevalplus.jsonl" "$OUT/in/items.jsonl" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
open(sys.argv[2], "w").write("".join(json.dumps({"id": r["task_id"], "question": r["prompt"]}) + "\n" for r in rows))
print("items", len(rows))
PY
cp "$HARNESS" "$OUT/in/harness.json"
docker run --rm --gpus all --network none --user "$(id -u):$(id -g)" -v "$OUT/in:/in:ro" -v "$HFH:/models:ro" -v "$OUT/out:/out:rw" \
  -e HF_HOME=/models -e HF_HUB_OFFLINE=1 pravrudhi/exec-5090:latest agent_code --model-dir "$REL" --seed "$SEED" --batch-size 16 2>&1 | grep -vE "Warning|warn" | tail -2
python3 - "$OUT/out/samples.jsonl" "$OUT/out/evalplus_samples.jsonl" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
open(sys.argv[2], "w").write("".join(json.dumps({"task_id": r["id"], "solution": r["solution"]}) + "\n" for r in rows))
PY
docker run --rm --network none --user "$(id -u):$(id -g)" -v "$OUT/out:/work:rw" -v "$ROOT/.pravrudhi/ext_cache:/cache:rw" -e HOME=/cache -e HF_HOME=/cache \
  pravrudhi/ext-scorers:latest bash -c "cd /work && evalplus.evaluate --dataset humaneval --samples evalplus_samples.jsonl --parallel 8 2>&1 | grep -vE 'Warning|warn' | tail -6"
ls "$OUT/out"/*eval_results.json 2>/dev/null | head -1
