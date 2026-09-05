# Harness track night 1 — rendered from research/ledger.jsonl

**Label: harness-measured (fixed model, mutable scaffold), screen tier, paired on the same MBPP+ rotation and sampling seed; hidden tests executed in the sandbox; isolation container.**

| candidate | strategy | family | selected | paired deltas | boundary | canary | outcome | hetvābhāsa | Brier |
|---|---|---|---|---|---|---|---|---|---|
| c-0054 | retry_policy | retries | yes | -0.050 | prune |  | pruned | asiddha |  |
| c-0055 | sampling_policy | sampling | yes | -0.190 | prune |  | pruned | asiddha |  |
| c-0056 | prompt_only | system_prompt | yes | -0.310 | prune |  | pruned | asiddha |  |
| c-0057 | retry_policy | retries | yes | -0.110 | prune |  | pruned | asiddha |  |
| c-0058 | sampling_policy | sampling | yes | -0.190 | prune |  | pruned | asiddha |  |
| c-0059 | prompt_only | system_prompt | yes |  |  |  | proposed |  |  |
| c-0060 | retry_policy | retries | yes | +0.090 | confirm |  | promotion_withdrawn |  |  |
| c-0061 | sampling_policy | sampling | yes | -0.150 | prune |  | pruned | asiddha |  |

Candidates proposed: 8; selected: 8; outcomes: promotion_withdrawn=1, proposed=1, pruned=6; GPU-hours charged (spend rows): 0.16.

Audits:

- kind=strategy_switch_rate, switches=48, n=97, wilson=[0.3974565165320967, 0.5926269410885678]
- kind=night_end, spent_gpu_h=0.0, outcomes={}
- kind=strategy_switch_rate, switches=48, n=97, wilson=[0.3974565165320967, 0.5926269410885678]
- kind=night_end, spent_gpu_h=0.0, outcomes={}
- kind=strategy_switch_rate, switches=48, n=97, wilson=[0.3974565165320967, 0.5926269410885678]
- kind=night_end, spent_gpu_h=0.0, outcomes={}
