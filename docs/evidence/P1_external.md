# External proof tier

Rendered from the ledger's `audit{kind: external_eval}` rows alone. Every row was scored by third-party tooling outside the kernel (tier: external); the result file is admitted by SHA-256. The kernel's own selection record is in the night documents.

| seq | track | condition | model | scorer | metric | value | ±  | n | file sha256 |
|---|---|---|---|---|---|---|---|---|---|
| 717 | M | base | Qwen/Qwen3-0.6B | lm-eval 0.4.9 | gsm8k exact_match,strict-match | 0.4086 | 0.0135 | 1319 | f5ec2ebf2ae4ec04 |
| 718 | M | adapter:c-0045 | Qwen/Qwen3-0.6B | lm-eval 0.4.9 | gsm8k exact_match,strict-match | 0.4898 | 0.0138 | 1319 | dd9805e97e36f919 |
| 719 | H | base | Qwen/Qwen3-1.7B | evalplus 0.3.1 | humaneval+ pass@1 | 0.5915 | 0.0744 | 164 | 78e9c2b0dba677f6 |
| 900 | H | harness:c-0060 | Qwen/Qwen3-1.7B | evalplus 0.3.1 | humaneval+ pass@1 | 0.0854 | 0.0433 | 164 | e8c2b06f7b245d7b |

## Paired differences

- H humaneval+ pass@1: harness:c-0060 − base = -0.5061 (base 0.5915±0.0744, harness:c-0060 0.0854±0.0433, n=164)
- M gsm8k exact_match,strict-match: adapter:c-0045 − base = +0.0811 (base 0.4086±0.0135, adapter:c-0045 0.4898±0.0138, n=1319)

## Tensions

External rows are not kernel-executed: they carry tier `external`, not pratyakṣa in the kernel sense. Their standard errors are the scorer's own (lm-eval) or a Wilson half-width (EvalPlus), not the loop's σ_seed.
