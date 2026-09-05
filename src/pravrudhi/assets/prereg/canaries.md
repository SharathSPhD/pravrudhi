# Canaries for the LoRA target (frozen 2026-09-04, before the first night; changes only by ADR)

Trainee Qwen/Qwen3-4B; adapters only. Every candidate that reaches `confirm` on the sequential boundary is checked against the incumbent on all canaries before promotion; any failure prunes with hetvābhāsa `bādhita`.

| Canary | Measure | Margin / rule | Source |
|---|---|---|---|
| anchor_nll | mean per-token NLL on a frozen 200-item anchor set (GSM8K train items 7000–7199 as question + answer text, disjoint from the sampling prompts and from the sealed test pool) | relative increase ≤ 3.0% vs incumbent | 04-weight-level-spec §7.3 |
| distinct2 | distinct-2 ratio of the candidate's completions on the paired rotation vs the incumbent's on the same rotation | ratio ≥ 0.90 | 04-weight-level-spec §2.3 (svātantrya) |
| entropy_proxy | mean completion length ratio candidate/incumbent (collapse proxy while per-token entropy is not sampled) | ratio in [0.5, 2.0] | provisional stand-in for ΔH ≤ 0.5 nats; replaced when entropy sampling lands (P1) |

The GSM8K-canary of the blueprint is the target metric here and is therefore not a canary.
