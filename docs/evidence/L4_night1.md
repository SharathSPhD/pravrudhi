# L4 first night (night 1) — rendered from research/ledger.jsonl

**Label: model-measured, screen tier, one loop seed, paired on the same rotation and sampling seed; isolation container.**

| candidate | strategy | family | selected | paired deltas | boundary | canary | outcome | hetvābhāsa | Brier |
|---|---|---|---|---|---|---|---|---|---|
| c-0001 | sft_rejection | data_mixture | yes | -0.030 | prune |  | pruned | asiddha | 0.562 |
| c-0002 | grpo_verifiable | grpo |  |  |  |  | proposed |  |  |
| c-0003 | sft_rejection | adapter | yes |  |  |  | proposed |  |  |
| c-0004 | grpo_verifiable | grpo |  |  |  |  | proposed |  |  |
| c-0005 | sft_rejection | data_mixture |  |  |  |  | proposed |  |  |
| c-0006 | sft_rejection | template | yes | +0.000 | continue |  | observed |  | 0.078 |
| c-0007 | grpo_verifiable | grpo | yes | +0.050 | continue |  | observed |  | 0.032 |
| c-0008 | sft_rejection | optimiser | yes | +0.020 | continue |  | observed |  | 0.384 |
| c-0009 | grpo_verifiable | grpo |  |  |  |  | proposed |  |  |
| c-0010 | sft_rejection | adapter | yes | -0.020 | prune |  | pruned | asiddha | 0.137 |
| c-0011 | grpo_verifiable | grpo | yes | +0.040 | continue |  | observed |  | 0.068 |
| c-0012 | sft_rejection | data_mixture | yes | +0.000 | continue |  | observed |  |  |
| c-0013 | grpo_verifiable | grpo | yes | -0.020 | prune |  | pruned | asiddha |  |
| c-0014 | sft_rejection | adapter | yes | +0.020 | continue |  | observed |  |  |
| c-0015 | grpo_verifiable | grpo |  |  |  |  | proposed |  |  |
| c-0016 | sft_rejection | data_mixture |  |  |  |  | proposed |  |  |
| c-0017 | grpo_verifiable | grpo | yes |  |  |  | proposed |  |  |
| c-0018 | sft_rejection | optimiser | yes | +0.010 | continue |  | observed |  |  |
| c-0019 | grpo_verifiable | grpo | yes | +0.020 | continue |  | observed |  |  |
| c-0020 | sft_rejection | adapter |  |  |  |  | proposed |  |  |
| c-0021 | grpo_verifiable | grpo |  |  |  |  | proposed |  |  |
| c-0022 | sft_rejection | template | yes | +0.010 | continue |  | observed |  |  |
| c-0023 | grpo_verifiable | grpo | yes | -0.010 | prune |  | pruned | asiddha |  |

Candidates proposed: 23; selected: 15; outcomes: observed=9, proposed=10, pruned=4; GPU-hours charged (spend rows): 0.92.

Audits:

- kind=samples_verified, n_kept=937, kept_rate=0.9150390625, run_id=n1-sample-72258763
- kind=job_failed, run_id=n1-train-c-0003-73536624
- kind=job_failed, run_id=n1-train-c-0017-74001014
- kind=strategy_switch_rate, switches=6, n=14, wilson=[0.21380509930400526, 0.6740973309713064]
- kind=night_end, spent_gpu_h=0.920095317161823, outcomes={'c-0014': 'continue', 'c-0007': 'continue', 'c-0011': 'continue', 'c-0012': 'continue', 'c-0003': 'failed:train', 'c-0013': 'pruned', 'c-0023': 'pruned', 'c-0017': 'failed:train', 'c-0010': 'pruned', 'c-0001': 'pruned', 'c-0022': 'continue', 'c-0019': 'continue', 'c-0006': 'continue', 'c-0018': 'continue', 'c-0008': 'continue'}
