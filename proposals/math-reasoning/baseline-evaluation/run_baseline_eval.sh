#!/usr/bin/env bash
# Thin wrapper around run_baseline_eval.py — see README.md for the full
# proposal this belongs to. Proposal-stage only: writes under ./results/
# in this directory, never to the ledger, research/, gates/ or
# pravrudhi_kernel/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${BASE_MODEL:-}" ]]; then
    echo "Set BASE_MODEL to the checkpoint under evaluation (HF dir or hub id)." >&2
    exit 1
fi

uv run python "${HERE}/run_baseline_eval.py" "$@"
