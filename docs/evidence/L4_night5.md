# L4 first night (night 5) — rendered from research/ledger.jsonl

**Label: model-measured, screen tier, one loop seed, paired on the same rotation and sampling seed; isolation container.**

| candidate | strategy | family | selected | paired deltas | boundary | canary | outcome | hetvābhāsa | Brier |
|---|---|---|---|---|---|---|---|---|---|
| c-0046 | grpo_verifiable | grpo | yes | -0.140 | prune |  | pruned | asiddha | 0.722 |
| c-0047 | grpo_verifiable | grpo | yes | -0.095 | prune |  | pruned | asiddha | 0.078 |
| c-0048 | grpo_verifiable | grpo | yes | -0.040 | prune |  | pruned | asiddha | 0.608 |
| c-0049 | grpo_verifiable | grpo | yes | -0.145 | prune |  | pruned | asiddha | 0.090 |
| c-0050 | sft_rejection | data_mixture | yes | -0.055 | prune |  | pruned | asiddha | 0.640 |
| c-0051 | sft_rejection | adapter | yes | +0.025, -0.010 | continue |  | observed |  | 0.562 |
| c-0052 | grpo_verifiable | grpo | yes | -0.125 | prune |  | pruned | asiddha | 0.672 |
| c-0053 | sft_rejection | data_mixture | yes | +0.020, -0.035 | prune |  | pruned | asiddha | 0.533 |

Candidates proposed: 8; selected: 8; outcomes: observed=1, pruned=7; GPU-hours charged (spend rows): 0.74.

Audits:

- kind=samples_verified, n_kept=947, kept_rate=0.9248046875, run_id=n5-sample-teacher-98785222
- kind=samples_verified, n_kept=943, kept_rate=0.9208984375, run_id=n5-sample-teacher-855163
- kind=decorative_controller
- kind=night_end, reason=decorative_controller
