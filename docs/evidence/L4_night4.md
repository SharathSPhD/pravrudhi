# L4 first night (night 4) — rendered from research/ledger.jsonl

**Label: model-measured, screen tier, one loop seed, paired on the same rotation and sampling seed; isolation container.**

| candidate | strategy | family | selected | paired deltas | boundary | canary | outcome | hetvābhāsa | Brier |
|---|---|---|---|---|---|---|---|---|---|
| c-0038 | grpo_verifiable | grpo | yes | -0.020 | prune |  | pruned | asiddha |  |
| c-0039 | sft_rejection | data_mixture | yes | -0.005, -0.020 | prune |  | pruned | asiddha |  |
| c-0040 | grpo_verifiable | grpo | yes | -0.025 | prune |  | pruned | asiddha |  |
| c-0041 | sft_rejection | adapter | yes | +0.010, -0.015 | prune |  | pruned | asiddha |  |
| c-0042 | grpo_verifiable | grpo | yes | +0.025, -0.045 | prune |  | pruned | asiddha |  |
| c-0043 | sft_rejection | template | yes | +0.000, -0.065 | prune |  | pruned | asiddha |  |
| c-0044 | grpo_verifiable | grpo | yes | -0.025 | prune |  | pruned | asiddha |  |
| c-0045 | sft_rejection | data_mixture | yes | +0.090, +0.040 | confirm | pass | observed |  |  |

Candidates proposed: 8; selected: 8; outcomes: observed=1, pruned=7; GPU-hours charged (spend rows): 0.97.

Audits:

- kind=samples_verified, n_kept=944, kept_rate=0.921875, run_id=n4-sample-teacher-95769409
- kind=strategy_switch_rate, switches=48, n=97, wilson=[0.3974565165320967, 0.5926269410885678]
- kind=night_end, spent_gpu_h=0.6812475921252432, outcomes={'c-0042': 'pruned', 'c-0044': 'pruned', 'c-0040': 'pruned', 'c-0038': 'pruned', 'c-0045': 'promoted', 'c-0039': 'pruned', 'c-0041': 'pruned', 'c-0043': 'pruned'}
