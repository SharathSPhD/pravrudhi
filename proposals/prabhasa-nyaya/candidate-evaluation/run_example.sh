#!/usr/bin/env bash
# Exercises scripts/evaluate.py against the fabricated example configs.
# This produces an ILLUSTRATIVE output file only — the numbers are
# invented (see configs/*.example.json) and must never be cited as a
# measured result. Real runs must point --objective/--benchmarks/
# --baseline/--candidate at actual artifacts supplied by upstream steps.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

uv run python scripts/evaluate.py \
  --objective configs/objective.example.json \
  --benchmarks configs/benchmarks.example.json \
  --baseline configs/baseline_results.example.json \
  --candidate configs/retrieval_candidate.example.json \
  --out /tmp/candidate_comparison.example.json

echo "Example (fabricated-input) comparison written to /tmp/candidate_comparison.example.json"
