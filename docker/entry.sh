#!/usr/bin/env bash
# usage: <job> [args...]; default job is generate for backward compatibility
set -euo pipefail
job="${1:-generate}"
case "$job" in
  generate|sample|train_sft|train_grpo|anchor_nll) shift; exec python "/opt/pravrudhi/jobs/${job}.py" "$@" ;;
  *) exec python /opt/pravrudhi/jobs/generate.py "$@" ;;
esac
